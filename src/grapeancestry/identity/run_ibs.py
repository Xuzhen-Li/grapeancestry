"""Run IBS / 4K identity against panel dosage cache."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from grapeancestry.core.dosage import load_cache, load_sample_dosage
from grapeancestry.identity.ibs import (
    IdentityCall,
    all_pair_stats,
    clone_screen_hits,
    interpret_identity,
    summarize_relationships,
)


def _pair_row(p) -> list:
    return [
        p.ref_id,
        p.ibs0,
        p.ibs1,
        p.ibs2_star,
        f"{p.ibs2_star_pct:.6f}",
        f"{p.r0:.6f}" if p.r0 == p.r0 else "NA",
        f"{p.r1:.6f}" if p.r1 == p.r1 and p.r1 != float("inf") else ("inf" if p.r1 == float("inf") else "NA"),
        f"{p.king_robust:.6f}" if p.king_robust == p.king_robust else "NA",
        f"{p.kinship:.6f}" if p.kinship == p.kinship else "NA",
        p.relationship,
    ]


IBS_HEADER = [
    "ref",
    "IBS0",
    "IBS1",
    "IBS2*",
    "IBS2*_pct",
    "R0",
    "R1",
    "KING_Robust",
    "kinship",
    "relationship",
]
_PAIR_HEADER = IBS_HEADER
_REQUIRED_4K = {"ref", "R1", "KING_Robust", "relationship"}


def read_ibs_table(path: Path) -> list[dict[str, str]]:
    """Load a 4K IBS TSV. Old schemas raise so the report cannot print None."""
    with path.open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    if not rows:
        return []
    keys = set(rows[0].keys())
    if not _REQUIRED_4K <= keys:
        raise ValueError(
            f"IBS table {path} is not 4K schema (have {sorted(keys)}); rerun identity"
        )
    return rows


def format_identity_conclusion(call: IdentityCall) -> str:
    """Human conclusion: self-QC (if any) + nearest non-self with numeric R1/KING."""

    def _num(x: float) -> str:
        if x != x or x in (float("inf"), float("-inf")):
            return "NA"
        return f"{x:.3f}"

    parts = ["Identity (4K):"]
    if call.self_hit is not None:
        p = call.self_hit
        parts.append(
            f"self-in-panel {p.relationship} → {p.ref_id} "
            f"(R1={_num(p.r1)}, KING={_num(p.king_robust)}; QC)"
        )
    if call.nearest_nonself is not None:
        p = call.nearest_nonself
        parts.append(
            f"nearest non-self {p.relationship} → {p.ref_id} "
            f"(R1={_num(p.r1)}, KING={_num(p.king_robust)})"
        )
    elif call.self_hit is None:
        parts.append("no comparable panel pairs")
    parts.append(
        f"clone-screen Identical={call.n_identical_nonself} + PO={call.n_po_nonself}"
    )
    return " ".join(parts) + "."


def format_identity_conclusion_from_rows(rows: list[dict[str, str]], query_id: str) -> str:
    """Same text as format_identity_conclusion, from a 4K TSV dict rows."""

    def _num(s: str) -> str:
        try:
            x = float(s)
        except (TypeError, ValueError):
            return "NA"
        if x != x or x in (float("inf"), float("-inf")):
            return "NA"
        return f"{x:.3f}"

    self_row = next((r for r in rows if r.get("ref") == query_id), None)
    others = [r for r in rows if r.get("ref") != query_id]
    nearest = others[0] if others else None
    n_id = sum(1 for r in others if r.get("relationship") == "Identical")
    n_po = sum(1 for r in others if r.get("relationship") == "Parent-Offspring")
    parts = ["Identity (4K):"]
    if self_row is not None:
        parts.append(
            f"self-in-panel {self_row.get('relationship')} → {self_row.get('ref')} "
            f"(R1={_num(self_row.get('R1', ''))}, KING={_num(self_row.get('KING_Robust', ''))}; QC)"
        )
        if self_row.get("relationship") != "Identical":
            parts.append(
                "(query genotypes are independently called vs panel GT, not a clone control)"
            )
    if nearest is not None:
        parts.append(
            f"nearest non-self {nearest.get('relationship')} → {nearest.get('ref')} "
            f"(R1={_num(nearest.get('R1', ''))}, KING={_num(nearest.get('KING_Robust', ''))})"
        )
    elif self_row is None:
        parts.append("no comparable panel pairs")
    parts.append(f"clone-screen Identical={n_id} + PO={n_po}")
    return " ".join(parts) + "."


def run_identity(
    query_vcf: Path,
    sample: str,
    cache_npz: Path,
    out_tsv: Path,
    *,
    top_n: int = 10,
    clone_threshold: float = 0.98,  # kept for API compat; unused by 4K rules
    exclude_self: bool = False,
) -> Path:
    mat, ref_ids, sites = load_cache(cache_npz)
    query = load_sample_dosage(query_vcf, sample, sites)
    rows = all_pair_stats(query, mat, ref_ids, exclude_id=sample if exclude_self else None)
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(_PAIR_HEADER)
        for p in rows:
            w.writerow(_pair_row(p))
    # summary (all classes)
    if out_tsv.name.endswith(".ibs.tsv"):
        summary = out_tsv.with_name(out_tsv.name.replace(".ibs.tsv", ".ibs_summary.tsv"))
        hits_path = out_tsv.with_name(out_tsv.name.replace(".ibs.tsv", ".ibs_clone_hits.tsv"))
    else:
        summary = out_tsv.with_name(out_tsv.stem + ".ibs_summary.tsv")
        hits_path = out_tsv.with_name(out_tsv.stem + ".ibs_clone_hits.tsv")
    counts = summarize_relationships([p for p in rows if p.ref_id != sample])
    with summary.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["relationship", "count"])
        for rel, n in counts.items():
            w.writerow([rel, n])
    # Italy-style clone screen: Identical + Parent-Offspring only
    # (CLONE_CONTEXT.md clone_4k_summary = 60 Identical + 228 PO)
    hits = [p for p in clone_screen_hits(rows) if p.ref_id != sample]
    with hits_path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(_PAIR_HEADER)
        for p in hits:
            w.writerow(_pair_row(p))
    return out_tsv


def kinship_top(
    query_vcf: Path,
    sample: str,
    cache_npz: Path,
    out_tsv: Path,
    *,
    top_n: int = 20,
) -> Path:
    """Top relatedness by KING_Robust (4K)."""
    mat, ref_ids, sites = load_cache(cache_npz)
    query = load_sample_dosage(query_vcf, sample, sites)
    rows = all_pair_stats(query, mat, ref_ids, exclude_id=sample)
    rows.sort(
        key=lambda p: (
            -(p.king_robust if p.king_robust == p.king_robust else -999),
            -(p.ibs if p.ibs == p.ibs else -1),
        )
    )
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["rank", "ref_id", "KING_Robust", "kinship", "relationship", "ibs", "n_comparable"])
        for i, p in enumerate(rows[:top_n], 1):
            w.writerow(
                [
                    i,
                    p.ref_id,
                    f"{p.king_robust:.6f}" if p.king_robust == p.king_robust else "NA",
                    f"{p.kinship:.6f}" if p.kinship == p.kinship else "NA",
                    p.relationship,
                    f"{p.ibs:.6f}" if p.ibs == p.ibs else "NA",
                    p.n_comparable,
                ]
            )
    return out_tsv


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query-vcf", type=Path, required=True)
    p.add_argument("--sample", required=True)
    p.add_argument("--cache", type=Path, default=Path("results/cache/panel_dosage_5k.npz"))
    p.add_argument("--out-tsv", type=Path, required=True)
    p.add_argument("--top-n", type=int, default=10)
    args = p.parse_args(argv)
    path = run_identity(args.query_vcf, args.sample, args.cache, args.out_tsv, top_n=args.top_n)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
