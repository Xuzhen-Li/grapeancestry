# Data to stage locally

These files are not in git. Place them before a DIY run.

| What | Where | Notes |
|------|-------|-------|
| VS-1 fasta (+ `.fai`) | `data/ref/` | Reference for mapping and panel coordinates |
| Panel VCF / dosage cache | `data/panel/` | Frozen 2449 × 167K panel |
| Sites BED | `data/panel/` | 167K capture sites |
| Sample info | `data/panel/` | Panel sample table |
| Frozen PCA / ADMIXTURE | `data/panel/` | Frozen axes and Q/P (K=2–8) |
| FASTQ | `data/fastq/` | Query reads for a local mapping run |
