# Step 06 — Neighbour-joining tree (IBS)

## Goal

Show the query on an IBS-based neighbour-joining tree with the reference panel.

## Scripts / entrypoints

| Role | Path |
|------|------|
| Builder | `src/grapeancestry/popgen/tree_nj.py` |
| Wired from | `report/build_report.py` / interactive payload |

No separate top-level CLI required; produced during report/analyze.

## Inputs

- IBS / genotype identity distances (from identity + dosage cache)  
- Panel Grp labels for colouring

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Tree tip coordinates / Newick-like structure in payload | Layout for circular or rectangular view |
| Optional `results/{sample}.nj_tree.png` | Static export when generated |

## Visualization outputs

| Where | What |
|-------|------|
| Report → NJ Tree | Interactive circular (default) / rectangular phylogram |
| Controls | Search, pin, layout toggle |
| Marker | Query star on the ring |

## Claim note

Exploratory placement aid; not a formal species tree.
