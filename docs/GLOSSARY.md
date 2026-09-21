# Glossary — GrapeAncestry v1.0.0

Fact-checked from Gemini Pass A (corrected). Paper details only from the two cited DOIs when named.

| Term | Meaning |
|------|---------|
| **VS-1** | Reference coordinate frame (Dong et al. 2023 *Science*, [doi:10.1126/science.add8655](https://doi.org/10.1126/science.add8655)). |
| **167K** | Capture site list / BED; query VCF is called at these sites (not the 2449 matrix). |
| **Frozen PCA** | GCTA64 GRM-PCA axes on the panel freeze; query is projected (not used to refit). |
| **Frozen ADMIXTURE Q/P** | Panel Q/P for K=2–8; lookup or `admixture -P` / NNLS; no 2449+N unsupervised refit. |
| **Query VCF** | Customer VCF at 167K sites on VS-1. |
| **Dosage cache** | Analysis matrix for the frozen 2449 panel (`npz`; not in public git). |
| **Treat-as-query / `_query`** | Forces report id `{id}_query` so a recapture is not confused with a panel row. |
| **Sample-first V2** | v1 product HTML: `*.sample-first-v2.report.html` (kit port **8502**). |
| **OIV 225** | Only decision-grade colour GS today; **score ≠ phenotype**. |
| **SDR proxy** | Unphased window proxy; not Science haplotypes H1–H5. |
| **chip.json** | Optional Cloud/classroom JSON; **not** the v1 primary product. |
| **Kit** | Private Docker tar + `start.sh` (and/or [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit) scaffold). |
| **DIY** | Self-supply VS-1 + panel assets; follow `docs/steps/00a`–`13b`. |
| **Ages / V5** | Public aDNA demo (Noraz et al. 2026 *Nat Commun*, [doi:10.1038/s41467-026-70166-z](https://doi.org/10.1038/s41467-026-70166-z)). |
| **HUN89** | Panel row id in the 2449. |
| **HUN89_query** | Independent FASTQ recapture report stem (≠ panel `HUN89`). |
| **8501 / 8502** | Kit Streamlit UI / report server. |
| **MIT** | Code license only; not panel genotypes/phenotypes. |

See also: [`FAQ.md`](FAQ.md) · [`steps/`](steps/) · [`PIPELINE.md`](PIPELINE.md).
