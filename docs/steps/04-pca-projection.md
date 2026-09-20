# Step 04 — PCA projection (frozen axes)

## Goal

Place the query on **frozen** panel PCA axes (do not refit PCA on panel+customer).

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry project` |
| Project | `src/grapeancestry/adna/project.py`, `run_project.py` |
| Lock / cache | `adna/pca_lock.py` |
| Alt (historical) | `adna/smartpca_project.py` (not the shipped default) |
| Binary | `bin/gcta64` (GCTA64 GRM-PCA for frozen panel axes) |

Shipped method label: **GCTA64 GRM-PCA** on `panel167k_nogwas` (example profile).

## Inputs

- Query VCF  
- Frozen PCA / SVD cache for the panel  
- Panel info for colour-by-Grp (or chosen column)

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.pca.tsv` (when written) | Projected PC coordinates for the query |
| Report header Q/PC fields | PC1/PC2/PC3 shown in chrome |
| Cache under `results/cache/` | Frozen axes reused for all customers |

## Visualization outputs

| Where | What |
|-------|------|
| Report → Population placement → PCA | 2D PC scatter (switchable axes) + 3D view |
| Markers | Query = star/diamond; pinned ref = yellow diamond |

## CLI example

```bash
grapeancestry project --vcf results/Ages.vcf.gz --sample Ages
```

## Other chips

Freeze axes once on *your* panel; project every new sample with the same axes file pointer in the profile.
