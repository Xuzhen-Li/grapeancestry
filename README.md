<p align="center">
  <img src="docs/logo/grapeancestry_logo.png" alt="GrapeAncestry" width="180" />
</p>

# GrapeAncestry
[中文](README.zh.md)

GrapeAncestry v1.2.0 maps new grapevine samples to a frozen 2449 × 167K panel built on the VS-1 reference genome, and can also report the 8,044-site overlap with GrapeReseq. A batch of queries can share one report.

Code is provided under the MIT license. Panel genotypes and phenotypes are restricted (see [`DATA_NOTICE.md`](DATA_NOTICE.md)). Author: Li Xuzhen, [ORCID 0000-0003-3670-6657](https://orcid.org/0000-0003-3670-6657).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  <a href="https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.reports.html">Open the v1.2 demo overview</a><br/>
  28 archaeological seeds, Ramos-Madrigal et al. 2019 <em>Nat. Plants</em>
</p>

## Changes in v1.2

v1.2.0 lets you choose GrapeAncestry (167K), GrapeReseq (8K), or both before a run. Choosing both writes the two HTML reports and a 167K-vs-8K comparison with a short verdict. The browser and report wording were rewritten in English and Chinese. The Docker image also makes the panel info file readable inside the container. The runnable image is `grapeancestry:1.2.0` (`grapeancestry-v1.2.0-amd64.tar`).

| Page | What it is |
|------|------------|
| [Reports overview](https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.reports.html) | Entry page for the three reports below |
| [GrapeAncestry 167K demo](https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.batch.report.html) | v1.1 archive, unchanged |
| [GrapeReseq 8K demo](https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.8k.batch.report.html) | Same 28 seeds on the 8,044 shared sites |
| [167K vs 8K comparison](https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.167k_vs_8k.compare.html) | Side-by-side numbers and the verdict |

## Changes in v1.1

v1.1 adds a relationship graph for a batch of queries. The queries and the panel varieties they match are drawn on one graph, and those queries are placed together on PCA, ADMIXTURE, and the NJ tree. The figure is that graph from the 28-seed demo.

![v1.1 relationship graph](docs/guideline_shots/panels/v11_relationship_graph.png)

v1.1 new feature. Blue nodes are queries. Red nodes are panel varieties. Edge colour is the relationship class (identical, parent-offspring, full sib, and more distant). [Open the live report](https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.batch.report.html).

## Analysis flow

Input is FASTQ, BAM, or VCF. The pipeline trims and maps reads to VS-1, marks duplicates, and calls SNPs at the 167,433 target sites. It then performs QC, relatedness, PCA, ADMIXTURE, NJ, and aDNA damage calculations to build the interactive report.

![GrapeAncestry v1.1 flowchart](docs/flowchart_v1.1.png)

Overview of input, processing, analysis, and the interactive report. Reference data used in the analysis includes core genotypes, frozen PCA/ADMIXTURE references, VIVC passport, and OIV descriptors. Step map and claim boundaries: [`docs/FLOWCHART.md`](docs/FLOWCHART.md). VS-1: Dong et al. 2023 Science ([doi:10.1126/science.add8655](https://doi.org/10.1126/science.add8655)).

## Overview

- Takes FASTQ, a BAM already on VS-1, or a VCF at the 167K panel sites
- Places the sample on a frozen 2449-sample × 167K-site VS-1 panel
- Screens clones and parent-offspring, and reports IBS kinship against the panel
- Projects the sample onto frozen PCA axes and ADMIXTURE K=2–8, and draws an NJ tree
- Batch report includes the v1.1 relationship graph above, plus joint PCA, ADMIXTURE, and NJ placement
- Summarises aDNA damage for ancient samples
- Reports an OIV 225 berry-colour genomic score (score ≠ phenotype)
- Writes one self-contained HTML report per sample. The kit runs locally in Docker

## Usage

| Path | Action | Outcome |
|------|-------------|---------|
| Docker kit | Download `grapeancestry-v1.2.0-amd64.tar` from Zenodo Restricted ([doi:10.5281/zenodo.22868632](https://doi.org/10.5281/zenodo.22868632)), put next to `./start.sh`, run it | HTML report, UI http://127.0.0.1:8501, reports 8502 |
| Demo | [Open the v1.2 overview](https://xuzhen-li.github.io/grapeancestry/demo/results/ramos2019_np.reports.html). | View-only. Ramos-Madrigal et al. 2019, *Nat. Plants* ([doi:10.1038/s41477-019-0437-5](https://doi.org/10.1038/s41477-019-0437-5)) |
| DIY | Stage your own VS-1 and frozen 2449×167K assets (not in git). CLI: `pip install -e .` (see docs/USER_GUIDE.md §5) | Follow [`steps/`](steps/) `00a`–`13b` |

### Docker kit

1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/) or [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/). On Apple Silicon Macs, turn on x86_64/amd64 emulation in Docker Desktop settings.
2. Download this repository (green Code button, then Download ZIP) and the tar `grapeancestry-v1.2.0-amd64.tar` (~1.7 GB). Put the tar in the unzipped folder.
3. Mac: double-click `start.command`. Windows: double-click `start.bat`. Linux / terminal: `./start.sh`
4. The browser opens http://127.0.0.1:8501. First visit: set a local password. Then choose files, start the analysis, and open the report (port 8502). A copy is saved in `output/results/`.

Docker short command: `./start.sh` (macOS `start.command`, Windows `start.bat`) creates `input/` `output/` `settings/`, loads `grapeancestry:1.2.0` when the tar is present, and opens the UI. A docs-only clone without the tar cannot finish Analyze. Never `docker push` the fat image. Detail: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

v1 deliverable is `*.sample-first-v2.report.html` only (optional Cloud `chip.json` is not part of v1).

## Output

![First-time setup](docs/guideline_shots/ui/01-first-run-setup.png)

First run setup: local password, language, and threads (locks UI access only; does not encrypt data).

The file under `demo/results/` is the 28-seed batch report. Stills below are from the Ages report. The Docker kit also ships `HUN89_query` (panel id `HUN89` ≠ report stem `HUN89_query`). Walkthrough: [`docs/GUIDELINE.md`](docs/GUIDELINE.md). Cite Ages/V5: Noraz et al. 2026 *Nat Commun* ([doi:10.1038/s41467-026-70166-z](https://doi.org/10.1038/s41467-026-70166-z)). Cite the 28 seeds: Ramos-Madrigal et al. 2019 *Nat. Plants* ([doi:10.1038/s41477-019-0437-5](https://doi.org/10.1038/s41477-019-0437-5)).

![Sample validity](docs/guideline_shots/panels/01_sample_validity_01.png)

Sample validity: report metadata and method coverage for the Ages aDNA demo (V5; Noraz et al. 2026).

![Capture QC](docs/guideline_shots/panels/01_sample_validity_02.png)

Sample validity: capture QC (depth, calling, on-target) on the 167K sites.

![aDNA damage](docs/guideline_shots/panels/01_sample_validity_damage.png)

aDNA damage: terminal misincorporation and fragment-length patterns (Ages).

![Identity](docs/guideline_shots/panels/02_identity_01.png)

Identity: Ages clone and parent-offspring screen, and IBS kinship vs the frozen panel.

![PCA](docs/guideline_shots/panels/03_pca.png)

Population: query projected onto frozen GCTA64 PCA axes (VS-1 frame).

![ADMIXTURE](docs/guideline_shots/panels/03_admixture.png)

Population: ADMIXTURE using frozen Q/P for K=2–8 (no 2449+N refit).

![NJ](docs/guideline_shots/panels/03_nj.png)

Population: IBS neighbour-joining tree (use with identity tables).

![Sample evidence](docs/guideline_shots/panels/04_sample_evidence_01.png)

Sample evidence: only OIV 225 colour GS is decision-grade (score ≠ phenotype). SDR remains a proxy.

![LocusZoom](docs/guideline_shots/panels/05_locuszoom.png)

Panel research: LocusZoom regional panel map with query GT overlay (overlay ≠ "this sample was selected").

## Docs

| Doc | Role |
|-----|------|
| [`DATA_NOTICE.md`](DATA_NOTICE.md) | What is / is not in git; Docker tar policy |
| [`demo/`](demo/) | 28-seed batch HTML (view-only) |
| [`steps/`](steps/) | DIY `00a`–`13b` |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Start kit + browse; BAM/intake |
| [`docs/GUIDELINE.md`](docs/GUIDELINE.md) | How to read the report |
| [`docs/FAQ.md`](docs/FAQ.md) | First hour |
| [`docs/GLOSSARY.md`](docs/GLOSSARY.md) | Terms (167K vs 2449) |
| [`REPO_MAP.md`](REPO_MAP.md) | What each top-level folder holds |
| [`docs/CODE_AVAILABILITY.md`](docs/CODE_AVAILABILITY.md) | Git URL + Docker / Zenodo note |
| [`docs/FLOWCHART.md`](docs/FLOWCHART.md) | Flowchart claim caption |

## Author

Li Xuzhen, [ORCID 0000-0003-3670-6657](https://orcid.org/0000-0003-3670-6657)

Related: [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit), [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna), [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining)

## Earlier flowchart

![Earlier GrapeAncestry flowchart](docs/flowchart_vs1_analysis_v2.png)

Previous diagram. The current overview is under Analysis flow.