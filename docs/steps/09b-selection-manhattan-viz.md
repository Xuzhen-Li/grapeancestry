# Step 09b — Selection Manhattan and heatmaps

## Goal

Plot panel selection context; overlay query GT only as annotation.

## Inputs

- Selection scan products from 09a
- Optional query VCF for GT overlay in the report

## Commands

```bash
grapeancestry selection --top 40
grapeancestry analyze --sample Ages

# Viz libraries (no separate selection-plot CLI):
#   src/grapeancestry/popgen/selection_viz.py · selscan.py
#   src/grapeancestry/report/interactive_dashboard.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Metric toggles (Fst, …) | Interactive controls |
| Optional `results/{sample}.selection.png` | Static card when written |

## Plots

Manhattan / heat in Panel research section of the HTML.

## Notes

- **Query GT ≠ “this sample was selected.”** Overlay only.
- Sweep rows focus exact Manhattan points, not arbitrary LocusZoom windows.
