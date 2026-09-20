# Step 13 — Sample-first V2 HTML report

## Goal

Assemble the customer hand-in: interactive **sample-first V2** HTML with provenance and method coverage.

## Scripts / entrypoints

| Role | Path |
|------|------|
| Bundle + render | `src/grapeancestry/report/build_report.py` (`build_bundle`, `render_full_html`, `v2_report_path`) |
| Interactive shell | `report/interactive_dashboard.py` |
| Payload | `report/interactive_data.py` |
| Legacy | `html_report.py`, `dashboard_html.py` |
| Trigger | `grapeancestry run` / `analyze` → `_post_analyze` in `cli.py` |

## Inputs

- All prior step artifacts that exist (missing → method marked unavailable)  
- Front-end assets (`../assets` relative to HTML)

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.sample-first-v2.report.html` | **Suite hand-in filename** |
| Optional `*.sample-first-v2.report.data.json` | Query sidecar for downloads |
| Provenance table inside HTML | query_id, source_sample_id, artifact paths, sizes |

Public demo copy: `demo/results/Ages.sample-first-v2.report.html`.

## Visualization outputs

Full interactive report (Steps 02–12 surfaces). Theme: Light / Dark / System.

## CLI example

```bash
grapeancestry analyze --sample Ages
# open via: cd demo && python -m http.server  # or suite results/ + assets/
```
