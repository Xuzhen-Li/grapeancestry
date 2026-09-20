"""smartPCA projection via EIGENSOFT ``lsqproject`` (Italy ``smartPCA.md`` lineage).

One PED containing reference + query; ``poplistname`` lists reference Grp labels;
``lsqproject: YES`` projects non-reference individuals onto those axes
(Patterson / Price EIGENSOFT).

Falls back note: separate ``snploadingoutname`` + ``projection: YES`` is brittle
when query has high missingness on the SNP set (Italy notes hit the same issue
and moved to plink2 / merge).
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class SmartPCAResult:
    ref_ids: list[str]
    ref_coords: np.ndarray
    query_coords: np.ndarray
    query_ids: list[str]
    evals: list[float]
    workdir: Path
    method: str = "smartPCA lsqproject"


def _alleles_from_annot(annot: Path, sites: list[str]) -> dict[str, tuple[str, str]]:
    want = set(sites)
    out: dict[str, tuple[str, str]] = {}
    with annot.open() as fh:
        next(fh)
        for line in fh:
            chrom, pos, ref, alt, *_ = line.rstrip("\n").split("\t")
            key = f"{chrom}:{pos}"
            if key in want:
                out[key] = (ref or "A", (alt.split(",")[0] if alt else "T") or "T")
    return out


def write_ped_map(
    out_prefix: Path,
    sample_ids: list[str],
    dosage: np.ndarray,
    sites: list[str],
    alleles: dict[str, tuple[str, str]],
    *,
    pop_labels: list[str],
) -> tuple[Path, Path]:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    ped = out_prefix.with_suffix(".ped")
    mapf = out_prefix.with_suffix(".map")
    with mapf.open("w") as fh:
        for s in sites:
            chrom, _, pos = s.partition(":")
            ref, alt = alleles.get(s, ("A", "T"))
            fh.write(f"{chrom}\t{chrom}:{pos}:{ref}:{alt}\t0\t{pos}\n")
    if dosage.ndim == 1:
        dosage = dosage.reshape(1, -1)
    with ped.open("w") as fh:
        for i, sid in enumerate(sample_ids):
            row = [sid, sid, "0", "0", "0", pop_labels[i]]
            for j, s in enumerate(sites):
                ref, alt = alleles.get(s, ("A", "T"))
                d = int(dosage[i, j])
                if d < 0:
                    a1, a2 = "0", "0"
                elif d == 0:
                    a1, a2 = ref, ref
                elif d == 1:
                    a1, a2 = ref, alt
                else:
                    a1, a2 = alt, alt
                row.extend([a1, a2])
            fh.write(" ".join(row) + "\n")
    return ped, mapf


def _run_smartpca(par: Path, log: Path) -> None:
    import sys

    exe = shutil.which("smartpca")
    if not exe:
        cand = Path(sys.executable).resolve().parent / "smartpca"
        if cand.exists():
            exe = str(cand)
    if not exe:
        raise RuntimeError("smartpca not found — conda install eigensoft in env ga")
    with log.open("w") as fh:
        subprocess.run([exe, "-p", str(par)], check=True, stdout=fh, stderr=subprocess.STDOUT)


def _norm_id(sid: str) -> str:
    if ":" in sid:
        a, b = sid.split(":", 1)
        if a == b:
            return a
    return sid


def normalize_eigenvalues(values: list[float] | np.ndarray) -> list[float]:
    """Normalize finite, non-negative smartPCA eigenvalues to fractions."""
    raw = np.asarray(values, dtype=float)
    valid = np.isfinite(raw) & (raw >= 0)
    total = float(raw[valid].sum())
    if total <= 0 or not np.isfinite(total):
        return [float("nan")] * len(raw)
    out = np.full(raw.shape, np.nan, dtype=float)
    out[valid] = raw[valid] / total
    return [float(x) for x in out]


def _parse_evec(evec: Path, n_pcs: int = 2) -> tuple[list[str], np.ndarray, list[str]]:
    ids: list[str] = []
    pops: list[str] = []
    rows: list[list[float]] = []
    with evec.open() as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            p = line.split()
            if len(p) < n_pcs + 2:
                continue
            try:
                coords = [float(x) for x in p[1 : 1 + n_pcs]]
            except ValueError:
                continue
            if not np.isfinite(coords).all():
                continue
            ids.append(_norm_id(p[0]))
            rows.append(coords)
            pops.append(p[1 + n_pcs])
    return ids, np.asarray(rows, float).reshape(-1, n_pcs), pops


def _parse_eval(evl: Path, n_pcs: int | None = 2) -> list[float]:
    vals: list[float] = []
    if not evl.exists():
        return [] if n_pcs is None else [float("nan")] * n_pcs
    for line in evl.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            vals.append(float(line.split()[0]))
        except ValueError:
            continue
        if n_pcs is not None and len(vals) >= n_pcs:
            break
    while n_pcs is not None and len(vals) < n_pcs:
        vals.append(float("nan"))
    return vals


def parse_eigenvalue_ratios(evl: Path, n_pcs: int = 2) -> list[float]:
    """Return top-PC variance fractions using all valid eigenvalues as denominator."""
    ratios = normalize_eigenvalues(_parse_eval(evl, n_pcs=None))
    out = ratios[:n_pcs]
    while len(out) < n_pcs:
        out.append(float("nan"))
    return out


def run_smartpca_project(
    ref_ids: list[str],
    ref_dosage: np.ndarray,
    query_ids: list[str],
    query_dosage: np.ndarray,
    sites: list[str],
    allele_annot: Path,
    workdir: Path,
    *,
    n_pcs: int = 2,
    pop_labels: list[str] | None = None,
    reuse_ped: bool = True,
) -> SmartPCAResult:
    """Fit axes on reference Grps; lsqproject query samples.

    If ``reuse_ped`` and ``all.ped``/``all.map`` already exist, skip rewriting
    the (often multi-GB) PED and only re-run smartpca — useful after an aborted
    run left an empty ``all.evec``.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    if pop_labels is None:
        pop_labels = ["REF"] * len(ref_ids)
    # sanitize pops for poplist (no spaces)
    ref_pops = [p.replace(" ", "_") or "REF" for p in pop_labels]
    q_dose = query_dosage.reshape(1, -1) if query_dosage.ndim == 1 else query_dosage
    if q_dose.shape[0] != len(query_ids):
        raise ValueError("query_dosage rows != query_ids")

    prefix = workdir / "all"
    ped, mapf = prefix.with_suffix(".ped"), prefix.with_suffix(".map")
    can_reuse = (
        reuse_ped
        and ped.exists()
        and mapf.exists()
        and ped.stat().st_size > 1_000_000
        and mapf.stat().st_size > 0
    )
    if not can_reuse:
        alleles = _alleles_from_annot(allele_annot, sites)
        all_ids = list(ref_ids) + list(query_ids)
        all_dose = np.vstack([ref_dosage, q_dose])
        all_pops = ref_pops + ["QUERY"] * len(query_ids)
        ped, mapf = write_ped_map(prefix, all_ids, all_dose, sites, alleles, pop_labels=all_pops)

    popl = workdir / "ref.poplist"
    uniq = sorted(set(ref_pops))
    popl.write_text("\n".join(uniq) + "\n")

    evec = workdir / "all.evec"
    evl = workdir / "all.eval"
    # Write evec to a temp name so an aborted run does not leave a truncated empty file
    evec_tmp = workdir / "all.evec.tmp"
    if evec_tmp.exists():
        evec_tmp.unlink()
    par = workdir / "all.par"
    par.write_text(
        "\n".join(
            [
                f"genotypename: {ped}",
                f"snpname: {mapf}",
                f"indivname: {ped}",
                f"evecoutname: {evec_tmp}",
                f"evaloutname: {evl}",
                f"poplistname: {popl}",
                "lsqproject: YES",
                "numchrom: 19",
                "numoutlieriter: 0",
                "nooutlier: YES",
                f"numoutevec: {n_pcs}",
                "",
            ]
        )
    )
    _run_smartpca(par, workdir / "all.log")
    if not evec_tmp.exists() or evec_tmp.stat().st_size < 100:
        raise RuntimeError(f"smartpca produced empty evec; see {workdir / 'all.log'}")
    evec_tmp.replace(evec)

    ids, xy, pops = _parse_evec(evec, n_pcs)
    qset = set(query_ids)
    ref_i = [i for i, (s, p) in enumerate(zip(ids, pops)) if s not in qset and p != "QUERY"]
    qry_i = [i for i, s in enumerate(ids) if s in qset] or [i for i, p in enumerate(pops) if p == "QUERY"]
    if not qry_i:
        raise RuntimeError(f"query not found in evec; see {workdir / 'all.log'}")
    return SmartPCAResult(
        ref_ids=[ids[i] for i in ref_i],
        ref_coords=xy[ref_i],
        query_ids=[ids[i] for i in qry_i],
        query_coords=xy[qry_i],
        evals=parse_eigenvalue_ratios(evl, n_pcs),
        workdir=workdir,
        method="smartPCA lsqproject",
    )


def write_pca_tsvs(
    result: SmartPCAResult,
    out_sample: Path,
    out_ref: Path,
    meta: dict[str, dict] | None = None,
) -> None:
    meta = meta or {}
    out_ref.parent.mkdir(parents=True, exist_ok=True)
    with out_ref.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["sample", "PC1", "PC2", "PC3", "Grp", "GEO", "CON", "method"])
        for i, sid in enumerate(result.ref_ids):
            m = meta.get(sid, {})
            w.writerow(
                [
                    sid,
                    *[
                        f"{result.ref_coords[i, j]:.6f}"
                        if result.ref_coords.shape[1] > j
                        else "NA"
                        for j in range(3)
                    ],
                    m.get("Grp", ""),
                    m.get("GEO", ""),
                    m.get("CON", ""),
                    result.method,
                ]
            )
    with out_sample.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["sample", "PC1", "PC2", "PC3", "method"])
        for i, sid in enumerate(result.query_ids):
            w.writerow(
                [
                    sid,
                    *[
                        f"{result.query_coords[i, j]:.6f}"
                        if result.query_coords.shape[1] > j
                        else "NA"
                        for j in range(3)
                    ],
                    result.method,
                ]
            )
