# Step 02 — QC and coverage

## Goal

Measure how well the query covers the chip and what calling rates mean for downstream methods.

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry qc` · inside `analyze` / `_post_analyze` |
| Core | `src/grapeancestry/core/qc.py` |
| Dosage resolve | `src/grapeancestry/core/dosage.py` (`resolve_cache`) |

## Inputs

- Markdup BAM (preferred) + sites BED  
- Query VCF (for calling-rate denominators)  
- Optional panel dosage cache presence (method coverage)

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.qc.tsv` | On-target rate, fold enrichment, breadth ≥1×/5×/10×, mean/median depth, panel vs VCF calling rates, het/hom counts |
| Method-coverage rows (in report) | Which analyses have enough sites (PCA, selection windows, GWAS loci, damage, GS, …) |

Key distinctions (must stay explicit in UI/docs):

- **Panel calling rate** = called ÷ all chip sites  
- **VCF-site calling rate** = called ÷ sites written in this VCF  

## Visualization outputs

| Where | What |
|-------|------|
| Report → Sample validity | QC summary cards + metrics table |
| Report conclusions block | Auto text from QC + identity + Q |

No standalone plot required; cards are the viz.

## CLI example

```bash
grapeancestry qc --sample Ages   # see cli --help for flags
grapeancestry analyze --sample Ages
```
