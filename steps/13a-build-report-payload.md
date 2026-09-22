# Step 13a — Build report payload

## Goal

Gather all step artifacts into a structured bundle / interactive JSON payload (provenance + method coverage).

## Inputs

- Per-sample results from Steps 02–12 (QC, identity, PCA, ADMIXTURE, trees, f-stats, selection, GWAS/GS, damage)
- Configured root layout under `results/` and `data/`

## Commands

```bash
# Payload build is inside analyze / run (no standalone “bundle” CLI):
grapeancestry analyze --sample Ages
grapeancestry run --sample Ages --analyze

# Libraries:
#   src/grapeancestry/report/build_report.py  → build_bundle
#   src/grapeancestry/report/interactive_data.py
#   src/grapeancestry/cli.py → _post_analyze
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| In-memory / sidecar payload | QC, identity, Q, PC, trees, coverage flags, provenance IDs |
| Optional `*.report.data.json` | Downloads sidecar when written |

## Plots

None until HTML render (13b).

## Notes

- Provenance must record `query_id`, `source_sample_id`, artifact paths, and method coverage.
- Unavailable methods stay labeled unavailable.
