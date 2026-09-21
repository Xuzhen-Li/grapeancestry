# Step 06a — Build IBS distance for tree

## Goal

Compute identity distances between query and panel tips used in the NJ tree.

## Inputs

- Query dosage (from VCF) + panel dosage cache
- Tip subsample / keep rules inside the tree builder

## Commands

**No dedicated `grapeancestry` NJ/distance CLI.** Distance prep runs on the report path:

```bash
# Triggered by:
grapeancestry analyze --sample Ages
grapeancestry run --sample Ages

# Libraries only:
#   src/grapeancestry/popgen/tree_nj.py
#     ibs_distance_to_rows · ibs_distance_matrix · load_or_compute_panel_ibs_d · assemble_tree_distance
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Distance matrix / condensed vector | In memory or cache for layout (06b) |

## Plots

None yet (layout in 06b).

## Notes

- Honest gap: there is no `grapeancestry nj` / `tree` subcommand — use `analyze` / `run` or call `tree_nj` from Python.
