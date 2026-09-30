# Demo — 28 archaeological seeds

[Open the report](https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.batch.report.html).

View-only batch report for the 28 waterlogged grape seeds in Ramos-Madrigal et al. 2019, *Nature Plants*.

## Files

| Path | Role |
|------|------|
| `results/ramos2019_np.batch.report.html` | Interactive batch report (payload embedded) |
| `assets/` | Plotly / D3 / LocusZoom (required next to `results/` as `../assets`) |

## Open locally

The link above is the hosted copy. The GitHub blob viewer does not run this HTML. To open a local copy:

```bash
cd demo
python3 -m http.server 8000
# open http://localhost:8000/results/ramos2019_np.batch.report.html
```

**Cite:** Ramos-Madrigal et al. (2019) *Nat. Plants* https://doi.org/10.1038/s41477-019-0437-5
