# Step 02b — Calling rates and method coverage

## Goal

Separate panel vs VCF calling rates and declare which downstream methods are available.

## Scripts

`core/qc.py` + report provenance in `report/build_report.py`

## Statistical / file outputs

| Metric | Meaning |
|--------|---------|
| Panel calling rate | called ÷ all chip sites |
| VCF-site calling rate | called ÷ sites in this VCF |
| Method coverage rows | PCA/selection/GWAS/damage/GS available vs unavailable |

## Visualization outputs

Method-coverage table in Sample validity; conclusions bullets.
