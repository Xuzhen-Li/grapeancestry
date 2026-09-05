# Analysis (FASTQ → panel VCF → reports)

Calling and report recipes for the 167K capture panel.

## Scope

- FASTQ to panel VCF calling notes
- Ancestry, identity, and PCA report recipes
- CLI / Docker / Streamlit wrappers when ready

## Out of scope

- Probe / SNP design → [`../chip/`](../chip/)
- aDNA damage / authentication → [grapevine-adna](https://github.com/Xuzhen-Li/grapevine-adna)
- Theory dossiers → [genomics-theory-mining](https://github.com/Xuzhen-Li/genomics-theory-mining)

## Starter pipeline sketch

1. Demux and QC raw capture FASTQ (public or published runs only in this repo).
2. Map to the locked panel reference; call to a panel VCF.
3. Run ancestry / identity / PCA report recipes from that VCF.
4. Keep private sample matrices off GitHub.

## What will land later

Methods, scripts, and notes only — no unpublished genotypes or private coordinates.
