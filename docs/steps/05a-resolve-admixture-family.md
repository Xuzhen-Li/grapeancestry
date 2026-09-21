# Step 05a — Resolve ADMIXTURE family (lookup vs project)

## Goal

Choose the frozen ADMIXTURE family and decide **lookup** (in-panel ID) vs `-P` / NNLS (new ID).

## Inputs

- Ingested Q/P under `data/panel/admixture/` (Step 00e)
- Query sample id / VCF
- Mode flags from CLI (`auto` / `lookup` / `nnls` / `official`)

## Commands

```bash
# Resolution happens inside analyze / admix-project (no standalone “resolve” CLI):
grapeancestry analyze --sample Ages --admix-mode auto
grapeancestry analyze --sample HUN89 --as-query --admix-mode auto

grapeancestry admix-project --vcf results/Ages.vcf.gz --admix-mode auto

# Libraries: src/grapeancestry/adna/admixture.py · admix_project.py · panel167k_nogwas.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| Active family name | e.g. `panel167k_nogwas` when complete; else Science `core_ld_sort` archive |
| Mode decision | lookup vs project; K set 2–8 or K8-only |

## Plots

None.

## Notes

- Default family when ingested: `panel167k_nogwas`; else Science archive for lookup.
- `--admix-k8-only` applies to `run` / `analyze` report paths, not to `admix-project`.
