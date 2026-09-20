"""Catalog OIV / VIVC for a panel ID (self or clone hit)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

KEY_TRAITS = ("OIV 151", "OIV 225", "OIV 236", "OIV 241")
SOURCE_RANK = {"euvitis": 0, "descep": 1}

# Compact labels from data/oiv_traits.tsv (eu-vitis notations).
OIV_LABEL = {
    "OIV 151": {
        1.0: "male (no gynoecium)",
        2.0: "male (reduced gynoecium)",
        3.0: "hermaphrodite",
        4.0: "female",
        5.0: "female (score 5)",
    },
    "OIV 225": {
        1.0: "green-yellow",
        2.0: "rose",
        3.0: "red",
        4.0: "grey",
        5.0: "dark red violet",
        6.0: "blue-black",
        7.0: "blue-black (score 7)",
    },
    "OIV 236": {
        1.0: "none",
        2.0: "muscat",
        3.0: "foxy",
        4.0: "herbaceous",
        5.0: "other",
    },
    "OIV 241": {
        1.0: "seedless",
        2.0: "rudimentary seeds",
        3.0: "complete seeds",
    },
}


def _f(v: str) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


@lru_cache(maxsize=8)
def _pheno_index(path: str) -> dict[str, dict[str, tuple[float, str, str]]]:
    """id → trait → (value, source, raw); euvitis wins over descep."""
    p = Path(path)
    out: dict[str, dict[str, tuple[float, str, str]]] = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as fh:
        header = fh.readline()
        if not header:
            return out
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            sid, trait, value, source = parts[0], parts[1], parts[2], parts[3]
            if trait not in KEY_TRAITS:
                continue
            val = _f(value)
            if val is None:
                continue
            raw = parts[5] if len(parts) > 5 else value
            prev = out.setdefault(sid, {}).get(trait)
            rank = SOURCE_RANK.get(source, 9)
            if prev is None or rank < SOURCE_RANK.get(prev[1], 9):
                out[sid][trait] = (val, source, raw)
    return out


@lru_cache(maxsize=8)
def _annot_index(path: str) -> dict[str, dict[str, str]]:
    p = Path(path)
    out: dict[str, dict[str, str]] = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if not parts or not parts[0]:
                continue
            row = {header[i]: (parts[i] if i < len(parts) else "") for i in range(len(header))}
            out[parts[0]] = row
    return out


def phenotype_path(root: Path) -> Path:
    return root / "data" / "phenotype.tsv"


def annot_path(root: Path) -> Path:
    return root / "data" / "panel" / "sample_annot.tsv"


def oiv_value_for(sample_id: str, trait: str, root: Path) -> float | None:
    rec = _pheno_index(str(phenotype_path(root))).get(sample_id, {}).get(trait)
    return None if rec is None else rec[0]


def _trait_rows(sample_id: str, root: Path) -> list[dict]:
    recs = _pheno_index(str(phenotype_path(root))).get(sample_id, {})
    rows = []
    for trait in KEY_TRAITS:
        if trait not in recs:
            continue
        val, source, raw = recs[trait]
        rows.append(
            {
                "trait": trait,
                "value": val,
                "source": source,
                "raw": raw,
                "label": OIV_LABEL.get(trait, {}).get(float(val)),
            }
        )
    return rows


def _annot_snip(sample_id: str, root: Path) -> dict:
    row = _annot_index(str(annot_path(root))).get(sample_id) or {}
    from grapeancestry.identity.catalog import catalog_row

    passp = catalog_row(sample_id, root)
    out = {}
    keys = (
        "vivc_number",
        "vivc_prime_name",
        "vivc_utilization",
        "vivc_flower_sex",
        "vivc_muscat",
        "berry_skin_color_text",
        "source",
    )
    for k in keys:
        if row.get(k, ""):
            out[k] = row[k]
    # Passport fills VIVC / name / sex / clones for all 2449, not only 436 OIV IDs.
    if passp.get("VIVC") and "vivc_number" not in out:
        out["vivc_number"] = passp["VIVC"]
    if passp.get("VIVC_Prime_Name") and "vivc_prime_name" not in out:
        out["vivc_prime_name"] = passp["VIVC_Prime_Name"]
    if passp.get("Accession_Name"):
        out["accession_name"] = passp["Accession_Name"]
    if passp.get("VIVC_url"):
        out["vivc_url"] = passp["VIVC_url"]
    if passp.get("Origin"):
        out["origin"] = passp["Origin"]
    if passp.get("Flower_Sex") and "vivc_flower_sex" not in out:
        out["vivc_flower_sex"] = passp["Flower_Sex"]
    if passp.get("Muscat_Taste") and "vivc_muscat" not in out:
        out["vivc_muscat"] = passp["Muscat_Taste"]
    if passp.get("clone_of"):
        out["clone_of"] = passp["clone_of"]
    if passp.get("PO_partners"):
        out["po_partners"] = passp["PO_partners"]
    if passp.get("GEO"):
        out["geo"] = passp["GEO"]
    if passp.get("Grp"):
        out["grp"] = passp["Grp"]
    if passp.get("VIVC") or passp.get("VIVC_Prime_Name") or passp.get("Accession_Name"):
        out["eurisco"] = ""
        out["eurisco_note"] = "No EURISCO accession in Dong passport; VIVC is filled."
    return {k: v for k, v in out.items() if v or k == "eurisco_note"}


def record_for(sample_id: str, root: Path) -> dict | None:
    traits = _trait_rows(sample_id, root)
    annot = _annot_snip(sample_id, root)
    if not traits and not annot:
        return None
    return {"id": sample_id, "oiv": traits, "annot": annot}


def catalog_for_report(
    sample: str,
    *,
    clone_flag: bool,
    identity_top: list[dict],
    root: Path,
) -> dict:
    own = record_for(sample, root)
    if own:
        return {"ok": True, "via": "self", "borrowed_from": sample, **own}
    # Passport-only IDs (no OIV row) still get VIVC / clone_of.
    from grapeancestry.identity.catalog import catalog_row

    passp = catalog_row(sample, root)
    if passp.get("VIVC") or passp.get("VIVC_Prime_Name") or passp.get("Accession_Name"):
        annot = _annot_snip(sample_id=sample, root=root)
        if annot:
            return {
                "ok": True,
                "via": "passport",
                "borrowed_from": sample,
                "id": sample,
                "oiv": [],
                "annot": annot,
            }
    if clone_flag and identity_top:
        rid = identity_top[0].get("ref_id")
        if rid:
            rec = record_for(str(rid), root)
            if rec:
                return {
                    "ok": True,
                    "via": "clone",
                    "borrowed_from": str(rid),
                    "note": "OIV/VIVC of the Identical panel hit, not a new phenotyping.",
                    **rec,
                }
    return {
        "ok": False,
        "via": None,
        "reason": "ID not in phenotype.tsv / sample_annot.tsv and no clone-level hit.",
    }
