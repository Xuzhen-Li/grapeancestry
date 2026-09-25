# Step 00e — Freeze ADMIXTURE Q/P

## Goal

Fit or ingest frozen ADMIXTURE **P** (and panel Q) for K=2–8 so new samples only project (`admixture -P` / NNLS).

## Inputs

- Panel BED/fam for the chosen site family (`panel167k_nogwas` when ingested)
- HPC or local ADMIXTURE runs (`admixture` 1.3.0 on PATH)

## Commands

```bash
# Lab fit / ingest (scripts/ — not grapeancestry subcommands):
#   scripts/prep_admixture_bed.py
#   scripts/run_admixture_local.sh · scripts/submit_admixture_k*.sh
#   scripts/ingest_admixture_qp.py · scripts/admixture_fit_qc.py
#   scripts/rebuild_manual_qp.py
# Core I/O: src/grapeancestry/adna/admixture.py · panel167k_nogwas.py

# Customer / batch projection after ingest (dedicated CLI):
grapeancestry admix-project --vcf results/Ages.vcf.gz
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Frozen `*.P` / `*.Q` per K under `data/panel/admixture/` | Column order must match sites file |
| Family provenance / manifest | Which archive is active (`panel167k_nogwas` preferred) |

## Plots

| Artifact | Meaning |
|----------|---------|
| Lab purest-align / K-check PNGs (`scripts/plot_*.py`) | Archive QC only — not v1 product HTML |

## Notes

- In-panel IDs → Q **lookup**; new IDs → project with frozen P.
- Do not unsupervised-refit 2449+N customers each night.
- `grapeancestry run` / `analyze` accept `--admix-k8-only`; that flag is **not** an `admix-project` option.
