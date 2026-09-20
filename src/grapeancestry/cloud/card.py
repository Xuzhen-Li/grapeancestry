"""Trait-locus card: colour / muscat SNPs, seedless design coverage, our named windows.

Coverage of frozen windows is **not** a new XP-CLR / iHS scan.
Dong et al. 2023 *Science* Table S29 is a dual check, not this named list.
"""

from __future__ import annotations

from pathlib import Path

from grapeancestry.cloud.loci import n_called, sites_in_window, sites_with_token
from grapeancestry.cloud.mas import MAS_LOCI

# Dong 2023 VvDXS Chr5:19,419,686 — nearest panel site (783 bp).
MUSCAT_SITE = "5:19418903"
MYBA_SITE = "2:5116947"
MYBA_PAD = 10_000
SDR_START, SDR_END = 14_165_010, 14_345_273


def _mas_by_trait(site_map: dict[str, int], trait_substr: str) -> list[dict]:
    out = []
    for loc in MAS_LOCI:
        if trait_substr not in loc["trait"]:
            continue
        dose = int(site_map.get(loc["site"], -1))
        out.append({**loc, "dosage": dose, "called": dose >= 0})
    return out


def _muscat_row(site_map: dict[str, int]) -> dict:
    dose = int(site_map.get(MUSCAT_SITE, -1))
    return {
        "site": MUSCAT_SITE,
        "gene": "VvDXS proxy",
        "trait": "OIV 236 muscat",
        "dosage": dose,
        "called": dose >= 0,
        "note": (
            "Nearest panel site to Dong 2023 VvDXS Chr5:19,419,686 "
            f"(offset {19_419_686 - 19_418_903} bp). Not the exact Science SNP."
        ),
    }


def _seedless(site_map: dict[str, int], root: Path) -> dict:
    sites = sites_with_token(root, "OIV_241")
    n_ok, n_tot = n_called(site_map, sites)
    chr18 = [s for s in sites if s.startswith("18:")]
    n18, _ = n_called(site_map, chr18)
    return {
        "n_design": n_tot,
        "n_called": n_ok,
        "n_chr18_design": len(chr18),
        "n_chr18_called": n18,
        "coverage": None if n_tot == 0 else round(n_ok / n_tot, 4),
        "note": (
            "Italian design tags (trait_locus OIV_241), not a validated AGL11 hit. "
            "Panel GWAS on n_seedless=10 did not recover chr18 AGL11. Coverage only."
        ),
    }


def _sweep_row(
    name: str,
    chrom: str,
    start: int,
    end: int,
    site_map: dict[str, int],
    sites: list[str],
    note: str,
) -> dict:
    n_ok, n_tot = n_called(site_map, sites)
    return {
        "name": name,
        "window": f"{chrom}:{start}-{end}",
        "n_sites": n_tot,
        "n_called": n_ok,
        "coverage": None if n_tot == 0 else round(n_ok / n_tot, 4),
        "kind": "named_locus_coverage",
        "note": note,
    }


def trait_card(site_map: dict[str, int], root: Path) -> dict:
    from grapeancestry.cloud.sites import load_panel_sites
    from grapeancestry.popgen.selscan import WINDOWS_REL, load_named_windows, load_scan_tables

    panel_sites = load_panel_sites(root)
    windows = load_named_windows(root / WINDOWS_REL)
    scores = {r.get("name"): r for r in (load_scan_tables(root / "results" / "selection") or {}).get("named") or []}
    sweeps = []
    for w in windows:
        sites = [
            s
            for s in panel_sites
            if s.startswith(w["chrom"] + ":")
            and s.partition(":")[2].isdigit()
            and w["start"] <= int(s.partition(":")[2]) <= w["end"]
        ]
        row = _sweep_row(
            w["name"],
            w["chrom"],
            w["start"],
            w["end"],
            site_map,
            sites,
            w.get("source") or "named VS-1 window",
        )
        sc = scores.get(w["name"]) or {}
        if sc.get("mean_het"):
            row["panel_mean_het"] = sc.get("mean_het")
        if sc.get("mean_fst"):
            row["panel_mean_fst"] = sc.get("mean_fst")
        sweeps.append(row)
    if not sweeps:
        sdr_sites = sites_with_token(root, "sdr")
        myba_sites = sites_in_window(
            root, "2", 5_116_947 - MYBA_PAD, 5_116_947 + MYBA_PAD, token="OIV_225"
        )
        if MYBA_SITE not in myba_sites:
            myba_sites = [MYBA_SITE, *myba_sites]
        sweeps = [
            _sweep_row(
                "SDR",
                "2",
                SDR_START,
                SDR_END,
                site_map,
                sdr_sites,
                "trait_locus token sdr.",
            ),
            _sweep_row(
                "VvMybA",
                "2",
                5_116_947 - MYBA_PAD,
                5_116_947 + MYBA_PAD,
                site_map,
                myba_sites,
                "±10 kb of panel tag 2:5116947 (Dong 2023 Chr2:5116947). "
                "Not a published FST interval.",
            ),
        ]
    return {
        "colour": _mas_by_trait(site_map, "colour"),
        "muscat": _muscat_row(site_map),
        "seedless": _seedless(site_map, root),
        "sweeps": sweeps,
        "omitted": (
            "Named windows = our MAS/GWAS loci (SDR, VvMybA, colour, VvDXS). "
            "Dong 2023 Science Table S29 is a dual check "
            "(results/selection/vs_science_s29.tsv), not this list. "
            "doi:10.1126/science.add8655"
        ),
    }
