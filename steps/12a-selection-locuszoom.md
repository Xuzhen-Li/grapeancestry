# Step 12a — Selection LocusZoom (panel Fst windows)

## Goal

Interactive regional view of among-Grp Fst / selection windows (panel context).

## Inputs

- `results/selection/locuszoom.json` (from `grapeancestry selection` / selscan)
- Query GT only as overlay counts

## Commands

```bash
grapeancestry selection --half-bp 50000 --top 40
grapeancestry analyze --sample Ages

# Interactive embed:
#   src/grapeancestry/report/interactive_dashboard.py
#   selection locuszoom.json payload
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Window site metrics | Among-all-Grps panel regional context |
| Query GT counts in window | Overlay only |

## Plots

LocusZoom scatter + gene track + GT legend (Selection door).

## Notes

- Selection LocusZoom is **among-all-Grps panel regional context only**.
- Sweep rows still point at exact Manhattan points (09a/09b), not arbitrary LZ windows.
