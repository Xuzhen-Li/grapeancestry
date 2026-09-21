# GrapeAncestry Pass A (fact-checked)

> **Lead note:** Raw Gemini output saved as `GEMINI_passA_ABCD_out.md` had hard-boundary errors (e.g. MIT≠panel misread as mitochondria; DIY 00a≠fastp; LocusZoom≠GEA; HUN89_query mislabeled “simulated”). This file is the **corrected** markdown for workers. Still: **DRAFT for lead; workers land after fact-check.**

## A. Captions

| File | Caption |
|------|---------|
| `01_sample_validity_01.png` | Sample validity — report metadata and method coverage for the Ages aDNA demo (V5; Noraz et al. 2026 *Nat Commun* doi:10.1038/s41467-026-70166-z). |
| `01_sample_validity_02.png` | Sample validity — capture QC (depth, calling, on-target) on the 167K sites. |
| `01_sample_validity_damage.png` | aDNA damage — terminal misincorporation and fragment-length patterns (Ages). |
| `02_identity_01.png` | Identity — clone / parent–offspring screen and IBS kinship (keep panel `HUN89` ≠ stem `HUN89_query`). |
| `03_pca.png` | Population — query projected onto **frozen** GCTA64 PCA axes (VS-1 frame; Dong et al. 2023 *Science* doi:10.1126/science.add8655). |
| `03_admixture.png` | Population — ADMIXTURE proportions using **frozen** Q/P for K=2–8 (lookup or `-P` / NNLS; no 2449+N refit). |
| `03_nj.png` | Population — IBS neighbour-joining tree as a visual neighbor aid (use with identity tables). |
| `04_sample_evidence_01.png` | Sample evidence — query genotypes at curated sites; only **OIV 225** colour GS is decision-grade (**score ≠ phenotype**). |
| `05_locuszoom.png` | Panel research — LocusZoom regional **panel** map with **query GT overlay** (overlay ≠ “this sample was selected”). |

## B. First hour + FAQ

### First hour

1. **Demo (view-only):** `cd demo && python3 -m http.server 8000` → open `http://127.0.0.1:8000/results/Ages.sample-first-v2.report.html` (keep `demo/assets/` beside `demo/results/`).
2. **Docker kit:** Download `grapeancestry-v1.0.0-amd64.tar` from `[DOCKER_TAR_URL — fill before publish]`; place next to `start.sh`; run `./start.sh` (loads image via `docker load` when `grapeancestry:1.0.0` is missing). UI **http://127.0.0.1:8501** · reports **http://127.0.0.1:8502**.
3. **DIY:** Stage your own VS-1 + 2449 panel assets, then start at `docs/steps/` **`00a`** (panel sites/metadata) through **`13b`** (sample-first V2 HTML). Without those assets, analyze/run are expected to stop.

### FAQ

1. **BAM `@SQ` fail?** Accepted BAM must already be on **VS-1** contig names. `chr1` / 12X / PN40024 → fail → use FASTQ.
2. **Missing tar?** Docs-only clone cannot finish Analyze. Get `grapeancestry-v1.0.0-amd64.tar` from `[DOCKER_TAR_URL — fill before publish]`.
3. **MIT ≠ panel?** **MIT = code license only.** Panel genotypes/phenotypes are not MIT (`DATA_NOTICE.md`).
4. **ENA 12Xv2 BAM URL?** Download-demo only (`ERR16654874` / `PRJEB94459`). It is **not** VS-1; Analyze-as-BAM must fail `@SQ`.
5. **8501 vs 8502?** 8501 = product UI; 8502 = `*.sample-first-v2.report.html` server.
6. **`HUN89` vs `HUN89_query`?** Panel row ≠ report stem (independent FASTQ recapture). Do not strip `_query` for passport/Q lookup.
7. **Apple Silicon?** Use a **linux/amd64** engine; ADMIXTURE 1.3.0 is linux x86_64.
8. **Empty `./input`?** Add FASTQ/BAM/VCF, or use Get Ages / Get HUN89_query.
9. **OIV 225?** Only decision-grade colour GS today; **score ≠ phenotype**.
10. **`chip.json`?** Optional Cloud/classroom path — not the v1 product (v1 = `*.sample-first-v2.report.html` only).
11. **Never `docker push`?** Fat image contains panel assets.
12. **Ages cite?** V5; Noraz et al. 2026 *Nat Commun* doi:10.1038/s41467-026-70166-z.

## C. DIY spine (`00a`→`13b`)

User must supply **VS-1 + 2449** assets (not in public git).

| Step | Goal | Entry |
|------|------|-------|
| 00a | Panel sites + sample metadata | docs/steps `00a` · report-path only until assets staged |
| 00b | Reference genome (VS-1 coordinates) | docs/steps `00b` |
| 00c | Panel VCF + dosage cache | `python -m grapeancestry.core.dosage …` (suite) / docs/steps `00c` |
| 00d | Freeze PCA axes | docs/steps `00d` · `bin/gcta64` in suite |
| 00e | Freeze ADMIXTURE Q/P (K=2–8) | docs/steps `00e` · `bin/admixture` 1.3.0 |
| 00f–00g | Phenotype tables / optional cloud pack | skip if ancestry-only |
| 01a | Trim + map to VS-1 | `grapeancestry run` · Snakefile: `fastp` or AdapterRemoval3 → `bwa mem` / `bwa aln` |
| 01b | Markdup + call at 167K BED | same run path · `samtools markdup` → `bcftools mpileup/call -T` sites BED |
| 02a–02b | Capture QC + calling/method coverage | `grapeancestry qc` · inside `analyze` |
| 03a–03b | Clone/PO + IBS/kinship | `grapeancestry identity` |
| 04a–04b | Load frozen PCA + project query | `grapeancestry project` |
| 05a–05b | Resolve ADMIXTURE family + project Q | `grapeancestry admix-project` |
| 06a–06b | IBS distance + NJ layout | report-path (`popgen/tree_nj.py`) |
| 07a–07b | Optional aDNA damage | report-path / mapDamage lite (Ages SE) |
| 08–10 | f3/f4 · selection · GWAS (exploratory / panel) | `grapeancestry selection` · `grapeancestry gwas` · f-stats report-path |
| 11a–11b | GS train/predict (OIV 225 decision-grade) | `grapeancestry gs-train` · `gs-predict` |
| 12a–12b | Selection / GWAS LocusZoom | report-path |
| 13a–13b | Report payload + **sample-first V2 HTML** | `grapeancestry analyze` / report builders → `*.sample-first-v2.report.html` |
| 14a–14b | Optional Cloud JSON | `grapeancestry chip-report` → `chip.json` (not v1 product) |

## D. Glossary

- **VS-1** — Reference coordinate frame (Dong et al. 2023 *Science* doi:10.1126/science.add8655).
- **167K** — Capture site list / BED; query VCF is called here (not the 2449 matrix).
- **Frozen PCA** — GCTA64 GRM-PCA axes on `panel167k_nogwas`; query least-squares projected.
- **Frozen ADMIXTURE Q/P** — Panel Q/P for K=2–8; lookup or `admixture -P` / NNLS; no 2449+N refit.
- **Query VCF** — Customer VCF at 167K sites on VS-1.
- **Dosage cache** — Analysis matrix for the frozen 2449 panel (`npz`).
- **Treat-as-query / `_query`** — Forces report id `{id}_query`; keeps recapture ≠ panel row.
- **Sample-first V2** — v1 product HTML: `*.sample-first-v2.report.html` (port 8502 in kit).
- **OIV 225** — Only decision-grade colour GS today; score ≠ phenotype.
- **SDR proxy** — Unphased window proxy; not Science haplotypes H1–H5.
- **chip.json** — Optional Cloud/classroom JSON; not v1 primary.
- **Kit** — Private Docker tar + `start.sh` (and/or gtbs-chip-service-kit scaffold).
- **DIY** — Self-supply VS-1 + panel assets; follow `docs/steps/00a`–`13b`.
- **Ages / V5** — Public aDNA demo (Noraz et al. 2026 *Nat Commun* doi:10.1038/s41467-026-70166-z).
- **HUN89** — Panel row id in the 2449.
- **HUN89_query** — Independent FASTQ recapture report stem (≠ panel HUN89).
- **8501 / 8502** — Kit UI / report server.
- **MIT** — Code license only; not panel data.

李旭真 / Li Xuzhen. DRAFT for lead; workers land after fact-check.
