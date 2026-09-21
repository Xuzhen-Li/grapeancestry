# Step 07a — Run mapDamage (or lite)

## Goal

Estimate aDNA damage profile from the source BAM (aDNA door).

## Inputs

- Source markdup BAM (`--source-sample` lineage when report id is `*_query`)
- Reference fasta
- Sample type `adna` in samples YAML

## Commands

```bash
# Preferred: full aDNA run (damage after markdup):
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_ages.yaml --sample Ages -j 4

grapeancestry analyze --sample Ages --source-sample Ages

# Library / fallback (no dedicated grapeancestry damage CLI):
#   src/grapeancestry/adna/damage_lite.py  (mapDamage2 wrapper + lite fallback)
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.damage.tsv` | Terminal misincorporation summary |
| `results/{sample}.mapDamage/` | mapDamage2 directory when binary succeeds |

## Plots

Produced in 07b.

## Notes

- Modern PE libraries typically mark damage unavailable in method coverage.
- Keep `--source-sample` when analyzing a renamed `*_query` VCF so BAM lineage stays correct.
