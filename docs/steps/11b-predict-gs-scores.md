# Step 11b — Predict GS scores for query

## Goal

Score the query with trained models; expose only profile **decision-grade** traits as rankable.

## Inputs

- Trained GS artifacts / `results/gs/index.tsv` from 11a
- Query sample id + optional query VCF
- `--min-cv-r` threshold for which models emit scores

## Commands

```bash
grapeancestry gs-predict \
  --sample Ages \
  --vcf results/Ages.vcf.gz \
  --cache results/cache/panel_dosage_167k.npz \
  --min-cv-r 0.3

# Also wired through grapeancestry analyze / run when GS assets exist
# Libraries: src/grapeancestry/breeding/gs.py · report/Cloud wiring
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Per-trait scores for this sample | Model predictions |
| Decision-grade flag | From profile claims (not every CV-passing trait) |

## Plots

Colour GS card (example: OIV 225) placed last in classroom order on the HTML.

## Notes

- **GS score ≠ phenotype.**
- Grapevine example: only **OIV 225** is decision-grade / rankable; do not claim seedlessness from exploratory traits.
- Frozen axes / panel training stay separate from customer phenotype collection.
