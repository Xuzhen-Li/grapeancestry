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

---

## Usage flow (how it is used today)

Three lanes exist. Pick one; do not mix hand-in filenames.

### A · Public docs (this GitHub tree)

1. Read this GUIDELINE + [`FLOWCHART.md`](FLOWCHART.md) + [`CHIP_COMPANION.md`](CHIP_COMPANION.md).
2. Optionally open a **local suite** demo HTML (lane B). This docs-only clone has no runnable `grapeancestry` CLI.

### B · Local suite (developer / lab Mac)

From the private `grapeancestry_suite` checkout (not this repo):

```bash
conda activate ga
cd grapeancestry_suite
pip install -e ".[dev,web]"
export PATH="$PWD/bin:$PATH"

# End-to-end demo (FASTQ → 167K VCF → analyses → HTML)
grapeancestry run --config config/mbp_demo.yaml --samples config/samples_demo.yaml \
  --sample HUN89 --mapping full -j 4
# → results/HUN89*.vcf.gz + sample-first V2 report under results/

# View an existing demo report (view-only; does not create a hand-in)
python -m http.server
# http://localhost:8000/results/HUN89_query.sample-first-v2.report.html
```

Typical post-VCF pieces (same suite): `grapeancestry analyze`, `identity`, `project`, `admix-project`, `chip-report`, `selection`, `gs-predict`. Cloud pack: `python -m grapeancestry.cloud` then `streamlit run app.py`.

### C · Cloud Chip Companion (classroom night)

1. Upload a **167K-site query VCF** (not FASTQ) in Streamlit.
2. Hand in **`chip.json`** (Cloud door). Suite door remains `*.sample-first-v2.report.html`.

Scan order in the product: QC → self-vs-clone IBS → passport / SDR **proxy** / trait card → purity & parentage → (advanced) f3/f4, NJ, GEA/Fst, impute → **colour GS last** (only OIV 225 decision-grade).

**Reading the HTML report (sidebar order):** Sample validity → Identity → Population (PCA / ADMIXTURE / NJ) → Sample evidence → Panel research (incl. **LocusZoom**) → Methods → Downloads. Black ★/♦ = query; yellow ♦ = pinned reference. Click a table row or plot point to pin.

Screenshots below are **non-overlapping panel crops** (no full+viewport duplicates). Panel research stays coarse; **one dedicated LocusZoom** shot is included.

---

## Walk the demo report

### 1 · Sample validity

**Section:** Prove the report is about *this* query: provenance, method coverage, capture QC, and whether aDNA damage applies.

![validity 1 — metadata and conclusions](guideline_shots/panels/01_sample_validity_01.png)

*Panel:* Report metadata, artifact paths (incl. Selection / GWAS LocusZoom JSON), method coverage, and the auto conclusions strip. Check calling rate and that conclusions match the library type.

![validity 2 — capture QC](guideline_shots/panels/01_sample_validity_02.png)

*Panel:* Capture QC (on-target, depth, breadth, calling). Heterozygosity here is a screen, not a purity call.

![validity 3 — damage note](guideline_shots/panels/01_sample_validity_03.png)

*Panel:* Damage / aDNA module. Missing aDNA damage on modern PE is expected.

### 2 · Identity & placement

**Section:** Who is this sample relative to the frozen 2449 panel — clone / PO first, then IBS and KING neighbors. Pin a reference to overlay later plots.

![identity 1 — clone and PO](guideline_shots/panels/02_identity_01.png)

*Panel:* Identical + parent–offspring list, then IBS / kinship tops. Identical ≠ naming a variety from a mid-rank IBS hit. Panel ID `HUN89` ≠ stem `HUN89_query`.

![identity 2 — neighbors detail](guideline_shots/panels/02_identity_02.png)

*Panel:* Continued neighbor / kinship detail. Click a row to pin that reference (yellow ♦) onto PCA / ADMIXTURE / NJ.

### 3 · Population placement

**Section:** Project the query onto frozen panel axes — do not refit PCA or ADMIXTURE on the customer sample alone.

![PCA](guideline_shots/panels/03_pca.png)

*Panel:* GCTA64 PCA projection (2D + 3D). Switch PC pairs; black star = query.

![ADMIXTURE](guideline_shots/panels/03_admixture.png)

*Panel:* ADMIXTURE K=2–8 — in-panel lookup of frozen Q, or `-P` / NNLS for new IDs.

![NJ](guideline_shots/panels/03_nj.png)

*Panel:* Neighbor-joining on IBS identity (query + panel tips).

### 4 · Sample evidence

**Section:** What this query *calls* at curated MAS / GWAS / trait sites. Labels describe the **panel** context; observed GT is not a phenotype call.

![evidence 1 — genotype evidence table](guideline_shots/panels/04_sample_evidence_01.png)

*Panel:* Query genotype evidence table (curated MAS/GWAS tags and panel GWAS leads). Colour pills = GT, not phenotype.

![evidence 2 — trait / GS cards](guideline_shots/panels/04_sample_evidence_02.png)

*Panel:* Trait / MAS cards and GS scores. Only **OIV 225** colour GS is decision-grade; score ≠ phenotype; SDR ≠ haplotype sex.

### 5 · Panel research

**Section:** 2449-panel research context (selection / GEA / named windows). Query GT is an **overlay** only — it does not prove the sample was selected.

![panel 1 — genome-wide selection / sweeps](guideline_shots/panels/05_panel_research_01.png)

*Panel:* Genome-wide selection / sweep scan and related tables on the panel.

![panel 2 — query overlay at named windows](guideline_shots/panels/05_panel_research_02.png)

*Panel:* This sample’s genotypes at sites overlapping named / selection windows.

![panel 3 — regional context toward LocusZoom](guideline_shots/panels/05_panel_research_03.png)

*Panel:* Regional panel context leading into interactive LocusZoom (among-Grps Fst / named windows).

![panel 4 — window / trait locus tables](guideline_shots/panels/05_panel_research_04.png)

*Panel:* Window summaries, reference overlaps, and trait-locus indexes for the region under study.

![panel 5 — GWAS index into LocusZoom](guideline_shots/panels/05_panel_research_05.png)

*Panel:* Panel GWAS / GS index and the start of the GWAS LocusZoom + query overlay stack.

### 5b · LocusZoom (one dedicated panel)

**Section:** Interactive regional plot (LocusZoom.js 0.14.0). Y = panel association or selection statistic; colour = panel r²; strip / table below = **this query’s** genotypes. Drag to pan, scroll to zoom, click a SNP or gene. Sidebar also has **Selection LocusZoom** and **GWAS LocusZoom** as separate entries.

![LocusZoom — panel GWAS + query GT](guideline_shots/panels/05_locuszoom.png)

*Panel:* Example **GWAS LocusZoom** (here OIV 225 colour locus on chr19) with lead SNP, gene track, and `HUN89_query` genotype overlay. Selection LocusZoom uses the same widget with Y = Fst / windowed het among Grps — panel map, not proof of selection on the query.

### 6 · Methods

**Section:** How each number was made. Not a field-release SOP.

![methods 1](guideline_shots/panels/06_methods_01.png)

*Panel:* Pipeline / method narrative for QC and identity layers.

![methods 2](guideline_shots/panels/06_methods_02.png)

*Panel:* Methods for projection, ADMIXTURE, and relatedness / tree.

![methods 3](guideline_shots/panels/06_methods_03.png)

*Panel:* Methods for GS, selection / GEA context, and report assembly caveats.

### 7 · Downloads

**Section:** Query-only sidecars you can take away. The full 2449 reference matrix is not included.

![downloads](guideline_shots/panels/07_downloads.png)

*Panel:* Download links for query-scoped artifacts.

---

## Privacy

No unpublished genotypes, private coordinates, or full 2449 matrices in public demos.

## Related

[`CHIP_COMPANION.md`](CHIP_COMPANION.md) · [`FLOWCHART.md`](FLOWCHART.md) · https://github.com/Xuzhen-Li/grapeancestry
