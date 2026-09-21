# Step 00b — Reference genome (coordinate system)

## Goal

Fix the coordinate system every BAM/VCF in this profile must use.

## Inputs

- Reference fasta + `.fai` (profile `paths.ref_fa` in `config/*.yaml`)
- Optional sub-reference + lift map for gated accelerated mapping

## Commands

No dedicated `grapeancestry` CLI for staging the genome. Wire paths in config; optional lift runs inside the Snakefile:

```bash
# Config: config/mbp_demo.yaml (or hpc_full) → paths.ref_fa / subref
# Snakefile rule that may invoke lift:
#   snakemake -s workflow/Snakefile --configfile config/mbp_demo.yaml \
#     --config samples_file=config/samples_demo.yaml lift_or_copy
# Library: src/grapeancestry/core/lift.py · src/grapeancestry/core/subref.py
python -m grapeancestry.core.lift --help
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `data/ref/*.fa` + `.fai` (local) | Contig names must match VCF/`@SQ` |
| Gate concordance stats | When comparing subref vs full mapping (`src/grapeancestry/core/gate.py`) |

## Plots

None.

## Notes

- Contig naming must match the panel VCF and sites BED before Steps 01–04.
- Wrong coordinate system fails later projection and calling—catch here.
