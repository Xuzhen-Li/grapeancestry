# Step 09 — Selection / Fst (panel context)

## Goal

Panel-only Grp-vs-rest selection context; query genotypes are an **overlay**, not proof the sample was selected.

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry selection` |
| Logic | `src/grapeancestry/adna/selection.py` |
| Report | `popgen/selection_report.py` |
| Viz | `popgen/selection_viz.py`, `selscan.py` |
| Fst helpers | `popgen/stats.py` (`fst_sites` = simplified contrast unless WC benchmarked) |

## Inputs

- Frozen panel dosages + Grp labels  
- Precomputed selection / manhattan JSON when packed  
- Query VCF for overlay only

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Sweep rows | Fst ≥ within-Grp 95th **and** windowed het ≤ 5th |
| `results/selection/*.json` (panel) | Manhattan / window tables |
| Query GT inside windows | Counts toward method coverage, not selection proof |

## Visualization outputs

| Where | What |
|-------|------|
| Report → Panel research / selection | Manhattan, heat, metric toggles |
| Optional `results/{sample}.selection.png` | Static export |

## Claim note

Selection = **2449 panel context** (example). Query GT ≠ “this sample was selected.”
