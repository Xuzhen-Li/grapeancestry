# Step 01a — Trim and map

## Goal

Clean reads and align them to the profile reference.

## Scripts / entrypoints

| Role | Path |
|------|------|
| Orchestration | `grapeancestry run`, `workflow/Snakefile` |
| Gate | `src/grapeancestry/core/gate.py` |

### Modern PE

`fastp` → `bwa mem` → sort

### aDNA SE

AdapterRemoval3 → `bwa aln` + `samse` → sort

## Inputs

FASTQ + reference fasta (Step 00b) + sample YAML `type`

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Aligned BAM (pre-markdup) | Mapping product |
| Trim / adapter reports | fastp or AdapterRemoval logs |

## Visualization outputs

None required (log tables).
