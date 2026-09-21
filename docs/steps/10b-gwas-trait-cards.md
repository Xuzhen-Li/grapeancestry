# Step 10b — GWAS trait cards

## Goal

Present per-trait GWAS results and imbalance warnings on the report / Cloud cards.

## Inputs

- GWAS summaries from 10a
- Query VCF only for GT overlay fields

## Commands

```bash
# Cards assembled on report / Cloud paths:
grapeancestry analyze --sample Ages
grapeancestry chip-report --vcf results/Ages.vcf.gz --out chip.json

# Libraries:
#   src/grapeancestry/breeding/methods_doc.py
#   src/grapeancestry/cloud/mas.py · card.py
#   src/grapeancestry/report/build_report.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Card fields | Top site, N, coverage, Bayes/p summaries as available |
| Imbalance warnings | Binary case/control n when relevant |

## Plots

Sample evidence / MAS cards in HTML or Cloud UI.

## Notes

- **Panel GWAS ≠ customer measured phenotype.**
- Score ≠ phenotype (see also GS Step 11b).
