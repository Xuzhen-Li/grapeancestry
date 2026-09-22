# Step 08b — f-statistic report panels

## Goal

Surface highest shared drift / largest |Z| summaries in the UI.

## Inputs

- f3/f4 contrast tables from 08a (report payload)

## Commands

```bash
# Report path only (same as 08a):
grapeancestry analyze --sample Ages

# Libraries:
#   src/grapeancestry/popgen/fstats_report.py
#   src/grapeancestry/report/interactive_dashboard.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Summary strings in payload | Highest shared drift / |Z| highlights |
| Optional `results/{sample}.fstats.png` | Static card when written |

## Plots

Outgroup-f3 / pairwise f4 panels in the interactive HTML.

## Notes

- Exploratory only — not ADMIXTOOLS qp graphs.
- No dedicated f-stats CLI; panels are assembled by the report builder.
