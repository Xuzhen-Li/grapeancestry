# Step 05b — Project query ADMIXTURE Q

## Goal

Write query Q for each requested K using frozen **P** (`admixture -P` or NNLS).

## Inputs

- Query VCF(s) at panel sites
- Complete `panel167k_nogwas` P/Q ingest (required for `admix-project`)
- `admixture` 1.3.0 on PATH

## Commands

```bash
# Batch / dedicated projection:
grapeancestry admix-project \
  --vcf results/Ages.vcf.gz \
  --vcf results/HUN89_query.vcf.gz \
  --out-dir results/admix_project \
  --admix-mode auto

# Single-sample report path:
grapeancestry analyze --sample Ages --admix-all-k
grapeancestry run --sample Ages --admix-all-k

# Libraries: src/grapeancestry/adna/admix_project.py · admixture.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.admix.K{k}.Q.tsv` (or under `--out-dir`) | Query Q per K |
| Optional `{sid}.report.html` from `admix-project --html` | K=2–8 interactive ADMIXTURE-only report |

## Plots

ADMIXTURE bar chart with K tabs; query column highlighted (full HTML or admix-project HTML).

## Notes

- New samples on `panel167k_nogwas` use **`admixture -P`** for K=2–8 (same P rows as sites file).
- Report states the LE assumption is violated (no extra LD prune).
- If P is not ingested, `admix-project` exits with a clear warning — do not invent Q.
