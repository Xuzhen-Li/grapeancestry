# Interactive demo report (Ages)

Self-contained **sample-first V2** HTML for the public aDNA demo **`Ages`** (archaeological **V5**; cite Noraz et al. 2026 / Orlando — see root README Demo).

## Files

| Path | Role |
|------|------|
| `results/Ages.sample-first-v2.report.html` | Interactive report (~38 MB; payload embedded) |
| `results/Ages.sample-first-v2.report.data.json` | Optional query sidecar (downloads section) |
| `assets/` | Plotly / D3 / LocusZoom (required next to `results/` as `../assets`) |

## Open locally

GitHub does **not** run this HTML in the blob viewer. Clone or download, then:

```bash
cd demo
python -m http.server 8000
# open http://localhost:8000/results/Ages.sample-first-v2.report.html
```

Or open the HTML file from a local file tree that keeps `results/` beside `assets/`.

**Cite source data:** Noraz et al. (2026) *Nat Commun* https://doi.org/10.1038/s41467-026-70166-z
