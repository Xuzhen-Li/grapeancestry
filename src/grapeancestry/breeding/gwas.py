"""Simple LM GWAS + contiguous haploblock heuristic + phenotype loaders."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def _impute_col(x: np.ndarray) -> np.ndarray:
    x = x.astype(float).copy()
    ok = x >= 0
    mu = x[ok].mean() if ok.any() else 0.0
    x[~ok] = mu
    return x


def gwas_lm(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (beta, neglog10_p) per site using simple correlation/t approx."""
    from math import erf, sqrt

    y = y.astype(float)
    y = y - y.mean()
    n = len(y)
    betas = np.zeros(X.shape[1])
    nlp = np.zeros(X.shape[1])
    for j in range(X.shape[1]):
        x = _impute_col(X[:, j])
        x = x - x.mean()
        denom = np.dot(x, x)
        if denom < 1e-12:
            continue
        b = float(np.dot(x, y) / denom)
        resid = y - b * x
        sigma2 = float(np.dot(resid, resid) / max(n - 2, 1))
        se = sqrt(sigma2 / denom) if sigma2 > 0 else 1.0
        t = b / se if se > 0 else 0.0
        p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
        p = max(p, 1e-300)
        betas[j] = b
        nlp[j] = -np.log10(p)
    return betas, nlp


def haploblocks(nlp: np.ndarray, threshold: float = 3.0, min_run: int = 3) -> list[tuple[int, int]]:
    """Contiguous runs where -log10(p) >= threshold."""
    blocks: list[tuple[int, int]] = []
    start = None
    for i, v in enumerate(nlp):
        if v >= threshold:
            if start is None:
                start = i
        else:
            if start is not None and i - start >= min_run:
                blocks.append((start, i - 1))
            start = None
    if start is not None and len(nlp) - start >= min_run:
        blocks.append((start, len(nlp) - 1))
    return blocks


def load_phenotype(path: Path, trait: str | None = None) -> dict[str, float | str]:
    """Load ID→value from phenotype.tsv (cols: ID, trait, value)."""
    out: dict[str, float | str] = {}
    if not path.exists():
        return out
    with path.open() as fh:
        header = None
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if header is None:
                header = [p.lower() for p in parts]
                continue
            row = dict(zip(header, parts))
            tid = row.get("id") or row.get("sample") or ""
            tname = row.get("trait", "")
            if trait and tname != trait:
                continue
            val = row.get("value", "")
            try:
                out[tid] = float(val)
            except ValueError:
                out[tid] = val
    return out


def metadata_traits(info_path: Path) -> dict[str, dict[str, str]]:
    """Return {trait: {id: value}} for Uti, GEO, Wild, CON from 2449.info."""
    traits = {k: {} for k in ("Uti", "GEO", "Wild", "CON")}
    if not info_path.exists():
        return traits
    with info_path.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            p = line.rstrip().split("\t")
            row = dict(zip(hdr, p))
            sid = row.get("ID", "")
            for k in traits:
                traits[k][sid] = row.get(k, "")
    return traits


def encode_categorical(phenomap: dict[str, float | str], ref_ids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Encode categorical (or numeric) phenotype to y float + boolean mask."""
    raw = [phenomap.get(i) for i in ref_ids]
    # numeric?
    nums = []
    for v in raw:
        if v is None or v == "":
            nums.append(None)
            continue
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            nums = None
            break
    if nums is not None:
        y = np.array([np.nan if v is None else v for v in nums], float)
        mask = np.isfinite(y)
        return y, mask
    # categorical → integer codes; one-vs-rest on most common non-empty class
    labels = ["" if v is None else str(v) for v in raw]
    nonempty = [x for x in labels if x]
    if not nonempty:
        return np.full(len(ref_ids), np.nan), np.zeros(len(ref_ids), dtype=bool)
    from collections import Counter

    top = Counter(nonempty).most_common(1)[0][0]
    y = np.array([1.0 if x == top else (0.0 if x else np.nan) for x in labels], float)
    mask = np.isfinite(y)
    return y, mask


def align_to_panel(phenomap: dict[str, float | str], ref_ids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    return encode_categorical(phenomap, ref_ids)


MIN_PHENO_N = 50


def n_overlapping_phenotypes(phenomap: dict[str, float | str], ref_ids: list[str]) -> int:
    ids = set(ref_ids)
    n = 0
    for k, v in phenomap.items():
        if k not in ids or v in ("", None):
            continue
        n += 1
    return n


def phenotype_is_usable(
    phenomap: dict[str, float | str],
    ref_ids: list[str],
    *,
    min_n: int = MIN_PHENO_N,
) -> tuple[bool, int]:
    n = n_overlapping_phenotypes(phenomap, ref_ids)
    return n >= min_n, n


def gwas_from_phenotype(
    mat: np.ndarray,
    ref_ids: list[str],
    sites: list[str],
    phenomap: dict[str, float | str],
    *,
    max_sites: int = 2000,
) -> dict:
    """Mixed-model GWAS (P3D) on phenotype aligned to panel rows; same return keys."""
    y_full, mask = align_to_panel(phenomap, ref_ids)
    if mask.sum() < 20:
        return {"nlp": None, "chrom": [], "pos": [], "blocks": [], "n": int(mask.sum())}
    X = mat[mask][:, : min(max_sites, mat.shape[1])].astype(float)
    y = y_full[mask]
    site_use = sites[: X.shape[1]]
    try:
        from grapeancestry.breeding.mixed_model import (
            grm_vanraden,
            impute_mean,
            p3d_scan,
            pcs_from_K,
            reml_delta,
            site_filter,
        )

        keep = site_filter(X, maf_min=0.01, max_missing=0.5)
        if int(keep.sum()) < 5:
            keep = np.ones(X.shape[1], dtype=bool)
        Xs = impute_mean(X[:, keep])
        K = grm_vanraden(Xs)
        C0 = np.ones((len(y), 1))
        _d0, _sg, _se, U0, _S0, _ll = reml_delta(y - y.mean(), K, C0)
        pcs = pcs_from_K(U0, min(3, max(len(y) - 5, 1)))
        C = np.column_stack([np.ones(len(y)), pcs]) if pcs.size else C0
        delta, _sg, _se, U, S, _ll = reml_delta(y - y.mean(), K, C)
        _b, _se, _t, p = p3d_scan(Xs, y, C, U, S, delta)
        nlp = np.zeros(X.shape[1])
        nlp[keep] = -np.log10(np.clip(p, 1e-300, 1.0))
        site_use = sites[: X.shape[1]]
    except Exception:
        _b, nlp = gwas_lm(X, y)
    blocks = haploblocks(nlp, threshold=max(3.0, float(np.percentile(nlp, 99))), min_run=2)
    chroms, positions = [], []
    for s in site_use:
        c, _, pos = s.partition(":")
        chroms.append(c)
        positions.append(int(pos) if pos.isdigit() else 0)
    return {
        "nlp": nlp,
        "chrom": chroms,
        "pos": positions,
        "blocks": blocks,
        "n": int(mask.sum()),
        "y": y,
        "X": X,
        "sites": site_use,
    }


CURATED_GWAS = [
    ("euvitis", "OIV 225", True),
    ("euvitis", "OIV 151", True),
    ("euvitis", "OIV 241", True),
    ("euvitis", "OIV 236", True),
    ("euvitis", "OIV 220", False),
    ("euvitis", "OIV 202", False),
    ("euvitis", "OIV 502", False),
    ("euvitis", "OIV 303", False),
    ("euvitis", "OIV 452", False),
    ("euvitis", "OIV 455", False),
]


def _load_trait_locus(path: Path) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as fh:
        hdr = fh.readline()
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 3:
                continue
            try:
                rows.append((p[0], int(p[1]), p[2]))
            except ValueError:
                continue
    return rows


def _load_gwas_exclude(path: Path) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            p = line.split("\t")
            if len(p) < 2:
                continue
            try:
                out.add((p[0].strip(), int(p[1])))
            except ValueError:
                continue
    return out


def plot_manhattan(
    chrom: list[str],
    pos: np.ndarray,
    nlp: np.ndarray,
    out_png: Path,
    *,
    title: str,
    bonf: float,
    suggestive: float,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from grapeancestry.breeding.mixed_model import chrom_sort_key

    out_png.parent.mkdir(parents=True, exist_ok=True)
    order = sorted(range(len(chrom)), key=lambda i: (chrom_sort_key(chrom[i]), int(pos[i])))
    chroms_u = []
    seen = set()
    for i in order:
        c = chrom[i]
        key = chrom_sort_key(c)
        if key[0] >= 10_000:
            c = "other"
        if c not in seen:
            chroms_u.append(c)
            seen.add(c)
    fig, ax = plt.subplots(figsize=(8.2, 2.8))
    x = 0
    ticks, labels = [], []
    colors = ["#2f5d3a", "#8b7355"]
    for i, c in enumerate(chroms_u):
        idx = [j for j in order if (chrom[j] if chrom_sort_key(chrom[j])[0] < 10_000 else "other") == c]
        xs = np.arange(len(idx)) + x
        ys = nlp[idx]
        ax.scatter(xs, ys, s=3, c=colors[i % 2], alpha=0.75, linewidths=0)
        ticks.append(x + len(idx) / 2)
        labels.append(c)
        x += len(idx)
    ax.axhline(-np.log10(bonf), color="#c1121f", ls="--", lw=0.8, label="Bonferroni 0.05/m")
    ax.axhline(-np.log10(suggestive), color="#f4a261", ls=":", lw=0.8, label="1/m")
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=6, rotation=90)
    ax.set_ylabel("-log10 p")
    ax.set_title(title)
    ax.legend(fontsize=6, loc="upper right")
    fig.savefig(out_png, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_qq(p: np.ndarray, out_png: Path, *, lam: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = np.sort(np.clip(p[np.isfinite(p) & (p > 0)], 1e-300, 1.0))
    n = len(p)
    exp = -np.log10(np.arange(1, n + 1) / (n + 1))
    obs = -np.log10(p)
    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    ax.scatter(exp, obs, s=4, c="#2f5d3a", alpha=0.7)
    m = max(float(exp.max()), float(obs.max()), 1.0)
    ax.plot([0, m], [0, m], color="#888", lw=0.8)
    ax.set_xlabel("expected -log10 p")
    ax.set_ylabel("observed -log10 p")
    ax.set_title(f"QQ λ={lam:.3f}")
    fig.savefig(out_png, dpi=140, bbox_inches="tight")
    plt.close(fig)


# LocusZoom r² bins (Pruim et al. 2010 Bioinformatics 26:2336).
_LZ_R2_COLORS = (
    (0.8, "#d62728"),
    (0.6, "#ff7f0e"),
    (0.4, "#2ca02c"),
    (0.2, "#6baed6"),
    (0.0, "#08306b"),
)
DONG_COLOUR_GENES = frozenset({"Vvsyl02G000229", "Vvsyl02G001064"})
LOCUSZOOM_WINDOW = 250_000


def _ld_color(r2: float) -> str:
    if r2 != r2:
        return "#888888"
    for thr, col in _LZ_R2_COLORS:
        if r2 >= thr:
            return col
    return "#08306b"


def r2_to_lead(mat: np.ndarray, lead_j: int, js: list[int], min_n: int = 20) -> np.ndarray:
    """Pearson r² of each column vs lead; missing dosage (<0) dropped pairwise."""
    lead = np.asarray(mat[:, lead_j], float)
    out = np.full(len(js), np.nan)
    for k, j in enumerate(js):
        x = np.asarray(mat[:, j], float)
        ok = (lead >= 0) & (x >= 0)
        if int(ok.sum()) < min_n:
            continue
        a = lead[ok]
        b = x[ok]
        a = a - a.mean()
        b = b - b.mean()
        da = float(np.dot(a, a))
        db = float(np.dot(b, b))
        if da < 1e-12 or db < 1e-12:
            continue
        out[k] = (float(np.dot(a, b)) ** 2) / (da * db)
    return out


def _opt_float(x: str) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v:
        return None
    return v


def _opt_int(x: str) -> int | None:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _read_assoc_window(path: Path, chrom: str, start: int, end: int) -> dict[str, list]:
    """assoc.tsv window: chrom pos site maf n beta se p neglog10p q bonf_sig."""
    sites: list[str] = []
    pos: list[int] = []
    nlp: list[float] = []
    maf: list[float | None] = []
    n: list[int | None] = []
    beta: list[float | None] = []
    se: list[float | None] = []
    p: list[float | None] = []
    q: list[float | None] = []
    bonf: list[int] = []
    with path.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9 or parts[0] != chrom:
                continue
            po = int(parts[1])
            if po < start or po > end:
                continue
            sites.append(parts[2] if len(parts) > 2 else f"{chrom}:{po}")
            pos.append(po)
            nlp.append(float(parts[8]))
            maf.append(_opt_float(parts[3]) if len(parts) > 3 else None)
            n.append(_opt_int(parts[4]) if len(parts) > 4 else None)
            beta.append(_opt_float(parts[5]) if len(parts) > 5 else None)
            se.append(_opt_float(parts[6]) if len(parts) > 6 else None)
            p.append(_opt_float(parts[7]) if len(parts) > 7 else None)
            q.append(_opt_float(parts[9]) if len(parts) > 9 else None)
            b = _opt_int(parts[10]) if len(parts) > 10 else 0
            bonf.append(1 if b else 0)
    return {
        "site": sites,
        "pos": pos,
        "nlp": nlp,
        "maf": maf,
        "n": n,
        "beta": beta,
        "se": se,
        "p": p,
        "q": q,
        "bonf": bonf,
    }


def _tl_index(
    trait_locus: list[tuple[str, int, str]],
) -> dict[str, tuple[list[int], list[str]]]:
    by: dict[str, list[tuple[int, str]]] = {}
    for c, p, t in trait_locus:
        by.setdefault(c, []).append((p, t))
    out: dict[str, tuple[list[int], list[str]]] = {}
    for c, rows in by.items():
        rows.sort()
        out[c] = ([p for p, _ in rows], [t for _, t in rows])
    return out


def _trait_tags_at(
    chrom: str,
    pos: int,
    index: dict[str, tuple[list[int], list[str]]],
    window: int = 50_000,
) -> str:
    from bisect import bisect_left, bisect_right

    rec = index.get(chrom)
    if not rec:
        return ""
    xs, tags = rec
    lo = bisect_left(xs, pos - window)
    hi = bisect_right(xs, pos + window)
    if hi <= lo:
        return ""
    return ",".join(sorted(set(tags[lo:hi]))[:8])


def _read_alleles_window(
    vcf: Path,
    chrom: str,
    start: int,
    end: int,
) -> dict[str, tuple[str, str]]:
    """REF/ALT for sites in a window (needs .tbi)."""
    import subprocess

    if not vcf.exists():
        return {}
    region = f"{chrom}:{int(start)}-{int(end)}"
    try:
        raw = subprocess.check_output(
            ["bcftools", "query", "-r", region, "-f", "%CHROM:%POS\t%REF\t%ALT\n", str(vcf)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return {}
    out: dict[str, tuple[str, str]] = {}
    for line in raw.splitlines():
        p = line.split("\t")
        if len(p) >= 3:
            out[p[0]] = (p[1], p[2])
    return out


def _snp_window_annos(
    chrom: str,
    pos_list: list[int],
    sites: list[str],
    genes,
    features,
    *,
    mas_by_site: dict[str, dict] | None = None,
    mas_by_gene: dict[str, dict] | None = None,
    tl_index: dict[str, tuple[list[int], list[str]]] | None = None,
    exclude: set[tuple[str, int]] | None = None,
) -> dict[str, list]:
    from grapeancestry.resource.genes import annotate_site

    gene: list[str] = []
    dist: list[int | None] = []
    region: list[str] = []
    strand: list[str] = []
    overlap: list[str] = []
    design: list[int] = []
    mas: list[str] = []
    for po, site in zip(pos_list, sites):
        ann = annotate_site(
            chrom,
            int(po),
            genes,
            features,
            mas_by_site=mas_by_site,
            mas_by_gene=mas_by_gene,
        )
        gene.append(ann.get("gene") or "")
        d = ann.get("dist") or ""
        dist.append(_opt_int(d) if d != "" else None)
        region.append(ann.get("region") or "")
        strand.append(ann.get("strand") or "")
        overlap.append(_trait_tags_at(chrom, int(po), tl_index or {}, window=50_000))
        design.append(1 if exclude and (chrom, int(po)) in exclude else 0)
        note = ann.get("science_note") or ""
        alias = ann.get("alias") or ""
        if note and alias:
            mas.append(f"{alias}: {note}")
        else:
            mas.append(note or alias)
    return {
        "gene": gene,
        "dist": dist,
        "region": region,
        "strand": strand,
        "overlap": overlap,
        "design": design,
        "mas": mas,
    }


def _genes_in_window(genes_chrom: list, start: int, end: int) -> list:
    out = []
    for g in genes_chrom or []:
        if g.end < start or g.start > end:
            continue
        out.append(g)
    return out


def plot_locuszoom(
    pos: np.ndarray,
    nlp: np.ndarray,
    r2: np.ndarray | None,
    lead_pos: int,
    genes: list,
    features: dict | None,
    out_png: Path,
    *,
    title: str,
    chrom: str,
    window_start: int,
    window_end: int,
    bonf_nlp: float | None = None,
) -> None:
    """Regional association + gene track (LocusZoom layout; no full Manhattan)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Rectangle

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax, gx) = plt.subplots(
        2,
        1,
        figsize=(7.2, 4.4),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.1], "hspace": 0.05},
    )
    x = pos.astype(float) / 1e6
    lead_x = lead_pos / 1e6
    cols = [_ld_color(float(v)) if r2 is not None else "#4a7c59" for v in (r2 if r2 is not None else nlp)]
    ax.scatter(x, nlp, s=12, c=cols, alpha=0.85, linewidths=0, zorder=2)
    lead_mask = pos == int(lead_pos)
    if np.any(lead_mask):
        ax.scatter(
            x[lead_mask],
            nlp[lead_mask],
            s=48,
            c="#7D26CD",
            marker="D",
            zorder=4,
            edgecolors="white",
            linewidths=0.4,
            label="lead",
        )
    if bonf_nlp is not None and bonf_nlp == bonf_nlp:
        ax.axhline(bonf_nlp, color="#c1121f", ls="--", lw=0.7)
    ax.set_ylabel("-log10 p")
    ax.set_title(title, fontsize=10)
    ax.set_xlim(window_start / 1e6, window_end / 1e6)
    handles = [
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#7D26CD", markersize=7, label="lead"),
    ]
    if r2 is not None:
        handles.extend(
            Patch(facecolor=c, edgecolor="none", label=lab)
            for lab, c in (
                ("r²≥0.8", "#d62728"),
                ("0.6", "#ff7f0e"),
                ("0.4", "#2ca02c"),
                ("0.2", "#6baed6"),
                ("<0.2", "#08306b"),
            )
        )
    ax.legend(handles=handles, fontsize=6, loc="upper right", frameon=False, ncol=2)

    gx.set_xlim(window_start / 1e6, window_end / 1e6)
    gx.set_ylim(-0.15, 1.15)
    gx.set_yticks([])
    gx.set_xlabel(f"chr{chrom} (Mb)")
    win_genes = _genes_in_window(genes, window_start, window_end)
    label_ok = len(win_genes) <= 12
    for g in win_genes:
        y = 0.62 if (g.strand != "-") else 0.18
        x0 = max(g.start, window_start) / 1e6
        x1 = min(g.end, window_end) / 1e6
        gx.plot([g.start / 1e6, g.end / 1e6], [y, y], color="#444", lw=0.8, zorder=1)
        feats = (features or {}).get(g.gene_id) or {}
        boxes = feats.get("cds") or [(g.start, g.end)]
        for s, e in boxes:
            xs = max(s, window_start) / 1e6
            xe = min(e, window_end) / 1e6
            if xe <= xs:
                continue
            gx.add_patch(
                Rectangle((xs, y - 0.12), xe - xs, 0.24, facecolor="#2f5d3a", edgecolor="none", zorder=2)
            )
        if label_ok or (g.start <= lead_pos <= g.end):
            gx.text(
                (x0 + x1) / 2,
                y + (0.28 if g.strand != "-" else -0.32),
                g.gene_id,
                ha="center",
                va="bottom" if g.strand != "-" else "top",
                fontsize=5.5,
                rotation=0,
            )
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def loci_for_locuszoom(hits: list[dict], slug: str) -> list[dict]:
    """Top Bonferroni clump, plus Dong 2023 colour genes on OIV 225."""
    if not hits:
        return []
    picked = [hits[0]]
    if slug == "OIV_225_bin":
        seen = {(str(hits[0].get("chrom")), int(hits[0].get("pos") or 0))}
        for h in hits[1:]:
            if (h.get("nearest_gene") or "") not in DONG_COLOUR_GENES:
                continue
            key = (str(h.get("chrom")), int(h.get("pos") or 0))
            if key in seen:
                continue
            picked.append(h)
            seen.add(key)
    return picked


def _gene_track(
    genes_chrom: list,
    features: dict | None,
    start: int,
    end: int,
    *,
    sprot_by_gene: dict | None = None,
    mas_by_gene: dict | None = None,
) -> list[dict]:
    from grapeancestry.resource.sprot import apply_swissprot

    rows: list[dict] = []
    for g in _genes_in_window(genes_chrom, start, end):
        cds_raw = ((features or {}).get(g.gene_id) or {}).get("cds") or []
        cds = []
        for s, e in cds_raw:
            lo, hi = max(int(s), start), min(int(e), end)
            if hi > lo:
                cds.append([lo, hi])
            if len(cds) >= 40:
                break
        row: dict = {
            "id": g.gene_id,
            "start": int(g.start),
            "end": int(g.end),
            "strand": g.strand or ".",
            "biotype": g.biotype or "",
            "cds": cds,
        }
        ann: dict[str, str] = {}
        apply_swissprot(ann, (sprot_by_gene or {}).get(g.gene_id))
        for k, v in ann.items():
            if v:
                row[k] = v
        mas = (mas_by_gene or {}).get(g.gene_id)
        if mas:
            alias = str(mas.get("gene") or "")
            if alias and alias != g.gene_id:
                row["alias"] = alias
            if mas.get("note"):
                row["science_note"] = str(mas["note"])
            if mas.get("trait"):
                row["mas_trait"] = str(mas["trait"])
        rows.append(row)
    return rows


def locuszoom_record(
    *,
    trait: str,
    slug: str,
    chrom: str,
    pos: int,
    gene: str,
    nlp_lead: str | float,
    sites: list[str],
    pos_a: np.ndarray,
    nlp_a: np.ndarray,
    r2: np.ndarray | None,
    genes_chrom: list,
    features: dict | None,
    window_start: int,
    window_end: int,
    bonf_nlp: float,
    snp_extra: dict[str, list] | None = None,
    sprot_by_gene: dict | None = None,
    mas_by_gene: dict | None = None,
    locus_meta: dict | None = None,
) -> dict:
    """JSON for one interactive LocusZoom (parallel SNP arrays)."""
    r2_list: list[float | None] = []
    if r2 is None:
        r2_list = [None] * len(pos_a)
    else:
        for v in np.asarray(r2, float):
            r2_list.append(None if v != v else round(float(v), 3))
    pos_i = [int(x) for x in pos_a]
    lead_i = next((i for i, p in enumerate(pos_i) if p == int(pos)), None)
    snps: dict = {
        "site": list(sites),
        "pos": pos_i,
        "nlp": [round(float(x), 4) for x in nlp_a],
        "r2": r2_list,
    }
    if snp_extra:
        for k, vals in snp_extra.items():
            if k in snps:
                continue
            snps[k] = list(vals)
    n_bonf_window = 0
    if "bonf" in snps:
        n_bonf_window = sum(1 for x in snps["bonf"] if x)
    rec = {
        "trait": trait,
        "slug": slug,
        "chrom": chrom,
        "pos": int(pos),
        "gene": gene or "",
        "nlp": str(nlp_lead),
        "n_snps": int(len(pos_a)),
        "n_bonf_window": n_bonf_window,
        "lead_i": lead_i,
        "window_start": int(window_start),
        "window_end": int(window_end),
        "bonf_nlp": round(float(bonf_nlp), 3) if bonf_nlp == bonf_nlp else None,
        "snps": snps,
        "genes": _gene_track(
            genes_chrom,
            features,
            window_start,
            window_end,
            sprot_by_gene=sprot_by_gene,
            mas_by_gene=mas_by_gene,
        ),
    }
    if locus_meta:
        rec.update(locus_meta)
    lead_gene = next((g for g in rec["genes"] if g.get("id") == rec["gene"]), None)
    if lead_gene:
        if lead_gene.get("product"):
            rec["gene_product"] = lead_gene["product"]
        if lead_gene.get("alias"):
            rec["gene_alias"] = lead_gene["alias"]
        if lead_gene.get("uniprot"):
            rec["gene_uniprot"] = lead_gene["uniprot"]
    return rec


def write_curated_locuszooms(
    root: Path,
    *,
    window: int = LOCUSZOOM_WINDOW,
    cache_path: Path | None = None,
    write_png: bool = False,
) -> list[dict]:
    """Write interactive LocusZoom JSON from existing assoc/hits (no GWAS refit)."""
    from grapeancestry.cloud.mas import MAS_LOCI
    from grapeancestry.core.dosage import load_cache, resolve_cache
    from grapeancestry.resource.genes import load_gene_annotation
    from grapeancestry.resource.oiv import _variants, describe_trait, load_oiv_table
    from grapeancestry.resource.sprot import load_gene_func

    gwas_root = root / "results" / "gwas"
    idx_path = gwas_root / "index.tsv"
    if not idx_path.exists():
        return []
    gff = root / "data" / "ref" / "VS1.final.gff3"
    genes: dict = {}
    features: dict = {}
    if gff.exists():
        genes, features = load_gene_annotation(gff)
    sprot = load_gene_func(root)
    mas_by_gene = {str(r["gene"]): r for r in MAS_LOCI if r.get("gene")}
    mas_by_site = {str(r["site"]): r for r in MAS_LOCI if r.get("site")}
    tl_index = _tl_index(_load_trait_locus(root / "data" / "trait_locus.tsv"))
    exclude = _load_gwas_exclude(root / "data" / "panel" / "admixture" / "gwas_exclude.tsv")
    oiv = load_oiv_table(root / "data" / "oiv_traits.tsv")
    panel_vcf = root / "data" / "panel" / "panel167k_2449.vcf.gz"
    cache_p = cache_path or resolve_cache(root)
    mat = None
    site_index: dict[str, int] = {}
    if cache_p.exists():
        mat, _ids, sites_all = load_cache(cache_p)
        site_index = {str(s): i for i, s in enumerate(sites_all)}
    rows_out: list[dict] = []
    import csv

    with idx_path.open(encoding="utf-8") as fh:
        index_rows = list(csv.DictReader(fh, delimiter="\t"))
    for rec in index_rows:
        try:
            n_bonf = int(float(rec.get("n_bonf") or 0))
        except (TypeError, ValueError):
            n_bonf = 0
        if n_bonf <= 0:
            continue
        slug = rec.get("slug") or ""
        source = rec.get("source") or "euvitis"
        dest = gwas_root / source / slug
        hits_path = dest / "hits.tsv"
        assoc_path = dest / "assoc.tsv"
        if not hits_path.exists() or not assoc_path.exists():
            continue
        with hits_path.open(encoding="utf-8") as fh:
            hits = list(csv.DictReader(fh, delimiter="\t"))
        m_sites = float(rec.get("m") or 0) or 1.0
        bonf_nlp = -np.log10(0.05 / m_sites)
        trait = str(rec.get("trait") or "")
        orec: dict[str, str] = {}
        for key in _variants(trait):
            if key in oiv:
                orec = oiv[key]
                break
        locus_meta = {
            "source": source,
            "scale": rec.get("scale") or "",
            "n": _opt_int(str(rec.get("n") or "")),
            "m": _opt_int(str(rec.get("m") or "")),
            "lambda": _opt_float(str(rec.get("lambda") or "")),
            "n_bonf": n_bonf,
            "n_fdr": _opt_int(str(rec.get("n_fdr") or "")),
            "descriptor": describe_trait(trait, oiv),
            "notations": (orec.get("notations") or "").strip(),
            "trait_locus_overlap": rec.get("trait_locus_overlap") or "",
        }
        for hit in loci_for_locuszoom(hits, slug):
            chrom = str(hit.get("chrom") or "")
            pos = int(hit.get("pos") or 0)
            if not chrom or pos <= 0:
                continue
            start = max(1, pos - window)
            end = pos + window
            win = _read_assoc_window(assoc_path, chrom, start, end)
            sites_w = win["site"]
            pos_a = np.array(win["pos"], int)
            nlp_a = np.array(win["nlp"], float)
            if pos_a.size == 0:
                continue
            r2 = None
            if mat is not None:
                js = [site_index[s] for s in sites_w if s in site_index]
                lead_key = str(hit.get("site") or f"{chrom}:{pos}")
                lead_j = site_index.get(lead_key)
                if lead_j is not None and js:
                    r2_full = r2_to_lead(mat, lead_j, js)
                    by_j = {j: r2_full[k] for k, j in enumerate(js)}
                    r2 = np.array(
                        [by_j.get(site_index[s], np.nan) if s in site_index else np.nan for s in sites_w],
                        float,
                    )
            g_chrom = genes.get(chrom) or genes.get(f"chr{chrom}") or []
            alleles = _read_alleles_window(panel_vcf, chrom, start, end)
            extra = {
                "maf": win["maf"],
                "n": win["n"],
                "beta": win["beta"],
                "se": win["se"],
                "p": win["p"],
                "q": win["q"],
                "bonf": win["bonf"],
                "ref": [alleles.get(s, ("", ""))[0] for s in sites_w],
                "alt": [alleles.get(s, ("", ""))[1] for s in sites_w],
            }
            extra.update(
                _snp_window_annos(
                    chrom,
                    win["pos"],
                    sites_w,
                    genes,
                    features,
                    mas_by_site=mas_by_site,
                    mas_by_gene=mas_by_gene,
                    tl_index=tl_index,
                    exclude=exclude,
                )
            )
            hit_meta = dict(locus_meta)
            if hit.get("gene_dist"):
                hit_meta["lead_gene_dist"] = hit.get("gene_dist")
            if hit.get("trait_locus_overlap"):
                hit_meta["lead_overlap"] = hit.get("trait_locus_overlap")
            rec_lz = locuszoom_record(
                trait=trait,
                slug=slug,
                chrom=chrom,
                pos=pos,
                gene=str(hit.get("nearest_gene") or ""),
                nlp_lead=hit.get("neglog10p") or "",
                sites=sites_w,
                pos_a=pos_a,
                nlp_a=nlp_a,
                r2=r2,
                genes_chrom=g_chrom,
                features=features,
                window_start=start,
                window_end=end,
                bonf_nlp=float(bonf_nlp),
                snp_extra=extra,
                sprot_by_gene=sprot,
                mas_by_gene=mas_by_gene,
                locus_meta=hit_meta,
            )
            if write_png:
                png = dest / f"locuszoom_{chrom}_{pos}.png"
                plot_locuszoom(
                    pos_a,
                    nlp_a,
                    r2,
                    pos,
                    g_chrom,
                    features,
                    png,
                    title=f"{rec.get('trait') or slug}  {chrom}:{pos}  {hit.get('nearest_gene') or ''}".strip(),
                    chrom=chrom,
                    window_start=start,
                    window_end=end,
                    bonf_nlp=bonf_nlp,
                )
                rec_lz["href"] = f"gwas/{source}/{slug}/{png.name}"
            rows_out.append(rec_lz)
    idx_lz = gwas_root / "locuszoom.tsv"
    slim_keys = ("trait", "slug", "chrom", "pos", "gene", "nlp", "n_snps")
    if rows_out:
        with idx_lz.open("w", encoding="utf-8") as fh:
            fh.write("\t".join(slim_keys) + "\n")
            for r in rows_out:
                fh.write("\t".join(str(r.get(k, "")) for k in slim_keys) + "\n")
        import json

        (gwas_root / "locuszoom.json").write_text(
            json.dumps(rows_out, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    else:
        idx_lz.write_text("trait\tslug\tchrom\tpos\tgene\tnlp\tn_snps\n", encoding="utf-8")
    return rows_out


def _strip_chr(chrom: str) -> str:
    s = str(chrom)
    if s.lower().startswith("chr"):
        return s[3:]
    return s


def norm_site_key(site: str) -> str:
    c, _, p = str(site).partition(":")
    return f"{_strip_chr(c)}:{p}"


def region_strings(chrom: str, start: int, end: int) -> list[str]:
    c = _strip_chr(chrom)
    return [f"{c}:{int(start)}-{int(end)}", f"chr{c}:{int(start)}-{int(end)}"]


def _vcf_sample_ids(vcf: Path) -> list[str]:
    import subprocess

    try:
        raw = subprocess.check_output(["bcftools", "query", "-l", str(vcf)], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return []
    return [x.strip() for x in raw.splitlines() if x.strip()]


def _pick_vcf_sample(vcf: Path, sample: str) -> str:
    ids = _vcf_sample_ids(vcf)
    if sample in ids:
        return sample
    low = str(sample).lower()
    for i in ids:
        if i.lower() == low:
            return i
    if len(ids) == 1:
        return ids[0]
    return sample


def _bcf_gt_lines(vcf: Path, sample: str, region: str | None) -> str:
    import subprocess

    cmd = [
        "bcftools",
        "query",
        "-s",
        sample,
        "-f",
        "%CHROM:%POS[\t%GT]\\n",
    ]
    if region:
        cmd.extend(["-r", region])
    cmd.append(str(vcf))
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)


def attach_query_gt_to_loci(
    loci: list[dict],
    vcf: Path,
    sample: str,
) -> list[dict]:
    """Add ``snps.gt`` (0/1/2/-1) from this sample's VCF. Panel p/β/r² unchanged."""
    import subprocess

    from grapeancestry.core.dosage import _gt_to_dose

    if not loci or not vcf.exists():
        return loci
    vcf_sample = _pick_vcf_sample(vcf, sample)
    for rec in loci:
        snps = rec.get("snps") or {}
        sites = snps.get("site") or []
        chrom = str(rec.get("chrom") or "")
        start = rec.get("window_start")
        end = rec.get("window_end")
        if not sites or not chrom or start is None or end is None:
            continue
        want = {norm_site_key(s): i for i, s in enumerate(sites)}
        gt = [-1] * len(sites)
        raw = ""
        for region in region_strings(chrom, int(start), int(end)) + [None]:
            try:
                raw = _bcf_gt_lines(vcf, vcf_sample, region)
            except (OSError, subprocess.CalledProcessError):
                raw = ""
            if raw.strip():
                break
        n_called = 0
        for line in raw.splitlines():
            if not line.strip():
                continue
            bits = line.split("\t", 1)
            if len(bits) < 2:
                continue
            j = want.get(norm_site_key(bits[0]))
            if j is None:
                continue
            d = _gt_to_dose(bits[1])
            gt[j] = int(d)
            if d >= 0:
                n_called += 1
        snps["gt"] = gt
        rec["query_gt_sample"] = vcf_sample
        rec["query_gt_called"] = n_called
        rec["query_gt_n"] = len(sites)
        if vcf_sample != sample:
            rec["query_gt_note"] = f"VCF sample {vcf_sample} (requested {sample})"
    return loci


def annotate_hits(
    hits: list[dict],
    *,
    genes,
    trait_locus: list[tuple[str, int, str]],
    gwas_exclude: set[tuple[str, int]],
    window: int = 50_000,
    features=None,
) -> list[dict]:
    from grapeancestry.resource.genes import annotate_site

    by_chrom: dict[str, list[tuple[int, str]]] = {}
    for c, p, t in trait_locus:
        by_chrom.setdefault(c, []).append((p, t))
    for c in by_chrom:
        by_chrom[c].sort()
    out = []
    for h in hits:
        row = dict(h)
        gene_id, dist = "", ""
        if genes:
            ann = annotate_site(
                str(h["chrom"]),
                int(h["pos"]),
                genes,
                features,
                max_dist=50_000,
            )
            gene_id, dist = ann.get("gene") or "", ann.get("dist") or ""
            row["gene_region"] = ann.get("region") or ""
            row["gene_strand"] = ann.get("strand") or ""
            row["gene_span"] = ann.get("span") or ""
            row["gene_alias"] = ann.get("alias") or ""
        tags = []
        for p, t in by_chrom.get(str(h["chrom"]), []):
            if abs(p - int(h["pos"])) <= window:
                tags.append(t)
        row["nearest_gene"] = gene_id
        row["gene_dist"] = dist
        row["trait_locus_overlap"] = ",".join(sorted(set(tags))[:8])
        row["panel_gwas_site"] = (str(h["chrom"]), int(h["pos"])) in gwas_exclude
        out.append(row)
    return out


def run_gwas_trait(
    cache_path: Path,
    pheno_path: Path,
    trait: str,
    source: str,
    out_dir: Path,
    *,
    pcs: int = 3,
    maf: float = 0.05,
    max_missing: float = 0.2,
    binary: bool = False,
    root: Path | None = None,
    max_sites: int | None = None,
) -> dict:
    """Full mixed-model GWAS for one trait; writes assoc/hits/plots/summary."""
    import json
    import time

    from grapeancestry.breeding.mixed_model import (
        allele_freq,
        bh_fdr,
        clump_hits,
        genomic_inflation_lambda,
        grm_vanraden,
        impute_mean,
        p3d_scan,
        parse_site,
        pcs_from_K,
        reml_delta,
        site_filter,
    )
    from grapeancestry.breeding.phenotype import apply_binary_rule, load_phenotype_table, trait_slug
    from grapeancestry.core.dosage import load_cache
    from grapeancestry.resource.genes import load_gene_annotation

    t0 = time.time()
    mat, ref_ids, sites = load_cache(cache_path)
    phenomap = load_phenotype_table(pheno_path, trait=trait, source=source)
    if binary:
        phenomap = {k: v for k, v in ((i, apply_binary_rule(v, trait)) for i, v in phenomap.items()) if v is not None}
    y_full = np.array([phenomap.get(i, np.nan) for i in ref_ids], float)
    mask = np.isfinite(y_full)
    n_pheno = int(mask.sum())
    if n_pheno < MIN_PHENO_N:
        return {"ok": False, "n": n_pheno, "reason": "n<MIN_PHENO_N"}
    X = mat[mask].astype(np.float32)
    y = y_full[mask]
    m_before = X.shape[1]
    keep = site_filter(X, maf_min=maf, max_missing=max_missing)
    if max_sites is not None:
        idx = np.where(keep)[0][: max_sites]
        keep = np.zeros_like(keep)
        keep[idx] = True
    m_after = int(keep.sum())
    if m_after < 10:
        return {"ok": False, "n": n_pheno, "reason": "too few sites"}
    site_use = [s for s, k in zip(sites, keep) if k]
    Xk = impute_mean(X[:, keep].astype(float))
    freqs = allele_freq(X[:, keep].astype(float))
    maf_v = np.minimum(freqs, 1.0 - freqs)
    K = grm_vanraden(Xk, freqs)
    C0 = np.ones((n_pheno, 1))
    _d, _sg, _se, U0, _S0, _ll = reml_delta(y - y.mean(), K, C0)
    pc_mat = pcs_from_K(U0, pcs)
    C = np.column_stack([np.ones(n_pheno), pc_mat]) if pc_mat.size else C0
    delta, sg, se, U, S, _ll = reml_delta(y - y.mean(), K, C)
    beta, se_b, tstat, p = p3d_scan(Xk, y, C, U, S, delta)
    q = bh_fdr(p)
    lam = genomic_inflation_lambda(p)
    m = len(p)
    bonf = 0.05 / m
    sugg = 1.0 / m
    nlp = -np.log10(np.clip(p, 1e-300, 1.0))
    chrom, pos = zip(*(parse_site(s) for s in site_use))
    chrom_l = list(chrom)
    pos_a = np.array(pos, int)

    slug = trait_slug(trait, binary=binary)
    dest = out_dir / source / slug
    dest.mkdir(parents=True, exist_ok=True)
    assoc_path = dest / "assoc.tsv"
    with assoc_path.open("w", encoding="utf-8") as fh:
        fh.write("chrom\tpos\tsite\tmaf\tn\tbeta\tse\tp\tneglog10p\tq\tbonf_sig\n")
        for i, s in enumerate(site_use):
            fh.write(
                f"{chrom_l[i]}\t{pos_a[i]}\t{s}\t{maf_v[i]:.5f}\t{n_pheno}\t"
                f"{beta[i]:.6g}\t{se_b[i]:.6g}\t{p[i]:.6g}\t{nlp[i]:.4f}\t{q[i]:.6g}\t"
                f"{int(p[i] < bonf)}\n"
            )

    root = root or cache_path.resolve().parents[2]
    genes = None
    features = None
    gff = root / "data" / "ref" / "VS1.final.gff3"
    if gff.exists():
        genes, features = load_gene_annotation(gff)
    tl = _load_trait_locus(root / "data" / "trait_locus.tsv")
    exc = _load_gwas_exclude(root / "data" / "panel" / "admixture" / "gwas_exclude.tsv")
    leads = clump_hits(chrom_l, pos_a, p, window_bp=200_000, p_max=sugg)
    hit_rows = []
    for h in leads:
        i = h["i"]
        hit_rows.append(
            {
                "chrom": chrom_l[i],
                "pos": int(pos_a[i]),
                "site": site_use[i],
                "p": float(p[i]),
                "q": float(q[i]),
                "beta": float(beta[i]),
                "neglog10p": float(nlp[i]),
            }
        )
    hit_rows = annotate_hits(hit_rows, genes=genes, trait_locus=tl, gwas_exclude=exc, features=features)
    hits_path = dest / "hits.tsv"
    if hit_rows:
        keys = list(hit_rows[0].keys())
        with hits_path.open("w", encoding="utf-8") as fh:
            fh.write("\t".join(keys) + "\n")
            for r in hit_rows:
                fh.write("\t".join(str(r.get(k, "")) for k in keys) + "\n")
    else:
        hits_path.write_text("chrom\tpos\tsite\tp\n", encoding="utf-8")

    plot_manhattan(
        chrom_l,
        pos_a,
        nlp,
        dest / "manhattan.png",
        title=f"GWAS {source} {slug} n={n_pheno}",
        bonf=bonf,
        suggestive=sugg,
    )
    plot_qq(p, dest / "qq.png", lam=lam if lam == lam else 0.0)

    n_bonf = int(np.sum(p < bonf))
    n_fdr = int(np.sum(q < 0.05))
    top_i = int(np.argmin(p))
    top = hit_rows[0] if hit_rows else {
        "chrom": chrom_l[top_i],
        "pos": int(pos_a[top_i]),
        "p": float(p[top_i]),
        "nearest_gene": "",
        "trait_locus_overlap": "",
        "site": site_use[top_i],
    }
    h2 = float(sg / (sg + se)) if (sg + se) > 0 else float("nan")
    case_n = int(np.sum(y >= 0.5)) if binary else ""
    ctrl_n = int(np.sum(y < 0.5)) if binary else ""
    summary = {
        "ok": True,
        "trait": trait,
        "source": source,
        "slug": slug,
        "binary": binary,
        "n": n_pheno,
        "n_after_dedup": n_pheno,
        "m_sites_before": m_before,
        "m_after_maf": m_after,
        "m_after_missing": m_after,
        "n_pcs": int(pc_mat.shape[1]) if pc_mat.size else 0,
        "lambda_gc": lam,
        "delta": delta,
        "h2_snp": h2,
        "n_bonf": n_bonf,
        "n_fdr": n_fdr,
        "n_clumps": len(hit_rows),
        "runtime_s": time.time() - t0,
        "top_hit": top,
        "case_n": case_n,
        "control_n": ctrl_n,
        "out_dir": str(dest),
    }
    (dest / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    return summary


def run_gwas_all(
    cache_path: Path,
    pheno_path: Path,
    coverage_path: Path,
    out_dir: Path,
    *,
    min_n: int = MIN_PHENO_N,
    curated_only: bool = False,
    root: Path | None = None,
    **kw,
) -> Path:
    import csv

    jobs: list[tuple[str, str, bool]] = []
    if curated_only:
        jobs = list(CURATED_GWAS)
    elif coverage_path.exists():
        with coverage_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                n = int(float(row.get("n_nonmissing") or 0))
                if n < min_n:
                    continue
                src, trait = row["source"], row["trait"]
                jobs.append((src, trait, False))
                if trait in ("OIV 225", "OIV 151", "OIV 241", "OIV 236"):
                    jobs.append((src, trait, True))
    index_rows = []
    for src, trait, binary in jobs:
        try:
            sm = run_gwas_trait(
                cache_path, pheno_path, trait, src, out_dir, binary=binary, root=root, **kw
            )
        except Exception as exc:  # noqa: BLE001
            sm = {"ok": False, "trait": trait, "source": src, "reason": str(exc), "n": 0}
        if not sm.get("ok"):
            continue
        top = sm.get("top_hit") or {}
        index_rows.append(
            {
                "source": src,
                "trait": trait + ("_bin" if binary else ""),
                "scale": "binary" if binary else "",
                "n": sm.get("n"),
                "m": sm.get("m_after_maf"),
                "lambda": sm.get("lambda_gc"),
                "n_bonf": sm.get("n_bonf"),
                "n_fdr": sm.get("n_fdr"),
                "top_chrom": top.get("chrom", ""),
                "top_pos": top.get("pos", ""),
                "top_p": top.get("p", ""),
                "top_gene": top.get("nearest_gene", ""),
                "trait_locus_overlap": top.get("trait_locus_overlap", ""),
                "slug": sm.get("slug"),
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = out_dir / "index.tsv"
    if index_rows:
        keys = list(index_rows[0].keys())
        with idx.open("w", encoding="utf-8") as fh:
            fh.write("\t".join(keys) + "\n")
            for r in index_rows:
                fh.write("\t".join(str(r.get(k, "")) for k in keys) + "\n")
    else:
        idx.write_text("source\ttrait\tn\n", encoding="utf-8")
    return idx


