# Step 09a — Panel Fst / sweep scan

## Goal

Grp-vs-rest Fst and heterozygosity extremes on the **2449 panel only** (unphased).

## Inputs

- Panel dosage + Grp labels
- Optional half-window bp / top-N for named windows

## Commands

```bash
grapeancestry selection --half-bp 50000 --top 40

# Libraries:
#   src/grapeancestry/cli.py → selection
#   src/grapeancestry/popgen/selscan.py
#   src/grapeancestry/adna/selection.py · popgen/stats.py · popgen/selection_report.py

# Also wired into grapeancestry analyze / run when selection assets exist
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/selection/named_windows.tsv` | Named window het/Fst |
| `results/selection/by_grp_named.tsv` | Per-Grp summaries |
| Sweep rows | Fst ≥ within-Grp 95th **and** windowed het ≤ 5th |
| `results/selection/locuszoom.json` | When present (feeds 12a) |

## Plots

Built in 09b (Manhattan / heat).

## Notes

- Selection is **panel-only**; query GT is an overlay later — not evidence the sample “was selected.”
- `fst_sites()` is a simplified Fst contrast, not canonical Weir–Cockerham unless benchmarked.
- `GEO` is reserved for GEA/origin — not this selection door.
