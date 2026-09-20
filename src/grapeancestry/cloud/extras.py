"""Companion extras: purity, parentage, f3/f4, local ancestry, NJ, Fst/GEA, tree."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from grapeancestry.cloud.pack import pack_dir
from grapeancestry.cloud.vcf_py import align_dosage
from grapeancestry.identity.fingerprint import purity_z
from grapeancestry.identity.parentage import likely_parent, parentage_trio
from grapeancestry.popgen.fstats_report import fstats_for_query
from grapeancestry.popgen.tree_nj import build_nj_tree, to_newick
from grapeancestry.resource.local_ancestry import window_paint


def _info_groups(root: Path, ids: list[str]) -> list[str]:
    from grapeancestry.identity.catalog import load_info

    meta = load_info(root / "data" / "panel" / "2449.info")
    return [meta.get(i, {}).get("Grp", "") for i in ids]


def purity_block(query: np.ndarray, panel: np.ndarray) -> dict:
    z = purity_z(query.astype(float), panel)
    z["mixture"] = bool(z.get("z") == z.get("z") and z.get("z", 0) > 3.0)
    return z


def parentage_block(
    query: np.ndarray,
    panel: np.ndarray,
    ids: list[str],
    identity_top: list[dict],
) -> list[dict]:
    """Mendel scan of top identity hits (putative single parent / PO)."""
    idx = {s: i for i, s in enumerate(ids)}
    rows = []
    for hit in identity_top[:8]:
        rid = str(hit.get("ref_id") or "")
        if rid not in idx:
            continue
        cand = panel[idx[rid]]
        trio = parentage_trio(query, cand, np.ones_like(cand))
        rows.append(
            {
                "ref_id": rid,
                "ibs": hit.get("ibs"),
                "relationship": hit.get("relationship"),
                "king_robust": hit.get("king_robust"),
                "mendel_ok_other_unknown": trio.get("mendel_ok"),
                "n": trio.get("n"),
                "likely_parent": likely_parent(query, cand),
            }
        )
    return rows


def fstats_block(query: np.ndarray, panel: np.ndarray, ids: list[str], root: Path) -> dict:
    groups = _info_groups(root, ids)
    return fstats_for_query(query, panel, ids, groups)


def paint_block(query: np.ndarray, panel: np.ndarray, ids: list[str], root: Path) -> dict:
    groups = np.array(_info_groups(root, ids))
    labels = window_paint(query, panel, groups, window=25)
    n = len(labels)
    counts: dict[str, int] = {}
    for lab in labels:
        counts[lab] = counts.get(lab, 0) + 1
    return {
        "n_windows": n,
        "window": 25,
        "counts": counts,
        "labels": labels[:80],
        "note": "Nearest Grp by IBS per fingerprint window; not RFMix/ChromoPainter.",
    }


def nj_block(
    query: np.ndarray,
    panel: np.ndarray,
    ids: list[str],
    identity_top: list[dict],
    sample: str,
) -> dict:
    idx = {s: i for i, s in enumerate(ids)}
    tips = [sample]
    rows = [query.astype(np.int8)]
    for hit in identity_top[:15]:
        rid = str(hit.get("ref_id") or "")
        if rid in idx and rid not in tips:
            tips.append(rid)
            rows.append(panel[idx[rid]])
    if len(tips) < 3:
        return {"ok": False, "reason": "need ≥3 tips"}
    mat = np.vstack(rows)
    tree = build_nj_tree(tips, mat)
    return {"ok": True, "n_tips": len(tips), "tips": tips, "newick": to_newick(tree)}


def load_packed_gea(root: Path) -> dict:
    path = pack_dir(root) / "gea_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def gea_query_context(sample: str, root: Path, packed: dict | None = None) -> dict:
    from grapeancestry.identity.catalog import catalog_row
    from grapeancestry.popgen.gea import load_lonlat, origin_lonlat

    packed = packed if packed is not None else load_packed_gea(root)
    passp = catalog_row(sample, root)
    table = load_lonlat(root / "data" / "panel" / "country_lonlat.tsv")
    ll = origin_lonlat(passp.get("Origin", ""), table)
    out = {
        "origin": passp.get("Origin", ""),
        "geo": passp.get("GEO", ""),
        "lon": None if ll is None else ll[0],
        "lat": None if ll is None else ll[1],
        "panel": packed,
        "note": (
            "Panel GEA is dosage~origin longitude on the fingerprint pack. "
            "Not WorldClim. Query only contributes origin if the ID is in the passport."
        ),
    }
    return out
