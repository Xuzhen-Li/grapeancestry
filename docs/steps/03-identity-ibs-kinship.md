# Step 03 — Identity (IBS / kinship / clone-PO)

## Goal

Screen the query against the reference panel for near-identical / parent-offspring hits and rank IBS / KING neighbours.

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry identity` |
| Runner | `src/grapeancestry/identity/run_ibs.py` |
| Core | `identity/ibs.py`, `parentage.py`, `fingerprint.py`, `catalog.py` |

## Inputs

- Query VCF at panel sites  
- Panel dosage cache (`results/cache/panel_dosage_*.npz`)  
- Panel metadata (for variety/origin labels)

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.ibs.tsv` | Top IBS neighbours (rank, ref ID, metrics) |
| `results/{sample}.kinship_top.tsv` | Top KING / relatedness ranks |
| `results/{sample}.ibs_clone_hits.tsv` (when produced) | Identical + PO screen hits |
| `results/{sample}.ibs_summary.tsv` | Summary counts |

**ID trap:** panel row `HUN89` ≠ report stem `HUN89_query`. Never strip `_query` to look up passport/Q.

## Visualization outputs

| Where | What |
|-------|------|
| Report → Identity & placement | Clone/PO table; IBS top + Kinship top side-by-side |
| Interactive | Click row → pin sample on PCA / ADMIXTURE / NJ |

## CLI example

```bash
grapeancestry identity --vcf results/Ages.vcf.gz --sample Ages
```
