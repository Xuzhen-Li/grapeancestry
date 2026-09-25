# Script map (detailed)

This repository now ships both the **grapevine 167K docs and Ages demo** (docs + Ages demo HTML) and the **Python package** under `src/grapeancestry/`. The same modules are the template for **other GBTS / capture panels**: keep code generic at the CLI/domain layer; swap sites, reference, and frozen axes through `config/` (cross-crop profiles → [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit)).

## Repository map

Folder roles and what is not in git: **[REPO_MAP.md](../REPO_MAP.md)**.

## Step-by-step docs

One markdown per analysis step (scripts · stats · viz): **[steps/README.md](../steps/README.md)**.


[Xuzhen-Li/gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit).  
**Not in git:** panel dosage matrices, FASTQ/BAM, reference genomes — stage under `data/` locally (see `data/MANIFEST.md` and `data/*/README.md`).

## How modules map to “any chip”

| Your chip needs | This kit’s hook | Example (grapevine 167K) |
|-----------------|-----------------|---------------------------|
| Site list | BED / sites file in profile | `data/panel/panel167k.sites.bed` |
| Coordinate system | Reference fasta | VS-1 |
| Reference panel | Panel VCF → dosage `npz` | 2449 × 167K |
| Placement | Frozen PCA + ADMIXTURE P | `panel167k_nogwas` |
| Hand-in | Sample-first HTML and/or `chip.json` | `*.sample-first-v2.report.html` |

CLI entry: `grapeancestry` (`src/grapeancestry/cli.py`) after `pip install -e .`.

---

## A · Full pipeline (FASTQ/BAM/VCF → panel sites)

### Orchestration

| Piece | Path | Role |
|-------|------|------|
| CLI group | `src/grapeancestry/cli.py` | `run`, `analyze`, `qc`, `identity`, `project`, `admix-project`, `gwas`, `gs-train`, `gs-predict`, `cross-recommend`, `chip-report`, `selection`, `gea`, `impute`, `catalog`, `locus-search`, `seq-score` |
| Snakemake | `workflow/Snakefile` | Mapping → markdup → `bcftools` call at panel BED |
| Config | `config/mbp_demo.yaml`, `config/hpc_full.yaml`, `config/samples_*.yaml` | Threads, paths, PE vs aDNA |

### Mapping → VCF (inside `run` / Snakefile)

| Step | Modern PE | aDNA SE | Code |
|------|-----------|---------|------|
| Trim | `fastp` | AdapterRemoval3 | workflow + `cli.run` |
| Map | `bwa mem` | `bwa aln` + `samse` | same |
| Markdup | `samtools markdup` | same | same |
| Call | `bcftools mpileup/call -T` sites BED | same | → `results/{sample}.vcf.gz` |
| Damage | — | mapDamage2 / lite | `src/grapeancestry/adna/damage_lite.py` |

### Core library

| Module | Path | Role |
|--------|------|------|
| Dosage cache | `src/grapeancestry/core/dosage.py` | Build/load panel dosage `npz` (analysis matrix) |
| QC | `src/grapeancestry/core/qc.py` | On-target, breadth, calling rate |
| Merge ref | `src/grapeancestry/core/merge_ref.py` | Optional 2449+query VCF artifact |
| Gate / subref | `src/grapeancestry/core/gate.py`, `subref.py`, `lift.py` | Concordance gate for accelerated mapping |

### Identity / placement / popgen / breeding

| Domain | CLI | Primary modules |
|--------|-----|-----------------|
| IBS / kinship / PO | `grapeancestry identity` | `src/grapeancestry/identity/run_ibs.py`, `ibs.py`, `parentage.py`, `fingerprint.py` |
| PCA project | `grapeancestry project` | `adna/project.py`, `pca_lock.py`, `smartpca_project.py` (+ `gcta64` on PATH) |
| ADMIXTURE project | `grapeancestry admix-project` | `adna/admix_project.py`, `admixture.py` (+ `admixture` 1.3.0 on PATH) |
| Selection / Fst | `grapeancestry selection` | `adna/selection.py`, `popgen/selection_report.py`, `popgen/stats.py` |
| f3/f4 | (report path) | `adna/fstats.py`, `popgen/fstats_report.py` |
| NJ tree | (report path) | `popgen/tree_nj.py` |
| Selection viz | (report path) | `popgen/selection_viz.py`, `selscan.py` |
| GEA | `grapeancestry gea` | `popgen/gea.py` |
| GWAS | `grapeancestry gwas` | `breeding/gwas.py`, `mixed_model.py` |
| GS | `gs-train` / `gs-predict` | `breeding/gs.py`, `gs_models.py`, `dl.py` |
| Cross | `cross-recommend` | `breeding/cross.py` |
| Phenotype ETL helpers | — | `breeding/phenotype.py`, `scripts/build_phenotype.py` |

### Typical commands

```bash
python3 -m venv .venv && source .venv/bin/activate  # or your lab env
pip install -e ".[dev,web]"
export PATH="$PWD/bin:$PATH"

# Example profile: aDNA Ages (needs local FASTQ + VS-1 + panel cache)
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_ages.yaml --sample Ages -j 4

# From existing query VCF at panel sites
grapeancestry analyze --sample Ages
grapeancestry chip-report --vcf results/Ages.vcf.gz --out chip.json
```

---

## B · Visualization

| Output | Builder | Notes |
|--------|---------|-------|
| Interactive PCA / ADMIXTURE / NJ / LocusZoom | `report/interactive_dashboard.py` + `report/interactive_data.py` | Plotly/D3/LocusZoom from `assets/` when present (see grapeancestry `demo/assets`) |
| Static PNG cards | `src/grapeancestry/report/build_report.py` (matplotlib → base64) | Italy-style figures |
| Selection Manhattan / heat | `popgen/selection_viz.py` | Panel Grp-vs-rest; query GT overlay only |
| Damage / fragment length | `adna/damage_lite.py` | aDNA door |
| Cloud Streamlit plots | `cloud/plot.py`, root `app.py` | VCF → cards |
| Lab ADMIXTURE QC plots | `scripts/plot_science_k8_check.py`, `plot_k2_k10_purest_align.py` | Archive QC, not the v1 product HTML |

Viz contracts live in `src/grapeancestry/` (cross-crop scaffold → [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit)).

---

## C · Report production

| Hand-in | Builder | Entry |
|---------|---------|-------|
| `{sample}.sample-first-v2.report.html` | `src/grapeancestry/report/build_report.py` (`build_bundle`, `render_full_html`) + `interactive_dashboard.py` | `run` / `analyze` → `grapeancestry analyze` / `run` |
| Optional `*.report.data.json` sidecar | same bundle | downloads section |
| `chip.json` | `cloud/analyze.py` | `grapeancestry chip-report` / Streamlit |
| Cloud pack | `scripts/build_cloud_pack.py`, `python -m grapeancestry.cloud` | fingerprints for Cloud |

V2 contract: provenance IDs, artifact list, method coverage (available/unavailable). Theme Light/Dark/System.

---

## D · Lab-only / panel-archive scripts (`scripts/`)

| Script | Role |
|--------|------|
| `prep_admixture_bed.py`, `run_admixture_local.sh`, `submit_admixture_k*.sh` | Fit frozen ADMIXTURE archives on HPC |
| `admixture_fit_qc.py`, `ingest_admixture_qp.py`, `rebuild_manual_qp.py` | Ingest Q/P into suite layout |
| `build_phenotype.py`, `extract_table_s17.py` | Phenotype ETL |
| `build_cloud_pack.py` | Pack Cloud fingerprints |

---

## E · Adding another chip (checklist)

1. Cross-crop profiles / scaffold: [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit) (not in this repo).  
2. Stage reference, sites BED, panel VCF → build dosage cache via `python -m grapeancestry.core.dosage …`.  
3. Point `config/*.yaml` `paths:` at your files (or add a new config profile).  
4. Freeze PCA/ADMIXTURE for *your* panel; do not unsupervised-refit panel+customer each night.  
5. Declare decision-grade traits in profile `CLAIMS.md` (kit profile contract).  
6. Keep matrices out of git; document them in a local `MANIFEST.md`.

---

## Claim boundaries (short)

- Decision-grade vs exploratory is **profile-defined** (grapevine example: only OIV 225 colour GS).  
- Selection / sex proxies / f-stats are exploratory unless the profile says otherwise.  
- Query GT on panel maps is overlay ≠ “this sample was selected.”  
- ID trap pattern: panel row ID ≠ independent recapture report stem (`*_query`).
