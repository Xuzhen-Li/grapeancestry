# 数据清单 MANIFEST（阶段一）/ Data Manifest (Phase 1)

> 2026-08-10 建。记录项目内已就位数据的事实（实测）+ 原位引用数据「是否需要」判定。
> Facts measured on staged files + need/no-need decisions for in-place external data.

## A. 项目内已就位 `data/`（实测事实）

| 文件 | 实测事实 | 用途 |
|---|---|---|
| `ref/VS1.final.fa` (462M) + `.fai` + `.gff3` (36M) | VS-1 参考基因组（Science add8655 比对用参考）；contig 为数字命名，与 `postion_all.txt` 一致 | A 比对/子参考/注释 |
| `panel/17wpos.vcf.gz` (2.7G) | **3527 样本 × 167,432 位点**，已是面板位点（[待确认] 与稿件 167,433 差 1 位点）；样本名含 `-A`/`-W` 后缀副本 | 参考面板裁剪源 |
| `panel/17window.vcf.gz.tbi` | ⚠️ 孤儿索引（文件名与 `17wpos.vcf.gz` 不匹配），暂不使用 | — |
| `panel/2449.info` | **2449 个样本**元数据（ID/CON/Wild/GEO/Uti/Grp），非 2448 | B/D/F 分组 |
| `panel/samples2449.txt` | 2449.info 首列 ∩ VCF header = **2449 全命中**（无缺失） | 裁剪名单 |
| `panel/panel167k_2449.vcf.gz` (97M, +`.tbi`) | **最终版** ✅ 2449 样本 × **167,433** 位点，GT-only 瘦身（17wpos 的 167,432 + 补回 `10:1001658` REF=G/ALT=A，基因型取自 `stat.ped`：1374 GG / 475 GA / 66 AA / 534 缺失）；可由 17wpos 重生成 | `merge_ref` 的参考集合 |
| `fastq/HUN89-1-ywk_{1,2}.fq.gz` (~235M/端) | 现代捕获样本，PE150 双 index，未降采样；HUN89 在 hunage5 基因型矩阵中有对照 | 批1 演示 + 门检 |
| `fastq/V5xL1xP2_Ages_3_5070.12Xv2.realigned.fastq.gz` (260M) | 古样本，SE merged 短读（37–43bp，`M_` 前缀），源自 12Xv2 比对产物转 fastq；坐标系无关（reads 重新比对 VS1/子参考） | B 域 aDNA demo |
| `data/cloud/fingerprint.npz` + `sdr.npz` + `manifest.json` + optional `gs/` | Chip Companion pack: ~4k IBS + SDR-window dosages × 2449 + copied GS. Build: `python -m grapeancestry.cloud.pack` | Streamlit Cloud / `chip-report` |
| `phenotype.tsv` | ✅ 长表 26,208 行：436 panel IDs × OIV 性状；列 `ID trait value source n_obs raw`；来源不合并 | C GWAS/GS |
| `oiv_traits.tsv` | OIV 字典：scale ∈ {ordinal,nominal,binary} + `binary_rule`（225/236/241/151） | ETL / GWAS binary |
| `panel/sample_annot.tsv` | VIVC 花性/用途等；冲突时 euvitis 优先并标 `[conflict]` | cross 性别过滤 |
| `trait_locus.tsv` | 18,707 行意大利 GWAS 位点（OIV_225 / OIV_241 / sdr …） | 阳性对照 + 注释 |
| `2022-05-23 Phenotype from DX/2022-05-23-ST1表型 3K sequenced samples.xlsx` | **主输入（只读）**。sheet `www.eu-vitis.de`：Excel 745 行 / **404 ∈ 面板**；sheet `des-cep-monde-edition-2009`：Excel used range **2256**（含空行），非空 **312** 唯一 Lib ID / **110 ∈ 面板**。`Library ID` = `2449.info` ID | ETL |
| `2022-05-23 Phenotype from DX/www.eu-vitis.de.xlsx` | OIV 描述字典（含 Trait type） | ETL |
| `2022-05-23 Phenotype from DX/des-cep-monde-edition-2009.xlsx` | OIV 描述字典（无 Trait type） | ETL |
| `2022-05-23 Phenotype from DX/2022-05-23-文件说明.docx` | 两来源不要合并成一个值 | ETL 规则 |
| `2022-05-23 Phenotype from DX/GRIN-GRAPE DAVIS.xlsx` | DVIT accession，**无 Library ID 映射** | ⏳ 本轮不用 |
| `2022-05-23 Phenotype from DX/npgsweb.ars-grin.gov.xlsx`（及 `-dx` 副本） | NPGS/GRIN，无 Library ID 映射 | ⏳ 本轮不用 |
| `2022-05-23 Phenotype from DX/2022-05-23-所有能对应样品表型…xlsx` (41MB) | eu-vitis sheet 约 100 万行多为空；ST1 是去重子集 | ⏳ 本轮不读 |
| `2022-05-23 Phenotype from DX/des-cep-monde-edition-2009.pdf` | OIV 2009 描述 PDF 副本 | 参考；官方页 https://www.oiv.int/node/2830 |
| `2022-05-23 Phenotype from DX/www.eu-vitis.de copy.xlsx` | eu-vitis 字典副本 | 不用（用无 copy 的那份） |

## B. 原位引用（`00_array/`，勿搬）— 阶段一需要 ✅

| 路径 | 用途 |
|---|---|
| `stat_vcf_from_3527/postion_all.txt`（170,327 行+表头） | 子参考位点 / QC 候选位点 |
| `stat_vcf_from_3527/target_regions.bed` | QC on-target 区间 |
| `stat_italy_array/DNA probe/loci.bed`（156,372） | 探针区间 QC |
| `addsata_*/hunage5/*genotypes*.txt`（HUN100/101/103/89/91） | B/C/D/F 单元测试 |
| `addsata_*/hun20to5/hun5new/double/`（Equality_10Way 等） | 批1.5 子参考门检 ground truth |
| `addsata_*/hunage5/IBS_Genotype_Match_Matrix.csv` | D 身份匹配单测 |
| `data/panel/admixture/science_manifest.json` + `science_k{2..8}_raw.Q` + `PROVENANCE.md` | Phase 1 Science-**named** 系列；Q = 2024-04-08 `core_ld_sort.{K}.Q` 字节拷贝（归档，不覆盖）。无匹配 Science P |
| `data/panel/admixture/gwas_exclude.tsv` + `panel167k_nogwas.sites.txt` | 167k minus GWAS（13,950 drop / 153,483 keep）；P 行序 = sites.txt。新拟合 family `panel167k_nogwas`（HPC ingest 后才有 Q/P） |
| `stat_vcf_from_3527/ADMIXTURE/` + `6speceis/pca.md` | Legacy chip-P projection reference: **K=2..8** precomputed Q/P; explicit `nnls` / `official` modes expose this separately and do not call it Science Q |
| `mapDamage/` | B 损伤报告流程复用 |
| `##芯片位点处理全流程.md`、`stat_italy_array/*.md` | 已验证命令锚点（喂 auto） |

## C. 原位引用 — 阶段一暂不需要，后期再定 ⏳/❌

| 路径 | 判定 |
|---|---|
| `V4_nc/Table S1-17 Final.xlsx` | ⏳ 批6（C 域 trait-locus）时提取 |
| `array_stat_3k/10k_8044.bed` | ⏳ E 域核心 SNP / 3K 子面板对照 |
| `addsata_*/hunage5/allhun_genotypes.txt` (172M) | ⏳ 可选 |
| `WGStest.csv/.py`、`wgs.pos`、`minimal_marker/`、`lifeover/`、`matched_intervals*`、`overlaps*.txt`、`figure_*`、`paired_boxplot.py`、`amber.sh`、`HUN bwa.sh`、`F2霜霉病qtl.md` | ❌ 历史分析残留，本套件不需要 |
| `stat_vcf_from_3527/grape.chip.vcf.gz` | ⚠️ **文件损坏/截断**（bgzf 流仅 ~2,063 条可读）；面板真值以 `stat.{ped,bim,fam}` 为准；如需原始 VCF 需从 HPC 重下 |
