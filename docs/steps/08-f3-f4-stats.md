# Step 08 — f3 / f4 (exploratory)

## Goal

Exploratory allele-sharing contrasts of the query vs panel Grp means (not formal ADMIXTOOLS qp graphs).

## Scripts / entrypoints

| Role | Path |
|------|------|
| Stats | `src/grapeancestry/adna/fstats.py` |
| Report wiring | `src/grapeancestry/popgen/fstats_report.py` |

## Inputs

- Query genotypes at panel sites  
- Grp reference means from the frozen panel

## Statistical / file outputs

| Artifact | Meaning |
|----------|---------|
| Per-contrast f3 / f4 with Z | Complete-case per contrast; report `n_sites`, `n_blocks` |
| Summary “highest shared drift” / largest |Z| | Shown in report cards |

## Visualization outputs

| Where | What |
|-------|------|
| Report → Population placement (advanced) | Outgroup-f3 / pairwise f4 panels |
| Optional PNG | `results/{sample}.fstats.png` when produced |

## Claim note

**Exploratory only** — not qp3Pop / qpDstat / qpAdm / qpGraph substitutes.
