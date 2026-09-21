# Repository map

What lives in this public tree, and what does not. Use this when the folder list feels crowded.

## Honest status

| Surface | What you get |
|---------|----------------|
| **Public GitHub** | Docs, flowchart, Ages HTML, Python source. No VS-1, no 2449 panel, no fat image. |
| **Private tar + `start.sh`** | Full UI. Demos Ages + HUN89_query. FASTQ/BAM/VCF → V2 HTML. |
| **Cloud `chip.json`** | Optional Cloud path, not v1. |

**One-line role:** grapevine **167K** public walkthrough (docs + Ages demo). Lab `src/` may exist in-tree but is **not** the newcomer default. Cross-panel *scaffold only*: [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit).

## Read this first (by goal)

| You want… | Go to |
|-----------|--------|
| Understand what the product is | [README.md](../README.md) → *What this is* |
| See the pipeline picture | [FLOWCHART.md](FLOWCHART.md) · `flowchart_vs1_analysis_v2.png` |
| Screenshot walkthrough (Ages) | [GUIDELINE.md](GUIDELINE.md) · `guideline_shots/` |
| Open interactive demo HTML | [`demo/`](../demo/) |
| Step docs (prep → report → cloud) | [`steps/`](steps/) |
| Which script / module does what | [SCRIPTS.md](SCRIPTS.md) |
| Science / claim rules | [PIPELINE.md](PIPELINE.md) · [ANALYSIS_METHODS.md](ANALYSIS_METHODS.md) |
| Onboarding / doors A–D | [USER_GUIDE.md](USER_GUIDE.md) |
| Optional Cloud JSON | [CHIP_COMPANION.md](CHIP_COMPANION.md) |
| Add another crop panel | [`../profiles/`](../profiles/) · kit repo above |

## Top-level folders

| Path | What it is | What it is not |
|------|------------|----------------|
| **`docs/`** | Human docs: GUIDELINE, step MDs, flowchart, methods | Not the runnable engines |
| **`demo/`** | Ages sample-first HTML + Plotly/D3/LocusZoom `assets/` | Not a full panel matrix; not FASTQ |
| **`src/grapeancestry/`** | Python package (CLI `grapeancestry`, domains below) | Not species-agnostic kit SPI (that is the kit repo) |
| **`workflow/`** | Snakemake skeleton (map → call at panel BED) | Not a full HPC dump of every lab job |
| **`scripts/`** | Thin wrappers / ADMIXTURE paste / pack builders | Prefer package modules for new work |
| **`config/`** | YAML for local/HPC demos (`samples_ages.yaml`, …) | No cloud secrets |
| **`profiles/`** + **`templates/`** | Grapevine 167K profile hooks | Cross-crop profiles → **kit**, not here |
| **`platform/`** | Grapevine lab seam notes | **Not** kit SPI; kit has its own thin `platform/` |
| **`templates/`** | Starting `profile.yaml` + claims scaffold | Copy out → `profiles/<id>/` |
| **`chip/`** | Pointers to 167K chip *design* notes | Design detail may also live under grapeancestry `chip/` history |
| **`analysis/`** | Small analysis notes / pointers | Not the main step curriculum (`docs/steps/`) |
| **`data/`** | **Placeholders + READMEs** for where to stage assets | **No** FASTQ, VS-1 fasta, or 2449×167K dosage in git |
| **`bin/`** | Lab helper binaries (ADMIXTURE, GCTA) when present | Optional; self-supply on some clones |
| **`results/`** | Local run outputs (gitignored content) | Empty on a fresh clone |
| **`app.py`** | Streamlit / UI entry when you run the companion UI | Not required to read docs or open `demo/` |

Root also has `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `requirements*.txt`, `environment*.yml`, `LICENSE`.

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

## `docs/steps/` bands

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
