# Step 00a — Panel sites and sample metadata

## Goal

Define the chip: which sites belong to the panel, and which reference sample IDs / groups exist.

## Inputs

- Target site list → BED (one row per chip site)
- Panel sample list + metadata table (ID, origin, Grp, use, …)
- Optional: probe/loci BED for on-target QC
- Profile stub under `profiles/examples/` (grapevine example: `grapevine_167k`)

## Commands

No dedicated `grapeancestry` CLI. Prepare files and declare them in the profile / config:

```bash
# Profile stub (example id uses underscore)
# profiles/examples/grapevine_167k/profile.yaml
# templates/profile.yaml

# Helpers (library / export — not a suite CLI):
#   src/grapeancestry/resource/panel_export.py
```

Document inventory in `data/MANIFEST.md` (paths are local; matrices stay out of git).

## Outputs

| Artifact | Meaning |
|----------|---------|
| `data/panel/*.sites.bed` (local) | Calling and QC intervals |
| `data/panel/*.info` / sample annot | Grp colours, passport fields |
| Profile `panel_n_sites` | Declared site count for method coverage |

## Plots

None required. Document site count and ID rules in the profile README / `CLAIMS.md`.

## Notes

- First fork point for other chips: your BED + metadata replace the grapevine 167K example.
- Keep panel IDs distinct from independent recapture stems (e.g. panel `HUN89` ≠ report `HUN89_query`).
