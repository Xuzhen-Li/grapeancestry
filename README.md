# grapeancestry

Analysis companion for the grapevine **167K capture panel** — reports and Chip Companion, not a black-box resequencing suite.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## What this is

This repo is for breeders and classrooms that hand in a **query** sample or open a demo report. Sites are called on **VS-1** and compared to a **frozen 2449 × 167K** panel (dosage, PCA axes, ADMIXTURE Q/P). Your input is FASTQ, BAM/CRAM on VS-1, or a query VCF at the 167K sites — that VCF is **not** the panel matrix. New samples are projected onto the frozen reference (`-P` / NNLS), not used to refit the panel. The public tree ships **docs and a demo walkthrough** first; full `run` and matrices land later.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid path: your input → our frozen assets → analyses → report or `chip.json`. Detail: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

Only **OIV 225** colour GS is decision-grade today; claim rules live in the GUIDELINE.

## How to use (this public docs repo)

**Default today: read the docs and the demo walkthrough.** This GitHub tree does not yet ship a runnable `grapeancestry` CLI.

1. **Start here.** Open [`docs/GUIDELINE.md`](docs/GUIDELINE.md) — sidebar order, long screenshots, and reading notes. Diagram notes: [`docs/FLOWCHART.md`](docs/FLOWCHART.md). Cloud companion notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

2. **Open a local demo report (when you have the suite checkout).** Serve from that suite root so relative assets resolve. `python -m http.server` is **view-only**; it does not create a hand-in file.

```bash
# path = your local suite checkout (not this docs-only clone)
cd /path/to/local-suite
python -m http.server
# http://localhost:8000/results/HUN89_query.sample-first-v2.report.html
```

Panel ID `HUN89` ≠ report stem `HUN89_query`.

3. **Later (local suite / Cloud — not copy-paste from this repo yet).** Cloud hand-in is `chip.json` from a 167K-site query VCF; Suite hand-in is `*.sample-first-v2.report.html`. Commands such as `chip-report`, `run`, and Docker live in the suite package when published — see CHIP_COMPANION / GUIDELINE, not a fake CLI in this tree.

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses (flowchart above).


## Demo panels

Non-overlapping panel crops from the demo report. Caption: **hand-in is a filename, not every sidebar tab.** Full set + reading notes: [`docs/GUIDELINE.md`](docs/GUIDELINE.md).

**Sample validity**

![Sample validity](docs/guideline_shots/panels/01_sample_validity_01.png)

**Identity**

![Identity](docs/guideline_shots/panels/02_identity_01.png)

**PCA · ADMIXTURE · NJ**

![PCA](docs/guideline_shots/panels/03_pca.png)

![ADMIXTURE](docs/guideline_shots/panels/03_admixture.png)

![NJ](docs/guideline_shots/panels/03_nj.png)

**Sample evidence · Panel research · Methods · Downloads**

![Evidence](docs/guideline_shots/panels/04_sample_evidence_01.png)

![Panel research](docs/guideline_shots/panels/05_panel_research_01.png)

![Methods](docs/guideline_shots/panels/06_methods_01.png)

![Downloads](docs/guideline_shots/panels/07_downloads.png)

## Related

[grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome) · [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip)

No unpublished genotypes or full 2449 matrices in this public tree. **Xuzhen Li** · [ORCID](https://orcid.org/0000-0003-3670-6657)
