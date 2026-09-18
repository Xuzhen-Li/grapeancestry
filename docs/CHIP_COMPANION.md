# Chip Companion (online)

**EN**: Streamlit Cloud app for the 167K capture panel. Python-only VCF parse (no bcftools, no ADMIXTURE binary).

**CN**: 167K 芯片在线配套工具。纯 Python 读 VCF，Cloud 不装 bwa/bcftools。

> Full walkthrough with demo screenshots: [`GUIDELINE.md`](GUIDELINE.md)

## Tonight — two doors / 今晚两门（勿混成一件）

| Door / 门 | Tonight deliverable / 今晚交件 | Not tonight / 今晚不做 |
|-----------|----------------------------------|------------------------|
| **Cloud** | `chip.json` (upload 167K VCF → Streamlit) | Docker / HPC / ADMIXTURE binary / full FASTQ pipeline |
| **Suite** | `*.sample-first-v2.report.html` | Claiming OIV 241 / seedlessness / haplotype sex |

**Done when (≤3):**
- [ ] Door chosen; filename matches the door
- [ ] VCF sites align to 167K (Cloud) **or** report opens with assets (Suite)
- [ ] No decision-grade claim beyond **OIV 225 colour GS**

**ID trap / 身份陷阱（表上方硬句）：**  
Panel demo `HUN89` (2449-row ID) ≠ capture demo `HUN89-capture` / report stem `HUN89_query` (independent FASTQ recapture).  
面板 demo `HUN89`（2449 行）≠ 捕获 demo `HUN89-capture` / 报告 stem `HUN89_query`（独立重捕获）。

**Outputs (scan order) / 产出扫读序：**  
QC → self-vs-clone IBS → passport / SDR **proxy** / trait card → purity & parentage → (advanced) f3/f4, local ancestry, NJ, GEA/Fst, impute → **colour GS last** (only decision-grade phenotype today).

## What it does

> **ID trap (above the table) / 身份陷阱（主表正上方）：** Panel `HUN89` (2449-row) ≠ `HUN89-capture` / `HUN89_query`. Do not treat the FASTQ recapture as the panel ID.

| Tab | Input | Output (scan order — top five) |
|---|---|---|
| Chip companion (**Tonight Cloud**) | panel-site **167K VCF** or named demos (not FASTQ) | 1 QC · 2 IBS identity · 3 passport / SDR **proxy** · 4 purity & parentage · 5 colour GS (**OIV 225 only** rankable) |
| Lab (**Later** only) | Docker / HPC + local tables | `admixture -P`, catalog, locus search, GWAS/GS/GEA indexes — **not** tonight |

<details>
<summary>Full output list / 全清单（展开）</summary>

QC, self-vs-clone IBS, VIVC passport, SDR proxy, trait card, purity, parentage, f3/f4, local ancestry, NJ, origin-GEA/Fst, k-NN impute, colour GS. Advanced tabs are optional after the top five.

</details>

OIV 225 colour GS is currently the only rankable phenotype. Shipped `model.npz` is the best **marker-effect** model (`topk_ridge`, CV *r*≈0.62), not rrBLUP. Flower sex is an **unphased SDR-window proxy** (`trait_locus` token `sdr`, chr2:14165010–14345273; empirical het on this panel: female n=22 median ≈0.01, herm n=352 median ≈0.70). Science sex = haplotypes H1–H5 ([doi:10.1126/science.add8655](https://doi.org/10.1126/science.add8655)), not GS. Clone-level IBS hits borrow OIV from `phenotype.tsv`. Seedless card is design-tag coverage (n_seedless=10; AGL11 not recovered).

## Breeding decision scope / 育种决策范围

**EN**: Only OIV 225 colour GS is currently rankable/decision-grade (`results/gs/index.tsv`: `cv_r=0.6246`, `best_model=topk_ridge`). OIV 241 has `cv_r=0.4975`, but `results/gwas/euvitis/OIV_241_bin/summary.json` records `case_n=10` and `control_n=374`; it is exploratory, not suitable for ranking parents or claiming seedlessness. Binary-trait interpretation follows the EMMAX caveat ([Kang et al.](https://doi.org/10.1038/ng.548)).

**CN**：目前只有 OIV 225 颜色 GS 达到可排序、可用于决策的证据标准（`results/gs/index.tsv`：`cv_r=0.6246`，`best_model=topk_ridge`）。OIV 241 的 `cv_r=0.4975`，但 `results/gwas/euvitis/OIV_241_bin/summary.json` 记录 `case_n=10`、`control_n=374`；属于探索性结果，不适合排亲本，也不能据此声称无核。二元性状解释遵循 EMMAX 限制（[Kang 等](https://doi.org/10.1038/ng.548)）。

### Selection evidence / Selection 证据边界

Selection is a 2449 panel-only, unphased Grp-vs-rest contrast; named windows are MAS/GWAS context, and the report applies the documented Fst/within-Grp-windowed-het sweep rule. Query GT is an overlay only, not evidence that one sample was selected. Selection LocusZoom is among-all-Grps panel regional context only; sweep rows focus exact Manhattan points, not arbitrary LZ windows.

**CN**：Selection 仅是 2449 面板内、未分相的 Grp-vs-rest 对比；query GT 只是 overlay，不能证明某个样本被选中。Selection 的 LocusZoom 仅提供所有 Grp 的面板区域背景，sweep 行对应精确 Manhattan 点，不是任意 LZ 窗口。

### GEA/origin scope / GEA/起源范围

`GEO` is reserved for the separate GEA/origin-longitude analysis.

**CN**：GEO 只用于独立的 GEA/起源经度分析，不用于 Selection。

HTML report shows the same LocusZoom.js as GWAS (Y = Fst or windowed het; stacked dual panel optional), plus a genome-wide Fst/het Manhattan, Grp×window het/Fst heatmap, genome-wide Fst vs het scatter, and Table S29 scatter. Dong 2023 Table S29 is a **dual check** (`results/selection/vs_science_s29.tsv`), not the named-window list.

Dong et al. 2023: `Vvsyl02G000229` / `Vvsyl02G001064` *are better predictors of berry skin colors* than VvMybA (`2:3519247`, `2:16051309`). In-panel IDs look up frozen `panel167k_nogwas` Q. New IDs use NNLS onto frozen P (Cloud has no ADMIXTURE binary; Docker/HPC uses `admixture -P`). Archive Science Q has no matching P.

## Tonight Cloud vs Later Lab / 今晚 Cloud vs 稍后 Lab

**Tonight Cloud:** upload a **167K-site VCF** (not FASTQ) → Streamlit → hand in `chip.json`.

**Later Lab:** `docker compose up` / HPC (`environment-hpc.yml`). Do not start here for a classroom night.

**Honest stop:** if `results/HUN89_query.vcf.gz` (etc.) is missing, `python -m grapeancestry.cloud` will **not** write the matching `demo_*.npz` — that is **expected**, not a failed command.

## Streamlit Cloud

Root `environment.yml` is **cloud-safe** (conda-forge + pip). Lab stack is `environment-hpc.yml`.

1. On a machine with `results/cache/panel_dosage_167k.npz` (or 5k fallback):

```bash
conda activate ga
cd grapeancestry_suite
python -m grapeancestry.cloud
# → data/cloud/fingerprint.npz, data/cloud/sdr.npz, data/cloud/demos.npz
#   data/cloud/demo_HUN89_capture.npz, data/cloud/demo_Ages.npz
#   data/cloud/gea_summary.json
```

`data/cloud/demo_HUN89_capture.npz` is generated only when `results/HUN89_query.vcf.gz` exists, and `data/cloud/demo_Ages.npz` only when `results/Ages.vcf.gz` exists. Demo outputs are otherwise conditional on the corresponding results VCF.

2. Commit `data/cloud/` (fingerprint is a few MB).
3. Push GitHub → https://share.streamlit.io → Main file `app.py`.
4. Customers upload a **167K-site VCF**, not FASTQ.

```bash
grapeancestry chip-report --vcf sample.vcf.gz --out chip.json
streamlit run app.py
```

## Docker (full lab)

```bash
conda env create -f environment-hpc.yml   # local
docker compose up                         # uses environment-hpc.yml in the image
```
