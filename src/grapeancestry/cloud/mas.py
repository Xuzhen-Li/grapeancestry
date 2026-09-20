"""Dong et al. 2023 Science add8655 loci that sit on the 167K panel.

Colour / SDR tags sit on the 167K panel; muscat uses the nearest panel site
to Science VvDXS (not the exact coordinate).
Science colour SNPs: Vvsyl02G000229 and Vvsyl02G001064 are *better predictors
of berry skin colors* than VvMybA (Dong 2023 main text). Sex is SDR haplotype,
not a GS score. Muscat VvDXS Chr5:19,419,686 is not this exact panel site.
"""

from __future__ import annotations

# site, gene, trait, science_claim
MAS_LOCI: list[dict[str, str]] = [
    {
        "site": "2:3519247",
        "gene": "Vvsyl02G000229",
        "trait": "OIV 225 colour",
        "note": "Dong 2023; panel tag of acylaminoacyl-peptidase (Science chr2:3,521,538)",
    },
    {
        "site": "2:16051309",
        "gene": "Vvsyl02G001064",
        "trait": "OIV 225 colour",
        "note": "Dong 2023 lysine-specific demethylase (Science chr2:16,051,309)",
    },
    {
        "site": "2:5116947",
        "gene": "VvMybA1",
        "trait": "OIV 225 colour",
        "note": "Dong 2023 Chr2:5116947 G/T (This et al. 2006 / Kobayashi lineage)",
    },
    {
        "site": "2:14277567",
        "gene": "SDR",
        "trait": "OIV 151 flower sex",
        "note": "Panel SDR tag; Science sex = haplotype (H1/H2), not this SNP alone",
    },
    {
        "site": "5:19418903",
        "gene": "VvDXS proxy",
        "trait": "OIV 236 muscat",
        "note": "Nearest panel site to Dong 2023 VvDXS Chr5:19,419,686 (783 bp). Not the exact Science SNP.",
    },
]

MAS_SITES = [r["site"] for r in MAS_LOCI]
