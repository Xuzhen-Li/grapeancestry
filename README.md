# grapeancestry

Analysis suite for the grapevine **167K capture panel**: FASTQ → panel VCF → ancestry / identity / PCA.

Chip design (probe and SNP selection) lives in this repo under [`chip/`](chip/) — not as a separate public grain.

## Layout

| Path | Role |
|------|------|
| [`chip/`](chip/) | Probe / SNP selection notes and design-file layouts for 167K and follow-on arrays |
| [`analysis/`](analysis/) | Calling and report recipes (FASTQ → panel VCF → ancestry / identity / PCA) |

## This is not

- Not an ancient-DNA damage or authentication pipeline → [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna)
- Not population-genetic theory notes → [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining)
- Not a nuclear pangenome / PAV graph → [vitis-pangenome](https://github.com/Xuzhen-Li/vitis-pangenome)
- Not a stand-in for public structure / gene-flow work → [vitis-popgen](https://github.com/Xuzhen-Li/vitis-popgen)

## What is here now

- Folder contract for chip design vs analysis
- Starter notes under `chip/` and `analysis/` (methods and checklists only)

No unpublished genotypes, private coordinates, or sample-level matrices.

## See also

- [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna) — damage, authentication, aDNA capture, projection
- [vitis-popgen](https://github.com/Xuzhen-Li/vitis-popgen) — structure and gene flow on public or published data
- [bioinfo-agent-skills](https://github.com/Xuzhen-Li/bioinfo-agent-skills) — index of sibling repos

**Author:** Xuzhen Li · [ORCID](https://orcid.org/0000-0003-3670-6657)
