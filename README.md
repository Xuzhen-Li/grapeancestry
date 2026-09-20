# grapeancestry

Analysis companion for the grapevine **167K capture panel**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## What this is

GrapeAncestry takes a new grapevine sample and places it against a **frozen 2449 × 167K** reference built on the **VS-1** genome. From the same query you get capture QC, identity / kinship screens, PCA and ADMIXTURE placement, an IBS neighbor-joining tree, passport-style cards, and a colour genomic-selection score where the evidence supports it. The public tree here is the **docs face** first: how the pieces fit, how to read the demo report, and what the final package will accept. Runnable suite code and large panel matrices land in later commits.

Think of three layers: **your input** (FASTQ, BAM/CRAM on VS-1, or a query VCF at the 167K sites), **our reference assets** (VS-1, 167K BED, dosage cache, frozen PCA axes and ADMIXTURE Q/P, passport tables, GS training phenotypes), and **the report** (interactive HTML) or **`chip.json`** on the Cloud path. A query VCF uses the same sites as the chip; it is **not** the 2449-panel matrix.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

More detail on the diagram: [`docs/FLOWCHART.md`](docs/FLOWCHART.md). Claim boundaries, ID traps, and a full sidebar teaching walk live in [`docs/GUIDELINE.md`](docs/GUIDELINE.md).

## How to use

### 1. Read the demo report (today)

The screenshots and walkthrough assume the local suite demo `HUN89_query.sample-first-v2.report.html`. From the suite root so relative assets resolve:

```bash
cd grapeancestry_suite
python -m http.server
# open http://localhost:8000/results/HUN89_query.sample-first-v2.report.html
```

Sidebar order: Sample validity → Identity & placement → Population placement → Sample evidence → Panel research → Methods → Downloads. Walk each section with long screenshots in [`docs/GUIDELINE.md`](docs/GUIDELINE.md).

### 2. Cloud path (when Streamlit is wired)

Upload a **167K-site query VCF** (not FASTQ) into the Chip Companion app, then export **`chip.json`**. Notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

```bash
grapeancestry chip-report --vcf sample.vcf.gz --out chip.json
```

### 3. Final package inputs (VS-1)

| You provide | What happens |
|-------------|--------------|
| **FASTQ** | Trim → map to VS-1 → call genotypes at the 167K BED → query VCF → analyses → report |
| **BAM / CRAM** (on VS-1) | Markdup → call at 167K → same downstream |
| **Query VCF** (@ 167K sites) | Skip calling; run analyses → report or `chip.json` |

Panel row `HUN89` is not the same thing as the capture demo stem `HUN89_query` (independent recapture). Keep those IDs straight when you compare to the 2449 reference.

### 4. What to open next

| Doc | Use it for |
|-----|------------|
| [`docs/GUIDELINE.md`](docs/GUIDELINE.md) | Full demo walk + scientific reading notes |
| [`docs/FLOWCHART.md`](docs/FLOWCHART.md) | Node list behind the diagram |
| [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md) | Online / Cloud companion |
| [`chip/`](chip/) · [`analysis/`](analysis/) | Design and calling folders (fill as code lands) |

## Related repos

- aDNA authentication → [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna)
- Theory dossiers → [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining)
- Nuclear pangenome → [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome)
- Older chip shell → [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip) (points at `chip/`)

## Privacy

This public tree does not ship unpublished genotypes, private coordinates, or the full 2449 panel matrix.

## Author

**Xuzhen Li** · [ORCID 0000-0003-3670-6657](https://orcid.org/0000-0003-3670-6657)
