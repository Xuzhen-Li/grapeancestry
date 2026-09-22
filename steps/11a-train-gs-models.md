# Step 11a — Train GS models

## Goal

Train panel genomic-selection models and record CV metrics / provenance.

## Inputs

- `data/phenotype.tsv` (Step 00f)
- Panel dosage cache
- Trait filters (`--curated`, `--trait`, …)

## Commands

```bash
grapeancestry gs-train \
  --pheno data/phenotype.tsv \
  --cache results/cache/panel_dosage_167k.npz \
  --curated \
  --min-n 50 --k-folds 3

# Libraries: src/grapeancestry/breeding/gs.py · gs_models.py · provenance.py
# CLI: src/grapeancestry/cli.py → gs-train
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/gs/index.tsv` | CV r, best model name per trait |
| Training provenance JSON | Reproducibility metadata |

## Plots

None required (tables / index).

## Notes

- Grapevine decision-grade example: **OIV 225** colour (`cv_r≈0.62`, `best_model=topk_ridge` in local index).
- OIV 241 and other traits may be exploratory only — declare in `CLAIMS.md`.
