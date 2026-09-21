# FAQ — GrapeAncestry v1.0.0

Fact-checked from Gemini Pass A (corrected). Commands and claims fenced to this repo + Dong et al. 2023 *Science* (VS-1) + Noraz et al. 2026 *Nat Commun* (Ages/V5).

## First hour

1. **Demo (view-only):** `cd demo && python3 -m http.server 8000` → open `http://127.0.0.1:8000/results/Ages.sample-first-v2.report.html` (keep `demo/assets/` beside `demo/results/`).
2. **Docker kit:** Download `grapeancestry-v1.0.0-amd64.tar` from `[DOCKER_TAR_URL — fill before publish]`; place next to `start.sh`; run `./start.sh`. UI **http://127.0.0.1:8501** · reports **http://127.0.0.1:8502**.
3. **DIY:** Stage your own VS-1 + 2449 panel assets, then follow [`docs/steps/`](steps/) **`00a`→`13b`**. Without those assets, analyze/run are expected to stop.

Three paths / outcomes: [README](../README.md). Data bans: [`DATA_NOTICE.md`](../DATA_NOTICE.md).

## FAQ

1. **BAM `@SQ` fail?** Accepted BAM must already use **VS-1** contig names. `chr1` / 12X / PN40024 → fail → use FASTQ.
2. **Missing tar?** A docs-only clone cannot finish Analyze. Get `grapeancestry-v1.0.0-amd64.tar` from `[DOCKER_TAR_URL — fill before publish]`.
3. **MIT ≠ panel?** **MIT = code license only.** Panel genotypes/phenotypes are not MIT (`DATA_NOTICE.md`).
4. **ENA 12Xv2 BAM URL?** Download-demo only (`ERR16654874` / `PRJEB94459`). It is **not** VS-1; Analyze-as-BAM must fail `@SQ`.
5. **8501 vs 8502?** 8501 = product UI; 8502 = `*.sample-first-v2.report.html` server.
6. **`HUN89` vs `HUN89_query`?** Panel row ≠ report stem. Do not strip `_query` for passport or frozen-Q lookup.
7. **Apple Silicon?** Use a **linux/amd64** engine; ADMIXTURE 1.3.0 is linux x86_64.
8. **Empty `./input`?** Add FASTQ/BAM/VCF, or use **Get Ages** / **Get HUN89_query** in the kit UI.
9. **OIV 225?** Only decision-grade colour GS today; **score ≠ phenotype**.
10. **`chip.json`?** Optional Cloud/classroom path — not the v1 product (v1 = `*.sample-first-v2.report.html` only).
11. **Never `docker push`?** The fat image contains panel assets.
12. **Ages cite?** Sample **V5**; Noraz et al. 2026 *Nat Commun* [doi:10.1038/s41467-026-70166-z](https://doi.org/10.1038/s41467-026-70166-z).

Author: 李旭真 / Li Xuzhen · ORCID [0000-0003-3670-6657](https://orcid.org/0000-0003-3670-6657).
