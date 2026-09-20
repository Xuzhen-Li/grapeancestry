# grapeancestry

Analysis companion for the grapevine **167K capture panel** — interactive reports and Chip Companion, not a black-box whole-genome resequencing suite.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## Analysis flow

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses → report or `chip.json`.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid arrows stop at tonight's hand-in (`*.sample-first-v2.report.html` / `chip.json`). Dashed = how you read the report. Detail: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

## What's in this repository

The public tree grew on purpose: **docs + Ages demo + runnable grapevine companion**. Folder-by-folder map: [`docs/REPO_MAP.md`](docs/REPO_MAP.md).

| Area | Path | One-line description |
|------|------|----------------------|
| Product story + flowchart | `README` · [`docs/FLOWCHART.md`](docs/FLOWCHART.md) | 167K companion on VS-1; three inputs → report / `chip.json` |
| Screenshot walkthrough | [`docs/GUIDELINE.md`](docs/GUIDELINE.md) | Ages sidebar panels (incl. LocusZoom) |
| Interactive demo | [`demo/`](demo/) | Ages `*.sample-first-v2.report.html` + `assets/` |
| Fine-grained steps | [`docs/steps/`](docs/steps/) | `00a`–`14b`: prep → map/call → QC → identity → placement → report/cloud |
| Script / module index | [`docs/SCRIPTS.md`](docs/SCRIPTS.md) | CLI, Snakefile, domains, report/cloud builders |
| Methods & science rules | [`docs/ANALYSIS_METHODS.md`](docs/ANALYSIS_METHODS.md) · [`docs/PIPELINE.md`](docs/PIPELINE.md) | What each analysis does; claim grades |
| Onboarding doors | [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) · [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md) | Docs-only · Docker · Cloud · local suite |
| Python package | `src/grapeancestry/` | CLI `grapeancestry` (`core` · `identity` · `adna` · `popgen` · `breeding` · `report` · `cloud`) |
| Orchestration | `workflow/` · `scripts/` · `config/` | Snakemake + wrappers + sample YAMLs |
| Panel profile hooks | `profiles/` · `templates/` | Swap sites/reference/frozen axes for another chip |
| Platform seams | `platform/` | Notes for pipeline / report / viz / cloud doors |
| Chip design pointer | `chip/` | 167K design door (not the kit scaffold) |
| Local staging | `data/` · `bin/` · `results/` | READMEs / optional binaries; **matrices & FASTQ not in git** |

**Cross-panel scaffold** (not grape walkthrough): [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit).

## Analysis methods

Narrative methods and science contracts: [`docs/ANALYSIS_METHODS.md`](docs/ANALYSIS_METHODS.md) · [`docs/PIPELINE.md`](docs/PIPELINE.md). Step pages under [`docs/steps/`](docs/steps/) name scripts, statistical outputs, and visualizations for each band (`00*` prep · `01*`–`13*` suite · `14*` cloud).

## What this is

GrapeAncestry places a **new grapevine query** against a **frozen 2449 × 167K** reference built on the **VS-1** genome. From the same sample you can read capture QC, identity and kinship screens, PCA and ADMIXTURE placement on frozen axes, an IBS neighbour-joining tree, passport-style cards, and — where the evidence supports ranking — a colour genomic-selection score.

The scientific frame is fixed on purpose. Coordinates and calling use **VS-1**. Your input is FASTQ, BAM/CRAM already on VS-1, or a **query VCF at the 167K sites**. That query VCF uses the same sites as the chip; it is **not** the 2449-panel dosage matrix. PCA axes and ADMIXTURE Q/P are **frozen**; new samples are projected (`admixture -P` in the lab image, or NNLS on Cloud), not used to refit the panel. Today only **OIV 225** colour GS is treated as decision-grade; other traits and flower-sex / selection narratives stay exploratory (full rules in the GUIDELINE).

**ID trap:** panel row `HUN89` ≠ report stem `HUN89_query` (independent FASTQ recapture). Do not strip `_query` to look up passport or frozen Q.

This public tree includes the **docs face**, the **Ages demo HTML**, and the **runnable** `grapeancestry` package. **VS-1, FASTQ, and the 2449 × 167K dosage cache are not shipped** — stage them under `data/` locally (see [`docs/REPO_MAP.md`](docs/REPO_MAP.md)).

## Tonight hand-in

| Door | Hand-in |
|------|---------|
| **Cloud** | `chip.json` |
| **Suite** (Docker / lab suite) | `*.sample-first-v2.report.html` |
| **This docs tree alone** | read only — no hand-in file |

Hand-in is a **filename**, not every sidebar tab.

## Demo

**Primary demo:** `Ages` — ancient SE library from archaeological grape material labeled **V5** in the source study (Iron Age Martigues, southern France, ~300–200 BCE). Suite config: `config/samples_ages.yaml` → FASTQ `V5xL1xP2_Ages_3_5070.12Xv2.realigned.fastq.gz` → AdapterRemoval + `bwa aln` on **VS-1** → 167K call → `Ages.sample-first-v2.report.html`.

**Cite the source data (required):** Noraz, R., … & **Orlando, L.** (2026). Ancient DNA reveals 4000 years of grapevine diversity, viticulture and clonal propagation in France. *Nature Communications*. [https://doi.org/10.1038/s41467-026-70166-z](https://doi.org/10.1038/s41467-026-70166-z). Sample **V5** is discussed there as an Iron Age Martigues pip with domesticated-like ancestry.

This demo shows the **aDNA** door of the companion (damage module meaningful; modern PE demos are separate). Hand-in name remains `Ages.sample-first-v2.report.html` when you run Suite / Docker.

**What the Ages report walks:**

1. Sample validity — provenance, capture QC, **aDNA damage** note
2. Identity — IBS / kinship vs the frozen 2449 panel
3. Population — frozen PCA · ADMIXTURE K=2–8 · NJ
4. Sample evidence — MAS / trait cards; only **OIV 225** colour GS is decision-grade
5. Panel research + **LocusZoom** — 2449 context; query GT is overlay only
6. Methods / Downloads

**How to open it**

- **In this repo (complete HTML):** [`demo/results/Ages.sample-first-v2.report.html`](demo/results/Ages.sample-first-v2.report.html) — keep `demo/assets/` beside `demo/results/`. Notes: [`demo/README.md`](demo/README.md).

```bash
cd demo
python -m http.server 8000
# http://localhost:8000/results/Ages.sample-first-v2.report.html
```

- **Screenshot walkthrough:** [`docs/GUIDELINE.md`](docs/GUIDELINE.md).
- **Docker image:** sidebar → **Demos** → Ages.

**Preview frames** (cropped from Ages full-section long screenshots; fuller set in GUIDELINE):

![Ages sample validity](docs/guideline_shots/panels/01_sample_validity_01.png)

*Sample validity — report metadata / method coverage (Ages aDNA).*

![Ages conclusions and QC](docs/guideline_shots/panels/01_sample_validity_02.png)

*Sample validity — conclusions and capture QC cards.*

![Ages aDNA damage](docs/guideline_shots/panels/01_sample_validity_damage.png)

*aDNA damage — mapDamage misincorporation + fragment length (Ages SE).*

![Ages identity](docs/guideline_shots/panels/02_identity_01.png)

*Identity — clone/PO screen and IBS / kinship vs the frozen panel.*

![Ages PCA](docs/guideline_shots/panels/03_pca.png)

*Population — Ages query on frozen GCTA64 PCA.*

![Ages ADMIXTURE](docs/guideline_shots/panels/03_admixture.png)

*Population — Ages projected on frozen ADMIXTURE K=8.*

![Ages NJ](docs/guideline_shots/panels/03_nj.png)

*Population — IBS neighbour-joining tree with Ages marked.*

![Ages sample evidence](docs/guideline_shots/panels/04_sample_evidence_01.png)

*Sample evidence — passport / MAS cards; only OIV 225 colour GS is decision-grade.*

![Ages LocusZoom](docs/guideline_shots/panels/05_locuszoom.png)

*Panel research — LocusZoom + Ages genotype overlay.*

## Install and use

Full step-by-step: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md). Short version below.

### A · This docs tree (today)

1. Folder map (what all the new paths mean): [`docs/REPO_MAP.md`](docs/REPO_MAP.md).
2. Open [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) for onboarding.
3. Open [`docs/GUIDELINE.md`](docs/GUIDELINE.md) for the demo screenshot walkthrough (incl. LocusZoom).
4. Diagram: [`docs/FLOWCHART.md`](docs/FLOWCHART.md) · steps: [`docs/steps/`](docs/steps/).
5. Script / methods map: [`docs/SCRIPTS.md`](docs/SCRIPTS.md) · [`docs/ANALYSIS_METHODS.md`](docs/ANALYSIS_METHODS.md) · [`docs/PIPELINE.md`](docs/PIPELINE.md).
6. Interactive Ages HTML: [`demo/`](demo/).

The `grapeancestry` package is in `src/`; after `pip install -e .` the CLI is available. **VS-1 and the 2449 dosage cache still do not ship** — stage under `data/` (see USER_GUIDE / `data/MANIFEST.md`).

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
2. Hand in **`chip.json`**.
3. Notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

### D · Local lab suite (developers with private checkout)

If you already have a finished demo HTML next to `assets/`:

```bash
cd /path/to/local-suite   # not this docs-only clone
python -m http.server
# http://localhost:8000/results/Ages.sample-first-v2.report.html
```

`http.server` is **view-only** — it does not create a hand-in file. End-to-end `grapeancestry run` needs conda env `ga` + panel assets; see USER_GUIDE / suite README when you have that tree.

## Related

[grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome) · [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip)

No unpublished genotypes or full 2449 matrices in this public tree. **Xuzhen Li** · [ORCID](https://orcid.org/0000-0003-3670-6657)
