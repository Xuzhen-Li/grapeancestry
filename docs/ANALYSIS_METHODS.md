# Analysis methods and script map

This page summarizes **how GrapeAncestry analyzes a query** and **which suite modules own each step**.  
The runnable Python package lives in the private lab suite today; this public tree ships the **docs face**, the **Ages demo HTML**, and this map. Module paths below are suite layout (`src/grapeancestry/…`).

Related: [`PIPELINE.md`](PIPELINE.md) (science contracts) · [`FLOWCHART.md`](FLOWCHART.md) · [`GUIDELINE.md`](GUIDELINE.md) · demo HTML [`../demo/`](../demo/).

## End-to-end idea

**Three inputs → one genome frame → 167K sites → frozen-panel analyses → hand-in.**

| Input | Mapping / call | Hand-in |
|-------|----------------|---------|
| FASTQ (modern PE or aDNA SE) | trim → map **VS-1** → markdup → `bcftools` `-T` 167K BED | `*.sample-first-v2.report.html` |
| BAM/CRAM already on VS-1 | markdup → call at 167K | same |
| Query VCF (sites ∩ 167K on VS-1) | analyses only | Suite HTML **or** Cloud `chip.json` |

Coordinates and calling use **VS-1**. PCA / ADMIXTURE use a **frozen 2449** reference (`panel167k_nogwas`). New samples are **projected**, not used to refit the panel. Only **OIV 225** colour GS is decision-grade today.

## A · Full-pipeline analysis scripts

Orchestration: CLI `grapeancestry` (`src/grapeancestry/cli.py`) + Snakemake `workflow/Snakefile`.

### Mapping → VCF

| Step | Modern PE | aDNA SE (Ages demo) | Code / tools |
|------|-----------|---------------------|--------------|
| Trim | `fastp` | AdapterRemoval3 (min length 25) | `workflow/Snakefile`, `grapeancestry run` |
| Map | `bwa mem` → VS-1 | `bwa aln -l 1024 -n 0.01` + `samse` | same |
| Markdup | `samtools markdup` | same | same |
| Call | `bcftools mpileup/call -T` 167K BED → `results/{sample}.vcf.gz` | same | same |
| Damage | — | `mapDamage2` (fallback `adna/damage_lite.py`) | `grapeancestry.adna.damage_lite` |

Entry: `grapeancestry run --config … --samples … --sample Ages|HUN89 …`

### Post-VCF domains (what `run` / `analyze` call)

| Domain | CLI | Primary modules |
|--------|-----|-----------------|
| QC | `grapeancestry qc` · inside `analyze` | `core/qc.py` |
| Dosage cache (once) | `python -m grapeancestry.core.dosage …` | `core/dosage.py` → `results/cache/panel_dosage_167k.npz` |
| Merge artifact (2449+query VCF) | inside analyze | `core/merge_ref.py` (analysis still uses **npz**, not merged VCF) |
| Identity / IBS / kinship | `grapeancestry identity` | `identity/run_ibs.py`, `identity/ibs.py`, `identity/parentage.py` |
| PCA project | `grapeancestry project` | `adna/project.py`, `adna/pca_lock.py`, `gcta64` on PATH (frozen axes) |
| ADMIXTURE project | `grapeancestry admix-project` | `adna/admix_project.py`, `adna/admixture.py`, `admixture` 1.3.0 on PATH (`-P` for new IDs) |
| Selection / Fst context | `grapeancestry selection` | `adna/selection.py`, `popgen/selection_report.py`, `popgen/stats.py` |
| f3/f4 (exploratory) | inside report build | `adna/fstats.py`, `popgen/fstats_report.py` |
| NJ tree | inside report build | `popgen/tree_nj.py` |
| GWAS | `grapeancestry gwas` | `breeding/gwas.py`, `breeding/mixed_model.py` |
| GS train / predict | `grapeancestry gs-train` · `gs-predict` | `breeding/gs.py`, `breeding/gs_models.py` |
| Cross recommend | `grapeancestry cross-recommend` | `breeding/cross.py` |
| GEA | `grapeancestry gea` | `popgen/gea.py` |
| Cloud JSON | `grapeancestry chip-report` | `cloud/analyze.py`, `cloud/card.py`, … |
| Impute / catalog / locus / seq-score | `impute` · `catalog` · `locus-search` · `seq-score` | `resource/*` |

Batch post-VCF rebuild (VCF already exists):

```bash
grapeancestry analyze --sample Ages   # QC + identity + PCA/ADMIX + HTML bundle
```

## B · Visualization scripts

| Figure / UI | Where it is built | Notes |
|-----------|-------------------|-------|
| PCA 2D/3D (Plotly) | `report/interactive_dashboard.py` + payload from `report/interactive_data.py` | Frozen GCTA64 axes; query star |
| ADMIXTURE K=2–8 bars | same + `adna/admixture.py` | Frozen P; `admixture -P` or NNLS |
| NJ tree (circular/rectangular) | `popgen/tree_nj.py` → interactive JS | IBS identity tree |
| mapDamage / fragment length | `adna/damage_lite.py` + report embed | aDNA door |
| Selection Manhattan / heat | `popgen/selection_viz.py` | Panel Grp-vs-rest; query GT overlay only |
| LocusZoom (selection + GWAS) | report JS + `assets/locuszoom-*.js` | Panel regional context / trait leads |
| Static PNG fallbacks (Italy-style) | `report/build_report.py` (matplotlib → base64) | Used when building older/full bundles |
| Cloud Streamlit plots | `cloud/plot.py`, `app.py` | Classroom VCF → cards |
| One-off science checks | `scripts/plot_science_k8_check.py`, `scripts/plot_k2_k10_purest_align.py` | Lab QC of ADMIXTURE archives, not customer path |

Front-end libraries shipped beside the HTML: `demo/assets/` (Plotly, D3, LocusZoom).

## C · Report production scripts

| Output | Builder | Entry |
|--------|---------|-------|
| **`{sample}.sample-first-v2.report.html`** | `report/build_report.py` (`build_bundle`, `render_full_html`, `v2_report_path`) + `report/interactive_dashboard.py` + `report/interactive_data.py` | `grapeancestry run` / `analyze` → `_post_analyze` in `cli.py` |
| Optional sidecar JSON | same bundle / downloads section | `*.sample-first-v2.report.data.json` |
| Legacy / alt HTML | `report/html_report.py`, `report/dashboard_html.py` | historical paths |
| **`chip.json`** (Cloud door) | `cloud/analyze.py` via `grapeancestry chip-report` | Streamlit `app.py` |
| Cloud pack | `scripts/build_cloud_pack.py`, `python -m grapeancestry.cloud` | fingerprints for Streamlit Cloud |

**V2 contract:** provenance (`query_id`, `source_sample_id`), artifact list, method coverage (available / unavailable). No invented universal QC pass line. Theme: Light / Dark / System.

Public demo file: [`../demo/results/Ages.sample-first-v2.report.html`](../demo/results/Ages.sample-first-v2.report.html).

## D · Supporting / lab-only scripts (`scripts/`)

These support **panel ADMIXTURE archives and phenotype ETL**, not the nightly customer hand-in:

- `prep_admixture_bed.py`, `run_admixture_local.sh`, `submit_admixture_k*.sh`, `admixture_fit_qc.py`, `ingest_admixture_qp.py`, `rebuild_manual_qp.py`
- `build_phenotype.py`, `extract_table_s17.py`, `build_cloud_pack.py`

## E · Typical customer commands (lab suite)

```bash
# aDNA demo (Ages / V5)
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_ages.yaml --sample Ages -j 4

# modern PE demo
grapeancestry run --config config/mbp_demo.yaml \
  --samples config/samples_demo.yaml --sample HUN89 --mapping full -j 4

# from existing query VCF
grapeancestry analyze --sample Ages
grapeancestry chip-report --vcf results/Ages.vcf.gz --out chip.json
```

## Claim boundaries (short)

- **OIV 225** colour GS = decision-grade; other GS / flower-sex / selection narratives = exploratory.
- **SDR** = unphased window proxy, not Science haplotype sex.
- **Selection** = 2449 panel context; query GT is overlay ≠ “this sample was selected”.
- **ID trap:** panel `HUN89` ≠ report stem `HUN89_query`.

## Official methods (pointers)

Dong et al. 2023 (Science grape panel) · Patterson et al. 2012 (f-statistics) · ADMIXTURE · GCTA (Yang et al.; shipped PCA) · EMMAX (Kang et al.) · LocusZoom · mapDamage2. Full breeding notes: suite `docs/METHODS_breeding.md` (not all mirrored here yet).


See also the detailed file map: [SCRIPTS.md](SCRIPTS.md).
