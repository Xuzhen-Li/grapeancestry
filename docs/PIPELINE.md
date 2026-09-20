# Pipeline (as implemented)

See also `docs/BUILD.md`. Default: `grapeancestry run --sample HUN89 --mapping full`.

## Modern PE (`type: pe`)

1. fastp trim (PE)
2. bwa mem → VS1 (`mapping: full` after gate 0.959)
3. samtools markdup
4. bcftools mpileup/call `-T` 167k BED → `results/{sample}.vcf.gz`

## aDNA SE (`type: adna`, default demo Ages)

1. AdapterRemoval3 trim (min length 25)
2. bwa aln `-l 1024 -n 0.01` + samse
3. samtools markdup
4. bcftools mpileup/call `-T` 167k BED
5. mapDamage2 on markdup BAM (damage_lite fallback)

## Post-VCF analysis

- QC (on-target, breadth, calling rate)
- Merge artifact: `{sample}.merged.vcf.gz` (2449 + query). **Analysis matrix is the dosage npz**, not the merged VCF.
- Identity: Italy 4K IBS vs panel cache. If the query ID is already in the 2449 panel, report **self-in-panel as QC** then nearest **non-self**. `HUN89_query` is **not** panel ID `HUN89` (independent chip FASTQ); do not strip `_query` to look up Q/passport. Clone-screen = non-self Identical + Parent-Offspring.
- PCA uses frozen 2449 reference axes from GCTA64 GRM-PCA on `panel167k_nogwas`; each query is least-squares projected onto those frozen axes. ADMIXTURE: in-panel **lookup** of frozen Q (default family
  `panel167k_nogwas` when ingested, else Science `core_ld_sort` archive). New
  samples on `panel167k_nogwas` use **`admixture -P`** for **K=2–8** (same P rows
  as `panel167k_nogwas.sites.txt`). No extra LD prune; the report states the LE
  assumption is violated. Do not unsupervised-refit 2449+N per customer.
  Batch CLI: `grapeancestry admix-project --vcf a.vcf.gz --vcf b.vcf.gz`.
  run/analyze accept `--admix-k8-only` to restrict those report-producing paths
  to K=8; it is not an `admix-project` option.
- Interactive HTML (`{sample}.report.html`) with method cards + downloads; Plotly from `assets/` when present

Cache: prefer `results/cache/panel_dosage_167k.npz`; fall back to `panel_dosage_5k.npz` for smoke tests.

```bash
# build 167k cache (once)
python -m grapeancestry.core.dosage \
  --panel-vcf data/panel/panel167k_2449.vcf.gz \
  --out-npz results/cache/panel_dosage_167k.npz --full
```

GWAS/GS run only if `data/phenotype.tsv` has ≥50 IDs overlapping the panel. Uti (WINE/TABLE) is **not** used as a breeding trait.

## Sample-first V2 report contract / 样本优先 V2 报告约定

Each report has explicit report provenance: `query_id`, `source_sample_id`, query/source IDs, artifact paths, and method coverage. Unavailable methods are labeled unavailable. This report invents no universal QC pass threshold; QC remains method- and data-specific. The top-bar switch offers **Light**, **Dark**, and **System**; System follows `prefers-color-scheme`, and an explicit choice may persist in `localStorage`.

**CN**：报告显式记录溯源、query/source ID、产物路径和方法覆盖率；不可用方法标为 unavailable。不存在人为发明的统一 QC 通过阈值。顶部提供 **Light / Dark / System**，System 跟随 `prefers-color-scheme`，显式选择可写入 `localStorage`。

### PCA method / PCA 方法

**EN**: Shipped report metadata records `GCTA64 GRM-PCA (panel167k_nogwas)`: the frozen 2449 reference axes define the panel coordinate system, and each query is least-squares projected onto those frozen axes. EIGENSOFT smartPCA is historical/alternative documentation only, not the current shipped result. Method source: [GCTA Yang et al.](https://doi.org/10.1016/j.ajhg.2010.11.011).

**CN**：当前报告元数据记录 `GCTA64 GRM-PCA (panel167k_nogwas)`：2449 面板轴固定为参考坐标系，query 样本以最小二乘投影到这些固定轴上。EIGENSOFT smartPCA 仅作为历史/备选方法记录，不是当前交付结果。方法来源：[GCTA Yang 等](https://doi.org/10.1016/j.ajhg.2010.11.011)。

### Selection evidence / Selection 证据边界

Selection is a **2449 panel-only**, unphased **Grp-vs-rest** contrast. A sweep row requires `Fst >= within-Grp 95th percentile AND within-Grp windowed het <= 5th percentile`. The `query GT` is an overlay only; it is not evidence that one sample was selected.

Selection LocusZoom is **among-all-Grps panel regional context only**. Sweep rows focus **exact Manhattan points**, not arbitrary LZ windows.

The helper `fst_sites()` is documented only as a **simplified Fst contrast**, not canonical Weir–Cockerham/WC unless benchmarked.

**CN**：Selection 仅是 **2449 面板内**、未分相的 **Grp-vs-rest** 对比；sweep 必须同时满足 Fst ≥ Grp 内第 95 百分位、且 Grp 内窗口杂合度 ≤ 第 5 百分位。query GT 只是 overlay，不能证明某个样本被选中。Selection 的 LocusZoom 仅提供所有 Grp 的面板区域背景，sweep 行对应精确 Manhattan 点，不是任意 LZ 窗口。`fst_sites()` 仅称 simplified Fst contrast，未 benchmark 前不称 canonical Weir–Cockerham/WC。

### GEA/origin scope / GEA/起源范围

`GEO` is reserved for the separate GEA/origin-longitude analysis.

**CN**：GEO 只用于独立的 GEA/起源经度分析，不用于 Selection。

### f3/f4 and breeding evidence / f3/f4 与育种证据

f3/f4 use Grp reference means and one query genotype. Each contrast is complete-case per contrast: missing query sites excluded. The report gives `n_sites` and `n_blocks`. These results are exploratory, not formal qp3Pop/qpDstat/qpAdm/qpGraph.

**CN**：f3/f4 使用 Grp reference means 和一个 query genotype；每个 contrast 独立按 complete-case 计算，缺失的 query 位点排除。报告给出 `n_sites` 与 `n_blocks`。这些结果仅供探索，不是正式的 qp3Pop/qpDstat/qpAdm/qpGraph。

GWAS p/beta/r2 are panel results. The `query GT overlay` and GS model scores are not observed phenotypes. The report surfaces binary case/control imbalance with the relevant panel result.

**CN**：GWAS 的 p/beta/r2 是面板结果；query GT overlay 和 GS model scores 不是观测表型。报告会提示二元性状的 case/control 不平衡及其对结果解释的影响。

### GS decision scope / GS 决策范围

Only OIV 225 colour GS is currently rankable/decision-grade (local `results/gs/index.tsv`: `cv_r=0.6246`, `best_model=topk_ridge`). OIV 241 has `cv_r=0.4975`, but its local GWAS summary has `case_n=10` and `control_n=374`; it is exploratory, not suitable for ranking parents or claiming seedlessness. Binary-trait interpretation follows the EMMAX caveat ([Kang et al.](https://doi.org/10.1038/ng.548)).

**CN**：目前只有 OIV 225 颜色 GS 达到可排序、可用于决策的证据标准（`results/gs/index.tsv`：`cv_r=0.6246`，`best_model=topk_ridge`）。OIV 241 的 `cv_r=0.4975`，但本地 GWAS summary 中 `case_n=10`、`control_n=374`，仅属探索性结果，不适合排亲本，也不能据此声称无核。二元性状解释遵循 EMMAX 的限制说明（[Kang 等](https://doi.org/10.1038/ng.548)）。

Official methods: [Dong et al. 2023](https://doi.org/10.1126/science.add8655), [Patterson et al. 2012](https://doi.org/10.1534/genetics.112.145037), [ADMIXTURE](https://doi.org/10.1101/gr.094052.109), [EIGENSOFT (historical/alternative only)](https://doi.org/10.1371/journal.pgen.0020190), [EMMAX](https://doi.org/10.1038/ng.548), and [LocusZoom](https://doi.org/10.1093/bioinformatics/btab186). Theme behavior follows [MDN `prefers-color-scheme`](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme) and [MDN `localStorage`](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage).

Software: env `ga` + `bin/admixture` (1.3.0). EIGENSOFT smartPCA is historical/alternative only; it is not the current shipped PCA result.
