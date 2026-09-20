# grapeancestry

Analysis companion for the grapevine **167K capture panel** — interactive reports and Chip Companion, not a black-box whole-genome resequencing suite.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## What this is

GrapeAncestry places a **new grapevine query** against a **frozen 2449 × 167K** reference built on the **VS-1** genome. From the same sample you can read capture QC, identity and kinship screens, PCA and ADMIXTURE placement on frozen axes, an IBS neighbour-joining tree, passport-style cards, and — where the evidence supports ranking — a colour genomic-selection score.

The scientific frame is fixed on purpose. Coordinates and calling use **VS-1**. Your input is FASTQ, BAM/CRAM already on VS-1, or a **query VCF at the 167K sites**. That query VCF uses the same sites as the chip; it is **not** the 2449-panel dosage matrix. PCA axes and ADMIXTURE Q/P are **frozen**; new samples are projected (`admixture -P` in the lab image, or NNLS on Cloud), not used to refit the panel. Today only **OIV 225** colour GS is treated as decision-grade; other traits and flower-sex / selection narratives stay exploratory (full rules in the GUIDELINE).

**ID trap:** panel row `HUN89` ≠ report stem `HUN89_query` (independent FASTQ recapture). Do not strip `_query` to look up passport or frozen Q.

This public GitHub tree is the **docs face** first. A runnable CLI, Docker customer image, VS-1, and large matrices land in later releases.

## Tonight hand-in

| Door | Hand-in |
|------|---------|
| **Cloud** | `chip.json` |
| **Suite** (Docker / lab suite) | `*.sample-first-v2.report.html` |
| **This docs tree alone** | read only — no hand-in file |

Hand-in is a **filename**, not every sidebar tab.

## Install and use

Full step-by-step: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md). Short version below.

### A · This docs tree (today)

1. Open [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) for onboarding.
2. Open [`docs/GUIDELINE.md`](docs/GUIDELINE.md) for the demo screenshot walkthrough (incl. LocusZoom).
3. Optional diagram: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).

No `grapeancestry` binary, VS-1, or 2449 dosage cache ships in this clone yet.

### B · Customer Docker image (when you have the package)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). On Apple Silicon use **linux/amd64**.
2. Unpack the customer package so `start.sh` (or `start.command`) sits next to `input/`, `output/`, `settings/`.
3. Run:

```bash
./start.sh
# macOS: double-click start.command
```

4. Browser opens **http://localhost:8501** — first visit: set password / language / threads; later: password only.
5. Put FASTQ, BAM/CRAM (**VS-1** contigs), or a 167K-site query VCF in `./input` → **Analysis** → live log → open the V2 HTML (often port **8502**) or download it.
6. Hand-in file: `*.sample-first-v2.report.html` (also under `output/results/` with `output/assets/`).

BAM tip: if `@SQ` looks like `chr1` / 12X / PN40024, the job fails — start from FASTQ or re-align to VS-1.

### C · Cloud Chip Companion (classroom)

1. Upload a **167K-site query VCF** (not FASTQ) in Streamlit.
2. Hand in **`chip.json`.
3. Notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

### D · Local lab suite (developers with private checkout)

If you already have a finished demo HTML next to `assets/`:

```bash
cd /path/to/local-suite   # not this docs-only clone
python -m http.server
# http://localhost:8000/results/HUN89_query.sample-first-v2.report.html
```

`http.server` is **view-only** — it does not create a hand-in file. End-to-end `grapeancestry run` needs conda env `ga` + panel assets; see USER_GUIDE / suite README when you have that tree.

## Demo

**Demo sample:** `HUN89_query` — modern PE recapture of the panel variety story behind `HUN89`. Same biology narrative, **different file identity** (see ID trap above).

**What the demo report walks:**

1. Sample validity — provenance, capture QC, damage note
2. Identity — clone / PO / IBS neighbors (pin a row to overlay plots)
3. Population — frozen PCA · ADMIXTURE K=2–8 · NJ
4. Sample evidence — MAS / trait cards; only **OIV 225** colour GS is decision-grade
5. Panel research + **LocusZoom** — 2449 context; query GT is overlay only
6. Methods / Downloads

**How to see it today**

- **On this GitHub tree:** follow the long screenshots in [`docs/GUIDELINE.md`](docs/GUIDELINE.md) (article-style intros + every panel).
- **With a local suite HTML:** use the `http.server` command in Install §D.
- **With the Docker image:** sidebar → **Demos** → `HUN89_query` / Ages.

**Three preview frames** (full set in GUIDELINE):

![Sample validity](docs/guideline_shots/panels/01_sample_validity_01.png)

*Sample validity — metadata, method coverage, conclusions.*

![PCA](docs/guideline_shots/panels/03_pca.png)

*Population placement — query (black star) on frozen GCTA64 PCA.*

![LocusZoom](docs/guideline_shots/panels/05_locuszoom.png)

*LocusZoom — panel GWAS map + this query genotype overlay (OIV 225 example).*

## Analysis flow

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses → report or `chip.json`.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid arrows stop at tonight's hand-in (`*.sample-first-v2.report.html` / `chip.json`). Dashed = how you read the report. Detail: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

## Related

[grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome) · [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip)

No unpublished genotypes or full 2449 matrices in this public tree. **Xuzhen Li** · [ORCID](https://orcid.org/0000-0003-3670-6657)
