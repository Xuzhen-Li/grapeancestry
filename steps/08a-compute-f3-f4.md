# Step 08a — Compute f3/f4 contrasts

## Goal

Complete-case f3/f4 of the query vs Grp reference means (exploratory).

## Inputs

- Query genotype / dosage at panel sites
- Grp means from panel metadata (`2449.info`)
- Panel dosage cache

## Commands

**No dedicated `grapeancestry` f3/f4 CLI.** Statistics run on the report path:

```bash
grapeancestry analyze --sample Ages
grapeancestry run --sample Ages

# Libraries only:
#   src/grapeancestry/adna/fstats.py
#   src/grapeancestry/popgen/fstats_report.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Per-contrast f, Z | Exploratory f3/f4 |
| `n_sites`, `n_blocks` | Complete-case + jackknife block counts |

## Plots

Tables/cards in 08b.

## Notes

- Missing dedicated CLI — do not invent `grapeancestry fstats`.
- Not formal qp3Pop / qpDstat / qpAdm / qpGraph.
- Each contrast is complete-case; missing query sites excluded.
