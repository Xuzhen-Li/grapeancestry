# Step 00e — Freeze ADMIXTURE Q/P

## Goal

Fit or ingest frozen ADMIXTURE **P** (and panel Q) for K=2–8 so new samples only project (`-P` / NNLS).

## Scripts / entrypoints

| Role | Path |
|------|------|
| Core I/O | `src/grapeancestry/adna/admixture.py`, `panel167k_nogwas.py` |
| Lab fit / ingest | `scripts/prep_admixture_bed.py`, `run_admixture_local.sh`, `submit_admixture_k*.sh`, `ingest_admixture_qp.py`, `admixture_fit_qc.py` |
| QC plots | `scripts/plot_science_k8_check.py`, `plot_k2_k10_purest_align.py` |
| Binary | `bin/admixture` |

## Inputs

- Panel BED/fam for the chosen site family  
- HPC or local ADMIXTURE runs  

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Frozen `*.P` / `*.Q` per K | Column order must match sites file |
| `science_manifest.json` / family provenance | Which archive is active |

## Visualization outputs

| Artifact | Meaning |
|----------|---------|
| Lab purest-align / K-check PNGs | Archive QC only |

## Contract

In-panel IDs → Q lookup; new IDs → project with frozen P.
