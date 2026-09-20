# Step 03b — IBS and kinship ranks

## Goal

Rank reference samples by IBS and KING-related metrics.

## Scripts

`identity/ibs.py`, `run_ibs.py`

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.ibs.tsv` | Top IBS neighbours |
| `results/{sample}.kinship_top.tsv` | Top kinship ranks |
| Summary TSVs | Counts / nearest non-self |

## Visualization outputs

Side-by-side IBS top / Kinship top tables in the report.
