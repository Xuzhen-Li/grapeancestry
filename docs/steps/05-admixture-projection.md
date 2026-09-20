# Step 05 — ADMIXTURE projection (frozen P)

## Goal

Obtain ancestry fractions for the query at K=2–8 using **frozen** panel P (lookup if in-panel; `admixture -P` or NNLS if new).

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry admix-project` |
| Core | `src/grapeancestry/adna/admixture.py`, `admix_project.py` |
| Sites family | `adna/panel167k_nogwas.py` (example) |
| Binary | `bin/admixture` (1.3.0) |
| Archive QC (lab) | `scripts/plot_science_k8_check.py`, `prep_admixture_bed.py`, `ingest_admixture_qp.py` |

## Inputs

- Query VCF aligned to the same sites order as frozen P  
- Frozen Q/P for the panel family  
- Optional: `--admix-k8-only` on run/analyze paths

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.admix.K{k}.Q.tsv` | Query Q vector(s) per K |
| In-panel lookup Q | Used when sample ID already in panel |
| Projection Q | `admixture -P` (lab) or NNLS (Cloud) |

Report states LD/LE caveats when no extra prune is applied.

## Visualization outputs

| Where | What |
|-------|------|
| Report → ADMIXTURE bar | Full/compact stacked bars; K tabs 2–8; query bar highlighted |
| Optional static PNG | `results/{sample}.admixture*.png` when built |
| Lab plots | `scripts/plot_k2_k10_purest_align.py` for archive QC |

## CLI example

```bash
grapeancestry admix-project --vcf results/Ages.vcf.gz
```
