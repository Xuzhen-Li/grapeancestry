# GrapeAncestry analysis flow (what happens to your data)

**user input → our panel assets → software → analyses → outputs**

**Caption:** Inputs must be on **VS-1**. Your sample is then placed on a frozen 2449 × 167K reference; boxes name the software or asset at each step. **Solid** arrows into the output = core path (QC · IBS · PCA · ADMIXTURE · NJ). **Dashed** arrows (f3/f4 · selection/GEA · colour GS · passport/SDR) = report modules — read claim rules before citing.

```mermaid
flowchart TB
  subgraph IN["User input (any one · on VS-1)"]
    FQ[FASTQ\nmodern PE or aDNA SE]
    BAM[BAM / CRAM\nalready on VS-1]
    UVCF[query VCF\n167K sites · not the panel]
  end

  subgraph OURS["Our reference assets (stay with us)"]
    VS1[VS-1 reference genome]
    BED[167K capture BED / sites]
    DOSE[panel dosage cache\n2449 × 167K]
    PCAX[frozen GCTA64 PCA axes]
    ADMIX[frozen ADMIXTURE Q / P\nK=2–8]
    PASS[passport / VIVC / Grp]
    PHENO[phenotype.tsv\nGS training]
  end

  subgraph SW1["To query VCF @ 167K"]
    FQ --> TRIM[fastp or AdapterRemoval]
    TRIM --> MAP[bwa mem / bwa aln\nto VS-1]
    VS1 -.-> MAP
    MAP --> DUP[samtools markdup]
    BAM --> DUP
    VS1 -.-> BAM
    DUP --> CALL["bcftools mpileup/call\n-T 167K BED"]
    BED -.-> CALL
    CALL --> QVCF[query VCF.gz]
    UVCF --> CHECK[sites ∩ 167K\nVS-1 coordinates]
    CHECK --> QVCF
  end

  subgraph SW2["Analyses: query + our panel"]
    QVCF --> QC[QC · grapeancestry]
    DOSE --> IBS[IBS / kinship vs panel]
    QVCF --> IBS
    PCAX --> PROJ[PCA project\nonto frozen axes]
    QVCF --> PROJ
    ADMIX --> ADM[ADMIXTURE\nlookup or -P / NNLS]
    QVCF --> ADM
    QVCF --> NJ[NJ · IBS identity]
    QVCF --> F34[f3 / f4 exploratory]
    DOSE --> SEL[Selection / GEA\npanel Grp · GT overlay]
    PHENO --> GS[Colour GS\ntopk_ridge OIV 225]
    QVCF --> GS
    PASS --> CARD[Passport / SDR proxy\ntrait card]
    QVCF --> CARD
  end

  subgraph OUT["Outputs"]
    QC --> REP[sample-first-v2 report HTML\nor chip.json]
    IBS --> REP
    PROJ --> REP
    ADM --> REP
    NJ --> REP
    F34 -.-> REP
    SEL -.-> REP
    GS -.-> REP
    CARD -.-> REP
  end
```

## Lane legend

| Lane | Content |
|------|---------|
| User input | **FASTQ** or **BAM/CRAM on VS-1** or **query VCF @ 167K sites** (customer sample; not 2449 panel) |
| Our assets | VS-1, 167K BED, 2449 dosage, frozen PCA, frozen ADMIXTURE, passport, phenotype |
| Software | fastp/AdapterRemoval, bwa→VS-1, samtools, bcftools, grapeancestry, GCTA64 axes, ADMIXTURE |
| Analyses | QC, IBS, PCA project, ADMIXTURE, NJ, f3/f4, selection/GEA, GS, passport/SDR proxy |
| Output | `*.sample-first-v2.report.html` or `chip.json` |

## Honest boundaries (footnote)

- All genomic coordinates / mappings: **VS-1**.
- Panel = our **2449 × 167K** reference (not user upload).
- PCA / ADMIXTURE: frozen on 2449; query projected / `-P` / NNLS.
- SDR = proxy ≠ haplotype sex; OIV 225 only decision-grade; score ≠ phenotype; selection overlay ≠ selected.
- Mermaid: solid → output = core path; dashed → output = optional / claim-bounded modules inside the same file.
