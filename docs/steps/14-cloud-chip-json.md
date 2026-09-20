# Step 14 — Cloud Chip Companion (`chip.json`)

## Goal

Classroom / Cloud door: upload a **panel-sites query VCF** (not FASTQ) and hand in **`chip.json`**.

## Scripts / entrypoints

| Role | Path |
|------|------|
| CLI | `grapeancestry chip-report` |
| Analyze | `src/grapeancestry/cloud/analyze.py` |
| Cards / MAS / SDR | `cloud/card.py`, `mas.py`, `sdr.py`, `loci.py` |
| Plots | `cloud/plot.py` |
| Pack fingerprints | `scripts/build_cloud_pack.py`, `python -m grapeancestry.cloud` |
| UI | root `app.py` (Streamlit) |

## Inputs

- 167K-site (or profile site count) query VCF on the panel reference  
- Cloud pack under `data/cloud/` (fingerprints; built locally, not all public)

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| **`chip.json`** | **Cloud hand-in filename** |
| Packed `fingerprint.npz` / `sdr.npz` | Reference side for IBS/SDR proxies |

## Visualization outputs

| Where | What |
|-------|------|
| Streamlit app | QC → IBS → passport/SDR proxy → trait cards → colour GS |
| Notes | [CHIP_COMPANION.md](../CHIP_COMPANION.md) |

## Claim note

Cloud has no bwa/bcftools; new samples use NNLS onto frozen P. Do not mix `chip.json` with Suite HTML hand-in names.
