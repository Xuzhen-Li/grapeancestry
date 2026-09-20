"""IBS nearest-neighbor identity matching against a reference genotype matrix.

Genotype coding: 0=HOM_REF, 1=HET, 2=HOM_ALT, -1=missing.

Italy-663 4K rules (CLONE_CONTEXT.md):
  IBS2* = only both-het matches (AG↔AG)
  R0 = IBS0 / IBS2*
  R1 = IBS2* / (IBS0 + IBS1)
  KING_Robust = (IBS2* - 2*IBS0) / (IBS1 + 2*IBS2*)
  IBS2*_Percent_Of_Informative ≈ IBS2* / (IBS0 + IBS2*)  # snpduo column, not /n
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

RELATIONSHIPS = (
    "Identical",
    "Parent-Offspring",
    "Full Sib",
    "2nd",
    "3rd",
    "Unrelated",
)


@dataclass
class IBSHit:
    ref_id: str
    ibs: float
    n_comparable: int


@dataclass
class PairStats:
    ref_id: str
    ibs0: int
    ibs1: int
    ibs2: int
    ibs2_star: int
    n_comparable: int
    ibs2_star_pct: float
    r0: float
    r1: float
    king_robust: float
    kinship: float
    relationship: str
    ibs: float  # allele-match fraction (legacy)


def ibs_similarity(a: np.ndarray, b: np.ndarray) -> tuple[float, int]:
    """Return (IBS fraction, n_comparable) for two genotype vectors."""
    mask = (a >= 0) & (b >= 0)
    n = int(mask.sum())
    if n == 0:
        return float("nan"), 0
    return float(np.mean(a[mask] == b[mask])), n


def ibs_counts(a: np.ndarray, b: np.ndarray) -> tuple[int, int, int, int, int]:
    """Return (IBS0, IBS1, IBS2, IBS2*, n_comparable).

    IBS2* = count of both-het (1,1) only — snpduo convention.
    """
    mask = (a >= 0) & (b >= 0)
    aa = a[mask].astype(np.int8)
    bb = b[mask].astype(np.int8)
    n = int(mask.sum())
    if n == 0:
        return 0, 0, 0, 0, 0
    same = aa == bb
    both_het = (aa == 1) & (bb == 1)
    opp_hom = ((aa == 0) & (bb == 2)) | ((aa == 2) & (bb == 0))
    # IBS2 = same genotype; IBS0 = opposite hom; IBS1 = rest comparable
    ibs2 = int(same.sum())
    ibs0 = int(opp_hom.sum())
    ibs1 = n - ibs2 - ibs0
    ibs2_star = int(both_het.sum())
    return ibs0, ibs1, ibs2, ibs2_star, n


def r0_r1(ibs0: int, ibs1: int, ibs2_star: int) -> tuple[float, float]:
    r0 = ibs0 / ibs2_star if ibs2_star > 0 else float("inf")
    denom = ibs0 + ibs1
    # denom→0 with IBS2*>0 ⇒ perfect clone-like → R1 → +∞ (CLONE_CONTEXT.md)
    r1 = ibs2_star / denom if denom > 0 else (float("inf") if ibs2_star > 0 else 0.0)
    return r0, r1


def ibs2_star_percent_of_informative(ibs0: int, ibs2_star: int) -> float:
    """snpduo IBS2*_Percent_Of_Informative ≈ IBS2* / (IBS0 + IBS2*).

    Not IBS2*/(IBS0+IBS1+IBS2) — that maxes ~0.29 in grape and is wrong for 4K
    (CLONE_CONTEXT.md; clone_4k_summary.csv Identical rows ≈ 0.994).
    """
    denom = ibs0 + ibs2_star
    return ibs2_star / denom if denom > 0 else 0.0


def king_robust(ibs0: int, ibs1: int, ibs2_star: int) -> float:
    denom = ibs1 + 2 * ibs2_star
    if denom <= 0:
        return float("nan")
    return (ibs2_star - 2 * ibs0) / denom


def classify_relationship(
    r0: float,
    r1: float,
    ibs2_star_pct: float,
    king: float,
    kinship: float,
) -> str:
    """Decision order: Identical → PO → Full Sib → 2nd → 3rd → Unrelated.

    Thresholds from CLONE_CONTEXT.md + modern663_pop.md kinship bins.
    """
    if (
        r1 >= 1.2
        and ibs2_star_pct >= 0.99
        and king == king
        and king >= 0.3426
    ):
        return "Identical"
    if (
        0.5 < r1 < 1.2
        and king == king
        and 0.21 <= king < 0.3426
        and r0 <= 0.096
    ):
        return "Parent-Offspring"
    # kinship bins (KING Dup/MZ / 1st / 2nd / 3rd)
    k = kinship if kinship == kinship else king
    if k == k and 0.177 <= k < 0.354:
        return "Full Sib"
    if k == k and 0.0884 <= k < 0.177:
        return "2nd"
    if k == k and 0.0442 <= k < 0.0884:
        return "3rd"
    return "Unrelated"


def pair_stats(query: np.ndarray, ref: np.ndarray, ref_id: str) -> PairStats:
    ibs0, ibs1, ibs2, ibs2_star, n = ibs_counts(query, ref)
    ibs_frac, _ = ibs_similarity(query, ref)
    ibs2_star_pct = ibs2_star_percent_of_informative(ibs0, ibs2_star)
    r0, r1 = r0_r1(ibs0, ibs1, ibs2_star)
    king = king_robust(ibs0, ibs1, ibs2_star)
    # kinship column: KING robust estimator (Italy 4K cross-check uses KING --kinship;
    # for dosage-only we reuse KING_Robust as kinship)
    kinship = king
    rel = classify_relationship(r0, r1, ibs2_star_pct, king, kinship)
    return PairStats(
        ref_id=ref_id,
        ibs0=ibs0,
        ibs1=ibs1,
        ibs2=ibs2,
        ibs2_star=ibs2_star,
        n_comparable=n,
        ibs2_star_pct=ibs2_star_pct,
        r0=r0 if r0 != float("inf") else float("nan"),
        r1=r1,
        king_robust=king,
        kinship=kinship,
        relationship=rel,
        ibs=ibs_frac,
    )


def nearest_neighbors(
    query: np.ndarray,
    ref_matrix: np.ndarray,
    ref_ids: list[str],
    top_n: int = 5,
    exclude_ids: set[str] | frozenset[str] | None = None,
) -> list[IBSHit]:
    """Rank reference samples by IBS to query (legacy match-fraction)."""
    skip = exclude_ids or set()
    hits: list[IBSHit] = []
    for i, rid in enumerate(ref_ids):
        if rid in skip:
            continue
        sim, n = ibs_similarity(query, ref_matrix[i])
        hits.append(IBSHit(ref_id=rid, ibs=sim, n_comparable=n))
    hits.sort(key=lambda h: (-(h.ibs if h.ibs == h.ibs else -1), -h.n_comparable))
    return hits[:top_n]


def all_pair_stats(
    query: np.ndarray,
    ref_matrix: np.ndarray,
    ref_ids: list[str],
    *,
    exclude_id: str | None = None,
) -> list[PairStats]:
    rows: list[PairStats] = []
    for i, rid in enumerate(ref_ids):
        if exclude_id and rid == exclude_id:
            continue
        rows.append(pair_stats(query, ref_matrix[i], rid))
    # rank: Identical first, then by king_robust desc, then ibs
    rank = {r: i for i, r in enumerate(RELATIONSHIPS)}

    def key(p: PairStats):
        k = p.king_robust if p.king_robust == p.king_robust else -999
        return (rank.get(p.relationship, 99), -k, -(p.ibs if p.ibs == p.ibs else -1))

    rows.sort(key=key)
    return rows


def summarize_relationships(rows: list[PairStats]) -> dict[str, int]:
    c = Counter(p.relationship for p in rows)
    return {r: int(c.get(r, 0)) for r in RELATIONSHIPS}


# Italy clone_4k_summary = Identical + ParentOffspring (CLONE_CONTEXT.md)
CLONE_SCREEN_CLASSES = frozenset({"Identical", "Parent-Offspring"})


def is_identical(relationship: str) -> bool:
    return relationship == "Identical"


def is_parent_offspring(relationship: str) -> bool:
    return relationship == "Parent-Offspring"


def is_clone_screen_hit(relationship: str) -> bool:
    """True for Identical or Parent-Offspring (Italy 4K clone screen)."""
    return relationship in CLONE_SCREEN_CLASSES


def clone_screen_hits(rows: list[PairStats]) -> list[PairStats]:
    """Filter to Identical + PO pairs (clone_4k_summary equivalent)."""
    return [p for p in rows if is_clone_screen_hit(p.relationship)]


def is_clone(best_ibs: float, threshold: float = 0.98) -> bool:
    """Deprecated: prefer is_identical / is_clone_screen_hit / PairStats.relationship."""
    return best_ibs >= threshold


class IdentityCall(NamedTuple):
    self_hit: PairStats | None
    nearest_nonself: PairStats | None
    n_identical_nonself: int
    n_po_nonself: int


def interpret_identity(rows: list[PairStats], query_id: str) -> IdentityCall:
    """Split self-in-panel QC hit from nearest non-self 4K call."""
    self_hit = next((p for p in rows if p.ref_id == query_id), None)
    others = [p for p in rows if p.ref_id != query_id]
    nearest = others[0] if others else None
    n_id = sum(1 for p in others if p.relationship == "Identical")
    n_po = sum(1 for p in others if p.relationship == "Parent-Offspring")
    return IdentityCall(self_hit, nearest, n_id, n_po)
