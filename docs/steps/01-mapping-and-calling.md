# Step 01 — Mapping and calling

## Goal

Place reads on the panel coordinate system and call genotypes **only at panel sites**.

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI orchestrator | `grapeancestry run` → `src/grapeancestry/cli.py` |
| Workflow | `workflow/Snakefile` |
| Config | `config/mbp_demo.yaml`, `config/samples_*.yaml` |
| Gate / subref | `src/grapeancestry/core/gate.py`, `subref.py`, `lift.py` |

### Modern PE (`type: pe`)

1. `fastp` trim  
2. `bwa mem` → reference (example: VS-1)  
3. `samtools markdup`  
4. `bcftools mpileup/call -T` sites BED → `results/{sample}.vcf.gz`

### aDNA SE (`type: adna`, Ages demo)

1. AdapterRemoval3 (min length 25)  
2. `bwa aln -l 1024 -n 0.01` + `samse`  
3. `samtools markdup`  
4. `bcftools` call at sites BED  
5. Continues to Step 07 (damage)

## Inputs

- FASTQ (PE or SE) **or** BAM/CRAM already on the panel reference  
- Reference fasta + fai  
- Panel sites BED  
- Sample YAML (`type`, `r1`/`r2`)

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.vcf.gz` (+ index) | Query genotypes at panel sites |
| `results/bam/{sample}.markdup.bam` | Deduplicated alignments |
| Mapping gate metrics (when enabled) | Subref vs full concordance vs threshold |

## Visualization outputs

None required at this step (tables only). Downstream report lists BAM/VCF in Sample validity provenance.

## CLI example

```bash
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_ages.yaml --sample Ages -j 4
```

## Notes for other chips

Change reference, BED, and sample YAML only. Keep “call at panel sites, not WGS deliverable” as the contract.
