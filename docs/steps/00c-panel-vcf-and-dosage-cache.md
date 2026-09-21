# Step 00c — Panel VCF and dosage cache

## Goal

Build the analysis matrix: panel genotypes at chip sites as a dosage cache (preferred over merging huge VCFs every run).

## Inputs

- Panel VCF at chip sites (GT)
- Sample order matching metadata from Step 00a

## Commands

```bash
# Primary build (module entry — not a grapeancestry subcommand):
python -m grapeancestry.core.dosage \
  --panel-vcf data/panel/panel167k_2449.vcf.gz \
  --out-npz results/cache/panel_dosage_167k.npz --full

# Library: src/grapeancestry/core/dosage.py
# Optional 2449+query VCF artifact only (not the analysis matrix):
#   src/grapeancestry/core/merge_ref.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/cache/panel_dosage_*.npz` | **Primary analysis matrix** for IBS/PCA/ADMIX/GS |
| Optional merged VCF | Convenience 2449+query file — not the analysis matrix |

## Plots

None at build time.

## Notes

- Prefer `panel_dosage_167k.npz`; smoke tests may fall back to a smaller cache.
- Downstream identity / project / GS all resolve the cache via `src/grapeancestry/core/dosage.py` (`resolve_cache`).
