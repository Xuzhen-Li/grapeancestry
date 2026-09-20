# Step 02a — Capture QC metrics

## Goal

Compute on-target, depth, and breadth statistics for the query library.

## Scripts

`src/grapeancestry/core/qc.py` · `grapeancestry qc`

## Inputs

Markdup BAM + sites BED + optional VCF

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.qc.tsv` | On-target %, fold enrichment, breadth ≥1×/5×/10×, mean/median depth, read counts |

## Visualization outputs

Report Sample validity **QC cards** and metrics table.
