# grapeancestry

Analysis companion for the grapevine **167K capture panel** — interactive reports and Chip Companion, not a black-box whole-genome resequencing suite.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## What this is

GrapeAncestry places a **new grapevine query** against a **frozen 2449 × 167K** reference built on the **VS-1** genome. From the same sample you can read capture QC, identity and kinship screens, PCA and ADMIXTURE placement on frozen axes, an IBS neighbour-joining tree, passport-style cards, and — where the evidence supports ranking — a colour genomic-selection score.

The scientific frame is fixed on purpose. Coordinates and calling use **VS-1**. Your input is FASTQ, BAM/CRAM already on VS-1, or a **query VCF at the 167K sites**. That query VCF uses the same sites as the chip; it is **not** the 2449-panel dosage matrix. PCA axes and ADMIXTURE Q/P are **frozen**; new samples are projected (`admixture -P` in the lab image, or NNLS on Cloud), not used to refit the panel. Today only **OIV 225** colour GS is treated as decision-grade; other traits and flower-sex / selection narratives stay exploratory (full rules in the GUIDELINE).

**ID trap (one line):** panel row `HUN89` (2449-row ID) ≠ report stem `HUN89_query` (independent FASTQ recapture).

This public GitHub tree is the **docs face** first: how the pieces fit, how to start, and how to read the demo. A runnable CLI, Docker customer image, VS-1, and large panel matrices land in later releases — do not expect `grapeancestry run` from this clone yet.

## Tonight hand-in

Pick **one** door. Do not mix filenames.

| Door | Hand-in |
|------|---------|
| **Cloud** | `chip.json` |
| **Suite** (local image / lab suite) | `*.sample-first-v2.report.html` |
| **Public docs (Lane A)** | read only — no hand-in file |

The hand-in is a **filename**, not every sidebar tab in the report.

## Start here

→ **[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)** — step-by-step onboarding (what works on this docs tree today vs what needs the customer image).

Deep read, claim rules, and long screenshots: [`docs/GUIDELINE.md`](docs/GUIDELINE.md).  
Diagram notes: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).  
Cloud door notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

## What you get

Inside the Suite HTML report (or the Cloud card), the read path is:

1. **Sample validity** — QC / provenance
2. **Identity & placement** — clone / PO / IBS screens
3. **Population placement** — PCA · ADMIXTURE · NJ on frozen axes
4. **Sample evidence** — MAS / trait cards; OIV 225 GS when in scope
5. **Panel research** — 2449 context + LocusZoom (query GT = overlay)
6. **Methods / Downloads** — how numbers were made; query-only exports

Screenshot walkthrough: [`docs/GUIDELINE.md#walk-the-demo-report`](docs/GUIDELINE.md#walk-the-demo-report) (not embedded here).

## Analysis flow

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses → report or `chip.json`.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid arrows stop at tonight's hand-in (`*.sample-first-v2.report.html` / `chip.json`). Dashed lines = how you read the report. Claim-bounded boxes are not field release — see GUIDELINE. Node list: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

## How to use (three lanes)

| Lane | Who | What you do | Hand-in |
|------|-----|-------------|---------|
| **A · Public docs** | Anyone with this GitHub tree | Follow **USER_GUIDE**; use GUIDELINE screenshots as the walkthrough | read only |
| **B · Local suite / image** | Lab with private suite or customer Docker package | Follow **USER_GUIDE** (and GUIDELINE) for commands — **not** copy-paste fake CLI from this clone | `*.sample-first-v2.report.html` |
| **C · Cloud** | Classroom Streamlit when wired | Upload a **167K-site query VCF** (not FASTQ) → export JSON | `chip.json` |

Lane A is the default for visitors to this repository. Lanes B and C need assets that are not in this public tree yet.

## Related

[grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome) · [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip)

No unpublished genotypes or full 2449 matrices in this public tree. **Xuzhen Li** · [ORCID](https://orcid.org/0000-0003-3670-6657)
