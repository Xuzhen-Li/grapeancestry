# Step 03a — Clone and parent-offspring screen

## Goal

Flag Identical / Parent-Offspring hits against the reference screen (**non-self**).

## Inputs

- Query VCF at panel sites
- Panel dosage cache (Step 00c)
- Sample id (report stem)

## Commands

```bash
grapeancestry identity \
  --vcf results/HUN89_query.vcf.gz \
  --sample HUN89_query \
  --out-tsv results/HUN89_query.ibs.tsv

# Inside full analyze:
grapeancestry analyze --sample HUN89 --as-query

# Libraries: src/grapeancestry/identity/run_ibs.py · parentage.py · fingerprint.py · ibs.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Clone/PO hit table | Identical + PO only; empty if none |
| Self-in-panel QC | If query ID already in panel, report self then nearest **non-self** |

## Plots

Identity section “Clone + PO list”; click-to-pin in interactive HTML.

## Notes

- **ID trap:** panel `HUN89` ≠ stem `HUN89_query` (independent chip FASTQ). Do not strip `_query` to look up Q/passport.
- Clone-screen = non-self Identical + Parent-Offspring only.
