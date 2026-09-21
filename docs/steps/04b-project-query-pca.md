# Step 04b — Project query onto PCA

## Goal

Least-squares (GCTA-consistent) projection of the query onto the **frozen** 2449 axes.

## Inputs

- Query VCF at panel sites
- Frozen axes from 04a / 00d
- Optional `data/panel/2449.info` for colour column

## Commands

```bash
grapeancestry project \
  --vcf results/Ages.vcf.gz \
  --sample Ages \
  --info data/panel/2449.info \
  --out-tsv results/Ages.pca.tsv

# Full report path also projects:
grapeancestry analyze --sample Ages --pca-color Grp

# Libraries: src/grapeancestry/adna/project.py · pca_lock.py
# CLI entry: src/grapeancestry/cli.py → project
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Query PC1/PC2/PC3 | Header print + `results/{sample}.pca.tsv` when written |
| Panel reference coords | From freeze (not refit) |

## Plots

Interactive 2D/3D PCA (query star; pin yellow diamond) in sample-first HTML.

## Notes

- Method metadata: `GCTA64 GRM-PCA (panel167k_nogwas)` — frozen axes + LSQ query projection.
- Do not claim smartPCA as the shipped result.
