"""Batch-project query VCFs onto frozen panel167k_nogwas P (K=2–8)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from grapeancestry.adna.admixture import (
    _alleles_for_sites,
    _find_admixture,
    component_labels_colors,
    load_admixture_p,
    project_q_nnls,
)
from grapeancestry.adna.manual_qp import (
    apply_q_dict_edits,
    projection_p_for_sample,
    sample_swaps_pink_yellow,
    swap_pink_yellow_columns,
)
from grapeancestry.adna.panel167k_nogwas import (
    PANEL167K_NOGWAS_FAMILY,
    align_dosage_to_sites,
    load_family_sites,
    p_counted_allele,
)


def write_q_tsv(
    path: Path,
    sample: str,
    q: dict[str, float],
    labels: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(q, key=lambda x: int(x[1:]) if x.startswith("K") and x[1:].isdigit() else 99)
    with path.open("w") as fh:
        fh.write("sample\tcomponent\tlabel\tQ\n")
        for i, key in enumerate(keys):
            lab = labels[i] if labels and i < len(labels) else key
            fh.write(f"{sample}\t{key}\t{lab}\t{q[key]:.8f}\n")


def write_admixture_q_row(path: Path, q: dict[str, float], k: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(" ".join(f"{float(q[f'K{j + 1}']):.6f}" for j in range(k)) + "\n")


def persist_sample_q(
    root: Path,
    sample: str,
    k: int,
    q: dict[str, float],
    labels: list[str] | None = None,
) -> None:
    """Write display-space Q for this sample (TSV + ADMIXTURE one-row .Q)."""
    write_q_tsv(root / "results" / f"{sample}.admix.K{k}.Q.tsv", sample, q, labels)
    write_admixture_q_row(
        root / "results" / "admixture_proj" / sample / f"k{k}" / f"proj_k{k}.{k}.Q",
        q,
        k,
    )


def dosages_matrix_from_maps(
    per_sample: dict[str, dict[str, float]],
    sites: list[str],
) -> tuple[list[str], np.ndarray]:
    """Build (n_samples × n_sites) from {sample: {chrom:pos → dosage}}; missing=-1."""
    ids = list(per_sample)
    mat = np.full((len(ids), len(sites)), -1.0)
    for i, sid in enumerate(ids):
        dmap = per_sample[sid]
        for j, s in enumerate(sites):
            if s in dmap:
                mat[i, j] = float(dmap[s])
    return ids, mat


def project_aligned_nnls(
    dosage_sites: np.ndarray,
    P: np.ndarray,
    *,
    counted_allele: str = "ALT",
) -> np.ndarray:
    return project_q_nnls(np.asarray(dosage_sites, float), P, counted_allele=counted_allele)


def project_batch_q_admixture(
    dosages: np.ndarray,
    sample_ids: list[str],
    sites: list[str],
    P: np.ndarray,
    alleles: dict[str, tuple[str, str]],
    workdir: Path,
    k: int,
    *,
    counted_allele: str = "REF",
) -> np.ndarray | None:
    """One BED, ``admixture -P``; returns (n_samples, k) raw columns or None."""
    import shutil
    import subprocess

    admix = _find_admixture()
    plink = shutil.which("plink")
    if not admix or not plink:
        return None
    if P.shape[0] != len(sites) or P.shape[1] != k:
        return None
    if dosages.shape != (len(sample_ids), len(sites)):
        return None

    workdir.mkdir(parents=True, exist_ok=True)
    prefix = workdir / f"batch_k{k}"
    with prefix.with_suffix(".map").open("w") as fh:
        for s in sites:
            chrom, _, pos = s.partition(":")
            ref, alt = alleles.get(s, ("A", "T"))
            fh.write(f"{chrom}\t{chrom}:{pos}:{ref}:{alt}\t0\t{pos}\n")
    with prefix.with_suffix(".ped").open("w") as fh:
        for i, sample in enumerate(sample_ids):
            row = [sample, sample, "0", "0", "0", "-9"]
            for j, s in enumerate(sites):
                ref, alt = alleles.get(s, ("A", "T"))
                d = int(dosages[i, j]) if dosages[i, j] >= 0 else -1
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

    a1_path = prefix.with_suffix(".a1")
    target = "REF" if counted_allele.upper() == "REF" else "ALT"
    with a1_path.open("w") as fh:
        for s in sites:
            ref, alt = alleles.get(s, ("A", "T"))
            chrom, _, pos = s.partition(":")
            allele = ref if target == "REF" else alt
            fh.write(f"{chrom}:{pos}:{ref}:{alt} {allele}\n")
    subprocess.run(
        [
            plink,
            "--file",
            str(prefix),
            "--make-bed",
            "--out",
            str(prefix),
            "--allow-extra-chr",
            "--keep-allele-order",
            "--a1-allele",
            str(a1_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    from grapeancestry.adna.panel167k_nogwas import align_p_to_study_bim

    P_use = align_p_to_study_bim(P, sites, Path(f"{prefix}.bim"), alleles, counted_allele=counted_allele)
    np.savetxt(Path(f"{prefix}.{k}.P.in"), P_use, fmt="%.6f")
    subprocess.run(
        [admix, "-P", f"{prefix}.bed", str(k)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(workdir),
    )
    q_path = workdir / f"{prefix.name}.{k}.Q"
    if not q_path.exists():
        q_path = Path(f"{prefix}.{k}.Q")
    if not q_path.exists():
        return None
    q = np.loadtxt(q_path)
    if q.ndim == 1:
        q = q.reshape(1, -1)
    if q.shape != (len(sample_ids), k):
        return None
    return q


def project_batch_family(
    dosages: np.ndarray,
    sample_ids: list[str],
    sites: list[str],
    admix_dir: Path,
    *,
    k_min: int = 2,
    k_max: int = 8,
    workdir: Path | None = None,
    allele_annot: Path | None = None,
    method: str = "auto",
    run_family: str = PANEL167K_NOGWAS_FAMILY,
) -> dict[str, dict[int, dict[str, float]]]:
    """Project N samples for K=k_min..k_max. Returns sample → K → Q dict (canonical)."""
    out: dict[str, dict[int, dict[str, float]]] = {s: {} for s in sample_ids}
    annot = allele_annot
    if annot is None:
        cand = Path(__file__).resolve().parents[3] / "data" / "panel" / "locus_annot.tsv"
        annot = cand if cand.exists() else None
    wd_root = workdir or (Path(__file__).resolve().parents[3] / "results" / "admixture_proj" / "batch")
    use_official = method in {"official", "auto"}
    alleles = _alleles_for_sites(annot, sites) if annot and annot.exists() else {}
    counted = p_counted_allele(admix_dir) if run_family == PANEL167K_NOGWAS_FAMILY else "ALT"

    for k in range(k_min, k_max + 1):
        try:
            P = load_admixture_p(admix_dir, k, run_family=run_family)
        except (FileNotFoundError, ValueError):
            continue
        if P.shape[0] != len(sites) or P.shape[1] != k:
            continue
        ages_only = bool(sample_ids) and all(sample_swaps_pink_yellow(s) for s in sample_ids)
        if ages_only:
            P = projection_p_for_sample(P, k, sample_ids[0])
        q_raw = None
        if use_official and alleles and _find_admixture():
            try:
                q_raw = project_batch_q_admixture(
                    dosages,
                    sample_ids,
                    sites,
                    P,
                    alleles,
                    wd_root / f"k{k}",
                    k,
                    counted_allele=counted,
                )
            except Exception:
                q_raw = None
        if q_raw is None:
            rows = []
            for i in range(len(sample_ids)):
                rows.append(project_aligned_nnls(dosages[i], P, counted_allele=counted))
            q_raw = np.vstack(rows)
        for i, sid in enumerate(sample_ids):
            row = np.asarray(q_raw[i], float)
            if k >= 7 and sample_swaps_pink_yellow(sid) and not ages_only:
                row = swap_pink_yellow_columns(row.reshape(1, -1))[0]
            raw_dict = {f"K{j + 1}": float(row[j]) for j in range(k)}
            out[sid][k] = apply_q_dict_edits(raw_dict, k, sid)
    return out


def load_vcf_dosages_for_sites(vcf: Path, sites: list[str]) -> dict[str, np.ndarray]:
    """One VCF → {sample: dosage aligned to sites}."""
    from grapeancestry.core.dosage import list_samples, load_sample_dosage

    out: dict[str, np.ndarray] = {}
    for sid in list_samples(vcf):
        raw = load_sample_dosage(vcf, sid, sites)
        out[sid] = np.asarray(raw, float)
    return out


def project_query_vcfs(
    vcfs: list[Path],
    admix_dir: Path,
    *,
    out_dir: Path,
    k_min: int = 2,
    k_max: int = 8,
    method: str = "auto",
    run_family: str = PANEL167K_NOGWAS_FAMILY,
    workdir: Path | None = None,
    allele_annot: Path | None = None,
) -> dict[str, dict[int, dict[str, float]]]:
    """Harmonize N query VCFs to sites.txt, one matrix, project every K."""
    sites = load_family_sites(admix_dir)
    if not sites:
        raise FileNotFoundError(f"missing {admix_dir} family sites")
    sample_ids: list[str] = []
    rows: list[np.ndarray] = []
    seen: set[str] = set()
    for vcf in vcfs:
        for sid, dose in load_vcf_dosages_for_sites(vcf, sites).items():
            name = sid
            if name in seen:
                name = f"{sid}__{vcf.stem}"
            seen.add(name)
            sample_ids.append(name)
            rows.append(align_dosage_to_sites(dose, sites, sites))
    if not sample_ids:
        return {}
    dosages = np.vstack(rows)
    projected = project_batch_family(
        dosages,
        sample_ids,
        sites,
        admix_dir,
        k_min=k_min,
        k_max=k_max,
        workdir=workdir or (out_dir / "work"),
        allele_annot=allele_annot,
        method=method,
        run_family=run_family,
    )
    for sid, by_k in projected.items():
        for k, q in by_k.items():
            labels, _c, _a = component_labels_colors(admix_dir, k, run_family=run_family)
            write_q_tsv(out_dir / f"{sid}.admix.K{k}.Q.tsv", sid, q, labels)
    return projected
