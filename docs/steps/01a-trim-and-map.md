# Step 01a — Trim and map

## Goal

Clean reads and align them to the profile reference (modern PE or aDNA SE).

## Inputs

- FASTQ paths from sample YAML (`config/samples_*.yaml`, field `type`: `pe` / `se` / `adna`)
- Reference fasta from Step 00b
- Config: `config/mbp_demo.yaml` (or `hpc_full.yaml`)

## Commands

```bash
# Preferred orchestration (runs Snakemake then optional analyze):
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_ages.yaml --sample Ages -j 4 --mapping full

# Or invoke Snakefile rules directly:
snakemake -s workflow/Snakefile --configfile config/mbp_demo.yaml \
  --config samples_file=config/samples_ages.yaml -j 4 \
  results/bam/Ages.raw.bam

# Rules: trim_pe | trim_se | trim_adna → map_pe | map_se | map_aln → lift_or_copy
# Gate helper: src/grapeancestry/core/gate.py
```

### Modern PE

`fastp` (`trim_pe`) → `bwa mem` (`map_pe`) → optional `lift_or_copy`

### aDNA SE

AdapterRemoval3 (`trim_adna`, min length 25) → `bwa aln` + `samse` (`map_aln`, `-l 1024 -n 0.01`) → `lift_or_copy`

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/trim/*` | Trimmed FASTQ + fastp / AdapterRemoval reports |
| `results/bam/{sample}.raw.bam` / `.lifted.bam` | Mapping product (pre-markdup) |

## Plots

None required (trim HTML/JSON logs only).

## Notes

- `mapping: full` after gate concordance (pipeline docs cite 0.959) uses the full reference; `subref` lifts via `python -m grapeancestry.core.lift`.
- aDNA door also feeds Steps 07a/07b (damage).
