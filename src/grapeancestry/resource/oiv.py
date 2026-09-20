"""OIV descriptor lookup from ``data/oiv_traits.tsv``."""

from __future__ import annotations

import csv
import re
from pathlib import Path

# Dong et al. 2023 Science add8655: sex is SDR haplotype, not a GS score.
# Same claim as grapeancestry.cloud.mas.MAS_LOCI SDR row.
_SDR_DESCRIPTOR = "SDR haplotype tag (flower sex; Dong 2023 / OIV 151)"
_OIV_NUM = re.compile(r"OIV[\s_]+(\d+(?:-\d+)?)", re.I)


def _clean_desc(text: str) -> str:
    d = text.replace("\xa0", " ").strip()
    if d.lower() in {"", "nan", "none", "na"}:
        return ""
    return d


def _norm_key(code: str) -> str:
    return " ".join(code.strip().replace("_", " ").split())


def _variants(code: str) -> list[str]:
    """OIV_203m / OIV 221Lm / OIV 225_bin → try exact then strip suffixes."""
    raw = code.strip()
    spaced = _norm_key(raw)
    out: list[str] = []

    def add(item: str) -> None:
        item = item.strip()
        if not item or item in out:
            return
        out.append(item)
        alt = item.replace(" ", "_") if " " in item else item.replace("_", " ")
        if alt not in out:
            out.append(alt)

    add(raw)
    add(spaced)
    m = re.search(r"(OIV)[\s_]+(\d+)", spaced, re.I)
    if m:
        add(f"OIV {m.group(2)}")
    t = spaced
    low = t.lower()
    if low.endswith("_bin") or low.endswith(" bin"):
        add(_norm_key(t[: -4]))
        t = _norm_key(t[: -4])
    while t and t[-1] in "mLWlw" and not t[-1].isdigit():
        t = t[:-1].rstrip()
        add(t)
    return out


def load_oiv_table(path: Path) -> dict[str, dict[str, str]]:
    """Key by both ``OIV 225`` and ``OIV_225``."""
    table: dict[str, dict[str, str]] = {}
    if not path.exists():
        return table
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            code = (row.get("code") or "").strip()
            if not code:
                continue
            rec = {
                "code": code,
                "descriptor": _clean_desc(row.get("descriptor") or ""),
                "notations": (row.get("notations") or "").strip(),
                "trait_type": (row.get("trait_type") or "").strip(),
                "source_sheet": (row.get("source_sheet") or "").strip(),
            }
            for key in _variants(code):
                prev = table.get(key)
                if prev is None or (not prev.get("descriptor") and rec["descriptor"]):
                    table[key] = rec
    return table


def oiv_number(code: str) -> str:
    """``OIV_225`` / ``OIV 236 muscat`` / ``sdr`` → PDF id ``225`` / ``151``.

    eu-vitis sheets use 3-digit zero padding (``OIV 001.pdf``, ``OIV 015-1.pdf``).
    http://www.eu-vitis.de/docs/descriptors/oivdesc/
    """
    raw = (code or "").strip()
    if raw.lower() == "sdr":
        return "151"
    m = _OIV_NUM.search(raw)
    if not m:
        return ""
    num = m.group(1)
    if "-" in num:
        left, right = num.split("-", 1)
        return f"{left.zfill(3)}-{right}"
    return num.zfill(3) if num.isdigit() else ""


def describe_trait(code: str, table: dict[str, dict[str, str]]) -> str:
    """Join comma-separated trait_locus codes to OIV descriptors.

    Unknown codes stay empty (no invented names). ``sdr`` uses the Dong 2023
    SDR tag wording from mas.py, not oiv_traits.tsv.
    """
    parts = [p.strip() for p in code.replace(";", ",").split(",") if p.strip()]
    labels: list[str] = []
    for part in parts:
        if part.lower() == "sdr":
            labels.append(_SDR_DESCRIPTOR)
            continue
        desc = ""
        for key in _variants(part):
            rec = table.get(key)
            if rec and rec.get("descriptor"):
                desc = rec["descriptor"]
                break
        if desc:
            labels.append(desc)
    return " · ".join(labels)
