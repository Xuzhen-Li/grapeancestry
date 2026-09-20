"""Unphased chip selection: our 167K het/Fst scan, then compare to Science.

Primary: windowed het + Fst by Grp (2449.info Grp), plus per-Grp het and Fst vs rest.
Not XP-CLR / iHS / G12. Dong et al. 2023 *Science* Table S29
(doi:10.1126/science.add8655) is a **second** contrast (CG1∩CG2 shared
domestication bins), used only for overlap checks.
GEO Fst stays in results/gea/, not this scan.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

WINDOWS_REL = Path("data/panel/selection_windows.tsv")
S29_GENES_REL = Path("data/panel/dong_table_s29_genes.tsv")


def parse_sites(sites: list[str]) -> tuple[np.ndarray, np.ndarray]:
    chroms: list[str] = []
    pos: list[int] = []
    for s in sites:
        c, _, p = s.partition(":")
        chroms.append(c)
        pos.append(int(p) if p.isdigit() else -1)
    return np.array(chroms, dtype=object), np.array(pos, dtype=np.int64)


def per_site_het(mat: np.ndarray) -> np.ndarray:
    """Fraction of called genotypes that are heterozygous (dosage==1)."""
    x = np.asarray(mat)
    called = x >= 0
    n = called.sum(axis=0)
    het = ((x == 1) & called).sum(axis=0)
    return np.where(n > 0, het / n, np.nan)


def rolling_mean_bp(
    values: np.ndarray,
    chroms: np.ndarray,
    pos: np.ndarray,
    *,
    half_bp: int = 50_000,
) -> np.ndarray:
    """Chromosome-aware mean of ``values`` in ±half_bp (two pointers)."""
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    by: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(chroms):
        if int(pos[i]) >= 0:
            by[str(c)].append(i)
    for idxs in by.values():
        idxs.sort(key=lambda i: int(pos[i]))
        p = np.array([int(pos[i]) for i in idxs], dtype=np.int64)
        v = np.array([values[i] for i in idxs], dtype=float)
        n = len(idxs)
        j0 = 0
        j1 = 0
        acc = 0.0
        cnt = 0
        for k in range(n):
            hi = p[k] + half_bp
            lo = p[k] - half_bp
            while j1 < n and p[j1] <= hi:
                if v[j1] == v[j1]:
                    acc += v[j1]
                    cnt += 1
                j1 += 1
            while j0 < n and p[j0] < lo:
                if v[j0] == v[j0]:
                    acc -= v[j0]
                    cnt -= 1
                j0 += 1
            if cnt > 0:
                out[idxs[k]] = acc / cnt
    return out


def fst_sites(mat: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Per-site simplified Weir–Cockerham Fst (same formula as stats.weir_cockerham_fst)."""
    x = np.asarray(mat)
    g = np.asarray(groups)
    uniq = [u for u in np.unique(g) if str(u) not in {"", "ND", "nan"}]
    if len(uniq) < 2:
        return np.full(x.shape[1], np.nan)
    p_rows = []
    n_rows = []
    for lab in uniq:
        sub = x[g == lab]
        called = sub >= 0
        n = called.sum(axis=0).astype(float)
        s = np.where(called, sub, 0).sum(axis=0).astype(float)
        p = np.divide(s, 2.0 * np.maximum(n, 1.0))
        p = np.where(n >= 2, p, np.nan)
        p_rows.append(p)
        n_rows.append(np.where(n >= 2, n, 0.0))
    p_arr = np.vstack(p_rows)
    n_arr = np.vstack(n_rows)
    wsum = n_arr.sum(axis=0)
    pbar = np.divide((np.nan_to_num(p_arr) * n_arr).sum(axis=0), np.maximum(wsum, 1.0))
    s2 = np.nansum(n_arr * (p_arr - pbar) ** 2, axis=0) / np.maximum(wsum, 1.0)
    den = pbar * (1.0 - pbar)
    fst = np.divide(s2, den, out=np.full_like(s2, np.nan), where=(den > 1e-12) & (wsum > 0))
    n_grp = (n_arr > 0).sum(axis=0)
    return np.where(n_grp >= 2, fst, np.nan)


def load_named_windows(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as fh:
        header = fh.readline()
        if not header:
            return rows
        cols = header.rstrip("\n").split("\t")
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            row = {cols[i]: parts[i] if i < len(parts) else "" for i in range(len(cols))}
            try:
                rows.append(
                    {
                        "name": row["name"],
                        "chrom": str(row["chrom"]),
                        "start": int(row["start"]),
                        "end": int(row["end"]),
                        "source": row.get("source", ""),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def load_s29_windows(path: Path) -> list[dict]:
    """Unique Table S29 bins from the gene-level extract (Science comparator)."""
    bins: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    if not path.exists():
        return bins
    with path.open(encoding="utf-8") as fh:
        header = fh.readline()
        if not header:
            return bins
        cols = header.rstrip("\n").split("\t")
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            row = {cols[i]: parts[i] if i < len(parts) else "" for i in range(len(cols))}
            try:
                chrom = str(row["chrom"])
                start = int(row["bin_start"])
                end = int(row["bin_end"])
            except (KeyError, ValueError):
                continue
            key = (chrom, start, end)
            if key in seen:
                continue
            seen.add(key)
            lab = (row.get("label") or "").strip()
            name = f"S29_{chrom}_{start}"
            if lab:
                name = f"S29_{lab}_{chrom}_{start}"
            bins.append(
                {
                    "name": name,
                    "chrom": chrom,
                    "start": start,
                    "end": end,
                    "source": "Dong 2023 Science Table S29",
                    "label": lab,
                }
            )
    return bins


def site_in_windows(chrom: str, pos: int | str, windows: list[dict]) -> str:
    try:
        p = int(pos)
    except (TypeError, ValueError):
        return ""
    for w in windows:
        if str(chrom) == str(w["chrom"]) and int(w["start"]) <= p <= int(w["end"]):
            return str(w["name"])
    return ""


def tag_sites_with_s29(
    rows: list[dict],
    s29: list[dict],
    *,
    chrom_key: str = "chrom",
    pos_key: str = "pos",
) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        rec = dict(r)
        hit = site_in_windows(str(r.get(chrom_key, "")), r.get(pos_key, ""), s29)
        rec["in_s29"] = "yes" if hit else "no"
        rec["s29_bin"] = hit
        out.append(rec)
    return out


def vs_science_summary(
    science: list[dict],
    fst_tagged: list[dict],
    het_tagged: list[dict],
) -> dict:
    n_bins = len(science)
    n_chip = sum(1 for r in science if int(r.get("n_sites") or 0) > 0)
    n_fst_hit = sum(1 for r in fst_tagged if r.get("in_s29") == "yes")
    n_het_hit = sum(1 for r in het_tagged if r.get("in_s29") == "yes")
    return {
        "n_s29_bins": n_bins,
        "n_s29_with_chip": n_chip,
        "n_s29_zero_chip": n_bins - n_chip,
        "n_fst_top": len(fst_tagged),
        "n_fst_top_in_s29": n_fst_hit,
        "n_het_dips": len(het_tagged),
        "n_het_dips_in_s29": n_het_hit,
        "note": (
            "Our scan = unphased windowed het + Fst by Grp, plus per-Grp vs rest. "
            "Science Table S29 = CG1∩CG2 shared domestication bins "
            "(Dong et al. 2023 doi:10.1126/science.add8655; nucleotide-diversity "
            "difference and population differentiation, both top 5%). "
            "fst_top_in_s29 / het_dips_in_s29 = whether our genome-wide tops sit in S29. "
            "S29 mean_het/Fst = chip scores inside those bins. Not XP-CLR."
        ),
    }


def score_named_windows(
    chroms: np.ndarray,
    pos: np.ndarray,
    het: np.ndarray,
    fst: np.ndarray | None,
    windows: list[dict],
) -> list[dict]:
    out = []
    fst = np.full(len(het), np.nan) if fst is None else np.asarray(fst, dtype=float)
    for w in windows:
        m = (chroms == w["chrom"]) & (pos >= w["start"]) & (pos <= w["end"])
        n = int(m.sum())
        rec = {
            **w,
            "n_sites": n,
            "mean_het": float(np.nanmean(het[m])) if n else float("nan"),
            "mean_fst": float(np.nanmean(fst[m])) if n else float("nan"),
            "max_fst": float(np.nanmax(fst[m])) if n and np.isfinite(fst[m]).any() else float("nan"),
            "kind": "named_window",
            "note": (
                "Chip sites in this VS-1 window. Unphased het/Fst; "
                "not a new XP-CLR/iHS scan. "
                + w.get("source", "")
            ),
        }
        out.append(rec)
    return out


def top_sites(
    sites: list[str],
    values: np.ndarray,
    *,
    top_n: int = 40,
    descending: bool = True,
    extra: dict | None = None,
) -> list[dict]:
    v = np.asarray(values, dtype=float)
    order = np.argsort(-v if descending else v)
    rows = []
    for i in order:
        if len(rows) >= top_n:
            break
        if v[i] != v[i]:
            continue
        chrom, _, pos = sites[i].partition(":")
        rec = {"site": sites[i], "chrom": chrom, "pos": pos, "value": float(v[i])}
        if extra:
            rec.update(extra)
        rows.append(rec)
    return rows


def fst_one_vs_rest(mat: np.ndarray, groups: np.ndarray, label: str) -> np.ndarray:
    """Per-site Fst of ``label`` versus all other labelled samples."""
    g = np.asarray(groups)
    mask = np.array([str(x) not in {"", "ND", "nan"} for x in g])
    if int((g[mask] == label).sum()) < 2 or int((g[mask] != label).sum()) < 2:
        return np.full(np.asarray(mat).shape[1], np.nan)
    two = np.where(g[mask] == label, str(label), "REST")
    return fst_sites(mat[mask], two)


def scan_by_group(
    mat: np.ndarray,
    sites: list[str],
    groups: list[str] | np.ndarray,
    windows: list[dict],
    chroms: np.ndarray,
    pos: np.ndarray,
    *,
    half_bp: int = 50_000,
    top_n: int = 15,
    min_n: int = 20,
    science_windows: list[dict] | None = None,
) -> dict:
    """Within-group windowed het + Fst(group vs rest). Skip groups with n<min_n."""
    g = np.asarray(groups)
    counts: dict[str, int] = {}
    for lab in g:
        key = str(lab)
        if key in {"", "ND", "nan"}:
            continue
        counts[key] = counts.get(key, 0) + 1
    named_rows: list[dict] = []
    science_rows: list[dict] = []
    het_dips: list[dict] = []
    fst_top: list[dict] = []
    used: list[dict] = []
    science_windows = science_windows or []
    for lab, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if lab == "OUT" or n < min_n:
            continue
        sub = mat[g == lab]
        het = per_site_het(sub)
        het_w = rolling_mean_bp(het, chroms, pos, half_bp=half_bp)
        fst = fst_one_vs_rest(mat, g, lab)
        used.append({"grp": lab, "n": n})
        for wrec in score_named_windows(chroms, pos, het, fst, windows):
            named_rows.append({"grp": lab, "n_samples": n, **wrec})
        for wrec in score_named_windows(chroms, pos, het, fst, science_windows):
            science_rows.append({"grp": lab, "n_samples": n, **wrec})
        for r in top_sites(sites, het_w, top_n=top_n, descending=False, extra={"grp": lab, "n_samples": n}):
            het_dips.append(r)
        for r in top_sites(sites, fst, top_n=top_n, descending=True, extra={"grp": lab, "n_samples": n}):
            fst_top.append(r)
    return {
        "groups_used": used,
        "named": named_rows,
        "science": science_rows,
        "het_dips": het_dips,
        "fst_top": fst_top,
        "min_n": min_n,
        "method": (
            f"Per-Grp unphased windowed het (±{half_bp} bp) and Fst(Grp vs rest). "
            f"Sweep call = Fst vs rest ≥95th ∩ within-Grp het ≤5th. "
            f"Skip n<{min_n}. Not XP-CLR/iHS. Science tables are overlap checks only."
        ),
    }


def scan_panel(
    mat: np.ndarray,
    sites: list[str],
    groups: list[str] | np.ndarray,
    windows: list[dict],
    *,
    half_bp: int = 50_000,
    top_n: int = 40,
    grp_labels: list[str] | np.ndarray | None = None,
    min_n: int = 20,
    science_windows: list[dict] | None = None,
) -> dict:
    science_windows = science_windows or []
    chroms, pos = parse_sites(sites)
    het = per_site_het(mat)
    het_w = rolling_mean_bp(het, chroms, pos, half_bp=half_bp)
    fst = fst_sites(mat, np.asarray(groups))
    named = score_named_windows(chroms, pos, het, fst, windows)
    science = score_named_windows(chroms, pos, het, fst, science_windows)
    het_dips = top_sites(sites, het_w, top_n=top_n, descending=False)
    fst_top = top_sites(sites, fst, top_n=top_n, descending=True)
    fst_tagged = tag_sites_with_s29(fst_top, science_windows)
    het_tagged = tag_sites_with_s29(het_dips, science_windows)
    by_grp = scan_by_group(
        mat,
        sites,
        grp_labels if grp_labels is not None else groups,
        windows,
        chroms,
        pos,
        half_bp=half_bp,
        top_n=max(5, top_n // 3),
        min_n=min_n,
        science_windows=science_windows,
    )
    return {
        "het": het,
        "het_window": het_w,
        "fst": fst,
        "sites": sites,
        "named": named,
        "science": science,
        "het_dips": het_dips,
        "fst_top": fst_top,
        "overlap_fst": fst_tagged,
        "overlap_het": het_tagged,
        "vs_summary": vs_science_summary(science, fst_tagged, het_tagged),
        "by_grp": by_grp,
        "half_bp": half_bp,
        "n_sites": len(sites),
        "method": (
            f"Unphased per-site het + ±{half_bp} bp windowed het + Fst by Grp; "
            f"per-Grp het + Fst(Grp vs rest), n≥{min_n}. "
            "Sweep = Fst vs rest ≥95th ∩ within-Grp het ≤5th. "
            "Not XP-CLR/iHS/G12. "
            "Science tables are overlap checks only, not the named-window list."
        ),
    }


def write_scan_arrays(scan: dict, out_dir: Path) -> Path | None:
    if "het" not in scan or "sites" not in scan:
        return None
    dest = out_dir / "scan.npz"
    np.savez_compressed(
        dest,
        sites=np.asarray(scan["sites"], dtype="U32"),
        het=np.asarray(scan["het"], dtype=np.float32),
        het_window=np.asarray(scan["het_window"], dtype=np.float32),
        fst=np.asarray(scan["fst"], dtype=np.float32),
    )
    return dest


def load_scan_arrays(out_dir: Path) -> dict | None:
    p = out_dir / "scan.npz"
    if not p.exists():
        return None
    z = np.load(p, allow_pickle=False)
    return {
        "sites": [str(s) for s in z["sites"]],
        "het": np.asarray(z["het"], dtype=float),
        "het_window": np.asarray(z["het_window"], dtype=float),
        "fst": np.asarray(z["fst"], dtype=float),
    }


def _fmt(x: float) -> str:
    if x != x:
        return ""
    return f"{x:.6f}"


def _write_named_tsv(path: Path, rows: list[dict], *, by_grp: bool = False) -> None:
    if by_grp:
        with path.open("w", encoding="utf-8") as fh:
            fh.write(
                "grp\tn_samples\tname\tchrom\tstart\tend\tn_sites\t"
                "mean_het\tmean_fst_vs_rest\tmax_fst_vs_rest\n"
            )
            for r in rows:
                fh.write(
                    f"{r.get('grp','')}\t{r.get('n_samples','')}\t{r['name']}\t"
                    f"{r['chrom']}\t{r['start']}\t{r['end']}\t{r['n_sites']}\t"
                    f"{_fmt(r['mean_het'])}\t{_fmt(r['mean_fst'])}\t{_fmt(r['max_fst'])}\n"
                )
        return
    with path.open("w", encoding="utf-8") as fh:
        fh.write("name\tchrom\tstart\tend\tn_sites\tmean_het\tmean_fst\tmax_fst\tnote\n")
        for r in rows:
            fh.write(
                f"{r['name']}\t{r['chrom']}\t{r['start']}\t{r['end']}\t{r['n_sites']}\t"
                f"{_fmt(r['mean_het'])}\t{_fmt(r['mean_fst'])}\t{_fmt(r['max_fst'])}\t"
                f"{r.get('note', '')}\n"
            )


def write_scan(scan: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    named_p = out_dir / "named_windows.tsv"
    _write_named_tsv(named_p, scan.get("named") or [])
    het_p = out_dir / "het_dips.tsv"
    with het_p.open("w", encoding="utf-8") as fh:
        fh.write("rank\tsite\tchrom\tpos\twindow_het\n")
        for i, r in enumerate(scan["het_dips"], 1):
            fh.write(f"{i}\t{r['site']}\t{r['chrom']}\t{r['pos']}\t{_fmt(r['value'])}\n")
    fst_p = out_dir / "fst_top.tsv"
    with fst_p.open("w", encoding="utf-8") as fh:
        fh.write("rank\tsite\tchrom\tpos\tfst_grp\n")
        for i, r in enumerate(scan["fst_top"], 1):
            fh.write(f"{i}\t{r['site']}\t{r['chrom']}\t{r['pos']}\t{_fmt(r['value'])}\n")
    science = scan.get("science") or []
    if science:
        _write_named_tsv(out_dir / "vs_science_s29.tsv", science)
    overlap_fst = scan.get("overlap_fst") or []
    overlap_het = scan.get("overlap_het") or []
    if overlap_fst or overlap_het:
        with (out_dir / "vs_science_overlap.tsv").open("w", encoding="utf-8") as fh:
            fh.write("kind\trank\tsite\tchrom\tpos\tvalue\tin_s29\ts29_bin\n")
            for i, r in enumerate(overlap_fst, 1):
                fh.write(
                    f"fst_top\t{i}\t{r['site']}\t{r['chrom']}\t{r['pos']}\t"
                    f"{_fmt(float(r.get('value', float('nan'))))}\t"
                    f"{r.get('in_s29','')}\t{r.get('s29_bin','')}\n"
                )
            for i, r in enumerate(overlap_het, 1):
                fh.write(
                    f"het_dip\t{i}\t{r['site']}\t{r['chrom']}\t{r['pos']}\t"
                    f"{_fmt(float(r.get('value', float('nan'))))}\t"
                    f"{r.get('in_s29','')}\t{r.get('s29_bin','')}\n"
                )
    summary = scan.get("vs_summary") or {}
    if summary:
        with (out_dir / "vs_science_summary.tsv").open("w", encoding="utf-8") as fh:
            fh.write("key\tvalue\n")
            for k, v in summary.items():
                fh.write(f"{k}\t{v}\n")
    (out_dir / "method.txt").write_text(scan["method"] + "\n", encoding="utf-8")
    write_scan_arrays(scan, out_dir)
    by = scan.get("by_grp") or {}
    if by.get("named"):
        _write_named_tsv(out_dir / "by_grp_named.tsv", by["named"], by_grp=True)
        with (out_dir / "by_grp_het_dips.tsv").open("w", encoding="utf-8") as fh:
            fh.write("grp\tn_samples\trank\tsite\tchrom\tpos\twindow_het\n")
            rank: dict[str, int] = {}
            for r in by.get("het_dips") or []:
                lab = str(r.get("grp", ""))
                rank[lab] = rank.get(lab, 0) + 1
                fh.write(
                    f"{lab}\t{r.get('n_samples','')}\t{rank[lab]}\t{r['site']}\t"
                    f"{r['chrom']}\t{r['pos']}\t{_fmt(r['value'])}\n"
                )
        with (out_dir / "by_grp_fst_top.tsv").open("w", encoding="utf-8") as fh:
            fh.write("grp\tn_samples\trank\tsite\tchrom\tpos\tfst_vs_rest\n")
            rank = {}
            for r in by.get("fst_top") or []:
                lab = str(r.get("grp", ""))
                rank[lab] = rank.get(lab, 0) + 1
                fh.write(
                    f"{lab}\t{r.get('n_samples','')}\t{rank[lab]}\t{r['site']}\t"
                    f"{r['chrom']}\t{r['pos']}\t{_fmt(r['value'])}\n"
                )
        if by.get("science"):
            _write_named_tsv(out_dir / "vs_science_by_grp.tsv", by["science"], by_grp=True)
        s29_wins = [
            {"name": r["name"], "chrom": r["chrom"], "start": r["start"], "end": r["end"]}
            for r in science
        ]
        if s29_wins:
            with (out_dir / "vs_science_by_grp_overlap.tsv").open("w", encoding="utf-8") as fh:
                fh.write("kind\tgrp\tn_samples\tsite\tchrom\tpos\tvalue\tin_s29\ts29_bin\n")
                for r in tag_sites_with_s29(by.get("fst_top") or [], s29_wins):
                    fh.write(
                        f"fst_top\t{r.get('grp','')}\t{r.get('n_samples','')}\t"
                        f"{r['site']}\t{r['chrom']}\t{r['pos']}\t{_fmt(float(r.get('value', float('nan'))))}\t"
                        f"{r.get('in_s29','')}\t{r.get('s29_bin','')}\n"
                    )
                for r in tag_sites_with_s29(by.get("het_dips") or [], s29_wins):
                    fh.write(
                        f"het_dip\t{r.get('grp','')}\t{r.get('n_samples','')}\t"
                        f"{r['site']}\t{r['chrom']}\t{r['pos']}\t{_fmt(float(r.get('value', float('nan'))))}\t"
                        f"{r.get('in_s29','')}\t{r.get('s29_bin','')}\n"
                    )
    return named_p


def _read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            rows.append({header[i]: parts[i] if i < len(parts) else "" for i in range(len(header))})
    return rows


def load_scan_tables(out_dir: Path) -> dict | None:
    named_p = out_dir / "named_windows.tsv"
    if not named_p.exists():
        return None
    return {
        "named": _read_tsv(named_p),
        "het_dips": _read_tsv(out_dir / "het_dips.tsv"),
        "fst_top": _read_tsv(out_dir / "fst_top.tsv"),
        "by_grp_named": _read_tsv(out_dir / "by_grp_named.tsv"),
        "science": _read_tsv(out_dir / "vs_science_s29.tsv"),
        "overlap": _read_tsv(out_dir / "vs_science_overlap.tsv"),
        "vs_summary": _read_tsv(out_dir / "vs_science_summary.tsv"),
        "science_by_grp": _read_tsv(out_dir / "vs_science_by_grp.tsv"),
    }


def run_from_root(root: Path, *, half_bp: int = 50_000, top_n: int = 40) -> dict:
    from grapeancestry.core.dosage import load_cache, resolve_cache
    from grapeancestry.identity.catalog import load_info

    cache = resolve_cache(root)
    if not cache.exists():
        raise FileNotFoundError(f"no dosage cache at {cache}")
    mat, ids, sites = load_cache(cache)
    info = load_info(root / "data" / "panel" / "2449.info")
    grp = [info.get(i, {}).get("Grp", "") for i in ids]
    windows = load_named_windows(root / WINDOWS_REL)
    science = load_s29_windows(root / S29_GENES_REL)
    scan = scan_panel(
        mat,
        sites,
        grp,
        windows,
        half_bp=half_bp,
        top_n=top_n,
        grp_labels=grp,
        min_n=20,
        science_windows=science,
    )
    out = root / "results" / "selection"
    write_scan(scan, out)
    cloud = root / "data" / "cloud"
    cloud.mkdir(parents=True, exist_ok=True)
    dest = cloud / "selection_named.tsv"
    dest.write_text((out / "named_windows.tsv").read_text())
    (cloud / "selection_fst_top.tsv").write_text((out / "fst_top.tsv").read_text())
    by_p = out / "by_grp_named.tsv"
    if by_p.exists():
        (cloud / "selection_by_grp_named.tsv").write_text(by_p.read_text())
    sci_p = out / "vs_science_s29.tsv"
    if sci_p.exists():
        (cloud / "selection_vs_science_s29.tsv").write_text(sci_p.read_text())
    ov_p = out / "vs_science_overlap.tsv"
    if ov_p.exists():
        (cloud / "selection_vs_science_overlap.tsv").write_text(ov_p.read_text())
    sm_p = out / "vs_science_summary.tsv"
    if sm_p.exists():
        (cloud / "selection_vs_science_summary.tsv").write_text(sm_p.read_text())
    bg_p = out / "vs_science_by_grp.tsv"
    if bg_p.exists():
        (cloud / "selection_vs_science_by_grp.tsv").write_text(bg_p.read_text())
    from grapeancestry.popgen.selection_viz import write_selection_viz

    write_selection_viz(root)
    return scan
