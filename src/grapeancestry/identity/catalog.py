"""VIVC / 2449.info / Dong passport join (EURISCO IDs are not in this repo)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

VIVC_VIEW = "https://www.vivc.de/index.php?r=passport%2Fview&id={id}"
_DIGITS = re.compile(r"(\d+)")


def load_info(info_tsv: Path) -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    if not info_tsv.exists():
        return meta
    with info_tsv.open(encoding="utf-8") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            row = dict(zip(hdr, line.rstrip("\n").split("\t")))
            sid = row.get("ID", "")
            if sid:
                meta[sid] = row
    return meta


def vivc_url(vivc_number: str) -> str:
    m = _DIGITS.search(vivc_number or "")
    if not m:
        return ""
    return VIVC_VIEW.format(id=m.group(1))


@lru_cache(maxsize=8)
def load_passport(path: str) -> dict[str, dict[str, str]]:
    """Dong 2449 passport (`dong_passport.tsv`). Skip `#` comment lines."""
    p = Path(path)
    out: dict[str, dict[str, str]] = {}
    if not p.exists():
        return out
    header: list[str] | None = None
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if header is None:
                header = parts
                continue
            row = {header[i]: (parts[i] if i < len(parts) else "") for i in range(len(header))}
            sid = (row.get("ID") or "").strip()
            if sid:
                out[sid] = row
    return out


def passport_path(root: Path) -> Path:
    return root / "data" / "panel" / "dong_passport.tsv"


def record(
    sample_id: str,
    *,
    info: dict[str, dict[str, str]] | None = None,
    passport: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """Merge 2449.info + passport. VIVC comes from passport, not 2449.info."""
    info_row = (info or {}).get(sample_id, {})
    pass_row = (passport or {}).get(sample_id, {})
    vivc = (pass_row.get("VIVC_Number") or info_row.get("VIVC") or "").strip()
    return {
        "ID": sample_id,
        "CON": info_row.get("CON", ""),
        "GEO": info_row.get("GEO", ""),
        "Uti": info_row.get("Uti", ""),
        "Grp": info_row.get("Grp", ""),
        "Accession_Name": pass_row.get("Accession_Name", ""),
        "VIVC_Prime_Name": pass_row.get("VIVC_Prime_Name", ""),
        "VIVC": vivc,
        "VIVC_url": vivc_url(vivc),
        "Origin": pass_row.get("Origin", ""),
        "Flower_Sex": pass_row.get("Flower_Sex", ""),
        "Muscat_Taste": pass_row.get("Muscat_Taste", ""),
        "Genetic_Background": pass_row.get("Genetic_Background", ""),
        "clone_of": pass_row.get("clone_of", ""),
        "PO_partners": pass_row.get("PO_partners", ""),
        "has_PO": pass_row.get("has_PO", ""),
        "Comments": pass_row.get("Comments", ""),
        "EURISCO": "",
        "note": (
            "VIVC from Dong 2449 passport. "
            "EURISCO accession numbers are not in this table."
        ),
    }


def crossref(sample_id: str, info: dict[str, dict[str, str]]) -> dict[str, str]:
    """Backward-compatible: info only (tests). Prefer ``record`` with passport."""
    return record(sample_id, info=info, passport=None)


def catalog_row(sample_id: str, root: Path) -> dict[str, str]:
    info = load_info(root / "data" / "panel" / "2449.info")
    passp = load_passport(str(passport_path(root)))
    return record(sample_id, info=info, passport=passp)
