# Step 01b — Markdup and call at panel sites

## Goal

Deduplicate alignments and call genotypes **only** at chip sites (sites BED from 00a).

## Inputs

- Lifted / aligned BAM from Step 01a
- Sites BED + reference fasta
- Same config / samples YAML as 01a

## Commands

```bash
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_demo.yaml --sample HUN89 -j 4 --no-analyze

# Snakefile rules:
snakemake -s workflow/Snakefile --configfile config/mbp_demo.yaml \
  --config samples_file=config/samples_demo.yaml -j 4 \
  results/HUN89.vcf.gz

# Rules: sort_markdup → call
#   sort_markdup: samtools sort / fixmate / markdup → results/bam/{sample}.markdup.bam
#   call: bcftools mpileup/call -T sites BED → results/{sample}.vcf.gz
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/bam/{sample}.markdup.bam` (+ `.bai`) | Deduplicated alignments |
| `results/{sample}.vcf.gz` (+ `.tbi`) | Query VCF at panel sites |

## Plots

Listed later in Sample validity provenance (Step 13).

## Notes

- Analysis matrix for IBS/PCA remains the panel dosage cache (00c), not a merged VCF.
- Independent chip FASTQ for a panel ID should use `--as-query` later so the report stem is `{id}_query`.
