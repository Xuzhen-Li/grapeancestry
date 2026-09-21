# Step 02a — Capture QC metrics

## Goal

Compute on-target, depth, and breadth statistics for the query library.

## Inputs

- Markdup BAM (`results/bam/{sample}.markdup.bam`)
- Sites BED (default `data/panel/panel167k.sites.bed`)
- Optional query VCF for calling-rate fields

## Commands

```bash
grapeancestry qc \
  --bam results/bam/Ages.markdup.bam \
  --bed data/panel/panel167k.sites.bed \
  --vcf results/Ages.vcf.gz \
  --sample Ages \
  --out-tsv results/Ages.qc.tsv

# Also run inside: grapeancestry run / grapeancestry analyze
# Library: src/grapeancestry/core/qc.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.qc.tsv` | On-target %, fold enrichment, breadth ≥1×/5×/10×, mean/median depth, read counts |

## Plots

Report Sample validity **QC cards** and metrics table (Step 13b).

## Notes

- No universal pass/fail threshold is invented; QC stays method- and data-specific.
