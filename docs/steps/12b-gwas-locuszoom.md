# Step 12b — GWAS LocusZoom (trait leads)

## Goal

LocusZoom for panel GWAS leads (e.g. OIV 225 region) with query GT overlay.

## Inputs

- `results/gwas/**/locuszoom.json` (or equivalent per-trait payload)
- Query VCF for genotype strip

## Commands

```bash
grapeancestry gwas --pheno data/phenotype.tsv --curated
grapeancestry analyze --sample Ages

# Interactive:
#   src/grapeancestry/report/interactive_dashboard.py
#   GWAS locuszoom payloads under results/gwas/
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Lead SNP GT for this sample | Overlay strip |
| Site table with p/β | Panel association context |

## Plots

GWAS LocusZoom + genotype overlay bars/table.

## Notes

- Strip colour = **genotype**, not LD.
- Panel association ≠ observed customer phenotype; GS score ≠ phenotype.
