"""167k-minus-GWAS SNP set and panel167k_nogwas ADMIXTURE run family.

Unsupervised fit: 2449 × (~153k) after dropping trait_locus overlap.
No extra LD prune. P rows follow panel167k_nogwas.sites.txt.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PANEL167K_NOGWAS_FAMILY = "panel167k_nogwas"
EXPECTED_PANEL_SITES = 167_433
EXPECTED_GWAS_IN_PANEL = 13_950
EXPECTED_KEEP_SITES = 153_483
ID_FILE_NAME = "id_panel167k.txt"
SITES_FILE_NAME = "panel167k_nogwas.sites.txt"
EXCLUDE_TSV_NAME = "gwas_exclude.tsv"
EXCLUDE_BED_NAME = "gwas_exclude.bed"
Q_PATTERN = "panel167k_nogwas.{k}.Q"
P_PATTERN = "panel167k_nogwas.{k}.P"
DISPLAY_Q_PATTERN = "panel167k_manual.{k}.Q"
MANIFEST_NAME = "panel167k_manifest.json"

LE_CAVEAT = (
    "Unsupervised ADMIXTURE on 167k minus GWAS sites was not LD-pruned. "
    "The model assumes linkage equilibrium; background LD may remain "
    "(Alexander et al. 2009 Genome Res 19:1655; ADMIXTURE manual §2.3). "
    "Q is a clustering affinity, not a qpAdm proportion. "
    "Dong et al. 2023 Fig. 1D used LD-pruned WGS SNPs — this is a separate "
    "chip-panel fit named to those K=8 ancestries."
)


def load_trait_locus_chrpos(path: Path) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    with path.open() as fh:
        header = fh.readline()
        if not header:
            return out
        for line in fh:
            if not line.strip():
                continue
            chrom, pos, *_ = line.split("\t")
            out.add((chrom, int(pos)))
    return out


def load_panel_sites_bed(path: Path) -> list[tuple[str, int]]:
    """Return 1-based chrom,pos in BED order (0-based start, 1-based end for 1bp)."""
    sites: list[tuple[str, int]] = []
    with path.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            a = line.split()
            chrom = a[0]
            start = int(a[1])
            end = int(a[2])
            pos = end if end - start == 1 else start + 1
            sites.append((chrom, pos))
    return sites


def gwas_panel_split(
    panel_sites: list[tuple[str, int]],
    gwas: set[tuple[str, int]],
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Return (keep, exclude_in_panel) preserving panel order."""
    keep: list[tuple[str, int]] = []
    exclude: list[tuple[str, int]] = []
    for site in panel_sites:
        if site in gwas:
            exclude.append(site)
        else:
            keep.append(site)
    return keep, exclude


def site_key(chrom: str, pos: int) -> str:
    return f"{chrom}:{pos}"


def write_exclude_and_sites(
    keep: list[tuple[str, int]],
    exclude: list[tuple[str, int]],
    out_dir: Path,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv = out_dir / EXCLUDE_TSV_NAME
    bed = out_dir / EXCLUDE_BED_NAME
    sites = out_dir / SITES_FILE_NAME
    with tsv.open("w") as fh:
        fh.write("chrom\tpos\n")
        for chrom, pos in exclude:
            fh.write(f"{chrom}\t{pos}\n")
    with bed.open("w") as fh:
        for chrom, pos in exclude:
            fh.write(f"{chrom}\t{pos - 1}\t{pos}\n")
    with sites.open("w") as fh:
        for chrom, pos in keep:
            fh.write(f"{site_key(chrom, pos)}\n")
    return {"exclude_tsv": tsv, "exclude_bed": bed, "sites": sites}


def load_family_sites(admix_dir: Path) -> list[str]:
    path = admix_dir / SITES_FILE_NAME
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]


def panel167k_assets_complete(admix_dir: Path, k_min: int = 2, k_max: int = 8) -> bool:
    ids = admix_dir / ID_FILE_NAME
    sites = admix_dir / SITES_FILE_NAME
    if not ids.exists() or not sites.exists():
        return False
    return all(
        (admix_dir / Q_PATTERN.format(k=k)).exists()
        and (admix_dir / P_PATTERN.format(k=k)).exists()
        for k in range(k_min, k_max + 1)
    )


def freeze_q_path(admix_dir: Path, k: int) -> Path:
    """Aligned Q written with freeze P."""
    return admix_dir / Q_PATTERN.format(k=k)


def q_path(admix_dir: Path, k: int) -> Path:
    """Q used for panel bars and in-panel lookup."""
    preferred = admix_dir / DISPLAY_Q_PATTERN.format(k=k)
    if preferred.exists():
        return preferred
    return freeze_q_path(admix_dir, k)


def p_path(admix_dir: Path, k: int) -> Path:
    """P used for admixture -P."""
    return admix_dir / P_PATTERN.format(k=k)


def count_summary(panel_n: int, gwas_in_panel: int, keep_n: int) -> dict[str, int]:
    return {
        "panel_sites": panel_n,
        "gwas_in_panel": gwas_in_panel,
        "keep_sites": keep_n,
        "expected_panel_sites": EXPECTED_PANEL_SITES,
        "expected_gwas_in_panel": EXPECTED_GWAS_IN_PANEL,
        "expected_keep_sites": EXPECTED_KEEP_SITES,
    }


def parse_cv_errors(log_text: str) -> float | None:
    """Parse ADMIXTURE ``CV error (K=n): x`` lines; return the last value."""
    val: float | None = None
    for line in log_text.splitlines():
        if "CV error" in line:
            try:
                val = float(line.rsplit(":", 1)[-1].strip())
            except ValueError:
                continue
    return val


def pearson_cols(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute Pearson r of matching columns (already aligned)."""
    if a.shape != b.shape or a.shape[1] == 0:
        return float("nan")
    rs = []
    for j in range(a.shape[1]):
        x = a[:, j]
        y = b[:, j]
        if np.std(x) < 1e-12 or np.std(y) < 1e-12:
            continue
        r = float(np.corrcoef(x, y)[0, 1])
        if np.isfinite(r):
            rs.append(abs(r))
    return float(np.mean(rs)) if rs else float("nan")


def load_bim_site_keys(bim: Path) -> list[str]:
    """chrom:pos from a PLINK .bim (ADMIXTURE P row order)."""
    keys: list[str] = []
    with bim.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            a = line.split()
            keys.append(f"{a[0]}:{a[3]}")
    return keys


def reorder_p_rows_to_sites(P: np.ndarray, bim_keys: list[str], sites: list[str]) -> np.ndarray:
    """Map P rows from BIM/genomic order onto ``sites.txt`` order."""
    arr = np.asarray(P, float)
    if arr.ndim != 2 or arr.shape[0] != len(bim_keys):
        raise ValueError(f"P rows {arr.shape} vs bim {len(bim_keys)}")
    if set(bim_keys) != set(sites):
        raise ValueError("bim SNP set != sites.txt")
    index = {s: i for i, s in enumerate(bim_keys)}
    return arr[np.asarray([index[s] for s in sites], dtype=int)]


def p_counted_allele(admix_dir: Path) -> str:
    """Allele whose frequency is stored in dest P (this freeze: VCF REF).

    Measured against ``panel_dosage_167k.npz`` ALT dosages: mean(P) ≈ 1 −
    mean(ALT/2). BIM A1 is ALT, so this is A2 / REF, not the ADMIXTURE
    manual's 'allele 1' wording.
    """
    path = admix_dir / MANIFEST_NAME
    if not path.exists():
        return "ALT"
    try:
        man = json.loads(path.read_text())
    except Exception:
        return "REF"
    val = str(man.get("p_counted_allele") or "").upper()
    if val in {"REF", "ALT"}:
        return val
    return "ALT"


def align_p_to_study_bim(
    P: np.ndarray,
    sites: list[str],
    bim: Path,
    alleles: dict[str, tuple[str, str]],
    *,
    counted_allele: str = "REF",
) -> np.ndarray:
    """Permute P to PLINK .bim order; convert dest P to BIM **A2** frequency.

    Dest panel167k P is VCF REF frequency (measured vs ALT dosages).
    ADMIXTURE 1.3 ``-P`` uses the frequency of bim A2, not A1
    (HUN89 lookup Q recovered at corr=1 only after this conversion).
    ``plink --make-bed`` also genomic-sorts SNPs (chr1→19).
    """
    arr = np.asarray(P, float)
    if arr.ndim != 2 or arr.shape[0] != len(sites):
        raise ValueError(f"P rows {arr.shape} vs sites {len(sites)}")
    index = {s: i for i, s in enumerate(sites)}
    counted = counted_allele.upper()
    rows: list[np.ndarray] = []
    with bim.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            a = line.split()
            key = f"{a[0]}:{a[3]}"
            i = index.get(key)
            if i is None:
                raise ValueError(f"bim SNP {key} not in P sites")
            row = arr[i].copy()
            a1, a2 = a[4], a[5]
            ref, alt = alleles.get(key, (None, None))
            target = ref if counted == "REF" else alt
            if target and a2 == target:
                pass
            elif target and a1 == target:
                row = 1.0 - row
            rows.append(row)
    return np.vstack(rows)


def align_dosage_to_sites(
    dosage: np.ndarray,
    cache_sites: list[str],
    panel_sites: list[str],
) -> np.ndarray:
    """Map a query dosage vector onto P-row / sites.txt order (missing = -1)."""
    index = {s: i for i, s in enumerate(cache_sites)}
    out = np.full(len(panel_sites), -1.0)
    for j, s in enumerate(panel_sites):
        i = index.get(s)
        if i is not None:
            out[j] = float(dosage[i])
    return out


def cv_story_ok(cv_by_k: dict[int, float]) -> tuple[bool, str]:
    """Require an elbow/plateau story on K=2–8 (ingest gate)."""
    need = list(range(2, 9))
    missing = [k for k in need if k not in cv_by_k]
    if missing:
        return False, f"CV missing K={missing}"
    ks = need
    vals = [float(cv_by_k[k]) for k in ks]
    k_star = ks[int(np.argmin(vals))]
    if k_star >= 5:
        return True, f"CV minimum at K={k_star}"
    overall = max(vals) - min(vals)
    tail = vals[-3:]
    if overall > 0 and (max(tail) - min(tail)) <= 0.25 * overall:
        return True, f"CV plateau at high K (min still K={k_star})"
    return False, f"CV minimum at K={k_star}; expected elbow/plateau at K>=5"


METHODS_PANEL167K = (
    "ADMIXTURE K=2–8 is one unsupervised series on the 2449 reference using "
    "167k capture sites minus GWAS/trait-locus overlap (13,950 sites dropped; "
    "153,483 kept). No extra LD prune. "
    + LE_CAVEAT
    + " Q and P columns use the same permutation: K=2 seeded by the "
    "WWE1-purest individual (west first), then greedy Pearson match K→K+1 "
    "on 2448 non-OUT samples (Alexander et al. 2009 label switching, "
    "https://doi.org/10.1101/gr.094052.109). Each component has its own colour "
    "(Dong et al. 2023 Fig. 1D https://doi.org/10.1126/science.add8655); "
    "newest column drawn on top. In-panel samples use lookup of this Q. "
    "New samples are projected with admixture -P onto this family's P for "
    "every K in 2–8. P rows follow panel167k_nogwas.sites.txt (VCF REF "
    "frequency); after plink --make-bed the study .P.in is remapped to BIM "
    "genomic order and A1. This is not a new unsupervised run on the query "
    "VCF and is not Dong WGS Fig. 1D."
)

# Visible report Methods card: same facts, no internal filenames.
REPORT_METHODS_PANEL167K = (
    "ADMIXTURE K=2–8 is one unsupervised series on the 2449 reference using "
    "167k capture sites minus GWAS/trait-locus overlap (13,950 sites dropped; "
    "153,483 kept). No extra LD prune. "
    + LE_CAVEAT
    + " Q and P columns use the same permutation: K=2 seeded by the "
    "WWE1-purest individual (west first), then greedy Pearson match K→K+1 "
    "on 2448 non-OUT samples (Alexander et al. 2009 label switching, "
    "https://doi.org/10.1101/gr.094052.109). Each component has its own colour "
    "(Dong et al. 2023 Fig. 1D https://doi.org/10.1126/science.add8655); "
    "newest column drawn on top. In-panel samples use lookup of this Q. "
    "New samples are projected with ADMIXTURE -P onto the frozen "
    "allele-frequency matrix for every K in 2–8. This is not a new unsupervised "
    "run on the query and is not Dong WGS Fig. 1D."
)
