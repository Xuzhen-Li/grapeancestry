"""Origin-geography association + Weir–Cockerham Fst by GEO.

Not a WorldClim raster GEA. Each 2449 sample with a passport Origin is given
the country/region centroid in ``data/panel/country_lonlat.tsv``. Per-site
Spearman is dosage vs longitude (east–west cline).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from grapeancestry.popgen.stats import spearman_gea, weir_cockerham_fst

LONLAT_REL = Path("data/panel/country_lonlat.tsv")


def load_lonlat(path: Path) -> dict[str, tuple[float, float]]:
    out: dict[str, tuple[float, float]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        header = None
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if header is None:
                header = parts
                continue
            row = {header[i]: parts[i] if i < len(parts) else "" for i in range(len(header))}
            name = (row.get("origin") or "").strip()
            try:
                out[name] = (float(row["lon"]), float(row["lat"]))
            except (KeyError, ValueError):
                continue
    return out


def origin_lonlat(origin: str, table: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    key = (origin or "").strip()
    if not key:
        return None
    if key in table:
        return table[key]
    # USSR / Geilweilerhof strings are not countries
    return None


def site_spearman_vs_lon(
    mat: np.ndarray,
    lons: np.ndarray,
    *,
    min_n: int = 20,
) -> np.ndarray:
    """Per-site Spearman(dosage, longitude); missing dosage skipped."""
    g = np.asarray(mat, dtype=float)
    lon = np.asarray(lons, dtype=float)
    ok_s = np.isfinite(lon)
    n_sites = g.shape[1]
    out = np.full(n_sites, np.nan)
    for j in range(n_sites):
        col = g[:, j]
        m = ok_s & (col >= 0)
        if int(m.sum()) < min_n:
            continue
        out[j] = spearman_gea(col[m], lon[m])
    return out


def fst_by_geo(mat: np.ndarray, groups: list[str]) -> dict:
    g = np.asarray(groups)
    counts = Counter(x for x in groups if x and x not in {"ND", ""})
    overall = weir_cockerham_fst(mat, g)
    pairs: list[dict] = []
    top = [name for name, _ in counts.most_common(6)]
    for i, a in enumerate(top):
        for b in top[i + 1 :]:
            mask = (g == a) | (g == b)
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "n_a": int(counts[a]),
                    "n_b": int(counts[b]),
                    "fst": weir_cockerham_fst(mat[mask], g[mask]),
                }
            )
    return {
        "overall_fst": overall,
        "n_groups": len(counts),
        "group_n": dict(counts),
        "pairs": pairs,
        "note": "Weir–Cockerham simplified Fst on fingerprint/dosage subset; GEO from 2449.info.",
    }


def gea_panel(
    mat: np.ndarray,
    sites: list[str],
    origins: list[str],
    groups: list[str],
    lonlat: dict[str, tuple[float, float]],
    *,
    top_n: int = 30,
    min_n: int = 20,
) -> dict:
    lons = np.array(
        [np.nan if origin_lonlat(o, lonlat) is None else origin_lonlat(o, lonlat)[0] for o in origins],
        dtype=float,
    )
    r = site_spearman_vs_lon(mat, lons, min_n=min_n)
    abs_r = np.where(np.isfinite(r), np.abs(r), -1.0)
    order = np.argsort(abs_r)[::-1]
    top = []
    for i in order[:top_n]:
        if abs_r[i] < 0:
            break
        top.append({"site": sites[i], "spearman_lon": float(r[i]), "abs_r": float(abs_r[i])})
    n_geo = int(np.isfinite(lons).sum())
    fst = fst_by_geo(mat, groups)
    mean_abs = float(np.nanmean(np.abs(r))) if np.isfinite(r).any() else float("nan")
    return {
        "n_with_origin_lon": n_geo,
        "n_sites": len(sites),
        "mean_abs_spearman": mean_abs,
        "top": top,
        "fst": fst,
        "method": "dosage~origin_longitude Spearman; Fst by GEO",
        "climate": "none (no WorldClim raster)",
    }


def write_gea_tables(payload: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    top_path = out_dir / "index.tsv"
    with top_path.open("w", encoding="utf-8") as fh:
        fh.write("rank\tsite\tspearman_lon\tabs_r\n")
        for i, row in enumerate(payload.get("top") or [], 1):
            fh.write(f"{i}\t{row['site']}\t{row['spearman_lon']:.6f}\t{row['abs_r']:.6f}\n")
    fst_path = out_dir / "fst_geo.tsv"
    fst = payload.get("fst") or {}
    with fst_path.open("w", encoding="utf-8") as fh:
        fh.write("a\tb\tn_a\tn_b\tfst\n")
        for row in fst.get("pairs") or []:
            fh.write(f"{row['a']}\t{row['b']}\t{row['n_a']}\t{row['n_b']}\t{row['fst']:.6f}\n")
        fh.write(f"OVERALL\tALL\t{fst.get('n_groups', 0)}\t\t{fst.get('overall_fst', float('nan'))}\n")
