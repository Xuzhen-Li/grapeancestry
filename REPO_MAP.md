# Repository map

What lives in this public tree, and what does not.

## What a clone contains

| Surface | What you get |
|---------|----------------|
| **Public GitHub** | Docs, flowchart, Ages HTML, Python source. No VS-1, no 2449 panel, no fat image. |
| **Private tar + `start.sh`** | Full UI. Demos Ages + HUN89_query. FASTQ/BAM/VCF → V2 HTML. |
| **Cloud `chip.json`** | Optional Cloud path, not v1. |

grapevine **167K** public walkthrough (docs + Ages demo). Lab `src/` may exist in-tree but is **not** the newcomer default. Cross-panel *scaffold only*: [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit).

## Read this first (by goal)

| You want… | Go to |
|-----------|--------|
| Understand the product | [README.md](README.md) |
| See the pipeline picture | [FLOWCHART.md](docs/FLOWCHART.md) · `docs/flowchart_vs1_analysis_v2.png` |
| Screenshot walkthrough (Ages) | [GUIDELINE.md](docs/GUIDELINE.md) · `docs/guideline_shots/` |
| Open interactive demo HTML | [`demo/`](demo/) |
| Step docs (prep → report → cloud) | [`steps/`](steps/) |
| Which script / module does what | [SCRIPTS.md](docs/SCRIPTS.md) |
| Science / claim rules | [PIPELINE.md](docs/PIPELINE.md) · [ANALYSIS_METHODS.md](docs/ANALYSIS_METHODS.md) |
| How to start (Docker kit / Demo / DIY) | [USER_GUIDE.md](docs/USER_GUIDE.md) |
| Optional Cloud JSON | [CHIP_COMPANION.md](docs/CHIP_COMPANION.md) |
| Add another crop panel | [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit) |

## Top-level folders

| Path | What it is | What it is not |
|------|------------|----------------|
| **`config/`** | YAML for local/HPC demos (`samples_ages.yaml`, …) | No cloud secrets |
| **`data/`** | **Placeholders + READMEs** for where to stage assets | **No** FASTQ, VS-1 fasta, or 2449×167K dosage in git |
| **`demo/`** | Ages sample-first HTML (view-only) + Plotly/D3/LocusZoom `assets/` | Not a full panel matrix; not FASTQ |
| **`steps/`** | DIY step curriculum `00a`–`13b` (+ optional `14*`) | Not the runnable engines |
| **`docs/`** | Human docs: GUIDELINE, flowchart, methods, FAQ, SCRIPTS | Not the runnable engines; DIY steps live in root `steps/` |
| **`input/`** | Host mount from `start.sh`; FASTQ / BAM / VCF land here | Empty in git; not panel dosage |
| **`output/`** | Host mount from `start.sh`; run results land here | Empty in git; not committed lab dumps |
| **`results/`** | Local run outputs (gitignored content) | Empty on a fresh clone |
| **`scripts/`** | Thin wrappers / ADMIXTURE paste / pack builders | Prefer package modules for new work |
| **`settings/`** | Host mount from `start.sh`; local UI auth (`auth.json`) | UI lock only; empty in git |
| **`src/`** | Python package under `src/grapeancestry/` (CLI `grapeancestry`) | Not species-agnostic kit SPI (that is the kit repo) |
| **`tests/`** | Placeholder for tests (`.gitkeep` only) | Empty of test files in git |
| **`workflow/`** | Snakemake skeleton (map → call at panel BED) | Not a full HPC dump of every lab job |

## Top-level files

| Path | What it is | What it is not |
|------|------------|----------------|
| **`README.md`** | Public homepage (`# GrapeAncestry`) | Not the step curriculum |
| **`DATA_NOTICE.md`** | What is / is not in git; Docker tar policy | Not a license text |
| **`LICENSE`** | Project license | Not the Zenodo access terms |
| **`REPO_MAP.md`** | This file — folder / file roles | Not the step curriculum |
| **`app.py`** | Streamlit / UI entry when you run the companion UI | Not required to read docs or open `demo/` |
| **`Dockerfile`** | Image build recipe for the companion UI stack | Not a substitute for the Zenodo fat tar alone |
| **`docker-compose.yml`** | Compose wiring for local UI / report ports | Not the Zenodo distribution channel |
| **`start.sh`** | Loads `grapeancestry:1.0.0`, UI `:8501`, reports `:8502` | Not a docs-only substitute for the fat image |
| **`start.command`** | macOS wrapper for `start.sh` | Not a Windows launcher |
| **`start.bat`** | Windows wrapper for `start.sh` | Not a macOS launcher |
| **`pyproject.toml`** | Package metadata / install entry for `grapeancestry` | Not runtime panel assets |
| **`requirements.txt`** | Pip deps for local / image Python | Not HPC conda pins |
| **`requirements-cloud.txt`** | Pip deps for optional Cloud path | Not v1 Docker kit deps |
| **`environment.yml`** | Conda env for local demos | Not the HPC-full pin set |
| **`environment-hpc.yml`** | Conda env pins for HPC-style runs | Not the minimal local demo env |
| **`.gitignore`** | Git ignore rules for local/generated paths | Not Docker build context rules |
| **`.dockerignore`** | Docker build context ignore rules | Not git ignore rules |

## `src/grapeancestry/` domains

| Package | Role |
|---------|------|
| `core/` | Dosage cache, QC, merge/gate/lift helpers |
| `identity/` | IBS, kinship, clone/PO, fingerprint |
| `adna/` | aDNA project, damage, ADMIXTURE project helpers |
| `popgen/` | f-stats, selection scans, GEA, NJ helpers |
| `breeding/` | GWAS / GS / phenotype helpers (OIV 225 decision-grade; others exploratory) |
| `report/` | Payload + sample-first V2 HTML builders |
| `cloud/` | Query-VCF path → `chip.json` |
| `resource/` | Panel/export/portal helpers |
| `cli.py` | `grapeancestry` entry |

## `steps/` bands

| Band | IDs | Meaning |
|------|-----|---------|
| Data prep (once per panel) | `00a`–`00g` | Sites, VS-1, dosage, frozen PCA/ADMIXTURE, phenotypes, cloud pack |
| Map & call | `01a`–`01b` | Trim/map → markdup/call at 167K |
| QC | `02a`–`02b` | Capture QC, calling rates |
| Identity | `03a`–`03b` | Clone/PO, IBS ranks |
| Placement | `04*`–`06*` | Frozen PCA, ADMIXTURE, NJ |
| aDNA extras | `07*` | mapDamage / plots |
| Panel research | `08*`–`12*` | f-stats, Fst, GWAS, GS, LocusZoom |
| Hand-ins | `13*`–`14*` | Sample-first HTML · cloud `chip.json` |

Index: [steps/README.md](steps/README.md).

## What is *not* in git

- Panel dosage matrices, reference genomes, FASTQ/BAM/CRAM  
- Full private lab results under `results/`  
- Unpublished genotypes  

Stage those under `data/` locally; see `data/MANIFEST.md` and `data/*/README.md`.

## Kit vs this repo

| Repo | Owns |
|------|------|
| **grapeancestry** (this) | Grapevine 167K walkthrough, GUIDELINE, Ages demo, step docs, grape-specific runnable modules |
| **gtbs-chip-service-kit** | Species-agnostic GBTS scaffold + profile contract only |
