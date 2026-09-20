# Step 00a — Panel sites and sample metadata

## Goal

Define the chip: which sites belong to the panel, and which reference sample IDs / groups exist.

## Scripts / helpers

| Role | Path |
|------|------|
| Profile stub | `profiles/examples/grapevine-167k/profile.yaml`, `templates/profile.yaml` |
| Manifest (lab inventory) | `data/MANIFEST.md` |
| Panel export helpers | `src/grapeancestry/resource/panel_export.py` |

## Inputs you prepare (not shipped in git)

- Target site list → BED (one row per chip site)  
- Panel sample list + metadata table (ID, origin, Grp, use, …)  
- Optional: probe/loci BED for on-target QC

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `data/panel/*.sites.bed` (local) | Calling and QC intervals |
| `data/panel/*.info` / sample annot | Grp colours, passport fields |
| Profile `panel_n_sites` | Declared site count for method coverage |

## Visualization outputs

None required. Document site count and ID rules in the profile README.

## Other chips

This is the first fork point: your BED + metadata replace the grapevine 167K example.
