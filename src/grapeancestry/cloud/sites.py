"""167K panel site list from git-tracked admixture assets (no panel VCF)."""

from __future__ import annotations

from pathlib import Path

N_PANEL_SITES = 167_433


def load_panel_sites(root: Path) -> list[str]:
    """Union of ``panel167k_nogwas.sites.txt`` + ``gwas_exclude.tsv``.

    Measured panel is 167,433 sites (MANIFEST). Order is nogwas then GWAS extras.
    """
    admix = root / "data" / "panel" / "admixture"
    nogwas = admix / "panel167k_nogwas.sites.txt"
    exc = admix / "gwas_exclude.tsv"
    sites: list[str] = []
    seen: set[str] = set()
    if nogwas.exists():
        for ln in nogwas.read_text().splitlines():
            s = ln.strip()
            if s and s not in seen:
                seen.add(s)
                sites.append(s)
    if exc.exists():
        for line in exc.read_text().splitlines():
            p = line.strip().split("\t")
            if len(p) < 2 or p[0].lower() in {"chrom", "chr"}:
                continue
            s = f"{p[0]}:{p[1]}"
            if s not in seen:
                seen.add(s)
                sites.append(s)
    return sites
