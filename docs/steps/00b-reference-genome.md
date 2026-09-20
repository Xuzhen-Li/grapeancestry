# Step 00b — Reference genome (coordinate system)

## Goal

Fix the coordinate system every BAM/VCF in this profile must use.

## Scripts / helpers

| Role | Path |
|------|------|
| Config paths | `config/*.yaml` → `paths.ref_fa` |
| Lift / subref (optional) | `src/grapeancestry/core/lift.py`, `subref.py` |

## Inputs you prepare

- Reference fasta + `.fai` (example profile: VS-1)  
- Optional sub-reference for gated accelerated mapping

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| `data/ref/*.fa` + `.fai` (local) | Contig names must match VCF/`@SQ` |
| Gate concordance stats | When comparing subref vs full mapping |

## Visualization outputs

None.

## Claim / ops note

Wrong reference (e.g. chr-prefixed 12X when profile expects numeric VS-1 contigs) fails later steps—catch here.
