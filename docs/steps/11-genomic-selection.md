# Step 11 — Genomic selection (GS)

## Goal

Predict trait scores for the query from panel-trained models. **Decision-grade scope is profile-defined.**

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry gs-train`, `grapeancestry gs-predict` |
| Core | `src/grapeancestry/breeding/gs.py`, `gs_models.py`, `dl.py` |
| Provenance | `breeding/provenance.py` |

## Inputs

- Panel dosage + phenotypes for training  
- Query dosage/VCF for prediction  
- Model index under `results/gs/`

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/gs/index.tsv` | Traits, CV metrics, best model |
| Per-query scores | Written into report / chip.json |
| Training provenance JSON | Reproducibility |

**Grapevine example:** only **OIV 225** colour GS is decision-grade today (`cv_r` / model recorded in local index). Other traits (e.g. OIV 241) stay exploratory when case/control is extreme.

## Visualization outputs

| Where | What |
|-------|------|
| Report → Sample evidence | Rankable colour card last (classroom order) |
| Cloud companion | Colour GS section in Streamlit |

## Claim note

GS score ≠ measured phenotype. Binary traits follow EMMAX caveats.
