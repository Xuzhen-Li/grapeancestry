# Step 03a — Clone and parent-offspring screen

## Goal

Flag Identical / Parent-Offspring hits against the reference screen (non-self).

## Scripts

`identity/run_ibs.py`, `parentage.py`, `fingerprint.py` · `grapeancestry identity`

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Clone/PO hit table | Identical + PO only; empty if none |
| Self-in-panel QC | If query ID already in panel, report self then nearest non-self |

## Visualization outputs

Identity section “Clone + PO list”; click-to-pin.

## ID trap

Panel `HUN89` ≠ stem `HUN89_query`.
