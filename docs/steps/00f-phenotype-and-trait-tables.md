# Step 00f — Phenotype and trait tables

## Goal

Stage phenotypes and trait dictionaries for panel GWAS/GS (skip for ancestry-only doors).

## Inputs

- Long-table phenotypes joined to panel IDs
- Trait scale rules (ordinal/binary); OIV / trait locus tables as available

## Commands

```bash
# ETL helpers (no grapeancestry phenotype subcommand):
python scripts/build_phenotype.py --help
# Library: src/grapeancestry/breeding/phenotype.py
# OIV helpers: src/grapeancestry/resource/oiv.py

# Downstream suite CLIs that consume data/phenotype.tsv:
grapeancestry gwas --pheno data/phenotype.tsv --curated
grapeancestry gs-train --pheno data/phenotype.tsv --curated
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `data/phenotype.tsv` | Training input; suite rule of thumb ≥50 overlapping panel IDs per trait |
| Trait dictionary / template TSVs | Binary rules, labels (`data/phenotype_template.tsv`) |

## Plots

None at prep; used later in Steps 10–11 cards.

## Notes

- Declare which traits are **decision-grade** in profile `CLAIMS.md` before treating scores as rankable.
- Grapevine example: only **OIV 225** colour GS is decision-grade; other traits may be exploratory.
- Uti (WINE/TABLE) is not used as a breeding trait.
