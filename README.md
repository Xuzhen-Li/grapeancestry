# grapeancestry

Analysis companion for the grapevine **167K capture panel**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

**Status:** documentation and demo walkthrough are live. Full pipeline code, Streamlit Cloud deploy, and large panel matrices land in later commits — do not expect `grapeancestry run` from this repo yet.

## Start here

→ **[`docs/GUIDELINE.md`](docs/GUIDELINE.md)** — three VS-1 inputs (FASTQ / BAM / query VCF), claim boundaries, and a full sidebar walkthrough with long screenshots.

Analysis diagram: [`docs/flowchart_vs1_analysis_v2.png`](docs/flowchart_vs1_analysis_v2.png) · [`docs/FLOWCHART.md`](docs/FLOWCHART.md).

## Tonight — two doors

| Door | Audience | Tonight deliverable | Not tonight |
|------|----------|---------------------|-------------|
| **Cloud** | Upload 167K VCF → Streamlit | `chip.json` | Docker / HPC / ADMIXTURE binary / full FASTQ pipeline |
| **Suite** | Local `grapeancestry run` + report | `*.sample-first-v2.report.html` | Claiming OIV 241 / seedlessness / haplotype sex |

> **ID trap:** Panel demo `HUN89` (2449-row ID) ≠ capture demo `HUN89-capture` / report stem `HUN89_query` (independent FASTQ recapture). Do not treat the recapture as the panel ID.

## What you get (scan order)

1. QC  
2. Self-vs-clone IBS / identity  
3. Passport / SDR **proxy** (not Science H1–H5 haplotype sex) / trait card  
4. Purity screen & parentage (screens, not final calls)  
5. Advanced: f3/f4, local ancestry, NJ, GEA/Fst, impute  
6. **Colour GS last** — only OIV 225 is currently rankable  

## Decision / explore / do-not-claim

| Class | Trait / claim | Rule |
|-------|---------------|------|
| Decision-grade | OIV 225 colour GS | May rank when policy + evidence say so |
| Exploratory | OIV 241, unbalanced case/control | Demo only; never parent ranking / seedlessness claim |
| Do not claim | SDR = haplotype sex; query GT = selection | SDR = unphased window **proxy**; selection overlay ≠ “this sample was selected” |
| Reminder | Model score | **Score ≠ observed phenotype** |

## Walk the demo

Full walkthrough: [`docs/GUIDELINE.md`](docs/GUIDELINE.md). Screenshots below are from the local suite demo report (`HUN89_query.sample-first-v2.report.html`).

### Sidebar + overview

![Sidebar and overview](docs/guideline_shots/01_sidebar_overview.png)

### PCA

![PCA](docs/guideline_shots/04_pca.png)

### ADMIXTURE

![ADMIXTURE](docs/guideline_shots/05_admixture.png)

## Layout

| Path | Role |
|------|------|
| [`docs/`](docs/) | GUIDELINE, Chip Companion, demo screenshots |
| [`chip/`](chip/) | Probe / SNP selection for 167K and follow-ons (design files land later) |
| [`analysis/`](analysis/) | Calling and report recipes when filled |

The old standalone shell [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip) redirects to `chip/`.

## This is not

- Not an aDNA authentication pipeline → [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna)
- Not theory dossiers → [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining)
- Not a nuclear pangenome / PAV graph → [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome)

## Privacy

No unpublished genotypes, private coordinates, or full 2449 panel matrices in this public tree.

## Author

**Xuzhen Li** · [ORCID 0000-0003-3670-6657](https://orcid.org/0000-0003-3670-6657)
