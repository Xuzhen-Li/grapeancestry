# Platform (generic contracts)

Implementation currently lives in `src/grapeancestry/` (first complete GBTS companion). These folders state the **stable seams** other chips should target:

| Dir | Maps to package | Intent |
|-----|-----------------|--------|
| `pipeline/` | `cli.py`, `workflow/`, `core/` | Config-driven run; VCF@panel-sites |
| `report/` | `report/` | Sample-first HTML/JSON |
| `viz/` | `report/interactive_*`, `popgen/selection_viz.py` | PCA/ADMIXTURE/NJ/LocusZoom shells |
| `cloud/` | `cloud/`, `app.py` | VCF → `chip.json` |

See [docs/SCRIPTS.md](../docs/SCRIPTS.md) for file-level detail.
