# GrapeAncestry guideline (chip companion)

**Status:** public docs on `Xuzhen-Li/grapeancestry` (demo walkthrough). Full suite CLI lands later.  
**Language:** English primary.

## Final-package inputs (all on VS-1)

| Input | Notes |
|-------|-------|
| **FASTQ** | Trim → map to VS-1 → call at 167K BED |
| **BAM / CRAM** | Already on VS-1 → markdup → call at 167K |
| **Query VCF** | 167K sites for the customer sample — **not** the 2449 panel matrix |

Diagram: [`flowchart_vs1_analysis_v2.png`](flowchart_vs1_analysis_v2.png) · [`FLOWCHART.md`](FLOWCHART.md).

**ID trap:** panel `HUN89` ≠ report stem `HUN89_query`.

**Claim boundaries:** only **OIV 225** colour GS is decision-grade today; SDR = proxy; selection overlay ≠ selected; score ≠ phenotype. Details below in each section.

> Classroom: Cloud → `chip.json`; Suite → `*.sample-first-v2.report.html`.

## How to open the demo

From your **local suite** root (not this docs-only clone):

```bash
cd /path/to/local-suite
python -m http.server
# http://localhost:8000/results/HUN89_query.sample-first-v2.report.html
```

`http.server` is view-only. Screenshots below are **non-overlapping panel crops** (no full+viewport duplicates).

---

## Walk the demo report

### 1 · Sample validity

![validity 1](guideline_shots/panels/01_sample_validity_01.png)

![validity 2](guideline_shots/panels/01_sample_validity_02.png)

![validity 3](guideline_shots/panels/01_sample_validity_03.png)

Read provenance / conclusions, then capture QC (calling rate, depth, breadth), then the damage note. Heterozygosity is a screen, not a purity call. Missing aDNA damage on modern PE is expected.

### 2 · Identity & placement

![identity 1](guideline_shots/panels/02_identity_01.png)

![identity 2](guideline_shots/panels/02_identity_02.png)

Clone + PO first, then IBS / KING neighbors. Pin a ref to overlay PCA / ADMIXTURE / NJ. Identical ≠ naming a variety from a mid-rank IBS hit.

### 3 · Population placement

![PCA](guideline_shots/panels/03_pca.png)

![ADMIXTURE](guideline_shots/panels/03_admixture.png)

![NJ](guideline_shots/panels/03_nj.png)

Frozen GCTA64 PCA projection; ADMIXTURE lookup or `-P` / NNLS; NJ on IBS identity. No duplicate “full section” strip.

### 4 · Sample evidence

![evidence 1](guideline_shots/panels/04_sample_evidence_01.png)

![evidence 2](guideline_shots/panels/04_sample_evidence_02.png)

Trait / MAS cards and GS scores. Only OIV 225 is decision-grade; score ≠ phenotype; SDR ≠ haplotype sex.

### 5 · Panel research

![panel 1](guideline_shots/panels/05_panel_research_01.png)

![panel 2](guideline_shots/panels/05_panel_research_02.png)

![panel 3](guideline_shots/panels/05_panel_research_03.png)

![panel 4](guideline_shots/panels/05_panel_research_04.png)

![panel 5](guideline_shots/panels/05_panel_research_05.png)

Sequential non-overlapping crops of the long panel-research section (GWAS / selection / GEA context). Query GT is overlay only.

### 6 · Methods

![methods 1](guideline_shots/panels/06_methods_01.png)

![methods 2](guideline_shots/panels/06_methods_02.png)

![methods 3](guideline_shots/panels/06_methods_03.png)

How each number was made; not a field-release SOP.

### 7 · Downloads

![downloads](guideline_shots/panels/07_downloads.png)

Query-only sidecars; 2449 reference is not included.

---

## Privacy

No unpublished genotypes, private coordinates, or full 2449 matrices in public demos.

## Related

[`CHIP_COMPANION.md`](CHIP_COMPANION.md) · [`FLOWCHART.md`](FLOWCHART.md) · https://github.com/Xuzhen-Li/grapeancestry
