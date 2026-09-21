# Data notice — GrapeAncestry public tree

## What is in this GitHub repository

- Source code (`src/`, `workflow/`, `app.py`, launchers)
- Documentation (`docs/`, including GUIDELINE screenshots)
- Ages **demo HTML** under `demo/` (view-only showcase)

## What is NOT in git (and must not be added)

- VS-1 FASTA / BWA index
- Panel VCF / 2449 × 167K dosage caches / frozen Q·P·eigenvec
- Customer FASTQ / BAM / CRAM
- Fat image blob `grapeancestry-v1.0.0-amd64.tar` (or any `*.amd64.tar`)
- `results/cache/*.npz`

## License split

- **MIT** applies to **code** in this repository.
- Panel **genotypes** and **phenotypes** are **not** MIT and are not redistributed here.

## Docker image policy

- Product tag: `grapeancestry:1.0.0`
- Customer file: `grapeancestry-v1.0.0-amd64.tar` — via **Zenodo Restricted ([doi:10.5281/zenodo.22868632](https://doi.org/10.5281/zenodo.22868632))**.
- **Never** `docker push` that fat image (panel assets inside).
- **Never** attach the tar to a **public** GitHub Release.

## DIY without the kit

Stage your own VS-1 + frozen 2449×167K panel assets (FASTA/indices, sites BED, dosage, PCA·ADMIXTURE) — not in public git.

