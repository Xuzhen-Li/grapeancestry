# Step 10a — Panel GWAS scan

## Goal

Run association on panel dosages × phenotypes (panel results, not customer phenotypes).

## Inputs

- `data/phenotype.tsv` with ≥50 IDs overlapping the panel (per trait)
- Panel dosage cache
- Trait selection flags (`--curated`, `--trait`, `--all-traits`, …)

## Commands

```bash
grapeancestry gwas \
  --pheno data/phenotype.tsv \
  --cache results/cache/panel_dosage_167k.npz \
  --curated \
  --pcs 3 --maf 0.05 --min-n 50

# Library: src/grapeancestry/breeding/gwas.py · mixed_model.py
# CLI: src/grapeancestry/cli.py → gwas
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/gwas/**` | Summaries, lead sites, p/β/r², case/control n |
| Per-trait tables | Panel association statistics |

## Plots

Feeds 10b cards and Step 12b GWAS LocusZoom.

## Notes

- GWAS p/β/r² are **panel** results. Query GT overlay and GS scores are not observed phenotypes.
- Binary traits: surface case/control imbalance (EMMAX caveat).
