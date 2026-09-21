# Homepage organize round (mandatory order)

Lead dispatches **every** role. Do not invent DOI/URL. Keep `start.sh` uid/`HOME=/tmp` fix.

## Homepage skeleton (mandatory)

1. `# GrapeAncestry` — what + MIT + author ≤12 lines (no Path A/B/C novels)
2. `## Analysis flow` — **`docs/flowchart_vs1_analysis_v2.png` HERE** + one line FASTQ/BAM/VCF → VS-1 → 167K → V2 HTML
3. `## Use it` — 3-row table only + ≤8 lines Docker (`./start.sh`, :8501/:8502, Zenodo Restricted — DOI after publish)
4. `## What you get` — existing 9 guideline_shots panels only (do not add shots)
5. `## Docs` — ≤8 links (DATA_NOTICE, USER_GUIDE, GUIDELINE, FAQ, GLOSSARY, steps, CODE_AVAILABILITY, …). No GROKBOT, no CHIP_COMPANION, no DIY_SPINE as peer of flowchart
6. `## Author`

**Must stay shallow:** flowchart, three paths (table), start.sh, 8501/8502, DATA_NOTICE.  
**Off README:** BAM knobs, CHIP_COMPANION, GROKBOT, DIY_SPINE peer, “Cloud demoted”, Path A/B/C long sections, grapeC experiment talk.

## Roles

| ID | Bot | Duty |
|----|-----|------|
| Gemini A | Gemini | Draft homepage markdown skeleton only |
| W1 | 设计-信息架构 | Land README reorder (flowchart §2; collapse paths into Use-it table) — report ①② + draft to Lead |
| W2 | 设计-课堂路径 | Verify only: three paths / start.sh / ports / DATA_NOTICE still visible |
| W3 | 设计-图文节奏 | No new screenshots; gallery must not push flowchart down |
| W4 | 语言润色-命令旁白 | DIY/steps only in Docs links |
| W5 | 遗传学专家 | Confirm science one-liner under flowchart; screenshots captions OK |
| W6 | 语言润色-英文 | Polish README English AFTER reorder |
| W7 | 语言润色-中文 | Chinese short report for Jason AFTER reorder (not public README) |
| W8 | 设计-图文节奏 or 遗传学 | Confirm flowchart appears above first screenshot |
| Gemini B | Gemini | Page review after push |

W8 this round: 遗传学专家 confirms flowchart above first screenshot.
