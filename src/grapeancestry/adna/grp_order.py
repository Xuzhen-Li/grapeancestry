"""Canonical Grp order from Italian 2449 ADMIXTURE (group_only_sort.txt).

Order used in pophelper / facet plots: C-Ad → CG1..CG6 → OUT → W-Ad → WEE* → WWE*.
Source: ``stat_vcf_from_3527/ADMIXTURE/group_only_sort.txt`` first-appearance unique.
"""

from __future__ import annotations

from pathlib import Path

# Fallback if sort file missing (matches measured unique order in group_only_sort.txt)
DEFAULT_GRP_ORDER: list[str] = [
    "C-Ad",
    "CG1",
    "CG2",
    "CG3",
    "CG4",
    "CG5",
    "CG6",
    "OUT",
    "W-Ad",
    "WEE1",
    "WEE2",
    "WWE1",
    "WWE2",
]

# Report-specific order: keep the outgroup reference at the far-left edge
# while preserving the requested C-Ad/CG/W-Ad/Syl sequence.
REPORT_GRP_ORDER: list[str] = [
    "OUT",
    "C-Ad",
    "CG1",
    "CG2",
    "CG3",
    "CG4",
    "CG5",
    "CG6",
    "W-Ad",
    "WEE1",
    "WEE2",
    "WWE1",
    "WWE2",
]


def load_grp_order(admix_dir: Path | None = None) -> list[str]:
    if admix_dir is None:
        # Prefer in-suite assets; fall back to sibling 00_array legacy path
        suite_root = Path(__file__).resolve().parents[3]
        suite = suite_root / "data" / "panel" / "admixture"
        legacy = suite_root.parent / "stat_vcf_from_3527" / "ADMIXTURE"
        admix_dir = suite if (suite / "group_only_sort.txt").exists() else legacy
    path = admix_dir / "group_only_sort.txt"
    if not path.exists():
        return list(DEFAULT_GRP_ORDER)
    order: list[str] = []
    seen: set[str] = set()
    for line in path.read_text().splitlines():
        g = line.strip()
        if not g or g in seen:
            continue
        seen.add(g)
        order.append(g)
    return order or list(DEFAULT_GRP_ORDER)


def grp_sort_key(grp: str, order: list[str] | None = None) -> tuple[int, str]:
    order = order or DEFAULT_GRP_ORDER
    try:
        return (order.index(grp), grp)
    except ValueError:
        return (len(order), grp)


def order_ids_by_group(
    ids: list[str],
    metadata: dict[str, dict[str, str]],
    order: list[str] | None = None,
) -> list[str]:
    """Return deterministic report order with lexical IDs within each group."""
    order = order or REPORT_GRP_ORDER
    rank = {group: i for i, group in enumerate(order)}
    return sorted(
        ids,
        key=lambda sid: (
            rank.get(metadata.get(sid, {}).get("Grp", ""), len(order)),
            str(sid),
        ),
    )
