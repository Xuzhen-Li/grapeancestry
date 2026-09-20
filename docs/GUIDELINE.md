# GrapeAncestry guideline (chip companion)

**Status:** public docs on `Xuzhen-Li/grapeancestry` (demo walkthrough). Full suite CLI lands later on this public tree.  
**Language:** English primary.

This page has two jobs:

1. **How to use** the product as it exists today (three lanes).
2. **How to read** the demo HTML report — every sidebar section and every screenshot below has an intro.

Diagram: [`flowchart_vs1_analysis_v2.png`](flowchart_vs1_analysis_v2.png) · [`FLOWCHART.md`](FLOWCHART.md) · Cloud notes: [`CHIP_COMPANION.md`](CHIP_COMPANION.md).

---

## Final-package inputs (all on VS-1)

| Input | What happens | What it is *not* |
|-------|----------------|------------------|
| **FASTQ** (modern PE or aDNA SE) | Trim → map to **VS-1** → markdup → `bcftools` call at the **167K BED** | Not a whole-genome resequencing deliverable |
| **BAM / CRAM** | Must already be on **VS-1** (`@SQ` names overlap VS-1). Then markdup → call at 167K | 12X / PN40024 / wrong reference will fail |
| **Query VCF** | Sites ∩ 167K on VS-1 coordinates → analyses only | **Not** the 2449 × 167K panel matrix |

**ID trap:** panel row `HUN89` ≠ capture/report stem `HUN89_query` (independent FASTQ recapture). Do not strip `_query` to look up passport or frozen Q.

**Claim boundaries (read before you cite anything):**

- Only **OIV 225** colour GS is decision-grade / rankable today.
- **SDR** = unphased window **proxy**, not Science haplotype sex (H1–H5).
- **Selection** = 2449 panel Grp-vs-rest context; query GT is overlay ≠ “this sample was selected”.
- **GS score ≠ phenotype**; GWAS p/β are panel results, not the customer’s measured trait.

> Classroom doors: **Cloud** → `chip.json`; **Suite** → `*.sample-first-v2.report.html`. Do not mix filenames.

---

## Usage flow (how it is used today)

Three lanes. Pick **one** lane for a given night; the hand-in filename must match that lane.

### Lane A — Public docs (this GitHub tree)

**Who:** Anyone reviewing the public face; classrooms without a suite checkout.

**Steps:**

1. Clone or browse `https://github.com/Xuzhen-Li/grapeancestry`.
2. Read this GUIDELINE top-to-bottom (usage → report walkthrough).
3. Open [`FLOWCHART.md`](FLOWCHART.md) for the analysis boxes; [`CHIP_COMPANION.md`](CHIP_COMPANION.md) for Cloud vs Lab doors.
4. Use the screenshots below as a stand-in for the interactive HTML (GitHub cannot run the report in-repo).

**Honest stop:** this tree does **not** ship a runnable `grapeancestry` binary, VS-1, or the 2449 dosage cache. Commands in Lane B live in the private suite package.

### Lane B — Local suite (developer / lab Mac)

**Who:** Lab machine with the private `grapeancestry_suite` checkout, conda env `ga`, and panel assets.

**Install (once):**

```bash
conda activate ga   # bwa fastp snakemake bcftools samtools python=3.11
cd /path/to/grapeancestry_suite
pip install -e ".[dev,web]"
export PATH="$PWD/bin:$PATH"   # ADMIXTURE 1.3.0 wrapper
grapeancestry --help
```

**End-to-end demo (FASTQ → 167K VCF → analyses → HTML):**

```bash
grapeancestry run --config config/mbp_demo.yaml --samples config/samples_demo.yaml \
  --sample HUN89 --mapping full -j 4
# Modern PE path: fastp → bwa mem → VS-1 → markdup → bcftools -T 167K BED
# → results/HUN89*.vcf.gz + sample-first V2 HTML under results/
```

Ages aDNA SE demo: `--samples config/samples_ages.yaml --sample Ages` (AdapterRemoval + `bwa aln`).

**If you already have a query VCF** (sites on VS-1 ∩ 167K), skip mapping and run post-VCF pieces, for example:

| Goal | Typical command (suite) |
|------|-------------------------|
| Rebuild QC + identity + HTML | `grapeancestry analyze …` (see suite `--help`) |
| IBS / clone screen | `grapeancestry identity --vcf … --sample …` |
| PCA project onto frozen axes | `grapeancestry project --vcf … --sample …` |
| ADMIXTURE for new IDs | `grapeancestry admix-project --vcf …` (lab `-P`) |
| Cloud / classroom JSON | `grapeancestry chip-report --vcf sample.vcf.gz --out chip.json` |
| Pack Streamlit demos | `python -m grapeancestry.cloud` then `streamlit run app.py` |

**View an existing demo report (view-only):**

```bash
cd /path/to/grapeancestry_suite   # must be suite root so ../assets resolve
python -m http.server
# open http://localhost:8000/results/HUN89_query.sample-first-v2.report.html
```

`http.server` does **not** create a hand-in file. Hand-in for Suite is the HTML filename itself (or Cloud `chip.json`).

**What “done” looks like for Suite:** `*.sample-first-v2.report.html` opens with assets; method coverage shows available vs unavailable; no decision-grade claim beyond OIV 225.

### Lane C — Cloud Chip Companion (classroom night)

**Who:** Streamlit Cloud (or local `streamlit run app.py`) with packed `data/cloud/` fingerprints.

**Steps:**

1. Prepare a **167K-site query VCF** (not FASTQ).
2. Open the Chip Companion app → upload VCF or pick a named demo.
3. Scan top-to-bottom: QC → self-vs-clone IBS → passport / SDR **proxy** / trait card → purity & parentage → (optional advanced) → **colour GS last**.
4. Hand in **`chip.json`** (Cloud door).

**Honest stop:** Cloud has no bwa/bcftools/ADMIXTURE binary; new samples use NNLS onto frozen P. Docker / HPC (`environment-hpc.yml`, `docker compose up`) is **Later Lab**, not tonight.

### After you have a report — how to read it

**Sidebar order (left):**

1. Sample validity  
2. Identity & placement  
3. Population placement (PCA · ADMIXTURE · NJ)  
4. Sample evidence  
5. Panel research (selection / GEA / **LocusZoom**)  
6. Methods  
7. Downloads  

**Chrome controls:**

- Black ★/♦ = **query**; yellow ♦ = **pinned** reference. Click a table row or plot point to pin; pinned IDs overlay PCA / ADMIXTURE / NJ.
- ADMIXTURE **K = 2…8** buttons change the Q bar / legend, not the frozen panel fit.
- Lang EN / 中文; Theme Light / Dark / System.
- Search: ID / variety / origin / VIVC when passport fields exist.

Screenshots below are **non-overlapping panel crops** (no full+viewport duplicates). Panel research stays coarse; **one dedicated LocusZoom** shot is included.

---

## Walk the demo report

Demo stem: `HUN89_query` (modern PE recapture). Compare mentally to panel ID `HUN89` — same variety story, different file identity.

### 1 · Sample validity

**What this section is for.** Prove the HTML is about *this* query before you trust any plot: who generated it, which artifacts fed it, which methods actually ran, and whether capture QC / aDNA damage make sense for the library type.

**How to use it.** Read metadata → method coverage → conclusions. If calling rate or depth look broken, stop; do not interpret IBS or GS. Modern PE should not show ancient-DNA damage patterns.

![validity 1 — metadata and conclusions](guideline_shots/panels/01_sample_validity_01.png)

*What you see:* Report / query / source IDs, timestamps, paths to dosage cache, VCF, BAM, damage, and LocusZoom JSON; method coverage table; auto conclusions.  
*How to read:* Confirm `query_id` vs `source_sample_id`. Check Selection / GWAS LocusZoom paths exist if you will open those tabs. Conclusions should match library type (modern PE vs aDNA).

![validity 2 — capture QC](guideline_shots/panels/01_sample_validity_02.png)

*What you see:* On-target fraction, mean depth, breadth, calling rate, heterozygosity summary.  
*How to read:* Calling rate and depth gate downstream overlays. Heterozygosity is a **screen**, not a purity or clone call — use Identity for that.

![validity 3 — damage note](guideline_shots/panels/01_sample_validity_03.png)

*What you see:* Damage / aDNA module status.  
*How to read:* Missing or “not applicable” damage on modern PE is expected. Only treat damage profiles as meaningful on SE aDNA libraries.

### 2 · Identity & placement

**What this section is for.** Place the query against the frozen **2449** panel: exact clone / parent–offspring first, then ranked IBS and KING neighbors. Pinning here drives overlays on Population plots.

**How to use it.** (1) Check Identical + PO. (2) Scan IBS / kinship tops. (3) Click a row to pin a reference (yellow ♦). (4) Jump to PCA / ADMIXTURE / NJ with that pin active. Mid-rank IBS hits are **not** variety names.

![identity 1 — clone and PO](guideline_shots/panels/02_identity_01.png)

*What you see:* Clone + PO list (Italy 4K screen) and top IBS / kinship tables for `HUN89_query`.  
*How to read:* Identical to panel `HUN89` is expected for this demo recapture — still keep the ID trap in mind for passport / Q lookup. PO / full-sib ranks are kinship hints, not pedigree certificates.

![identity 2 — neighbors detail](guideline_shots/panels/02_identity_02.png)

*What you see:* Continued neighbor detail (IBS and KING sides).  
*How to read:* Use pins to compare one neighbor at a time on Population plots. Do not invent a variety name from a mid-list IBS score.

### 3 · Population placement

**What this section is for.** Show where the query sits in the **frozen** panel coordinate system. PCA axes and ADMIXTURE Q/P were fit on 2449; the query is projected / `-P` / NNLS — never unsupervised-refit 2449+N per customer.

**How to use it.** Switch PC pairs and K; keep one pin from Identity; ask whether the query sits with the expected Grp / CG cluster. Out-of-window points may be hidden — use the PC pair toggles.

![PCA](guideline_shots/panels/03_pca.png)

*What you see:* 2D + 3D GCTA64 PCA projection; black star = query; colours = panel Grps.  
*How to read:* Metadata should say frozen GCTA64 GRM-PCA (`panel167k_nogwas`). Least-squares projection onto frozen axes — not a new smartPCA run per sample.

![ADMIXTURE](guideline_shots/panels/03_admixture.png)

*What you see:* ADMIXTURE bars / components for K = 2–8.  
*How to read:* In-panel IDs **lookup** frozen Q. New IDs use `admixture -P` (lab) or NNLS (Cloud). Changing K only changes which Q vector you view.

![NJ](guideline_shots/panels/03_nj.png)

*What you see:* Neighbor-joining tree on IBS identity (query + panel tips).  
*How to read:* Topology is a visual neighbor aid, not a dated phylogeny. Use with IBS tables, not instead of them.

### 4 · Sample evidence

**What this section is for.** Show what **this query called** at curated MAS / GWAS / trait sites, next to **panel** annotations. The section answers “what alleles do we observe?” — not “what phenotype does the plant have?”

**How to use it.** Read the caveat box first. Scan GT pills (0/0 REF, 0/1 het, 1/1 ALT). For breeding decisions, only treat **OIV 225** colour GS as rankable; treat SDR / seedless / other OIV cards as proxy or exploratory.

![evidence 1 — genotype evidence table](guideline_shots/panels/04_sample_evidence_01.png)

*What you see:* Site · evidence type (curated MAS/GWAS tag vs panel GWAS lead) · query GT · status · panel annotation (Dong 2023, gene notes, SDR tag, …).  
*How to read:* Colour pills encode **genotype**, not phenotype. “Panel GWAS lead” stats (e.g. −log10 p) are from the 2449 map.

![evidence 2 — trait / GS cards](guideline_shots/panels/04_sample_evidence_02.png)

*What you see:* Trait / MAS cards and GS prediction rows.  
*How to read:* **OIV 225** colour GS (`topk_ridge`) is the only decision-grade score today. OIV 241 / seedlessness remain exploratory (small case n). SDR = proxy ≠ haplotype sex. Score ≠ field phenotype.

### 5 · Panel research

**What this section is for.** Show **2449-panel** research context: selection / sweep scans, named domestication windows, GEA/origin indexes, and regional maps. The query appears only as a **genotype overlay**.

**How to use it.** Read panel Manhattan / heatmaps / tables first. Then open LocusZoom for a named window or GWAS lead. Never cite a sweep as “this customer sample was selected.”

![panel 1 — genome-wide selection / sweeps](guideline_shots/panels/05_panel_research_01.png)

*What you see:* Genome-wide selection / simplified-het vs mean-het style scans, sweep tables, named-window heatmaps / Fst–het summaries on the panel.  
*How to read:* Sweep rules are panel Grp-vs-rest (Fst high **and** within-Grp windowed het low). Clicking a cell / row jumps toward LocusZoom.

![panel 2 — query overlay at named windows](guideline_shots/panels/05_panel_research_02.png)

*What you see:* Per-site query genotypes inside carried / named windows (lead, design-time, literature tags).  
*How to read:* Overlay only — explains what *this* sample carries at panel-interesting sites; it does not move the panel Fst map.

![panel 3 — regional context toward LocusZoom](guideline_shots/panels/05_panel_research_03.png)

*What you see:* Regional panel context (among-Grps Fst), window picker, and the LocusZoom widget entry.  
*How to read:* Choose a named window (e.g. SDR trait locus) and Y metric (Fst / windowed het). Colour = panel r² to the lead.

![panel 4 — window / trait locus tables](guideline_shots/panels/05_panel_research_04.png)

*What you see:* Window summaries, reference / Dong-style overlaps, trait-locus indexes for the region.  
*How to read:* Use as a bibliography + interval checklist before claiming a gene story.

![panel 5 — GWAS index into LocusZoom](guideline_shots/panels/05_panel_research_05.png)

*What you see:* Panel GWAS / GS index rows and the start of the GWAS LocusZoom + query overlay stack.  
*How to read:* Pick a trait lead (prefer OIV 225 for decision talk). Then use the dedicated LocusZoom panel below.

### 5b · LocusZoom (one dedicated panel)

**What this section is for.** Interactive regional plot (**LocusZoom.js 0.14.0**). Sidebar entries: **Selection LocusZoom** and **GWAS LocusZoom**.

**How to use it.**

1. Pick window / trait from the dropdown.
2. Set Y (association −log10 p for GWAS; Fst or windowed het for selection).
3. Drag to pan, scroll to zoom, click a SNP or gene.
4. Read the **query genotype overlay** (strip + table) under the plot — that strip is *this sample*, while the scatter is the **panel** map.

![LocusZoom — panel GWAS + query GT](guideline_shots/panels/05_locuszoom.png)

*What you see:* Example **GWAS LocusZoom** for **OIV 225** colour on chr19: peak, gene track (`Vvsyl19G000343` region), lead `19:6564633`, and `HUN89_query` GT overlay (het at lead).  
*How to read:* p / β / MAF / r² come from the 2449 EMMAX/P3D map. Query GT answers “what did we call here?”, not “what colour is the berry?” Selection LocusZoom uses the same widget with Y = among-Grps Fst / het — still panel context only.

### 6 · Methods

**What this section is for.** Spell out how each number was produced (software, frozen assets, caveats). It is documentation inside the report — **not** a field SOP or a guarantee of publication readiness.

**How to use it.** When a plot looks surprising, jump here for the exact method string (e.g. GCTA64 projection, ADMIXTURE lookup vs `-P`, simplified Fst). Cite methods papers from the report text, not from memory.

![methods 1](guideline_shots/panels/06_methods_01.png)

*What you see:* Narrative for QC, calling, and identity layers.  
*How to read:* Match artifact paths back to Sample validity provenance.

![methods 2](guideline_shots/panels/06_methods_02.png)

*What you see:* PCA projection, ADMIXTURE, relatedness / NJ methods.  
*How to read:* Confirm “frozen axes / frozen Q” language — unsupervised refits are out of scope for customer reports.

![methods 3](guideline_shots/panels/06_methods_03.png)

*What you see:* GS, selection / GEA, f-stats, and assembly caveats.  
*How to read:* Re-check decision scope (OIV 225 only) and exploratory labels (f3/f4, OIV 241).

### 7 · Downloads

**What this section is for.** Take away **query-scoped** sidecars (tables / small plots). The public demo never ships the full 2449 dosage matrix.

**How to use it.** Download what you need for a notebook or hand-in appendix; do not expect panel VCFs here.

![downloads](guideline_shots/panels/07_downloads.png)

*What you see:* Links to query-only artifacts tied to this report stem.  
*How to read:* If a link is missing, the method was unavailable (see Sample validity coverage) — that is expected, not a broken page.

---

## Privacy

No unpublished genotypes, private coordinates, or full 2449 matrices in public demos.

## Related

[`CHIP_COMPANION.md`](CHIP_COMPANION.md) · [`FLOWCHART.md`](FLOWCHART.md) · https://github.com/Xuzhen-Li/grapeancestry
