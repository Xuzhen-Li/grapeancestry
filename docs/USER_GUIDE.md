# User guide — GrapeAncestry (chip companion)

**Audience:** end users who will run the packaged product (Docker UI) or, today, read the public docs and a demo report.  
**Language:** English.  
**Suggested path:** `docs/USER_GUIDE.md` on `Xuzhen-Li/grapeancestry`.

---

## 0. Honest status (read this first)

| When | What you can do |
|------|-----------------|
| **Public GitHub tree today** (`Xuzhen-Li/grapeancestry`) | Read docs + open Ages HTML (`cd demo && python3 -m http.server`). `src/` may be present, but **no** VS-1 / 2449 dosage ship here — end-to-end `grapeancestry run` is **expected to stop** until you have private assets. |
| **Local lab suite** (private checkout, if you have it) | `http.server` to open finished demo HTML; some CLI paths when conda + assets are installed. |
| **Customer image in hand** (`grapeancestry:1.0.0` / `./start.sh`) | Full UI at **http://localhost:8501**: three inputs (FASTQ / BAM / VCF on **VS-1**), demos, live log, V2 HTML report. |

This guide is written for the **image-in-hand** workflow as the final customer shape. Steps that only work after the image ships are marked **(image)**. Steps that work on the public docs tree alone are marked **(docs)**.

**Tonight deliverables (pick one door — do not mix filenames):**

| Door | Hand-in file |
|------|----------------|
| **Cloud** | `chip.json` |
| **Suite / Docker report** | `*.sample-first-v2.report.html` |

---

## 1. First start **(image)**

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). On **Apple Silicon**, use a **linux/amd64** engine (official ADMIXTURE is x86_64).
2. Unpack the customer package so you see `start.sh` (or `start.command` on macOS) next to `input/`, `output/`, and `settings/`.
3. Run:

```bash
./start.sh
# macOS alternative: double-click start.command
```

What `start.sh` does: creates `input` / `output` / `settings` if missing, loads or builds image tag `grapeancestry:1.0.0`, starts the container, opens **http://localhost:8501**.

4. **First visit — Setup:** choose password + confirm, language, threads, optional lab name. The password hash is stored in `./settings/auth.json` (no plaintext password in the image).
5. **Later visits:** password only. A wrong password stays on the login page.
6. Sidebar after login: **Analysis** / **Demos** / **Settings** (change password, language, threads, logout).

**Security note:** this login only blocks a casual browser on the same machine. Anyone with `docker exec` can still read data inside the container.

**Splash (optional):** after the UI is up, a standalone splash may be available at http://localhost:8502/web/splash/index.html.

Finished files under `examples/*/…sample-first-v2.report.html` are demo **outputs**, not the product login UI.

---

## 2. Analysis pages **(image)**

| Step | Page | What you do |
|------|------|-------------|
| 1 | Setup / Log in | First visit: password + language. Later: password only |
| 2 | Choose files | Put FASTQ / BAM / VCF in `./input`, select them, set sample ID, **Start analysis** |
| 3 | Analysis running | Live log — stay until finish or fail |
| 4 | Report ready | Open V2 HTML (often via port **8502**) or download HTML / JSON |

| Control | Meaning |
|---------|---------|
| Input type | FASTQ / BAM / VCF |
| FASTQ library | PE modern / SE modern / aDNA |
| Files | From `./input` (compose mount). VCF may also list packed demos |
| Sample ID | Output name. With “treat as query”, report id becomes `{id}_query` |
| Threads | Passed to Snakemake / bcftools |
| Start analysis | Opens the live-log page. Failure shows the log — no fake success |

**Reports:**

- Canonical: `results/{sample}.sample-first-v2.report.html`
- Customer copy: `output/results/` plus `output/assets/` so `../assets` resolves
- Open in a new tab on port **8502** (report files only; panel / VS-1 are not served as a public browse tree)
- Download buttons on the finished page

**Runtime (order of magnitude):** a modern capture FASTQ is much slower than a ready VCF. VCF-only analyze is often minutes on a laptop if the panel cache is already in the image.

---

## 3. Three inputs (all on VS-1)

Final package accepts **one** of:

| You provide | What happens | Not this |
|-------------|--------------|----------|
| **FASTQ** (modern PE or aDNA SE) | Trim → map to **VS-1** → markdup → call at the **167K BED** → analyses → report | Not a whole-genome resequencing deliverable |
| **BAM / CRAM** | Must already be on **VS-1** → markdup → call at 167K → same downstream | Wrong reference fails (see §4) |
| **Query VCF** | Sites ∩ 167K on VS-1 → analyses only (skip calling) | **Not** the 2449 × 167K panel matrix |

Cloud path (when Streamlit / Chip Companion is wired): upload a **167K-site query VCF** (not FASTQ) → export **`chip.json`**.

---

## 4. BAM must be VS-1 **(image)**

The BAM / CRAM must be aligned to **VS-1** numeric contigs.

- If `@SQ` names look like `chr1`, **12X**, or **PN40024**, the job **fails**.
- Fix: start from FASTQ (map to VS-1) or re-align to VS-1 before upload.

Do not strip contig prefixes hoping the caller will “just work”.

---

## 5. Demos **(image)** / **(docs)**

**(image)** Sidebar → **Demos**: primary **Ages** (V5 aDNA; cite Noraz et al. 2026 / Orlando — see README Demo) and optional modern-capture demos. New customer samples use **Analysis**, not Demos.

**(docs)** Without the image, open the walkthrough screenshots in [`GUIDELINE.md`](GUIDELINE.md), or — if you have a local suite checkout with finished HTML:

```bash
# path = local suite root (not the docs-only GitHub clone)
cd /path/to/local-suite
python3 -m http.server
# http://localhost:8000/results/Ages.sample-first-v2.report.html
```

`http.server` is **view-only**. It does **not** create a hand-in file.

### ID trap (read once)

Panel demo / panel row **`HUN89`** (2449-row ID) ≠ capture / report stem **`HUN89_query`** (independent FASTQ recapture).  
Do not strip `_query` to look up passport or frozen ADMIXTURE Q.

---

## 6. Apple Silicon **(image)**

Use Docker Desktop **linux/amd64** emulation.

Official ADMIXTURE binaries are **x86_64** ([download page](https://dalexander.github.io/admixture/download.html)). Native arm64-only setups are unsupported for the lab ADMIXTURE path.

---

## 7. How to read the report (sidebar order)

Walk top to bottom. Sidebar tabs are a **read path**, not separate hand-in files.

1. **Sample validity** — calling rate, depth, capture tables. Heterozygosity is a **screen**, not a purity call. Missing aDNA damage on a modern PE library is expected.
2. **Identity & placement** — IBS / kinship vs the 2449 panel. Non-self Identical and parent–offspring are clone/parentage **screens**. Pin a row to overlay the same ID on PCA / ADMIXTURE / NJ.
3. **Population placement** — frozen GCTA64 PCA projection, ADMIXTURE (in-panel lookup or `-P` / NNLS), NJ on IBS identity, optional f3/f4. The query is placed on a **frozen** reference — not an unsupervised 2449+N refit.
4. **Sample evidence** — passport / VIVC, SDR **proxy**, trait card, colour GS (see §8).
5. **Panel research** — selection / GEA and related panel contrasts. Query GT is an **overlay**.
6. **Methods** — software and frozen-asset notes for this report.
7. **Downloads** — export tables/figures from the demo; the public tree does not ship unpublished full 2449 matrices.

Long screenshots for each section: [`GUIDELINE.md`](GUIDELINE.md).

---

## 8. Evidence boundaries (do not skip)

Before you cite or rank anything:

| Topic | Rule |
|-------|------|
| **Colour GS** | Only **OIV 225** is decision-grade / rankable today |
| **OIV 241 / seedlessness** | Exploratory (unbalanced case/control) — no parent ranking, no seedlessness claim |
| **SDR / flower sex** | Unphased window **proxy** ≠ Science haplotype sex (H1–H5) |
| **Selection** | Panel Grp-vs-rest context; query GT overlay ≠ “this sample was selected” |
| **Scores** | **GS score ≠ observed phenotype** |
| **Hand-in** | Filename matches the door: `chip.json` **or** `*.sample-first-v2.report.html` |

Full claim table and teaching notes: [`GUIDELINE.md`](GUIDELINE.md) · flowchart: [`FLOWCHART.md`](FLOWCHART.md).

---

## 9. What “done” looks like

**Cloud:** `chip.json` exported from a 167K-site query VCF.  
**Suite / Docker:** `*.sample-first-v2.report.html` opens with assets; you can walk §7; you make no decision-grade claim beyond OIV 225.

Checklist:

- [ ] Door chosen (Cloud vs Suite); hand-in **filename** matches that door
- [ ] Input on **VS-1** (FASTQ mapped, BAM `@SQ` OK, or query VCF ∩ 167K)
- [ ] Report opens with assets (Suite) **or** `chip.json` written (Cloud)
- [ ] No decision-grade claim beyond **OIV 225** colour GS
- [ ] ID trap checked (`HUN89` ≠ `HUN89_query` when relevant)

**Later (not a classroom night):** Docker/HPC rebuilds, full FASTQ→VCF on new libraries, ADMIXTURE `-P` batch work, publishing large matrices — see maintainer Docker notes when shipped.

---

## 10. Related docs

| Doc | Use it for |
|-----|------------|
| [`GUIDELINE.md`](GUIDELINE.md) | Full demo walk + claim rules |
| [`FLOWCHART.md`](FLOWCHART.md) | Nodes behind the diagram |
| [`CHIP_COMPANION.md`](CHIP_COMPANION.md) | Cloud vs Lab doors |
| Public README | Short intro + honest “docs first” status |

**Note:** Prefer a **venv** if you `pip install -e .`. Without VS-1 + dosage cache, `grapeancestry run` / Docker `./start.sh` (customer pack only) / `chip-report` are **expected to stop**. Tonight’s copy-paste path on a fresh clone is **Ages `http.server` only**.

---

## Privacy

Do not put unpublished genotypes, private coordinates, or full 2449 panel matrices into public demos or tickets.
