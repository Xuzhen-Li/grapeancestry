# grapeancestry

**GrapeAncestry v1.0.0** — local Docker app for the grapevine **167K** capture panel. Place a new query on frozen **VS-1** axes and open a sample-first V2 HTML report.

Not a whole-genome resequencing suite. Cross-crop scaffold (optional): [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## Honest status

| Surface | What you get |
|---------|----------------|
| **Public GitHub** | Docs, flowchart, Ages HTML, Python source. No VS-1, no 2449 panel, no fat image. CLI installs; analyze/run **stop** without private assets. |
| **Private tar + `start.sh`** | Full UI. Demos **Ages** + **HUN89_query**. FASTQ / BAM / VCF → V2 HTML. |
| **Cloud `chip.json`** | Optional classroom path (VCF→JSON), **not** the v1 customer product. |

v1 customer output is **`*.sample-first-v2.report.html`** (UI **8501**, report server **8502**).

## Start here

1. **Browse without Docker (public clone):** open the Ages demo HTML.

```bash
cd demo
python3 -m http.server 8000
# http://127.0.0.1:8000/results/Ages.sample-first-v2.report.html
```

View-only. Does not run Analyze.

2. **Full product (private drop):** place `grapeancestry-v1.0.0-amd64.tar` next to `start.sh`, then:

```bash
./start.sh
# macOS: double-click start.command
# Windows: start.bat
```

UI: http://127.0.0.1:8501 · Reports: http://127.0.0.1:8502

A fresh GitHub clone has **no** fat image and **cannot** finish Analyze (no VS-1 / 2449 panel in public git). Never `docker push` the fat image (panel inside).

Full steps: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md). Screenshot walkthrough: [`docs/GUIDELINE.md`](docs/GUIDELINE.md).

## Product (v1.0.0)

- **Stack:** private linux/amd64 image `grapeancestry:1.0.0`. Customer drop = tar next to `start.sh` / `start.command` / `start.bat`.
- **First visit:** Setup — password twice, language, threads, optional lab name. Hash only in `./settings/auth.json` (scrypt). Later visits: password only.
- **Sidebar:** Analysis / Demos / Settings.
- **Inputs** (`./input`): FASTQ (PE modern / SE modern / aDNA), BAM, or VCF — drag-and-drop, host copy, **Get Ages** / **Get HUN89_query**, or http(s) URL (streamed).
- **BAM rule:** must already be **VS-1** numeric contigs. `chr1` / 12X / PN40024 → fail → use FASTQ. Example ENA BAM below is **12Xv2, not VS-1** — useful as a download demo only; Analyze as BAM must fail `@SQ`.
- **New samples:** treat as query on → report id `{id}_query`.
- **Report:** `*.sample-first-v2.report.html` on **8502**; copies under `./output/results/` + `./output/assets/`.
- **Packed demos:** Ages and HUN89_query V2 HTML (Companion tab merged into Demos).

Sample URL in the UI download box (download demo only — **not** a VS-1 BAM):

`https://ftp.sra.ebi.ac.uk/vol1/run/ERR166/ERR16654874/V5xL1xP2_Ages_3_5070.12Xv2.realigned.bam`  
ENA run **ERR16654874**, study **PRJEB94459**.

## Analysis flow

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses → **`*.sample-first-v2.report.html`**.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid arrows = core path (+ OIV 225 decision-grade GS). Dashed = do-not-claim modules. Detail: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

## What this is

GrapeAncestry places a **new grapevine query** against a **frozen 2449 × 167K** reference on **VS-1** (Dong et al. 2023 *Science*, [doi:10.1126/science.add8655](https://doi.org/10.1126/science.add8655)). From the same sample you can read capture QC, identity and kinship, PCA and ADMIXTURE on frozen axes, an IBS neighbour-joining tree, passport-style cards, and — where evidence supports ranking — a colour genomic-selection score.

- Query VCF uses the **167K sites**; it is **not** the 2449-panel dosage matrix.
- PCA / ADMIXTURE Q/P are **frozen**; new samples are projected, not used to refit the panel.
- Only **OIV 225** colour GS is decision-grade today (full rules in the GUIDELINE).
- **ID trap:** panel row `HUN89` ≠ report stem `HUN89_query`.

**MIT** covers **code** only. Panel genotypes / phenotypes are **not** MIT.

ADMIXTURE 1.3.0 (linux x86_64): [download](https://dalexander.github.io/admixture/download.html).

## Demo (Ages HTML in this repo)

Open the shipped Ages report to learn the sidebar (no need to re-run FASTQ from a public clone).

**Source data cite:** Noraz et al. 2026 *Nat Commun* ([doi:10.1038/s41467-026-70166-z](https://doi.org/10.1038/s41467-026-70166-z); incl. **Ludovic Orlando**). Sample **V5** as stated in that paper.

Keep `demo/assets/` beside `demo/results/`. Notes: [`demo/README.md`](demo/README.md). Screenshots: [`docs/GUIDELINE.md`](docs/GUIDELINE.md).

## Optional: Chip Companion (`chip.json`)

Separate, optional VCF→JSON path for classrooms — **not** the v1 Docker product. See [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

## Deeper docs

| Doc | Role |
|-----|------|
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Product onboarding (image + public browse) |
| [`docs/GUIDELINE.md`](docs/GUIDELINE.md) | Ages sidebar walkthrough |
| [`docs/steps/`](docs/steps/) | Fine steps `00a`–`14b` |
| [`docs/PIPELINE.md`](docs/PIPELINE.md) · [`docs/ANALYSIS_METHODS.md`](docs/ANALYSIS_METHODS.md) | Science contracts / methods |
| [`docs/SCRIPTS.md`](docs/SCRIPTS.md) · [`docs/REPO_MAP.md`](docs/REPO_MAP.md) | Module map · folder map |

## Author

**李旭真 / Li Xuzhen** · [ORCID 0000-0003-3670-6657](https://orcid.org/0000-0003-3670-6657)

Related: [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit) · [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome)

No unpublished genotypes or full 2449 matrices in this public tree.
