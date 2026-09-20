# Step 00f — Phenotype and trait tables

## Goal

Stage phenotypes and trait dictionaries for panel GWAS/GS (not required for ancestry-only doors).

## Scripts / entrypoints

| Role | Path |
|------|------|
| ETL | `scripts/build_phenotype.py`, `src/grapeancestry/breeding/phenotype.py` |
| OIV / trait locus | `resource/oiv.py`, `data/trait_locus.tsv` (local) |
| Template | `data/phenotype_template.tsv` |

## Inputs

- Long-table phenotypes joined to panel IDs  
- Trait scale rules (ordinal/binary)  

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `data/phenotype.tsv` | Training input; trait needs enough overlapping IDs (suite rule of thumb ≥50) |
| Trait dictionary TSVs | Binary rules, labels |

## Visualization outputs

None at prep; used later in Steps 10–11 cards.

## Claim note

Declare which traits will be decision-grade in profile `CLAIMS.md` before training.
