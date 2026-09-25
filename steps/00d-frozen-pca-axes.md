# Step 00d — Freeze PCA axes

## Goal

Compute **once** the panel PCA / GRM axes that every customer query will project onto (frozen coordinate system).

## Inputs

- Panel dosage at the sites used for PCA (example family: `panel167k_nogwas`)
- Sample keep list / GCTA inputs produced in the lab archive
- Binary: `gcta64` on PATH

## Commands

**No dedicated `grapeancestry` freeze-fit CLI.** Lab produces GCTA eigenvec/eigenval once; the suite **loads** the freeze:

```bash
# Load path (library only — used by grapeancestry project / analyze):
#   src/grapeancestry/adna/pca_lock.py  → load_gcta_freeze() / locked_pca_for_sample()
#   src/grapeancestry/adna/project.py
# Historical / alternative label only (not default shipped PCA):
#   src/grapeancestry/adna/smartpca_project.py
```

Per-query projection is Step 04b (`grapeancestry project`).

## Outputs

| Artifact | Meaning |
|----------|---------|
| GCTA freeze under `results/cache/` (lab) | Eigenvectors / eigenvalues reused by Step 04 |
| `pca_lock` stamp metadata | Provenance that axes are frozen |

## Plots

Optional lab QC scatter of panel-only PCA (not the customer hand-in).

## Notes

- Shipped method label: GCTA64 GRM-PCA on frozen 2449 axes; queries are least-squares projected — do **not** unsupervised-refit panel+N per night.
- EIGENSOFT smartPCA is historical/alternative documentation only.
