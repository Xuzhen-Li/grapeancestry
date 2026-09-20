# Step 10 — Panel GWAS

## Goal

Association scans on the **panel** with phenotypes; query contributes genotype overlay at trait loci, not its own measured phenotype.

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry gwas` |
| Core | `src/grapeancestry/breeding/gwas.py`, `mixed_model.py` |
| Phenotype ETL | `breeding/phenotype.py`, `scripts/build_phenotype.py` |
| Methods text | `breeding/methods_doc.py` |

## Inputs

- Panel dosage cache  
- `data/phenotype.tsv` (≥50 overlapping IDs for a trait to run)  
- Trait dictionary / OIV tables when used

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/gwas/**` | Per-trait summaries, lead sites, p/β/r² |
| Case/control counts | Surfaced for binary traits (imbalance warnings) |

## Visualization outputs

| Where | What |
|-------|------|
| Report → Sample evidence / Panel research | Trait cards; GWAS LocusZoom (Step 12) |
| Cloud MAS cards | `cloud/mas.py`, `cloud/plot.py` |

## Claim note

GWAS p/β are **panel** results. Query GT overlay ≠ observed customer phenotype.
