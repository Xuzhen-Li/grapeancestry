# grapeancestry

Analysis companion for the grapevine **167K capture panel** — reports and Chip Companion, not a black-box resequencing suite.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## What this is

This repo is for breeders and classrooms that hand in a **query** sample or open a demo report. Sites are called on **VS-1** and compared to a **frozen 2449 × 167K** panel (dosage, PCA axes, ADMIXTURE Q/P). Your input is FASTQ, BAM/CRAM on VS-1, or a query VCF at the 167K sites — that VCF is **not** the panel matrix. New samples are projected onto the frozen reference (`-P` / NNLS), not used to refit the panel. The public tree ships **docs and a demo walkthrough** first; full `run` and matrices land later.

**Tonight hand-in:** Cloud → `chip.json` · Suite → `*.sample-first-v2.report.html` · Public docs (Lane A) → read only (no file).

**Start here:** [`docs/GUIDELINE.md`](docs/GUIDELINE.md) — usage lanes, claim boundaries, and the demo report walkthrough (screenshots + LocusZoom). Hand-in is a **filename**, not every sidebar tab.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid arrows stop at tonight's filename (`report.html` / `chip.json`). Dashed = read inside the report. Claim rules = do not over-claim. Detail: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

Only **OIV 225** colour GS is decision-grade today; full claim rules live in the GUIDELINE.

## How to use (usage flow)

**Default today: read the docs and the demo walkthrough.** This GitHub tree does not yet ship a runnable `grapeancestry` CLI.

| Lane | Who | What you do | Hand-in |
|------|-----|-------------|---------|
| **A · Public docs** | Anyone | Open **Start here** (GUIDELINE); use screenshots as the walkthrough | read only |
| **B · Local suite** | Lab with private suite checkout | Commands live in GUIDELINE (and upcoming USER_GUIDE) — **not** copy-paste from this clone | `*.sample-first-v2.report.html` |
| **C · Cloud** | Classroom Streamlit | Upload a **167K-site query VCF** (not FASTQ) | `chip.json` |

Panel ID `HUN89` ≠ report stem `HUN89_query`. Cloud notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses (flowchart above).

## Related

[grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome) · [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip)

No unpublished genotypes or full 2449 matrices in this public tree. **Xuzhen Li** · [ORCID](https://orcid.org/0000-0003-3670-6657)
