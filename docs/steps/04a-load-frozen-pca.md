# Step 04a — Load frozen PCA axes

## Goal

Resolve the frozen GCTA / `pca_lock` axis cache built in Step 00d (no refit).

## Inputs

- Lab GCTA freeze artifacts under `results/cache/` (eigenvec/eigenval)
- Panel dosage cache for site alignment
- Root layout expected by `pca_lock`

## Commands

**No dedicated freeze-load CLI.** Loading is library-only:

```bash
# Used internally by grapeancestry project / analyze:
#   src/grapeancestry/adna/pca_lock.py → load_gcta_freeze() / locked_pca_for_sample()
#   src/grapeancestry/core/dosage.py → resolve_cache()

# Customer projection CLI is Step 04b:
grapeancestry project --vcf results/Ages.vcf.gz --sample Ages
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| In-memory `GctaFreeze` | Axis files + eigenvalue fractions ready for projection |
| Lock stamp | Confirms frozen axes (not per-customer refit) |

## Plots

None until 04b.

## Notes

- If the freeze is missing, projection cannot invent new panel axes — stage Step 00d first.
- Axes stay frozen; only the query is least-squares projected.
