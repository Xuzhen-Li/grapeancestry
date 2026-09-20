# Step 12 — LocusZoom and panel regional context

## Goal

Browse panel association / Fst windows with an interactive LocusZoom and overlay the query’s genotypes.

## Scripts / entrypoints

| Role | Path |
|------|------|
| Interactive UI | `src/grapeancestry/report/interactive_dashboard.py` |
| Payload | `report/interactive_data.py` |
| Assets | Plotly / D3 / LocusZoom under `demo/assets/` (or suite `assets/`) |
| Selection windows | From Step 09 JSON packs |
| GWAS windows | From Step 10 outputs |

## Inputs

- `locuszoom.json` / GWAS locus packs (panel)  
- Query GT at sites in the window  

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Window site table | alleles, −log10 p or Fst metric, gene tags |
| Query GT counts | 0/0, 0/1, 1/1, ./. in window |
| Lead SNP GT for this sample | Shown under the plot |

## Visualization outputs

| Where | What |
|-------|------|
| Report → Panel research | Selection LocusZoom (among-Grps Fst context) |
| Report → GWAS LocusZoom | e.g. OIV 225 region on chr19 (example) |
| Gene track | Under the scatter |

## Claim note

Strip colour is **genotype**, not LD. Overlay ≠ selection of this sample.
