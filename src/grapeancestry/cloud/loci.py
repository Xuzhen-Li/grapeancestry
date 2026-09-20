"""Chip trait-locus lists from ``data/trait_locus.tsv`` (Italian design tags)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


def trait_tokens(trait: str) -> set[str]:
    return {t.strip() for t in (trait or "").split(",") if t.strip()}


def _parse_pos(pos: str) -> int | None:
    try:
        return int(float(pos))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=8)
def load_trait_locus_rows(path: str) -> tuple[tuple[str, int, str], ...]:
    p = Path(path)
    if not p.exists():
        return ()
    rows: list[tuple[str, int, str]] = []
    with p.open(encoding="utf-8") as fh:
        header = fh.readline()
        if not header:
            return ()
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            pos = _parse_pos(parts[1])
            if pos is None:
                continue
            rows.append((parts[0].strip(), pos, parts[2].strip()))
    return tuple(rows)


def trait_locus_path(root: Path) -> Path:
    return root / "data" / "trait_locus.tsv"


def sites_with_token(root: Path, token: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for chrom, pos, trait in load_trait_locus_rows(str(trait_locus_path(root))):
        if token not in trait_tokens(trait):
            continue
        key = f"{chrom}:{pos}"
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def sites_in_window(
    root: Path,
    chrom: str,
    start: int,
    end: int,
    *,
    token: str | None = None,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for c, pos, trait in load_trait_locus_rows(str(trait_locus_path(root))):
        if c != chrom or pos < start or pos > end:
            continue
        if token is not None and token not in trait_tokens(trait):
            continue
        key = f"{c}:{pos}"
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def n_called(site_map: dict[str, int], sites: list[str]) -> tuple[int, int]:
    n = 0
    for s in sites:
        if int(site_map.get(s, -1)) >= 0:
            n += 1
    return n, len(sites)
