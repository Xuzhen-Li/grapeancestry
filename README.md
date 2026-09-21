# grapeancestry

Grapevine **167K** capture companion: place a new query on frozen **VS-1** axes and hand in a report — not a whole-genome resequencing suite, and not the cross-crop scaffold ([gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit)).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0003--3670--6657-a6ce39)](https://orcid.org/0000-0003-3670-6657)

## Tonight hand-in

**Tonight you hand in one filename** (not every sidebar tab):

| Door | Hand-in |
|------|---------|
| **Cloud** | `chip.json` |
| **Suite** (Docker / lab image) | `*.sample-first-v2.report.html` |

Opening the Ages demo in this public clone is **practice** — it does not mint a new hand-in file. Use the Suite/Cloud door above when you actually submit.

## Start here

**One door for newcomers:** [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

Then:

1. Open the Ages demo HTML: [`demo/`](demo/) (commands below).
2. Screenshot walkthrough: [`docs/GUIDELINE.md`](docs/GUIDELINE.md).
3. Classroom cloud notes: [`docs/CHIP_COMPANION.md`](docs/CHIP_COMPANION.md).

Folder inventory (optional): [`docs/REPO_MAP.md`](docs/REPO_MAP.md).

## Analysis flow

**Three inputs, one line:** FASTQ / BAM / query VCF → **VS-1** → 167K sites → analyses → report or `chip.json`.

![GrapeAncestry analysis flowchart](docs/flowchart_vs1_analysis_v2.png)

*Solid arrows stop at tonight's hand-in. Dashed = how you read the report. Detail: [`docs/FLOWCHART.md`](docs/FLOWCHART.md).*

## What this is

GrapeAncestry places a **new grapevine query** against a **frozen 2449 × 167K** reference on **VS-1**. From the same sample you can read capture QC, identity and kinship, PCA and ADMIXTURE on frozen axes, an IBS neighbour-joining tree, passport-style cards, and — where evidence supports ranking — a colour genomic-selection score.

- Coordinates and calling use **VS-1**. Inputs: FASTQ, BAM/CRAM already on VS-1, or a **query VCF at the 167K sites** (not the 2449-panel dosage matrix).
- PCA axes and ADMIXTURE Q/P are **frozen**; new samples are projected, not used to refit the panel.
- Today only **OIV 225** colour GS is decision-grade; other traits stay exploratory (rules in the GUIDELINE).
- **ID trap:** panel row `HUN89` ≠ report stem `HUN89_query`. Do not strip `_query` for passport or frozen Q lookups.

**Public clone default:** read docs + open Ages HTML. **VS-1, FASTQ, and the 2449 dosage cache are not shipped.** Lab CLI / Docker / full `src/` runs need private assets — see USER_GUIDE doors B–D; do not expect `grapeancestry run` from a fresh GitHub clone alone.

**Boundary:** this repo = grapevine **167K walkthrough**. Next crop's `profile.yaml` template = [gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit).

## Demo (Ages)

**Primary demo:** `Ages` (`Ages.sample-first-v2.report.html`). Open the shipped HTML to learn the sidebar — you do **not** need to re-run V5 FASTQ tonight.

**Cite the source data:** Noraz et al. 2026 *Nat Commun* ([doi:10.1038/s41467-026-70166-z](https://doi.org/10.1038/s41467-026-70166-z); incl. **Ludovic Orlando**).

Open the shipped HTML (view-only; does **not** create a hand-in):

```bash
cd demo
python -m http.server 8000
# http://localhost:8000/results/Ages.sample-first-v2.report.html
```

Keep `demo/assets/` beside `demo/results/`. Notes: [`demo/README.md`](demo/README.md). Full sidebar screenshots live in [`docs/GUIDELINE.md`](docs/GUIDELINE.md) only — not repeated here.

## Deeper docs (after Start here)

| Doc | Role |
|-----|------|
| [`docs/steps/`](docs/steps/) | Fine steps `00a`–`14b` (prep → report → cloud) |
| [`docs/PIPELINE.md`](docs/PIPELINE.md) · [`docs/ANALYSIS_METHODS.md`](docs/ANALYSIS_METHODS.md) | Science contracts / methods |
| [`docs/SCRIPTS.md`](docs/SCRIPTS.md) | Module / script map **(lab)** |

## Lab / image doors (optional)

Short reminders; full steps stay in USER_GUIDE.

- **B · Docker customer image** — unpack package → `./start.sh` → http://localhost:8501 → hand-in `*.sample-first-v2.report.html`.
- **C · Cloud** — upload 167K-site query VCF → hand in `chip.json` ([CHIP_COMPANION](docs/CHIP_COMPANION.md)).
- **D · Local suite** — needs conda env + panel assets not in this clone.

BAM tip: if `@SQ` looks like `chr1` / 12X / PN40024, re-align to VS-1 or start from FASTQ.

## Related

[gtbs-chip-service-kit](https://github.com/Xuzhen-Li/gtbs-chip-service-kit) · [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) · [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining) · [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome)

No unpublished genotypes or full 2449 matrices in this public tree. **Xuzhen Li** · [ORCID](https://orcid.org/0000-0003-3670-6657)
