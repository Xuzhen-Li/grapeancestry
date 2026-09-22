# Step 00g — Cloud fingerprint pack (optional)

## Goal

**Optional** for Cloud / Steps **14a–14b** — not required for DIY **13b** HTML.

Pack compact reference fingerprints for Streamlit Cloud / `chip-report` (no bwa on Cloud).

## Inputs

- Panel dosage subset for IBS/SDR windows
- Optional GS payloads staged under `data/cloud/`

## Commands

```bash
# Pack scripts (not required for DIY HTML 13b):
python scripts/build_cloud_pack.py --help
python -m grapeancestry.cloud --help
# Library: src/grapeancestry/cloud/pack.py

# Optional consumer (Chip Companion / Step 14):
grapeancestry chip-report --vcf results/Ages.vcf.gz --out chip.json
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `data/cloud/fingerprint.npz`, `sdr.npz`, `manifest.json` | Cloud reference side |

## Plots

None at pack time.

## Notes

- Optional for DIY / Docker v1 HTML path (stops at 13b).
- Cloud path never runs bwa; it consumes the packed fingerprints + query VCF.
