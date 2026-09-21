# Step 13b — Render sample-first V2 HTML

## Goal

Write the **v1 product** HTML (and optional data sidecar) — DIY / Docker hand-in.

## Inputs

- Report bundle from 13a
- Optional Plotly/D3/LocusZoom assets under `assets/` when present

## Commands

```bash
grapeancestry analyze --sample Ages
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_ages.yaml --sample Ages -j 4

# Stranger / independent chip FASTQ for an in-panel passport ID:
grapeancestry analyze --sample HUN89 --as-query --source-sample HUN89

# Libraries:
#   src/grapeancestry/report/build_report.py → render_full_html
#   src/grapeancestry/report/interactive_dashboard.py
#   src/grapeancestry/cli.py → _post_analyze
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `{sample}.sample-first-v2.report.html` | **Suite hand-in** |
| Optional `*.report.data.json` | Downloads sidecar |
| Provenance table | IDs, paths, sizes |

Public demo path: `demo/results/Ages.sample-first-v2.report.html`

## Plots

Full interactive report (PCA, ADMIXTURE, NJ, QC, selection/GWAS doors when available). Theme: Light / Dark / System.

## Notes

- DIY no-kit / v1 HTML **stops here** (00a–13b). Steps 14a/14b are optional Chip Companion JSON only.
- **HUN89 ≠ HUN89_query**; frozen PCA axes; OIV 225 decision-grade GS; score ≠ phenotype.
