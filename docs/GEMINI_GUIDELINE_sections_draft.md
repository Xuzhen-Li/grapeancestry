The GrapeAncestry 167K capture panel analysis companion provides a dedicated analytical framework on the VS-1 reference genome, utilizing a frozen 2449 × 167K dosage cache, GCTA64 principal component axes, ADMIXTURE Q/P matrices (K=2–8), and genomic selection models. This walkthrough uses the `HUN89_query` sample-first-v2 report HTML to demonstrate the workflow. Screenshots displayed across the interface reflect non-overlapping panel crops, supporting a streamlined evaluation pipeline without requiring unsupervised reference cohort refits.

---

### 1 · Sample validity

**Background.** High-throughput DNA capture panels applied to historical, degraded, or modern plant material require rigorous initial validation to ensure data integrity before downstream population and predictive workflows are executed. This layer flags anomalies early, preventing technical artifact propagation through downstream principal component projection and genomic selection models.

**What the report shows.** The interface surfaces key metrics including sequencing depth, missingness rates across the 167K capture sites, and direct concordance checks against the VS-1 reference coordinate space. Users can immediately inspect summary quality indicators within the report header and companion widgets.

**How a careful reader uses it.**

1. Inspect overall missingness and read-depth distribution across the 167K target coordinates.
2. Verify that input alignment matches the VS-1 reference framework.
3. Check for unexpected heterozygosity inflation indicative of DNA contamination or pooling errors.
4. Confirm sample-level identifier integrity, paying special attention to the `_query` suffix convention.
5. Determine whether the sample meets the baseline quality thresholds required for advanced population placement.

**What you may claim / must not claim.**

* **Allowed:** State whether the sample passes baseline quality control metrics for downstream 167K panel analysis.
* **Forbidden:** Do not claim that high data quality guarantees correct biological parentage or authenticates field passport records without further validation.

**Bridge to the next section.** Once technical validity is confirmed, the analysis proceeds to establish the sample's genetic identity and precise multidimensional placement relative to the reference cohort.

---

### 2 · Identity & placement

**Background.** Establishing a robust genetic identity requires distinguishing true biological accessions from technical recaptures while mapping the query against established cultivar space. Maintaining strict separation between query identifiers and panel accession keys prevents downstream registry errors.

**What the report shows.** This section displays matched passport data, group designations (`Grp`), and nearest-neighbor proximity metrics derived by comparing the query's genotype vector against the frozen 2449-sample reference matrix. It flags explicit identity relationships while preserving input provenance.

**How a careful reader uses it.**

1. Review the assigned accession name and associated passport metadata.
2. Confirm that the panel ID (e.g., `HUN89`) and report stem (`HUN89_query`) are correctly distinguished without stripping the `_query` suffix.
3. Evaluate nearest-neighbor distance metrics to assess clonal relationships or duplicate accessions within the 2449 panel.
4. Cross-reference the assigned group (`Grp`) context against historical or breeding records.

**What you may claim / must not claim.**

* **Allowed:** Report the closest matching accessions and passport metadata based on 167K panel distance metrics.
* **Forbidden:** Do not strip the `_query` suffix to look up passport or Q values, and do not treat database proximity as absolute proof of legal pedigree without multi-locus verification.

**Bridge to the next section.** With identity parameters established, the evaluation shifts to broader population-level structures using projection axes and admixture coefficients.

---

### 3 · Population placement (PCA · ADMIXTURE · NJ)

**Background.** Placing an individual sample into a global genomic context requires projecting its genotypes onto pre-computed coordinate systems without distorting established reference structures. This multi-faceted approach combines least-squares PCA projection, fixed ADMIXTURE Q-matrix lookups, and neighbor-joining topologies.

**What the report shows.** The interface renders interactive plots displaying GCTA64 principal component axes, ADMIXTURE ancestry proportions across K=2 through K=8, and neighbor-joining trees. Chrome toggles allow users to switch between K values, interface languages, and display themes while distinguishing query points (black ★/♦) from pinned references (yellow ♦).

**How a careful reader uses it.**

* Examine the query's position along the primary GCTA64 PCA axes to evaluate ancestry stratification.
* Toggle through K=2 to K=8 ADMIXTURE proportions to assess ancestral component allocations.
* Inspect neighbor-joining tree branch placements to identify immediate clade affiliations.
* Compare query placement against pinned reference accessions to verify consistency across methods.

**What you may claim / must not claim.**

* **Allowed:** Describe the query's least-squares projection onto frozen GCTA64 axes and its estimated Q proportions derived via in-panel lookup or `-P`/NNLS.
* **Forbidden:** Do not claim an unsupervised 2449+N reference cohort refit was performed, as the reference axes and parameters remain strictly frozen.

**Bridge to the next section.** Having resolved macro-population affiliations, the focus narrows to specific molecular evidence supporting regional allele states and variant distributions.

---

### 4 · Sample evidence

**Background.** High-resolution evaluation of individual capture sites provides granular validation of specific functional windows and marker genotypes across the genome. This layer inspects local allelic states to corroborate broader population and phenotypic inferences.

**What the report shows.** The section presents detailed genotype tables and regional summaries for key diagnostic windows, including unphased proxy intervals like the sex determination region (SDR). Data points are explicitly tied to the query's capture panel coordinates on VS-1.

**How a careful reader uses it.**

1. Navigate to specific chromosomal windows of interest within the 167K panel layout.
2. Extract individual marker genotypes for verification against expected reference alleles.
3. Review unphased window proxy states for structural or regional markers.
4. Cross-check local genotype patterns with overall sample quality metrics.

**What you may claim / must not claim.**

* **Allowed:** Report specific allele calls and unphased window proxy states observed in the query dataset.
* **Forbidden:** Do not treat unphased window proxies (such as the SDR on chr2 ~14.16–14.35 Mb) as resolved Science haplotypes H1–H5.

**Bridge to the next section.** Transitioning from individual marker evidence, the framework expands into panel-wide genetic association, selection mapping, and genomic prediction models.

---

### 5 · Panel research (incl. Selection Manhattan, Selection LocusZoom, GWAS index, GWAS LocusZoom)

**Background.** Genome-wide association studies (GWAS) and selection scans leverage the 2449-sample frozen panel context to evaluate marker-trait associations and genomic footprints of selection. Overlaying query data onto these established landscapes bridges individual characterization with population-level quantitative genomics.

**What the report shows.** The dashboard provides Manhattan plots and LocusZoom views illustrating selection metrics (such as $F_{ST}$ or heterozygosity) and GWAS index signals (utilizing models like EMMAX, referencing Dong et al. 2023 Science, add8655). Selection LocusZoom and GWAS LocusZoom modules combine panel-level statistical maps with individual query genotype overlays.

**How a careful reader uses it.**

1. Examine Manhattan plots for genome-wide selection signals and GWAS index peaks.
2. Select target loci to open LocusZoom views, analyzing panel-level association or selection statistics alongside query genotypes.
3. Review quantitative genomic selection scores, noting decision-grade boundaries.
4. Assess exploratory trait indicators while keeping sample-size imbalances in mind.

**What you may claim / must not claim.**

* **Allowed:** Report decision-grade genomic selection scores for OIV 225 color (topk_ridge, panel CV $r \approx 0.625$), and describe query genotype overlays on established 2449 panel selection or GWAS tracks.
* **Forbidden:** Do not treat score values as direct phenotypic measurements; do not rank parents or claim seedlessness based on exploratory OIV 241 models (given case_n=10 / control_n=374 imbalance); do not treat query GT overlays as proof that the individual sample was artificially selected; and do not interpret f3/f4 statistics as formal qpAdm/qpGraph analyses.

**Bridge to the next section.** The methodological foundations underpinning these analytical layers are detailed in the subsequent documentation.

---

### 6 · Methods

**Background.** Reproducibility in high-throughput grapevine genomics requires transparent documentation of algorithmic pipelines, reference coordinate systems, and statistical assumptions. This section codifies the mathematical and computational framework utilized throughout the analysis suite.

**What the report shows.** Comprehensive text outlines the VS-1 reference genome alignment standards, GCTA64 projection mechanics, ADMIXTURE estimation procedures, ridge regression genomic selection algorithms, and LocusZoom.js (0.14.0) visualization parameters.

**How a careful reader uses it.**

1. Verify the software versions and mathematical models used to generate upstream matrices and report outputs.
2. Review the constraints governing PCA projection and dosage caching.
3. Consult parameter settings for GWAS and genomic prediction pipelines to ensure proper interpretation of output scores.

**What you may claim / must not claim.**

* **Allowed:** Cite the exact software architectures, reference genomes (VS-1), and statistical models implemented in the pipeline.
* **Forbidden:** Do not present the suite as a black-box whole-genome sequencing (WGS) pipeline, and do not omit reference to the fixed 167K capture panel design.

**Bridge to the next section.** With methodology established, the final section provides access to exportable files and supplementary data formats.

---

### 7 · Downloads

**Background.** Accessing raw report deliverables and structured output files is essential for archiving, secondary analysis, and integration into institutional laboratory information management systems. Standardized file naming conventions prevent downstream parsing errors.

**What the report shows.** The interface offers direct links to download comprehensive deliverables, distinguishing between full Suite HTML outputs (`*.sample-first-v2.report.html`) and Cloud Streamlit JSON structures (`chip.json`) without cross-contamination.

**How a careful reader uses it.**

1. Select the appropriate download format matching your operational environment (Suite HTML vs. Cloud Streamlit JSON).
2. Verify that downloaded filenames preserve required identifiers without mixing output schemas.
3. Archive files alongside corresponding run metadata for audit and reproducibility purposes.

**What you may claim / must not claim.**

* **Allowed:** Retrieve and store standard report deliverables (`*.sample-first-v2.report.html` or `chip.json`) generated by the pipeline.
* **Forbidden:** Do not mix classroom or pipeline output filenames, and do not modify file extensions in a manner that breaks automated downstream parsers.

---

### LocusZoom exploration

The integrated LocusZoom.js (0.14.0) modules provide a dual-layer visualization interface designed to link population-level statistics with individual sample data. In these interactive plots, scatter points represent the **panel** statistical map—displaying GWAS $-\log_{10} p$ values, selection $F_{ST}$, or heterozygosity metrics, with point colors scaled by panel linkage disequilibrium ($r^2$). Directly beneath the scatter plot, the embedded strip and table display **this query’s** specific genotype calls at each corresponding coordinate, allowing researchers to inspect local genomic architecture and individual variant states within a unified window.

---

SOURCE: Gemini draft for GUIDELINE Walk the demo report