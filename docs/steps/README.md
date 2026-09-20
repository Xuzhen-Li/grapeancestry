# Analysis steps (one markdown per step)

Numbered walkthrough of the GrapeAncestry companion stack. Each page lists **scripts**, **statistical outputs**, and **visualization outputs**.

| Step | Doc | Domain |
|------|-----|--------|
| 01 | [01-mapping-and-calling.md](01-mapping-and-calling.md) | FASTQ/BAM → panel-site VCF |
| 02 | [02-qc-and-coverage.md](02-qc-and-coverage.md) | Capture QC / method coverage |
| 03 | [03-identity-ibs-kinship.md](03-identity-ibs-kinship.md) | Clone/PO, IBS, KING |
| 04 | [04-pca-projection.md](04-pca-projection.md) | Frozen GCTA64 PCA |
| 05 | [05-admixture-projection.md](05-admixture-projection.md) | Frozen ADMIXTURE K=2–8 |
| 06 | [06-nj-tree.md](06-nj-tree.md) | IBS neighbour-joining |
| 07 | [07-adna-damage.md](07-adna-damage.md) | mapDamage / fragment length |
| 08 | [08-f3-f4-stats.md](08-f3-f4-stats.md) | Exploratory f-statistics |
| 09 | [09-selection-fst.md](09-selection-fst.md) | Panel Grp-vs-rest selection |
| 10 | [10-gwas.md](10-gwas.md) | Panel GWAS |
| 11 | [11-genomic-selection.md](11-genomic-selection.md) | GS scores (OIV 225 decision-grade) |
| 12 | [12-locuszoom-panel-context.md](12-locuszoom-panel-context.md) | LocusZoom + query GT overlay |
| 13 | [13-sample-first-report.md](13-sample-first-report.md) | HTML report assembly |
| 14 | [14-cloud-chip-json.md](14-cloud-chip-json.md) | Cloud `chip.json` door |

Also: [../SCRIPTS.md](../SCRIPTS.md) (file index) · [../PIPELINE.md](../PIPELINE.md) (science contracts) · [../GUIDELINE.md](../GUIDELINE.md) (demo walkthrough).

**Other chips:** keep these step contracts; swap sites/reference/frozen axes via `profiles/` + `config/`.
