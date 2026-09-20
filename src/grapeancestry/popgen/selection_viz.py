"""Selection plots: LocusZoom regions, Manhattan, Grp heatmap, S29 scatter.

Y on LocusZoom is Fst (Grp) or windowed het — not a GWAS −log10 p.
Dong 2023 Table S29 is a dual-check overlay, not the named-window list.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from grapeancestry.popgen.selscan import (
    WINDOWS_REL,
    fst_one_vs_rest,
    load_named_windows,
    load_scan_arrays,
    load_scan_tables,
    parse_sites,
    site_in_windows,
    write_scan_arrays,
)

SEL_LZ_PAD = 250_000
MANHATTAN_STRIDE = 30
# Dong 2023 Table S29: FST and nucleotide-diversity difference both top 5%
# (doi:10.1126/science.add8655). Chip analogue: Grp-vs-rest Fst and within-Grp het.
SWEEP_FST_Q = 0.95
SWEEP_HET_Q = 0.05
SWEEP_TOP_N = 25


def chrom_sort_key(chrom: str) -> tuple:
    s = str(chrom)
    return (0, int(s)) if s.isdigit() else (1, s)


def cluster_peaks(
    rows: list[dict],
    *,
    merge_bp: int = 250_000,
    max_loci: int = 8,
) -> list[dict]:
    """Merge nearby fst_top/het_dip sites; keep the highest-value site per cluster."""
    by: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in rows:
        try:
            chrom = str(r.get("chrom") or "")
            pos = int(r.get("pos") or 0)
            val = float(r.get("value") or r.get("fst_grp") or r.get("fst_geo") or r.get("window_het") or "nan")
        except (TypeError, ValueError):
            continue
        if not chrom or pos <= 0 or val != val:
            continue
        by[chrom].append((pos, val))
    loci: list[dict] = []
    for chrom, pts in by.items():
        pts.sort()
        cluster: list[tuple[int, float]] = []
        for pos, val in pts:
            if not cluster or pos - cluster[-1][0] <= merge_bp:
                cluster.append((pos, val))
            else:
                lead = max(cluster, key=lambda t: t[1])
                loci.append({"chrom": chrom, "pos": lead[0], "value": lead[1]})
                cluster = [(pos, val)]
        if cluster:
            lead = max(cluster, key=lambda t: t[1])
            loci.append({"chrom": chrom, "pos": lead[0], "value": lead[1]})
    loci.sort(key=lambda r: -float(r["value"]))
    return loci[:max_loci]


def _f(x: float) -> float | None:
    v = float(x)
    if v != v:
        return None
    return round(v, 6)


def _lead_in_window(
    chroms: np.ndarray,
    pos: np.ndarray,
    fst: np.ndarray,
    chrom: str,
    start: int,
    end: int,
) -> int | None:
    m = (chroms == str(chrom)) & (pos >= int(start)) & (pos <= int(end))
    if not int(m.sum()):
        return None
    sub = np.where(m)[0]
    vals = fst[sub]
    if np.isfinite(vals).any():
        return int(pos[sub[int(np.nanargmax(np.where(np.isfinite(vals), vals, -np.inf)))]])
    return int(pos[sub[len(sub) // 2]])


def _in_any(chrom: str, pos: int, windows: list[dict]) -> bool:
    return bool(site_in_windows(chrom, pos, windows))


def _locus_specs(root: Path, chroms: np.ndarray, pos: np.ndarray, fst: np.ndarray) -> list[dict]:
    named = load_named_windows(root / WINDOWS_REL)
    tables = load_scan_tables(root / "results" / "selection") or {}
    specs: list[dict] = []
    covered: list[dict] = []
    for w in named:
        lead = _lead_in_window(chroms, pos, fst, w["chrom"], w["start"], w["end"])
        if lead is None:
            continue
        specs.append(
            {
                "kind": "named",
                "name": w["name"],
                "chrom": str(w["chrom"]),
                "pos": lead,
                "span_start": int(w["start"]),
                "span_end": int(w["end"]),
            }
        )
        covered.append(w)
    fst_rows = tables.get("fst_top") or []
    for r in fst_rows:
        r = dict(r)
        if "value" not in r:
            r["value"] = r.get("fst_grp") or r.get("fst_geo") or ""
    for peak in cluster_peaks(fst_rows, merge_bp=SEL_LZ_PAD, max_loci=8):
        if _in_any(peak["chrom"], peak["pos"], covered):
            continue
        specs.append(
            {
                "kind": "fst_peak",
                "name": f"Fst_{peak['chrom']}_{peak['pos']}",
                "chrom": str(peak["chrom"]),
                "pos": int(peak["pos"]),
                "span_start": int(peak["pos"]),
                "span_end": int(peak["pos"]),
            }
        )
    return specs


def _named_at(chrom: str, pos: int, windows: list[dict]) -> str:
    for w in windows:
        if str(w.get("chrom")) != str(chrom):
            continue
        try:
            if int(w["start"]) <= int(pos) <= int(w["end"]):
                return str(w.get("name") or w.get("kind") or "")
        except (TypeError, ValueError, KeyError):
            continue
    return ""


def _finite_quantile(arr: np.ndarray, q: float) -> float | None:
    fin = np.isfinite(arr)
    if not fin.any():
        return None
    return float(np.nanquantile(arr[fin], q))


def manhattan_pack(
    sites: list[str],
    fst: np.ndarray,
    het_w: np.ndarray,
    windows: list[dict],
    *,
    stride: int = MANHATTAN_STRIDE,
    extra_fst: dict[str, np.ndarray] | None = None,
    extra_het: dict[str, np.ndarray] | None = None,
    sweep_fst_q: float = SWEEP_FST_Q,
    sweep_het_q: float = SWEEP_HET_Q,
    sweep_top_n: int = SWEEP_TOP_N,
) -> dict:
    fst = np.asarray(fst, float)
    het_w = np.asarray(het_w, float)
    chroms, pos = parse_sites(sites)
    order = sorted(set(str(c) for c in chroms), key=chrom_sort_key)
    offset = 0
    offsets: dict[str, int] = {}
    ticks: list[dict] = []
    for c in order:
        m = chroms == c
        mx = int(pos[m].max()) if int(m.sum()) else 0
        offsets[c] = offset
        ticks.append({"chrom": c, "x": offset + mx // 2})
        offset += mx + 2_000_000
    q_fst = float(np.nanquantile(fst[np.isfinite(fst)], 0.90)) if np.isfinite(fst).any() else 1.0
    q_het = float(np.nanquantile(het_w[np.isfinite(het_w)], 0.10)) if np.isfinite(het_w).any() else 0.0
    keep = np.zeros(len(sites), dtype=bool)
    keep[:: max(1, stride)] = True
    keep |= np.where(np.isfinite(fst), fst >= q_fst, False)
    keep |= np.where(np.isfinite(het_w), het_w <= q_het, False)
    for w in windows:
        keep |= (chroms == str(w["chrom"])) & (pos >= int(w["start"])) & (pos <= int(w["end"]))
    extra_fst = extra_fst or {}
    extra_het = extra_het or {}
    extra_arr = {k: np.asarray(v, float) for k, v in extra_fst.items()}
    het_arr = {k: np.asarray(v, float) for k, v in extra_het.items()}
    sweep_full: dict[str, np.ndarray] = {}
    sweep_thr: dict[str, dict] = {}
    sweeps: dict[str, list[dict]] = {}
    for k, fa in extra_arr.items():
        qf = _finite_quantile(fa, sweep_fst_q)
        if qf is not None:
            keep |= np.isfinite(fa) & (fa >= qf)
        ha = het_arr.get(k)
        if ha is None or qf is None:
            continue
        qh = _finite_quantile(ha, sweep_het_q)
        if qh is None:
            continue
        sw = np.isfinite(fa) & np.isfinite(ha) & (fa >= qf) & (ha <= qh)
        keep |= sw
        sweep_full[k] = sw
        sweep_thr[k] = {"fst95": _f(qf), "het05": _f(qh), "n": int(sw.sum())}
        idx = np.where(sw)[0]
        if not len(idx):
            sweeps[k] = []
            continue
        order_i = idx[np.argsort(-np.where(np.isfinite(fa[idx]), fa[idx], -np.inf))]
        rows: list[dict] = []
        for i in order_i[: max(1, int(sweep_top_n))]:
            c = str(chroms[i])
            p = int(pos[i])
            rows.append(
                {
                    "chrom": c,
                    "pos": p,
                    "fst": _f(fa[i]),
                    "het": _f(ha[i]),
                    "named": _named_at(c, p, windows),
                }
            )
        sweeps[k] = rows
    extra_lists: dict[str, list[float | None]] = {k: [] for k in extra_arr}
    het_lists: dict[str, list[float | None]] = {k: [] for k in het_arr}
    sweep_lists: dict[str, list[int]] = {k: [] for k in sweep_full}
    xs: list[int] = []
    ys: list[float | None] = []
    hs: list[float | None] = []
    chs: list[str] = []
    ps: list[int] = []
    for i in np.where(keep)[0]:
        c = str(chroms[i])
        p = int(pos[i])
        xs.append(int(offsets[c] + p))
        ys.append(_f(fst[i]))
        hs.append(_f(het_w[i]))
        chs.append(c)
        ps.append(p)
        for k, arr in extra_arr.items():
            extra_lists[k].append(_f(arr[i]) if i < len(arr) else None)
        for k, arr in het_arr.items():
            het_lists[k].append(_f(arr[i]) if i < len(arr) else None)
        for k, sw in sweep_full.items():
            sweep_lists[k].append(1 if i < len(sw) and bool(sw[i]) else 0)
    marks = []
    for w in windows:
        c = str(w["chrom"])
        if c not in offsets:
            continue
        marks.append(
            {
                "name": w.get("name") or w.get("kind") or "",
                "kind": w.get("kind") or "window",
                "chrom": c,
                "start": int(w["start"]),
                "end": int(w["end"]),
                "x0": int(offsets[c] + int(w["start"])),
                "x1": int(offsets[c] + int(w["end"])),
            }
        )
    pack: dict = {
        "x": xs,
        "fst": ys,
        "het": hs,
        "chrom": chs,
        "pos": ps,
        "ticks": ticks,
        "windows": marks,
        "sweep_method": (
            "Fst(Grp vs rest) ≥ 95th and within-Grp windowed het ≤ 5th. "
            "Unphased het, not XP-CLR/iHS/G12. Science tables are overlap checks only."
        ),
    }
    if extra_lists:
        pack["fst_by_grp"] = extra_lists
    if het_lists:
        pack["het_by_grp"] = het_lists
    if sweep_lists:
        pack["sweep_by_grp"] = sweep_lists
        pack["sweep_thr"] = sweep_thr
        pack["sweeps"] = sweeps
    return pack


def _cell(rec: dict, *keys: str) -> float | None:
    for k in keys:
        raw = rec.get(k)
        if raw is None or raw == "":
            continue
        try:
            return _f(float(raw))
        except (TypeError, ValueError):
            continue
    return None


def _heatmap_window_lab(name: str, chrom: str = "", start: int = 0) -> str:
    short = {
        "SDR_trait_locus": "SDR",
        "VvMybA": "VvMybA",
        "Vvsyl02G000229": "Vvsyl02G000229",
        "Vvsyl02G001064": "Vvsyl02G001064",
        "VvDXS": "VvDXS",
    }.get(str(name), str(name))
    if chrom and int(start or 0) > 0:
        return f"{short}\nchr{chrom}:{int(start) / 1e6:.2f} Mb"
    return short


def heatmap_pack(by_grp: list[dict]) -> dict:
    windows: list[str] = []
    grps: list[str] = []
    seen_w: set[str] = set()
    seen_g: set[str] = set()
    meta: dict[str, dict] = {}
    for r in by_grp:
        w = str(r.get("name") or "")
        g = str(r.get("grp") or "")
        if w and w not in seen_w:
            windows.append(w)
            seen_w.add(w)
            try:
                chrom = str(r.get("chrom") or "")
                start = int(r.get("start") or 0)
                end = int(r.get("end") or 0)
                n_sites = int(float(r.get("n_sites") or 0))
            except (TypeError, ValueError):
                chrom, start, end, n_sites = "", 0, 0, 0
            meta[w] = {
                "lab": _heatmap_window_lab(w, chrom, start),
                "chrom": chrom,
                "start": start,
                "end": end,
                "n_sites": n_sites,
            }
        if g and g not in seen_g:
            grps.append(g)
            seen_g.add(g)
    het: list[list[float | None]] = []
    fst: list[list[float | None]] = []
    lookup = {(str(r.get("grp")), str(r.get("name"))): r for r in by_grp}
    for g in grps:
        het.append([_cell(lookup.get((g, w)) or {}, "mean_het") for w in windows])
        fst.append(
            [_cell(lookup.get((g, w)) or {}, "mean_fst_vs_rest", "mean_fst") for w in windows]
        )
    return {
        "grp": grps,
        "window": windows,
        "window_lab": [meta[w]["lab"] for w in windows],
        "chrom": [meta[w]["chrom"] for w in windows],
        "start": [meta[w]["start"] for w in windows],
        "end": [meta[w]["end"] for w in windows],
        "n_sites": [meta[w]["n_sites"] for w in windows],
        "het": het,
        "fst": fst,
    }


def fst_het_scatter_pack(
    sites: list[str],
    fst: np.ndarray,
    het: np.ndarray,
    windows: list[dict],
    *,
    stride: int = MANHATTAN_STRIDE,
) -> dict:
    """Genome subsample of per-site het vs among-all-Grps Fst; named windows as means.

    Background uses the same deterministic stride as the Manhattan pack (no tail
    dump). Stars use the same window means as the named-window table (mean het,
    mean Fst).
    """
    fst = np.asarray(fst, float)
    het = np.asarray(het, float)
    chroms, pos = parse_sites(sites)
    finite = np.isfinite(fst) & np.isfinite(het)
    q_fst = float(np.nanquantile(fst[finite], 0.90)) if finite.any() else 1.0
    q_het = float(np.nanquantile(het[finite], 0.10)) if finite.any() else 0.0
    keep = np.zeros(len(sites), dtype=bool)
    keep[:: max(1, stride)] = True
    keep &= finite
    xs: list[float | None] = []
    ys: list[float | None] = []
    chs: list[str] = []
    ps: list[int] = []
    for i in np.where(keep)[0]:
        xs.append(_f(het[i]))
        ys.append(_f(fst[i]))
        chs.append(str(chroms[i]))
        ps.append(int(pos[i]))
    named_means: list[dict] = []
    for w in windows:
        if str(w.get("kind") or "named") == "s29":
            continue
        m = (chroms == str(w["chrom"])) & (pos >= int(w["start"])) & (pos <= int(w["end"])) & finite
        n = int(m.sum())
        if not n:
            continue
        name = str(w.get("name") or "")
        named_means.append(
            {
                "name": name,
                "label": _heatmap_window_lab(name, str(w["chrom"]), int(w["start"])).split("\n")[0],
                "chrom": str(w["chrom"]),
                "pos": int((int(w["start"]) + int(w["end"])) // 2),
                "n": n,
                "het": _f(float(np.nanmean(het[m]))),
                "fst": _f(float(np.nanmean(fst[m]))),
            }
        )
    return {
        "het": xs,
        "fst": ys,
        "chrom": chs,
        "pos": ps,
        "kind": ["bg"] * len(xs),
        "q_fst90": _f(q_fst),
        "q_het10": _f(q_het),
        "named_means": named_means,
    }


def _s29_short_label(name: str, chrom: str = "", start: int = 0, end: int = 0) -> str:
    raw = str(name or "")
    if raw.startswith("S29_"):
        raw = raw[4:]
    parts = raw.split("_")
    if len(parts) >= 2 and parts[-2].isdigit() and parts[-1].isdigit():
        gene = "_".join(parts[:-2])
        if gene:
            return gene
        if chrom and start and end:
            return f"{chrom}:{start / 1e6:.2f}–{end / 1e6:.2f} Mb"
        return f"{parts[-2]}:{parts[-1]}"
    return raw or name


def _interval_overlap(a: dict, b: dict) -> bool:
    try:
        if str(a.get("chrom")) != str(b.get("chrom")):
            return False
        return int(a["start"]) <= int(b["end"]) and int(b["start"]) <= int(a["end"])
    except (TypeError, ValueError, KeyError):
        return False


def s29_scatter_pack(science: list[dict], named: list[dict] | None = None) -> dict:
    names: list[str] = []
    labels: list[str] = []
    het: list[float | None] = []
    fst: list[float | None] = []
    n: list[int] = []
    overlap: list[str] = []
    chroms: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    named = named or []
    for r in science:
        try:
            ns = int(float(r.get("n_sites") or 0))
        except (TypeError, ValueError):
            ns = 0
        if ns <= 0:
            continue
        nm = str(r.get("name") or "")
        names.append(nm)
        try:
            c = str(r.get("chrom") or "")
            st = int(r["start"])
            en = int(r["end"])
        except (TypeError, ValueError, KeyError):
            c, st, en = "", 0, 0
        labels.append(_s29_short_label(nm, c, st, en))
        try:
            het.append(_f(float(r.get("mean_het") or "nan")))
        except (TypeError, ValueError):
            het.append(None)
        try:
            fst.append(_f(float(r.get("mean_fst") or "nan")))
        except (TypeError, ValueError):
            fst.append(None)
        n.append(ns)
        hit = ""
        for w in named:
            if _interval_overlap(r, w):
                hit = str(w.get("name") or "")
                break
        overlap.append(hit)
        chroms.append(c)
        starts.append(st)
        ends.append(en)
    return {
        "name": names,
        "label": labels,
        "het": het,
        "fst": fst,
        "n_sites": n,
        "overlap": overlap,
        "chrom": chroms,
        "start": starts,
        "end": ends,
    }


def _write_pngs(root: Path, manh: dict, heat: dict, s29: dict, scatter: dict | None = None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dest = root / "results" / "selection"
    dest.mkdir(parents=True, exist_ok=True)
    cloud = root / "data" / "cloud"
    cloud.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10.5, 2.8))
    xs = manh.get("x") or []
    ys = manh.get("fst") or []
    chs = manh.get("chrom") or []
    palette = ["#4c72b0", "#dd8452"]
    cmap = {c: palette[i % 2] for i, c in enumerate(sorted(set(chs), key=chrom_sort_key))}
    colors = [cmap.get(c, "#888") for c in chs]
    ax.scatter(xs, [0 if y is None else y for y in ys], s=4, c=colors, linewidths=0, rasterized=True)
    for m in manh.get("windows") or []:
        if m.get("kind") != "named":
            continue
        ax.axvspan(m["x0"], m["x1"], color="#2ca02c", alpha=0.12, lw=0)
    ax.set_ylabel("Fst among all Grps")
    ax.set_xticks([t["x"] for t in manh.get("ticks") or []])
    ax.set_xticklabels([t["chrom"] for t in manh.get("ticks") or []], fontsize=7)
    ax.set_title("167K unphased Fst among all Grps (simplified Fst contrast; not XP-CLR)")
    fig.tight_layout()
    p = dest / "manhattan_fst.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    (cloud / "selection_manhattan_fst.png").write_bytes(p.read_bytes())

    fig, ax = plt.subplots(figsize=(10.5, 2.8))
    hs = manh.get("het") or []
    ax.scatter(xs, [0 if y is None else y for y in hs], s=4, c=colors, linewidths=0, rasterized=True)
    ax.set_ylabel("windowed het")
    ax.set_xticks([t["x"] for t in manh.get("ticks") or []])
    ax.set_xticklabels([t["chrom"] for t in manh.get("ticks") or []], fontsize=7)
    ax.set_title("167K windowed het ±50 kb (unphased)")
    fig.tight_layout()
    p = dest / "manhattan_het.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    (cloud / "selection_manhattan_het.png").write_bytes(p.read_bytes())

    z = heat.get("het") or []
    if z and heat.get("grp") and heat.get("window"):
        arr = np.array([[np.nan if v is None else v for v in row] for row in z], float)
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        im = ax.imshow(arr, aspect="auto", cmap="viridis_r", interpolation="nearest")
        ax.set_xticks(range(len(heat["window"])))
        ax.set_xticklabels(heat["window"], rotation=40, ha="right", fontsize=7)
        ax.set_yticks(range(len(heat["grp"])))
        ax.set_yticklabels(heat["grp"], fontsize=8)
        ax.set_title("Within-Grp windowed het (named windows)")
        fig.colorbar(im, ax=ax, shrink=0.8, label="het")
        fig.tight_layout()
        p = dest / "heatmap_grp_het.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        (cloud / "selection_heatmap_grp.png").write_bytes(p.read_bytes())

        zf = heat.get("fst") or []
        if zf:
            arr_f = np.array([[np.nan if v is None else v for v in row] for row in zf], float)
            fig, ax = plt.subplots(figsize=(7.2, 4.2))
            im = ax.imshow(arr_f, aspect="auto", cmap="magma", interpolation="nearest")
            ax.set_xticks(range(len(heat["window"])))
            ax.set_xticklabels(heat["window"], rotation=40, ha="right", fontsize=7)
            ax.set_yticks(range(len(heat["grp"])))
            ax.set_yticklabels(heat["grp"], fontsize=8)
            ax.set_title("Fst (Grp vs rest) at named windows")
            fig.colorbar(im, ax=ax, shrink=0.8, label="Fst vs rest")
            fig.tight_layout()
            p = dest / "heatmap_grp_fst.png"
            fig.savefig(p, dpi=120)
            plt.close(fig)
            (cloud / "selection_heatmap_grp_fst.png").write_bytes(p.read_bytes())

    names = s29.get("name") or []
    if names:
        fig, ax = plt.subplots(figsize=(6.4, 6.2))
        labels = s29.get("label") or [_s29_short_label(n) for n in names]
        fsts = [0.0 if v is None else float(v) for v in (s29.get("fst") or [])]
        ovs = s29.get("overlap") or [""] * len(names)
        order = sorted(range(len(names)), key=lambda i: fsts[i])
        ys = list(range(len(order)))
        cols = ["#16a34a" if ovs[i] else "#4c72b0" for i in order]
        ax.hlines(ys, 0, [fsts[i] for i in order], color="#cbd5e1", lw=1)
        ax.scatter([fsts[i] for i in order], ys, s=28, c=cols, zorder=3)
        ax.set_yticks(ys)
        ax.set_yticklabels([labels[i] for i in order], fontsize=7)
        ax.set_xlabel("mean Fst among Grps")
        ax.set_title("Table S29 bins (green = overlaps our named window)")
        fig.tight_layout()
        p = dest / "s29_dual.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        (cloud / "selection_s29_dual.png").write_bytes(p.read_bytes())

    sc = scatter or {}
    if sc.get("het"):
        fig, ax = plt.subplots(figsize=(5.6, 4.0))
        ax.scatter(
            [0 if h is None else h for h in sc.get("het") or []],
            [0 if f is None else f for f in sc.get("fst") or []],
            s=6,
            c="#9ca3af",
            alpha=0.35,
            linewidths=0,
            label="167K subsample",
        )
        qh = sc.get("q_het10")
        qf = sc.get("q_fst90")
        if qh is not None:
            ax.axvline(qh, color="#64748b", ls=":", lw=1)
        if qf is not None:
            ax.axhline(qf, color="#64748b", ls=":", lw=1)
        for rec in sc.get("named_means") or []:
            ax.scatter([rec.get("het")], [rec.get("fst")], s=60, c="#16a34a", marker="*", zorder=3)
            ax.annotate(str(rec.get("name") or ""), (rec.get("het"), rec.get("fst")), fontsize=6)
        ax.legend(fontsize=7, loc="upper right")
        ax.set_xlabel("windowed het ±50 kb")
        ax.set_ylabel("Fst among all Grps")
        ax.set_title("167K Fst vs het (stars = named-window means)")
        fig.tight_layout()
        p = dest / "fst_het_scatter.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        (cloud / "selection_fst_het_scatter.png").write_bytes(p.read_bytes())


def write_selection_locuszooms(root: Path, arrays: dict) -> list[dict]:
    from grapeancestry.breeding.gwas import (
        _load_gwas_exclude,
        _load_trait_locus,
        _snp_window_annos,
        _tl_index,
        locuszoom_record,
        r2_to_lead,
    )
    from grapeancestry.cloud.mas import MAS_LOCI
    from grapeancestry.core.dosage import load_cache, resolve_cache
    from grapeancestry.resource.genes import load_gene_annotation
    from grapeancestry.resource.sprot import load_gene_func

    sites = arrays["sites"]
    chroms, pos = parse_sites(sites)
    fst = np.asarray(arrays["fst"], float)
    het = np.asarray(arrays["het"], float)
    het_w = np.asarray(arrays["het_window"], float)
    site_index = {s: i for i, s in enumerate(sites)}
    specs = _locus_specs(root, chroms, pos, fst)
    gff = root / "data" / "ref" / "VS1.final.gff3"
    genes: dict = {}
    features: dict = {}
    if gff.exists():
        genes, features = load_gene_annotation(gff)
    sprot = load_gene_func(root)
    mas_by_gene = {str(r["gene"]): r for r in MAS_LOCI if r.get("gene")}
    mas_by_site = {str(r["site"]): r for r in MAS_LOCI if r.get("site")}
    tl_index = _tl_index(_load_trait_locus(root / "data" / "trait_locus.tsv"))
    exclude = _load_gwas_exclude(root / "data" / "panel" / "admixture" / "gwas_exclude.tsv")
    cache_p = resolve_cache(root)
    mat = None
    if cache_p.exists():
        mat, _ids, _sites = load_cache(cache_p)
    rows_out: list[dict] = []
    for spec in specs:
        chrom = spec["chrom"]
        lead = int(spec["pos"])
        start = max(1, min(int(spec["span_start"]), lead) - SEL_LZ_PAD)
        end = max(int(spec["span_end"]), lead) + SEL_LZ_PAD
        m = (chroms == chrom) & (pos >= start) & (pos <= end)
        idx = np.where(m)[0]
        if idx.size == 0:
            continue
        sites_w = [sites[i] for i in idx]
        pos_a = pos[idx]
        fst_a = fst[idx]
        het_a = het[idx]
        hetw_a = het_w[idx]
        nlp_a = np.where(np.isfinite(fst_a), fst_a, 0.0)
        r2 = None
        if mat is not None:
            lead_key = f"{chrom}:{lead}"
            lead_j = site_index.get(lead_key)
            js = [int(i) for i in idx]
            if lead_j is None and js:
                lead_j = int(js[int(np.nanargmax(np.where(np.isfinite(fst_a), fst_a, -np.inf)))])
                lead = int(pos[lead_j])
            if lead_j is not None:
                r2 = r2_to_lead(mat, lead_j, js)
        g_chrom = genes.get(chrom) or genes.get(f"chr{chrom}") or []
        extra = {
            "fst": [_f(v) for v in fst_a],
            "het": [_f(v) for v in het_a],
            "het_window": [_f(v) for v in hetw_a],
        }
        extra.update(
            _snp_window_annos(
                chrom,
                [int(p) for p in pos_a],
                sites_w,
                genes,
                features,
                mas_by_site=mas_by_site,
                mas_by_gene=mas_by_gene,
                tl_index=tl_index,
                exclude=exclude,
            )
        )
        rec = locuszoom_record(
            trait=str(spec["kind"]),
            slug=str(spec["name"]),
            chrom=chrom,
            pos=lead,
            gene="",
            nlp_lead=_f(float(fst[site_index[f"{chrom}:{lead}"]])) if f"{chrom}:{lead}" in site_index else "",
            sites=sites_w,
            pos_a=pos_a,
            nlp_a=nlp_a,
            r2=r2,
            genes_chrom=g_chrom,
            features=features,
            window_start=start,
            window_end=end,
            bonf_nlp=float("nan"),
            snp_extra=extra,
            sprot_by_gene=sprot,
            mas_by_gene=mas_by_gene,
            locus_meta={
                "kind": spec["kind"],
                "y_metric": "fst",
                "y_label": "Fst (Grp)",
                "span_start": int(spec["span_start"]),
                "span_end": int(spec["span_end"]),
            },
        )
        if rec.get("genes"):
            rec["gene"] = rec["genes"][0].get("id") or ""
        rows_out.append(rec)
    out = root / "results" / "selection"
    idx_lz = out / "locuszoom.tsv"
    keys = ("kind", "slug", "chrom", "pos", "gene", "n_snps")
    with idx_lz.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(keys) + "\n")
        for r in rows_out:
            fh.write(
                "\t".join(str(r.get(k, r.get("kind", "") if k == "kind" else "")) for k in keys) + "\n"
            )
    (out / "locuszoom.json").write_text(
        json.dumps(rows_out, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return rows_out


def grp_scan_arrays(
    root: Path, sites: list[str], *, min_n: int = 20
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Per-site Fst(Grp vs rest) and within-Grp windowed het. Empty if cache sites mismatch."""
    from grapeancestry.core.dosage import load_cache, resolve_cache
    from grapeancestry.identity.catalog import load_info
    from grapeancestry.popgen.selscan import per_site_het, rolling_mean_bp

    cache = resolve_cache(root)
    if not cache.exists():
        return {}, {}
    mat, ids, cache_sites = load_cache(cache)
    if list(cache_sites) != list(sites):
        return {}, {}
    info = load_info(root / "data" / "panel" / "2449.info")
    groups = np.array([info.get(i, {}).get("Grp", "") for i in ids], dtype=object)
    chroms, pos = parse_sites(sites)
    counts: dict[str, int] = {}
    for lab in groups:
        key = str(lab)
        if key in {"", "ND", "nan"}:
            continue
        counts[key] = counts.get(key, 0) + 1
    fst_out: dict[str, np.ndarray] = {}
    het_out: dict[str, np.ndarray] = {}
    for lab, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if lab == "OUT" or n < min_n:
            continue
        sub = mat[groups == lab]
        het = per_site_het(sub)
        het_out[lab] = rolling_mean_bp(het, chroms, pos, half_bp=50_000)
        fst_out[lab] = fst_one_vs_rest(mat, groups, lab)
    return fst_out, het_out


def grp_fst_vs_rest_arrays(root: Path, sites: list[str], *, min_n: int = 20) -> dict[str, np.ndarray]:
    """Per-site Fst(Grp vs rest) for groups with n≥min_n. Empty if cache sites mismatch."""
    fst, _het = grp_scan_arrays(root, sites, min_n=min_n)
    return fst


def write_selection_viz(root: Path) -> dict:
    """Write scan.npz (if present), Manhattan JSON/PNG, heatmap PNG, S29 scatter, LocusZoom JSON."""
    out = root / "results" / "selection"
    arrays = load_scan_arrays(out)
    if arrays is None:
        from grapeancestry.core.dosage import load_cache, resolve_cache
        from grapeancestry.identity.catalog import load_info
        from grapeancestry.popgen.selscan import fst_sites, per_site_het, rolling_mean_bp

        cache = resolve_cache(root)
        if not cache.exists():
            return {}
        mat, ids, sites = load_cache(cache)
        info = load_info(root / "data" / "panel" / "2449.info")
        grp = [info.get(i, {}).get("Grp", "") for i in ids]
        chroms, pos = parse_sites(sites)
        het = per_site_het(mat)
        het_w = rolling_mean_bp(het, chroms, pos, half_bp=50_000)
        fst = fst_sites(mat, np.asarray(grp))
        arrays = {"sites": sites, "het": het, "het_window": het_w, "fst": fst}
        write_scan_arrays(
            {"sites": sites, "het": het, "het_window": het_w, "fst": fst},
            out,
        )
    named = load_named_windows(root / WINDOWS_REL)
    tables = load_scan_tables(out) or {}
    manh_windows = [
        {"name": w["name"], "kind": "named", "chrom": w["chrom"], "start": w["start"], "end": w["end"]}
        for w in named
    ]
    manh_named = manh_windows
    extra_fst, extra_het = grp_scan_arrays(root, arrays["sites"])
    manh = manhattan_pack(
        arrays["sites"],
        arrays["fst"],
        arrays["het_window"],
        manh_named,
        extra_fst=extra_fst,
        extra_het=extra_het,
    )
    heat = heatmap_pack(tables.get("by_grp_named") or [])
    s29p = s29_scatter_pack(tables.get("science") or [], named=named)
    scatter = fst_het_scatter_pack(arrays["sites"], arrays["fst"], arrays["het"], manh_windows)
    (out / "manhattan.json").write_text(json.dumps(manh, ensure_ascii=False, allow_nan=False) + "\n")
    (out / "heatmap.json").write_text(json.dumps(heat, ensure_ascii=False, allow_nan=False) + "\n")
    (out / "s29_scatter.json").write_text(json.dumps(s29p, ensure_ascii=False, allow_nan=False) + "\n")
    (out / "fst_het_scatter.json").write_text(json.dumps(scatter, ensure_ascii=False, allow_nan=False) + "\n")
    _write_pngs(root, manh, heat, s29p, scatter)
    loci = write_selection_locuszooms(root, arrays)
    return {
        "n_loci": len(loci),
        "n_manhattan": len(manh.get("x") or []),
        "n_scatter": len(scatter.get("het") or []),
        "n_grp_fst": len((manh.get("fst_by_grp") or {})),
    }


def load_selection_viz(root: Path) -> dict:
    out = root / "results" / "selection"
    loci: list[dict] = []
    lz = out / "locuszoom.json"
    if lz.exists():
        loci = json.loads(lz.read_text(encoding="utf-8"))
    manh = {}
    mp = out / "manhattan.json"
    if mp.exists():
        manh = json.loads(mp.read_text(encoding="utf-8"))
    tables = load_scan_tables(out) or {}
    scatter: dict = {}
    sp = out / "fst_het_scatter.json"
    if sp.exists():
        scatter = json.loads(sp.read_text(encoding="utf-8"))
    return {
        "loci": loci,
        "manhattan": manh,
        "heatmap": heatmap_pack(tables.get("by_grp_named") or []),
        "s29_scatter": s29_scatter_pack(tables.get("science") or [], named=load_named_windows(root / WINDOWS_REL)),
        "fst_het_scatter": scatter,
    }
