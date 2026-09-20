# grapeancestry

Analysis companion for the grapevine **167K capture panel** — interactive reports and Chip Companion, not a black-box whole-genome resequencing suite.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## What this is

GrapeAncestry sits beside a fixed **167K** capture design for *Vitis*. Breeders and classrooms bring one **query** sample and ask where it sits against a shared reference: capture QC, identity and kinship screens, PCA and ADMIXTURE placement, a neighbor tree, passport-style cards, and — where the evidence supports it — a colour genomic-selection score. This public repository is the **docs face** of that companion: how the pieces fit, how to read a demo report, and what a tonight hand-in file is named.

Everything is anchored on the **VS-1** coordinate frame. You may start from FASTQ, from a BAM/CRAM already mapped to VS-1, or from a query VCF restricted to the 167K sites. In every case the analyses compare your sample to a **frozen 2449 × 167K** panel (dosage cache, PCA axes, ADMIXTURE Q/P, passport tables). That query VCF uses the same sites as the chip; it is **not** the panel matrix, and new samples are **projected** onto the frozen axes (`-P` / NNLS) rather than used to refit the panel.

Hand-in is a **filename**, not every sidebar tab. On Cloud night the file is `chip.json`; on Suite / local-demo night it is `*.sample-first-v2.report.html`. Reading this GitHub tree alone does not produce either file. Only **OIV 225** colour GS is treated as decision-grade today; SDR, seedlessness, selection overlays, and other trait cards are documented as proxy or exploratory in the deep-read pages — keep those nuances out of a one-line claim.

The public tree ships **documentation and a demo walkthrough** first. A runnable CLI, Docker image, and full matrices land later; until then, follow **Start here** for the honest path that matches what you actually have in hand.

**Tonight hand-in:** Cloud → `chip.json` · Suite → `*.sample-first-v2.report.html` · Public docs (Lane A) → read only (no file).

**Start here:** [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) — step-by-step onboarding (docs today vs image-in-hand). Deep read / screenshots: [`docs/GUIDELINE.md`](docs/GUIDELINE.md).

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid path ends at tonight's filename (`*.sample-first-v2.report.html` / `chip.json`). Dashed = read inside the report. Detail: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

Only **OIV 225** colour GS is decision-grade today; full claim rules live in the GUIDELINE.

## How to use (usage flow)

**Default today: read the docs and the demo walkthrough.** This GitHub tree does not yet ship a runnable `grapeancestry` CLI.

| Lane | Who | What you do | Hand-in |
|------|-----|-------------|---------|
| **A · Public docs** | Anyone | Open **Start here** ([USER_GUIDE](docs/USER_GUIDE.md)); use GUIDELINE screenshots as the walkthrough | read only |
| **B · Local suite** | Lab with private suite checkout | Commands live in USER_GUIDE / GUIDELINE — **not** copy-paste from this clone | `*.sample-first-v2.report.html` |
| **C · Cloud** | Classroom Streamlit | Upload a **167K-site query VCF** (not FASTQ) | `chip.json` |

Panel ID `HUN89` ≠ report stem `HUN89_query`. Cloud notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses (flowchart above).

## Related

[grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome) · [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip)

No unpublished genotypes or full 2449 matrices in this public tree. **Xuzhen Li** · [ORCID](https://orcid.org/0000-0003-3670-6657)
