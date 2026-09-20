# Step 07 — aDNA damage profile

## Goal

For ancient SE libraries, quantify terminal misincorporation and fragment-length distribution.

## Scripts / entrypoints

| Role | Path |
|------|------|
| mapDamage2 runner + lite fallback | `src/grapeancestry/adna/damage_lite.py` |
| Trigger | `grapeancestry run` aDNA path · `_post_analyze` |

## Inputs

- Markdup BAM for the **source** sample  
- mapDamage2 available, else lite profile

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.damage.tsv` | Summary damage metrics (e.g. 5′ C→T, 3′ G→A at pos1) |
| `results/{sample}.mapDamage/` | Full mapDamage directory when run |

Modern PE demos typically mark damage **unavailable**.

## Visualization outputs

| Where | What |
|-------|------|
| Report → Sample validity → Damage | Dual misincorporation curves + fragment-length histogram |

## Other chips

Keep the step optional: only meaningful for degraded aDNA-style libraries.
