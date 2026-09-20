"""Unphased SDR type on the chip window (not Science H1–H5).

Science sex is haplotype (Dong et al. 2023 *Science* 379:892–901,
doi:10.1126/science.add8655). This module does **not** phase or call H1/H2.

Window = ``trait_locus.tsv`` token ``sdr`` (chr2:14165010–14345273).
Het thresholds are empirical on this 2449 cache ∩ OIV 151 (euvitis):
female (score 4, n=22) median het ≈ 0.01; hermaphrodite (score 3, n=352)
median ≈ 0.70. No OIV 151 scores 1/2 (male) in ``phenotype.tsv``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from grapeancestry.cloud.loci import sites_with_token
from grapeancestry.cloud.vcf_py import align_dosage
from grapeancestry.identity.ibs import nearest_neighbors

SDR_LEAD = "2:14277567"
HET_FEMALE_MAX = 0.20
HET_HERM_MIN = 0.40
MIN_CALLED = 50
NN_IBS_STRONG = 0.98
NN_IBS_NEAR = 0.90
SDR_PACK = "sdr.npz"

OIV151_LABEL = {
    1.0: "male (no gynoecium)",
    2.0: "male (reduced gynoecium)",
    3.0: "hermaphrodite",
    4.0: "female",
    5.0: "female (OIV 151=5)",
}


def sdr_sites(root: Path) -> list[str]:
    return sites_with_token(root, "sdr")


def load_sdr_pack(root: Path) -> tuple[np.ndarray, list[str], list[str]] | None:
    path = root / "data" / "cloud" / SDR_PACK
    if not path.exists():
        return None
    z = np.load(path, allow_pickle=True)
    return z["mat"].astype(np.int8), list(z["samples"]), list(z["sites"])


def window_het(site_map: dict[str, int], sites: list[str]) -> tuple[int, float]:
    called = [int(site_map.get(s, -1)) for s in sites if int(site_map.get(s, -1)) >= 0]
    n = len(called)
    if n == 0:
        return 0, float("nan")
    return n, float(sum(d == 1 for d in called) / n)


def min_called_needed(n_window: int) -> int:
    if n_window <= 0:
        return MIN_CALLED
    if n_window < 20:
        return n_window
    return max(5, min(MIN_CALLED, n_window // 4))


def unphased_sex_proxy(het_frac: float, n_called_n: int, *, n_window: int = MIN_CALLED) -> str:
    need = min_called_needed(n_window)
    if n_called_n < need or het_frac != het_frac:
        return "low_coverage"
    if het_frac <= HET_FEMALE_MAX:
        return "female_like"
    if het_frac >= HET_HERM_MIN:
        return "herm_like"
    return "ambiguous"


def sdr_report(site_map: dict[str, int], root: Path) -> dict:
    sites = sdr_sites(root)
    n_win = len(sites)
    n_ok, het = window_het(site_map, sites)
    proxy = unphased_sex_proxy(het, n_ok, n_window=n_win)
    lead = int(site_map.get(SDR_LEAD, -1))
    out: dict = {
        "window": "2:14165010-14345273",
        "n_window": n_win,
        "n_called": n_ok,
        "het_frac": None if het != het else round(het, 4),
        "unphased_sex_proxy": proxy,
        "lead_snp": SDR_LEAD,
        "lead_dosage": lead,
        "lead_called": lead >= 0,
        "phase_status": (
            "unphased v1. Science sex = SDR haplotypes (H1–H5); "
            "H1/H2 vs H1/f needs a phased slice (Italian Beagle not packed)."
        ),
        "het_rule": (
            f"female_like het≤{HET_FEMALE_MAX}; herm_like het≥{HET_HERM_MIN}; "
            f"need ≥{min_called_needed(n_win)} called SDR sites. "
            "Empirical on this panel, not Dong Table S."
        ),
        "nearest": None,
        "catalog_sex": None,
        "pack": False,
        "note": (
            "M-bearing types (hermaphrodite/male) are heterozygous in the SDR; "
            "females are f/f. This catalog has herm vs female only (no OIV 151=1/2)."
        ),
    }
    packed = load_sdr_pack(root)
    if packed is None:
        return out
    mat, ids, pack_sites = packed
    out["pack"] = True
    out["n_pack"] = len(pack_sites)
    q = np.asarray(align_dosage(site_map, pack_sites), np.int8)
    hits = nearest_neighbors(q, mat, ids, top_n=1)
    if not hits:
        return out
    hit = hits[0]
    need = min_called_needed(len(pack_sites))
    if hit.n_comparable < need or hit.ibs != hit.ibs:
        return out
    strength = "weak"
    if hit.ibs >= NN_IBS_STRONG:
        strength = "identical_window"
    elif hit.ibs >= NN_IBS_NEAR:
        strength = "near"
    out["nearest"] = {
        "ref_id": hit.ref_id,
        "ibs": round(float(hit.ibs), 4),
        "n_comparable": int(hit.n_comparable),
        "strength": strength,
    }
    if strength == "weak":
        return out
    from grapeancestry.cloud.catalog import oiv_value_for

    val = oiv_value_for(hit.ref_id, "OIV 151", root)
    lab = OIV151_LABEL.get(float(val)) if val is not None else None
    if lab:
        out["catalog_sex"] = {
            "ref_id": hit.ref_id,
            "trait": "OIV 151",
            "value": val,
            "label": lab,
            "via": strength,
        }
    return out
