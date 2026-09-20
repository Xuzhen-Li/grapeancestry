# Step 00d — Freeze PCA axes

## Goal

Compute **once** the panel PCA / GRM axes that every customer query will project onto.

## Scripts / entrypoints

| Role | Path |
|------|------|
| Lock / cache | `src/grapeancestry/adna/pca_lock.py`, `project.py` |
| Binary | `bin/gcta64` |
| Historical alt | `adna/smartpca_project.py` (not default shipped label) |

## Inputs

- Panel dosage at the sites used for PCA (example: `panel167k_nogwas`)  
- Sample keep list  

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Frozen axis / SVD cache under `results/cache/` | Reused by Step 04b |
| Eigenvalue fractions | Stored for plot axis labels |

## Visualization outputs

Optional lab QC scatter of panel-only PCA (not customer hand-in).

## Contract

Never unsupervised-refit PCA on panel+N customers per night.
