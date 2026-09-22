# Step 06b — Layout NJ tree

## Goal

Produce circular/rectangular NJ tree layout and interactive tips for the report.

## Inputs

- IBS distances from 06a
- Tip IDs (query + subsampled panel)

## Commands

**No dedicated NJ CLI** — layout is report-path only:

```bash
grapeancestry analyze --sample Ages
grapeancestry run --sample Ages

# Libraries:
#   src/grapeancestry/popgen/tree_nj.py
#     build_nj_tree · tip_xy_circular · tip_xy_rectangular · to_newick
# Interactive payload: src/grapeancestry/report/interactive_data.py · interactive_dashboard.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Tip order / coordinates | Embedded in report payload |
| Optional `results/{sample}.nj_tree.png` | Static card when written |

## Plots

Report NJ Tree (circular default) with query marker.

## Notes

- No standalone `grapeancestry` tree command; do not invent one in DIY docs.
