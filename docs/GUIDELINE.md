# GrapeAncestry guideline (chip companion)

**Status:** draft for local suite → public `Xuzhen-Li/grapeancestry` when filled.  
**Language:** English primary for public files; Chinese teaching notes may live in Companion.

## Final-package inputs (pick one · all on VS-1)

| Input | What it is | Notes |
|-------|------------|-------|
| **FASTQ** | Modern PE or aDNA SE reads | Trim → map to **VS-1** → call at 167K BED |
| **BAM / CRAM** | Already aligned on **VS-1** | Markdup → call at 167K BED |
| **Query VCF** | Customer sample at **167K sites** | Sites ∩ 167K; not the 2449 panel matrix |

Full analysis flow: [`FLOWCHART.md`](FLOWCHART.md) · diagram: [`flowchart_vs1_analysis_v2.png`](flowchart_vs1_analysis_v2.png).

### ID trap (read once)

Panel demo `HUN89` (2449-row ID) ≠ capture demo `HUN89-capture` / report stem `HUN89_query` (independent FASTQ recapture). Do not treat the recapture as the panel row.

### Claim boundaries (short)

| Class | Trait / claim | Rule |
|-------|---------------|------|
| Decision-grade | OIV 225 colour GS | May rank when policy + evidence say so |
| Exploratory | OIV 241, unbalanced case/control | Demo only; never parent ranking / seedlessness claim |
| Do not claim | SDR = haplotype sex; query GT = selection | SDR = unphased window **proxy** (not Science H1–H5); selection overlay ≠ “this sample was selected” |
| Reminder | Model score | **Score ≠ observed phenotype** |

> **Classroom note (not the main story):** Cloud door → hand in `chip.json` from a 167K VCF; Suite door → hand in `*.sample-first-v2.report.html`. Pick one deliverable; do not mix them.

---

## How to open the demo locally

Demo report: `results/HUN89_query.sample-first-v2.report.html` (English UI).  
Serve from the **suite root** so relative `../assets/` (and section assets) resolve:

```bash
cd grapeancestry_suite
python -m http.server
# then open:
# http://localhost:8000/results/HUN89_query.sample-first-v2.report.html
```

Sidebar order below matches the live report. Each section: **one full long screenshot**, then a short teaching note (what to read · what it means · what not to claim).

---

## Walk the demo report

## 1 · Sample validity

![Sample validity (full section)](guideline_shots/sections/01_sample_validity_full.png)

Start here before any identity or ancestry claim. Read **panel calling rate**, **mean depth**, and the library/capture tables (total reads, mapped fraction, breadth at 1×/4×/10× on the 167K chip). High panel calling (demo ≈99.7%) and usable depth mean the query VCF is dense enough for IBS/PCA/ADMIXTURE; low calling rate or thin depth means later sections are under-powered, not “mysterious ancestry.” Heterozygosity is a **screen against the panel distribution**, not a purity verdict. Modern libraries skip the aDNA damage module—that absence is expected, not a failed run.

**Do not claim:** “high total reads” alone as quality, or that missing damage plots imply failure.

## 2 · Identity & placement

![Identity and placement (full section)](guideline_shots/sections/02_identity_placement_full.png)

This is the clone / kinship lane. Read **Clone + PO list** first (Identical / Parent-Offspring), then the **IBS neighbors** and **KING kinship** tops. In the demo, `HUN89 SZEKSZARDI` appears as Identical with KING ≈0.5; a PO hit (e.g. GM17) is a direct relative screen, not a pedigree certificate. Click a ref row to **pin** it (purple) onto PCA / ADMIXTURE / NJ so the same accession stays highlighted across plots.

**Do not claim:** a high IBS rank as “this variety” unless the class is Identical; do not treat Full-sib / 2nd-degree ranks as naming calls.

## 3 · Population placement

![Population placement (full section)](guideline_shots/sections/03_population_placement_full.png)

Query vs the frozen **2449 × 167K** panel: PCA projection, ADMIXTURE K=2–8, NJ on IBS identity, plus exploratory f3/f4. Use the full section shot for orientation; the three subshots below are the teaching close-ups.

### PCA

![PCA](guideline_shots/sections/03b_pca.png)

Axes are **frozen GCTA64 GRM-PCA** on the panel; the query is a least-squares projection onto those axes (star). Read neighborhood and Grp color, not a country label from a single PC pair.

**Do not claim:** PC coordinates as passport origin or cultivar name.

### ADMIXTURE

![ADMIXTURE](guideline_shots/sections/03c_admixture.png)

In-panel IDs look up frozen Q; new samples use `admixture -P` (lab) or NNLS (Cloud). Compare the query bar to panel strips at the same K; CG labels are **composition summaries**, not hard taxonomy.

**Do not claim:** a K-component fraction as exact geographic ancestry or pure-variety proof.

### NJ tree

![NJ tree](guideline_shots/sections/03d_nj.png)

Neighbor-Joining on **IBS genotype identity**. Tip clicks pin the same ref as in identity tables. Branch length ≠ years or breeding history.

**Do not claim:** the tree as a dated phylogeny or as replacement for clone/PO tables.

## 4 · Sample evidence

![Sample evidence (full section)](guideline_shots/sections/04_sample_evidence_full.png)

Two layers: **query genotype evidence** (curated MAS/GWAS tags and panel leads—observed GT badges, not phenotypes) and **per-query GS predictions** (model score, panel CV *r*, Flag). For breeding talk, only treat traits with decision-grade policy—today that is **OIV 225 colour**; Flag `ok` still means **score ≠ observed berry colour**. Low CV *r* / exploratory traits (e.g. OIV 241-class imbalance) stay demo-only.

**Do not claim:** SDR-window GT as Science haplotype sex; query GT on selection windows as “this sample was selected”; seedlessness from exploratory GS.

## 5 · Panel research

![Panel research (full section)](guideline_shots/sections/05_panel_research_full.png)

Panel-side research context: GWAS / selection / GEA-style views that explain the **reference**, with the query as an overlay where shown. Read which contrasts are panel-only (Grp-vs-rest, among-Grp LocusZoom) versus query-specific. This section teaches the frozen assets behind the report; it is not a second identity call.

**Do not claim:** panel Fst/het sweeps as proof the query was under selection; do not export unpublished full matrices from demos.

## 6 · Methods

![Methods (full section)](guideline_shots/sections/06_methods_full.png)

Provenance and recipes: PCA (GCTA64 axes), identity thresholds, ADMIXTURE lookup vs `-P`/NNLS, phenotype/GWAS/GS model cards, software versions, caveats and references. Use this when a reader asks “how was that number made?” Scope boundaries here match the claim table at the top—binary traits with tiny case counts stay exploratory.

**Do not claim:** methods text as a field-release SOP, or CV *r* as phenotype accuracy in a new orchard.

## 7 · Downloads

![Downloads (full section)](guideline_shots/sections/07_downloads_full.png)

Query-only sidecars: QC TSV, clone/PO, kinship top, this-sample PCA, damage (if any), ADMIXTURE Q for K=2–8. The **2449 reference is not included**. A missing sidecar means that artifact was not produced for this query—not that the HTML report failed.

**Do not claim:** downloads as a public dump of the panel dosage cache.

---

## Privacy

No unpublished genotypes, private coordinates, or full 2449 matrices in public demos.

## Related docs

- Local: `docs/CHIP_COMPANION.md`, `docs/METHODS_breeding.md`, `README.md`, [`FLOWCHART.md`](FLOWCHART.md)
- Public grain (placeholder): https://github.com/Xuzhen-Li/grapeancestry
