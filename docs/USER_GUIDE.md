# User guide — GrapeAncestry v1.0.0

**Audience:** people who will run the private Docker product, or browse the public docs + Ages HTML.  
**Language:** English.

---

## 0. Honest status

### First hour

Same three paths as the [README](../README.md#three-ways-in) (Docker kit → Demo → DIY). Detail Q&A: [`FAQ.md`](FAQ.md).


| Path | What you get |
|------|----------------|
| **Docker kit** | Download tar from **`Zenodo Restricted record — DOI after publish`**, put next to `start.sh`, `./start.sh` → full UI. Demos Ages + HUN89_query. FASTQ/BAM/VCF → V2 HTML. |
| **Demo on GitHub** | README screenshots + GUIDELINE + `demo/` Ages HTML (view-only). |
| **DIY, no kit** | Stage your own VS-1 + frozen 2449×167K panel assets (FASTA/indices, sites BED, dosage, PCA·ADMIXTURE) — not in public git. Follow `docs/steps/00a`–`13b`. |
| **Cloud `chip.json`** | Optional Cloud JSON only — **not** the v1 product. |

v1 customer output: **`*.sample-first-v2.report.html`**. UI **http://127.0.0.1:8501** · report server **http://127.0.0.1:8502**.

Steps that need the fat image are marked **(image)**. Public-clone browse steps are marked **(docs)**.

---

## 1. First start **(image)**

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). On **Apple Silicon**, use a **linux/amd64** engine (ADMIXTURE 1.3.0 is x86_64: [download page](https://dalexander.github.io/admixture/download.html)).
2. Download `grapeancestry-v1.0.0-amd64.tar` from **`Zenodo Restricted record — DOI after publish`**. Place it next to `start.sh` (or `start.command` / `start.bat`). Create folders as needed — the launcher runs `mkdir -p input output settings`.
3. Run:

```bash
./start.sh
# macOS: double-click start.command
# Windows: start.bat
```

What the launcher does: ensure folders; if image `grapeancestry:1.0.0` is missing, `docker load -i grapeancestry-v1.0.0-amd64.tar` when present, else attempt `docker build --platform linux/amd64` (a docs-only clone **cannot** produce a working fat image); `docker run -d --name grapeancestry -p 8501:8501 -p 8502:8502` with `./input`, `./output`, `./settings` mounted. Colima: if `~/.colima/default/docker.sock` exists and `docker info` fails, set `DOCKER_HOST` to that socket.

**Never `docker push`** the fat image (panel assets inside).

4. **First visit — Setup:** password twice, language, threads, optional lab name. Hash only in `./settings/auth.json` (scrypt). No plaintext password in the image.
5. **Later visits:** password only.
6. Sidebar: **Analysis** / **Demos** / **Settings**.

**Security note:** login only blocks a casual browser on the same machine. Anyone with `docker exec` can still read data inside the container.

---

## 2. Analysis **(image)**

| Step | What you do |
|------|-------------|
| 1 | Log in / Setup |
| 2 | Put FASTQ / BAM / VCF in `./input` (drag-and-drop, host copy, **Get Ages** / **Get HUN89_query**, or http(s) URL). Select files, set sample ID, **Start analysis** |
| 3 | Live log until finish or fail |
| 4 | Open V2 HTML on **8502** or download from `./output/results/` (+ `./output/assets/`) |

**Inputs**

| Kind | Notes |
|------|--------|
| FASTQ | PE modern / SE modern / aDNA |
| BAM / CRAM | Must already be **VS-1** numeric contigs. `chr1` / 12X / PN40024 → **fail** → start from FASTQ |
| VCF | Query at **167K** sites (not the 2449 matrix) |

**Treat as query on:** report id becomes `{id}_query`.

**Step settings** (existing flags only): query/force VCF, threads, `--forceall` → snakemake `-F`, fastp, AdapterRemoval3, `bwa mem -k/-T`, `bwa aln -l/-n/-o`, `bcftools mpileup -q/-Q/-d/-C` + optional DP, `--pca-color`, `--admix-mode`, K=2–8.

**Sample URL in the UI download box** (download demo only):

`https://ftp.sra.ebi.ac.uk/vol1/run/ERR166/ERR16654874/V5xL1xP2_Ages_3_5070.12Xv2.realigned.bam`  
ENA **ERR16654874** / **PRJEB94459**. This BAM is **12Xv2, not VS-1**. Do **not** Analyze it as a VS-1 BAM — `@SQ` must fail.

**Reports:** `*.sample-first-v2.report.html` on **8502**; copies under `./output/results/` with `./output/assets/`.

**Packed demos:** Ages and HUN89_query V2 HTML under **Demos** (Companion tab merged into Demos).

---

## 3. Browse Ages HTML **(docs)**

No Docker required:

```bash
cd demo
python3 -m http.server 8000
# http://127.0.0.1:8000/results/Ages.sample-first-v2.report.html
```

View-only. Does not create a product report. Keep `demo/assets/` beside `demo/results/`.

Screenshot walkthrough: [`GUIDELINE.md`](GUIDELINE.md).

---

## 4. Optional Chip Companion (`chip.json`)

Not the v1 Docker product. When a Cloud UI is available: upload a **167K-site query VCF** → export `chip.json`. See [`CHIP_COMPANION.md`](CHIP_COMPANION.md).

---

## 5. CLI from this clone **(docs / lab)**

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Without VS-1 + 2449 dosage cache, `grapeancestry run` / analyze paths are **expected to stop**. Do not install system-wide (PEP 668).

---

## 6. Science frame (short)

- Coordinates: **VS-1** (Dong et al. 2023 *Science*, [doi:10.1126/science.add8655](https://doi.org/10.1126/science.add8655)).
- Frozen PCA / ADMIXTURE; project new samples.
- Only **OIV 225** colour GS is decision-grade today.
- **ID trap:** `HUN89` ≠ `HUN89_query`.
- Ages source paper: Noraz et al. 2026 *Nat Commun* ([doi:10.1038/s41467-026-70166-z](https://doi.org/10.1038/s41467-026-70166-z)).

**MIT = code only.** Panel genotypes / phenotypes are not MIT.

Author: **李旭真 / Li Xuzhen** · ORCID [0000-0003-3670-6657](https://orcid.org/0000-0003-3670-6657).
