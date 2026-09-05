# Chip design (167K and follow-on)

Probe and SNP selection notes for the grapevine 167K capture panel and follow-on arrays.

This folder is the public home for chip design. The old standalone shell [grapevine-chip](https://github.com/Xuzhen-Li/grapevine-chip) redirects here.

## Scope

- Probe / SNP selection criteria and notes
- Design-file layouts and QC checklists
- Pointers to public array resources when they exist

## Out of scope

- FASTQ → panel VCF calling → see [`../analysis/`](../analysis/)
- Ancestry / identity / PCA reports → see [`../analysis/`](../analysis/)
- aDNA-specific capture or damage → [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna)
- Nuclear pangenome / PAV → [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome)

## Starter checklist

1. Lock the reference and target gene / region set for the panel version.
2. Record probe tiling rules (length, GC, uniqueness filters) before any private coordinate dump.
3. Keep design QC as a checklist, not a sample matrix.
4. Point to published array resources; do not commit unpublished genotypes.

## What will land later

Methods, scripts, and notes only — no unpublished coordinates or private sample tables.
