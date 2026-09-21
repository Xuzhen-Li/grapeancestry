# Step 03b — IBS and kinship ranks

## Goal

Rank reference samples by IBS and KING-related metrics for the query.

## Inputs

- Same identity inputs as 03a (query VCF + dosage cache)

## Commands

```bash
grapeancestry identity \
  --vcf results/Ages.vcf.gz \
  --sample Ages \
  --cache results/cache/panel_dosage_167k.npz \
  --out-tsv results/Ages.ibs.tsv

# Also produced by grapeancestry analyze / run
# Libraries: src/grapeancestry/identity/ibs.py · run_ibs.py
```

## Outputs

| Artifact | Meaning |
|----------|---------|
| `results/{sample}.ibs.tsv` | Top IBS neighbours |
| `results/{sample}.kinship_top.tsv` | Top kinship ranks (when written) |
| Summary TSVs | Counts / nearest non-self |

## Plots

Side-by-side IBS top / Kinship top tables in the report.

## Notes

- Italy 4K-style IBS vs panel cache; prefer 167k dosage when available.
