# Step 00c — Panel VCF and dosage cache

## Goal

Build the analysis matrix: panel genotypes at chip sites as a dosage `npz` (preferred over merging huge VCFs every run).

## Scripts / entrypoints

| Role | Path |
|------|------|
| Dosage build/load | `src/grapeancestry/core/dosage.py` (`python -m grapeancestry.core.dosage`) |
| Merge helper (artifact only) | `src/grapeancestry/core/merge_ref.py` |

## Inputs

- Panel VCF at chip sites (GT)  
- Sample order matching metadata  

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `results/cache/panel_dosage_*.npz` | **Primary analysis matrix** for IBS/PCA/ADMIX/GS |
| Optional merged VCF | 2449+query convenience file—not the analysis matrix |

## Visualization outputs

None at build time.

## CLI example

```bash
python -m grapeancestry.core.dosage \
  --panel-vcf data/panel/panel167k_2449.vcf.gz \
  --out-npz results/cache/panel_dosage_167k.npz --full
```
