# Analysis steps (fine-grained)

**DIY no-kit path:** `00a`–`13b`. **Optional** Chip Companion: `14a`–`14b`.

One markdown per sub-step. Names use **`00a`…`14b`** so order stays obvious.

**Legend:** `00*` = data preparation (before any customer sample) · `01*`+ = per-sample analysis · each page lists scripts, statistical outputs, and visualization outputs.

| Step | Doc | Focus |
|------|-----|-------|
| 00a | [00a-panel-sites-and-metadata.md](00a-panel-sites-and-metadata.md) | Panel sites and sample metadata |
| 00b | [00b-reference-genome.md](00b-reference-genome.md) | Reference genome (coordinate system) |
| 00c | [00c-panel-vcf-and-dosage-cache.md](00c-panel-vcf-and-dosage-cache.md) | Panel VCF and dosage cache |
| 00d | [00d-frozen-pca-axes.md](00d-frozen-pca-axes.md) | Freeze PCA axes |
| 00e | [00e-frozen-admixture-qp.md](00e-frozen-admixture-qp.md) | Freeze ADMIXTURE Q/P |
| 00f | [00f-phenotype-and-trait-tables.md](00f-phenotype-and-trait-tables.md) | Phenotype and trait tables |
| 00g | [00g-cloud-fingerprint-pack.md](00g-cloud-fingerprint-pack.md) | Cloud fingerprint pack (optional) |
| 01a | [01a-trim-and-map.md](01a-trim-and-map.md) | Trim and map |
| 01b | [01b-markdup-and-call.md](01b-markdup-and-call.md) | Markdup and call at panel sites |
| 02a | [02a-capture-qc-metrics.md](02a-capture-qc-metrics.md) | Capture QC metrics |
| 02b | [02b-calling-rates-and-method-coverage.md](02b-calling-rates-and-method-coverage.md) | Calling rates and method coverage |
| 03a | [03a-clone-and-po-screen.md](03a-clone-and-po-screen.md) | Clone and parent-offspring screen |
| 03b | [03b-ibs-and-kinship-ranks.md](03b-ibs-and-kinship-ranks.md) | IBS and kinship ranks |
| 04a | [04a-load-frozen-pca.md](04a-load-frozen-pca.md) | Load frozen PCA axes |
| 04b | [04b-project-query-pca.md](04b-project-query-pca.md) | Project query onto PCA |
| 05a | [05a-resolve-admixture-family.md](05a-resolve-admixture-family.md) | Resolve ADMIXTURE family (lookup vs project) |
| 05b | [05b-project-query-admixture.md](05b-project-query-admixture.md) | Project query ADMIXTURE Q |
| 06a | [06a-build-ibs-distance.md](06a-build-ibs-distance.md) | Build IBS distance for tree |
| 06b | [06b-layout-nj-tree.md](06b-layout-nj-tree.md) | Layout NJ tree |
| 07a | [07a-run-mapdamage.md](07a-run-mapdamage.md) | Run mapDamage (or lite) |
| 07b | [07b-damage-plots.md](07b-damage-plots.md) | Damage and fragment-length plots |
| 08a | [08a-compute-f3-f4.md](08a-compute-f3-f4.md) | Compute f3/f4 contrasts |
| 08b | [08b-fstats-report-panels.md](08b-fstats-report-panels.md) | f-statistic report panels |
| 09a | [09a-panel-fst-sweeps.md](09a-panel-fst-sweeps.md) | Panel Fst / sweep scan |
| 09b | [09b-selection-manhattan-viz.md](09b-selection-manhattan-viz.md) | Selection Manhattan and heatmaps |
| 10a | [10a-panel-gwas-scan.md](10a-panel-gwas-scan.md) | Panel GWAS scan |
| 10b | [10b-gwas-trait-cards.md](10b-gwas-trait-cards.md) | GWAS trait cards |
| 11a | [11a-train-gs-models.md](11a-train-gs-models.md) | Train GS models |
| 11b | [11b-predict-gs-scores.md](11b-predict-gs-scores.md) | Predict GS scores for query |
| 12a | [12a-selection-locuszoom.md](12a-selection-locuszoom.md) | Selection LocusZoom (panel Fst windows) |
| 12b | [12b-gwas-locuszoom.md](12b-gwas-locuszoom.md) | GWAS LocusZoom (trait leads) |
| 13a | [13a-build-report-payload.md](13a-build-report-payload.md) | Build report payload |
| 13b | [13b-render-sample-first-html.md](13b-render-sample-first-html.md) | Render sample-first V2 HTML |
| 14a | [14a-cloud-analyze-vcf.md](14a-cloud-analyze-vcf.md) | **Optional** Cloud analyze query VCF |
| 14b | [14b-emit-chip-json.md](14b-emit-chip-json.md) | **Optional** emit `chip.json` (not v1 product) |

## Suggested reading order

1. Data prep: `00a` → `00g` (skip `00f`/`00g` if ancestry-only)  
2. Per sample (DIY / v1 product): `01a` → `13b` → `*.sample-first-v2.report.html`  
3. **Optional** Cloud JSON only: `14a` → `14b` (skip for Docker kit / DIY HTML)  

Also: [../REPO_MAP.md](../REPO_MAP.md) · [../SCRIPTS.md](../SCRIPTS.md) · [../PIPELINE.md](../PIPELINE.md) · [../GUIDELINE.md](../GUIDELINE.md).

**Other chips:** reuse these step IDs; replace artifacts behind `00a`–`00e` via `profiles/` + `config/`.
