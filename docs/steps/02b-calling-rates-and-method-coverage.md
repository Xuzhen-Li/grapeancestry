# Step 02b — Calling rates and method coverage

## Goal

Separate panel vs VCF calling rates and declare which downstream methods are available vs unavailable.

## Inputs

- QC / VCF products from Steps 01b–02a
- Profile site count (`panel_n_sites`) and presence of frozen assets (PCA, ADMIXTURE, phenotypes)

## Commands

```bash
# Calling-rate fields come from grapeancestry qc / analyze:
grapeancestry qc --bam results/bam/Ages.markdup.bam --vcf results/Ages.vcf.gz --sample Ages
grapeancestry analyze --sample Ages

# Method-coverage rows assembled in report builder:
#   src/grapeancestry/core/qc.py
#   src/grapeancestry/report/build_report.py
```

## Outputs

| Metric | Meaning |
|--------|---------|
| Panel calling rate | called ÷ all chip sites |
| VCF-site calling rate | called ÷ sites present in this VCF |
| Method coverage rows | PCA / selection / GWAS / damage / GS → available vs unavailable |

## Plots

Method-coverage table in Sample validity; conclusions bullets in the HTML.

## Notes

- Unavailable methods must be labeled unavailable — do not invent placeholder statistics.
