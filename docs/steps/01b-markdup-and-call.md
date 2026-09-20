# Step 01b — Markdup and call at panel sites

## Goal

Deduplicate and call genotypes **only** at chip sites.

## Scripts / entrypoints

| Role | Path |
|------|------|
| Workflow / run | `workflow/Snakefile`, `cli.py` |
| Sites BED | from Step 00a |

## Inputs

Aligned BAM + sites BED + reference

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/bam/{sample}.markdup.bam` | Deduplicated alignments |
| `results/{sample}.vcf.gz` (+ index) | Query VCF at panel sites |

## Visualization outputs

Listed later in Sample validity provenance (Step 13).
