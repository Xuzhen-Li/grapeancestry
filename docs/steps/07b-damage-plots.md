# Step 07b — Damage and fragment-length plots

## Goal

Display terminal C→T / G→A curves and insert-size / fragment-length histogram.

## Inputs

- Damage TSV / mapDamage outputs from 07a
- Report builder context for the sample

## Commands

```bash
# Embedded by analyze / run report builders (no separate plot CLI):
grapeancestry analyze --sample Ages --source-sample Ages

# Plot helpers:
#   src/grapeancestry/adna/damage_lite.py
#   src/grapeancestry/report/build_report.py · interactive_dashboard.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Pos1 misincorporation rates | Figure caption / metadata |
| Damage panel payload | Curves + histogram for HTML |

## Plots

Sample validity → Damage panel (two curves + histogram).

## Notes

- aDNA-specific visualization; PE modern runs leave this door unavailable rather than fabricating curves.
