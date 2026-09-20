# Step 00g — Cloud fingerprint pack (optional)

## Goal

Pack compact reference fingerprints for Streamlit Cloud / `chip-report` (no bwa on Cloud).

## Scripts / entrypoints

| Role | Path |
|------|------|
| Pack | `scripts/build_cloud_pack.py`, `python -m grapeancestry.cloud` |
| Modules | `src/grapeancestry/cloud/pack.py` |

## Inputs

- Panel dosage subset for IBS/SDR windows  
- Optional GS payloads  

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `data/cloud/fingerprint.npz`, `sdr.npz`, `manifest.json` | Cloud reference side |

## Visualization outputs

None at pack time.
