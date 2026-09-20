"""Build a full multi-domain HTML report with figures (Italy-project style).

Sections: QC, Identity (IBS exclude-self), PCA, ADMIXTURE, Damage,
Trait-locus + gene, GWAS/GS demo, Fst/GEA, CoreSNP, purity.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from grapeancestry.adna.admixture import (
    COMPONENT_COLORS,
    SCIENCE_K8_COLORS,
    SCIENCE_K8_LEGEND_LABELS,
    SCIENCE_RUN_FAMILY,
    AdmixtureContrast,
    component_labels_colors,
    display_run_family,
    id_path_for_family,
    load_admixture_matrix,
    load_admixture_k_range,
    load_panel_site_index,
    load_saved_chip_projection,
    plot_order_indices,
    resolve_admixture_run_family,
)
from grapeancestry.adna.panel167k_nogwas import (
    PANEL167K_NOGWAS_FAMILY,
    load_family_sites,
)
from grapeancestry.adna.grp_order import REPORT_GRP_ORDER
from grapeancestry.adna.project import SVDCacheResult, load_svd_cache, write_svd_cache
from grapeancestry.adna.smartpca_project import (
    normalize_eigenvalues,
    parse_eigenvalue_ratios,
    run_smartpca_project,
)
from grapeancestry.breeding.gs import evaluate_models, gblup_predict, metrics as gs_metrics, rrblup_predict
from grapeancestry.breeding.gwas import gwas_from_phenotype, gwas_lm, haploblocks, metadata_traits
from grapeancestry.core.dosage import load_cache, load_sample_dosage
from grapeancestry.identity.ibs import IBSHit, nearest_neighbors
from grapeancestry.popgen.stats import weir_cockerham_fst
from grapeancestry.resource.coresnp import greedy_coresnp
from grapeancestry.resource.genes import annotate_site, load_gene_annotation
from grapeancestry.resource.oiv import describe_trait, load_oiv_table
from grapeancestry.resource.sprot import attach_func_fields, load_gene_func


REPORT_V2_SUFFIX = ".sample-first-v2.report.html"


def v2_report_path(results_dir: Path, sample: str) -> Path:
    return Path(results_dir) / f"{sample}{REPORT_V2_SUFFIX}"


def _fig_b64() -> str:
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _save_b64_png(b64: str | None, path: Path) -> None:
    if not b64:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(b64))


def _fmt(x: float, nd: int = 2) -> str:
    if x != x:
        return "NA"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    return f"{x:.{nd}f}"


def pca_method_label(method: str) -> str:
    """Short PCA label for report text. Do not show cache filenames."""
    s = str(method or "")
    if not s:
        return "PCA"
    low = s.lower()
    if "gcta" in low:
        return "GCTA64 PCA · 153,483 SNPs"
    if "smartpca" in low:
        return "smartPCA lsqproject · 153,483 SNPs"
    if "5k" in low:
        return "PCA · 5k SNPs"
    if "167k" in low:
        return "PCA · 167k SNPs"
    if "numpy svd" in low or "svd" in low:
        return "PCA (SVD)"
    return s


def sanitize_conclusion_text(c: str) -> str:
    """Drop cache / run-family / Chip-P plumbing from a conclusions bullet."""
    c = str(c or "").strip()
    if not c:
        return ""
    if re.match(
        r"(?:Selection:|Trait-locus overlap:|GS index:|Pop context Fst\b)",
        c,
        re.I,
    ):
        return ""
    if re.match(r"Analysis matrix:", c, re.I):
        return ""
    if re.search(r"chip-P", c, re.I):
        return ""
    if "not Science-coloured" in c:
        return ""
    c = re.sub(
        r"PCA \((.*)\)(?=:)",
        lambda m: pca_method_label(m.group(1)),
        c,
        count=1,
    )
    c = re.sub(r"ADMIXTURE K=8 \([^)]*\) on 2449; Grp=NA; ", "ADMIXTURE K=8 on 2449; ", c)
    c = re.sub(r"ADMIXTURE K=8 \([^)]*\) on 2449; ", "ADMIXTURE K=8 on 2449; ", c)
    c = re.sub(
        r"is an out-of-panel query, not (?:a|the) 2449 lookup row\.",
        "is not in the 2449 reference panel.",
        c,
    )
    c = c.replace(
        "Panel bars are the 2449 ADMIXTURE Q; the query is projected with admixture -P onto that P.",
        "The ADMIXTURE bars are the 2449 Q; this sample is projected onto that model.",
    )
    c = c.replace(
        "K=2–8 strips use Science Q/colours (Dong et al. 2023 doi:10.1126/science.add8655 Fig. 1D). ",
        "",
    )
    return re.sub(r"\s+", " ", c).strip()


def _workspace_relative_path(root: Path, path: Path) -> str:
    root_path = Path(root).resolve()
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = root_path / file_path
    try:
        relative = file_path.resolve().relative_to(root_path)
    except ValueError:
        relative = Path(os.path.relpath(str(file_path), str(root_path)))
    return relative.as_posix()


def file_signature(root: Path, path: Path) -> dict:
    """Return a small workspace-relative file signature without hashing content."""
    root = Path(root)
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = root / file_path
    out = {
        "path": _workspace_relative_path(root, file_path),
        "available": False,
    }
    try:
        stat = file_path.stat()
    except OSError:
        return out
    out.update(
        {
            "available": True,
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
    )
    return out


_file_signature = file_signature


LIBRARY_TYPE_CLASS = {
    "pe": "modern",
    "adna": "ancient",
}
MODERN_DAMAGE_CONCLUSION = (
    "Modern sample / modern PE library; mapDamage plots not shown."
)


def classify_library_type(raw: object) -> str:
    """Map config `type` to modern/ancient. `pe` and `adna` from docs/PIPELINE.md."""
    return LIBRARY_TYPE_CLASS.get(str(raw or "").strip().lower(), "")


def resolve_sample_library_type(
    root: Path,
    *,
    source_sample_id: str | None = None,
    query_id: str | None = None,
) -> dict[str, str]:
    """Read `samples.<id>.type` from config/samples*.yaml.

    Source: docs/PIPELINE.md (Modern PE `type: pe`; aDNA SE `type: adna`)
    and config/samples_demo.yaml / samples_hun89.yaml / samples_ages.yaml.
    """
    empty = {
        "library_type": "",
        "library_class": "",
        "library_type_sample_id": "",
    }
    wanted: list[str] = []
    for ident in (source_sample_id, query_id):
        text = str(ident or "").strip()
        if text and text not in wanted:
            wanted.append(text)
    if not wanted:
        return empty
    try:
        import yaml
    except ImportError:
        return empty
    cfg = Path(root) / "config"
    if not cfg.is_dir():
        return empty
    files: list[Path] = []
    seen: set[Path] = set()
    for path in (*sorted(cfg.glob("samples*.yaml")), *sorted(cfg.glob("samples*.yml"))):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        files.append(path)
    maps: list[dict] = []
    for path in files:
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except (OSError, yaml.YAMLError):
            continue
        samples = data.get("samples") if isinstance(data, dict) else None
        if isinstance(samples, dict):
            maps.append(samples)
    for ident in wanted:
        for samples in maps:
            row = samples.get(ident)
            if not isinstance(row, dict):
                continue
            raw = str(row.get("type") or "").strip().lower()
            if not raw:
                continue
            return {
                "library_type": raw,
                "library_class": classify_library_type(raw),
                "library_type_sample_id": ident,
            }
    return empty


def build_report_meta(
    root: Path,
    *,
    query_id: str,
    source_sample_id: str | None = None,
    panel_cache: Path,
    query_vcf: Path | None = None,
    source_bam: Path | None = None,
    source_damage_tsv: Path | None = None,
) -> dict:
    """Build sample-first provenance using relative paths and lightweight stats."""
    root = Path(root)
    source_id = source_sample_id or query_id
    library = resolve_sample_library_type(
        root, source_sample_id=source_id, query_id=query_id
    )
    return {
        "schema_version": "sample-first-v2",
        "report_id": f"{query_id}{REPORT_V2_SUFFIX}",
        "query_id": str(query_id),
        "source_sample_id": str(source_id),
        "library_type": library["library_type"],
        "library_class": library["library_class"],
        "library_type_sample_id": library["library_type_sample_id"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "panel_cache": file_signature(root, panel_cache),
        "query_vcf": file_signature(
            root,
            query_vcf or root / "results" / f"{query_id}.vcf.gz",
        ),
        "source_bam": file_signature(
            root,
            source_bam or root / "results" / "bam" / f"{source_id}.markdup.bam",
        ),
        "source_damage_tsv": file_signature(
            root,
            source_damage_tsv or root / "results" / f"{source_id}.damage.tsv",
        ),
        "shared_artifacts": {
            "selection": {
                "manhattan": file_signature(
                    root, root / "results" / "selection" / "manhattan.json"
                ),
                "locuszoom": file_signature(
                    root, root / "results" / "selection" / "locuszoom.json"
                ),
            },
            "gwas": {
                "index": file_signature(
                    root, root / "results" / "gwas" / "index.tsv"
                ),
                "locuszoom": file_signature(
                    root, root / "results" / "gwas" / "locuszoom.json"
                ),
            },
            "gs": {
                "index": file_signature(root, root / "results" / "gs" / "index.tsv"),
            },
        },
    }


def _coerce_query_gt(value: object) -> int:
    try:
        number = float(value)
        if not np.isfinite(number):
            return -1
        if not number.is_integer():
            return -1
        gt = int(number)
    except (TypeError, ValueError, OverflowError):
        return -1
    return gt if gt in {0, 1, 2} else -1


def _site_lookup_key(site: object) -> str:
    text = str(site or "").strip()
    if ":" not in text:
        return text
    chrom, pos = text.split(":", 1)
    chrom = chrom.removeprefix("chr")
    try:
        pos = str(int(pos))
    except ValueError:
        pass
    return f"{chrom}:{pos}"


def _record_site(record: dict) -> str:
    site = str(record.get("lead_site") or record.get("site") or "").strip()
    if site:
        return site
    chrom = str(
        record.get("chrom")
        or record.get("chr")
        or record.get("top_chrom")
        or ""
    ).strip()
    pos = record.get("pos") or record.get("top_pos")
    if chrom and pos not in (None, ""):
        return f"{chrom}:{pos}"
    snp_sites = (record.get("snps") or {}).get("site") or []
    lead_i = record.get("lead_i")
    try:
        if snp_sites and lead_i is not None:
            return str(snp_sites[int(lead_i)])
    except (TypeError, ValueError, IndexError):
        pass
    return ""


def _aligned_query_gt_map(query: object, sites: list[str]) -> dict[str, int]:
    aligned_sites = [_site_lookup_key(site) for site in sites]
    if isinstance(query, dict):
        values = {
            _site_lookup_key(site): _coerce_query_gt(value)
            for site, value in query.items()
        }
        return {site: values.get(site, -1) for site in aligned_sites}
    values = np.asarray(query).reshape(-1)
    if len(values) != len(aligned_sites):
        raise ValueError(
            f"query dosage array length {len(values)} does not match "
            f"sites length {len(aligned_sites)}"
        )
    return {
        site: _coerce_query_gt(values[index])
        for index, site in enumerate(aligned_sites)
    }


def _metric_value(record: dict) -> tuple[str, object]:
    for key in ("nlp", "neglog10p", "p", "beta", "effect"):
        if key not in record or record.get(key) in (None, ""):
            continue
        value = record[key]
        try:
            number = float(value)
            if np.isfinite(number):
                return key, number
        except (TypeError, ValueError):
            pass
        return key, value
    return "lead", _record_site(record)


def build_query_evidence(
    query: object,
    sites: list[str],
    gwas_loci: list[dict] | None,
    *,
    gwas_source: str | None = None,
) -> list[dict]:
    """Build query-genotype rows with panel evidence kept strictly separate."""
    from grapeancestry.cloud.mas import MAS_LOCI

    query_map = _aligned_query_gt_map(query, list(sites))
    rows: list[dict] = []
    seen: set[str] = set()

    def add_row(
        site: str,
        *,
        evidence: str,
        trait: object,
        gene: object,
        panel_context: dict,
    ) -> None:
        key = _site_lookup_key(site)
        if not key or key in seen:
            return
        seen.add(key)
        query_gt = query_map.get(key, -1)
        rows.append(
            {
                "site": site,
                "query_gt": query_gt,
                "call_status": "called" if query_gt >= 0 else "missing",
                "evidence": evidence,
                "trait": str(trait or ""),
                "gene": str(gene or ""),
                "panel_context": panel_context,
                "scope": "query_genotype",
            }
        )

    for locus in MAS_LOCI:
        site = _record_site(locus)
        add_row(
            site,
            evidence="curated_locus",
            trait=locus.get("trait"),
            gene=locus.get("gene"),
            panel_context={
                "source": "MAS_LOCI",
                "annotation": locus.get("note") or "curated MAS locus",
                "metric": "curated_locus",
                "value": True,
            },
        )

    for locus in gwas_loci or []:
        site = _record_site(locus)
        metric, value = _metric_value(locus)
        add_row(
            site,
            evidence="panel_gwas_lead",
            trait=locus.get("trait"),
            gene=locus.get("gene") or locus.get("top_gene"),
            panel_context={
                "source": str(
                    locus.get("source")
                    or gwas_source
                    or "results/gwas/locuszoom.json"
                ),
                "annotation": "panel GWAS lead",
                "metric": metric,
                "value": value,
            },
        )
    return rows


def _locus_gt_counts(loci: list[dict] | None) -> dict[str, int]:
    site_gt: dict[str, int] = {}
    fallback_called = 0
    fallback_total = 0
    for locus in loci or []:
        if not isinstance(locus, dict):
            continue
        snps = locus.get("snps") or {}
        snp_sites = snps.get("site") or locus.get("sites") or []
        gt = snps.get("gt")
        if snp_sites and gt is not None:
            values = [_coerce_query_gt(value) for value in np.asarray(gt).reshape(-1)]
            for site, value in zip(snp_sites, values):
                key = _site_lookup_key(site)
                if not key:
                    continue
                previous = site_gt.get(key)
                if previous is None or (previous < 0 and value >= 0):
                    site_gt[key] = value
            continue
        if locus.get("query_gt_called") is not None and locus.get("query_gt_n") is not None:
            try:
                fallback_called += max(0, int(locus["query_gt_called"]))
                fallback_total += max(0, int(locus["query_gt_n"]))
                continue
            except (TypeError, ValueError):
                pass
        if gt is None:
            continue
        values = [_coerce_query_gt(value) for value in np.asarray(gt).reshape(-1)]
        fallback_total += len(values)
        fallback_called += sum(value >= 0 for value in values)
    called = sum(value >= 0 for value in site_gt.values()) + fallback_called
    total = len(site_gt) + fallback_total
    return {"query_gt_called": called, "query_gt_n": total}


def _optional_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def build_method_coverage(
    query: object,
    sites: list[str],
    *,
    selection_loci: list[dict] | None = None,
    gwas_loci: list[dict] | None = None,
    fstat_query_called_sites: int = 0,
    gs_pred: list[dict] | None = None,
    qc: dict | None = None,
    damage_available: bool = False,
    damage_unavailable_reason: str = "",
    gs_available: bool = False,
    gs_unavailable_reason: str = "",
    damage_source_sample_id: str = "",
    damage_path: str = "",
    damage_path_available: bool = False,
) -> dict:
    """Return exact method coverage counts without threshold-based judgments."""
    aligned_query = _aligned_query_gt_map(query, list(sites))
    query_values = np.asarray(list(aligned_query.values()), dtype=np.int8)
    called = sum(_coerce_query_gt(value) >= 0 for value in query_values)
    total = len(sites)
    panel_coverage = called / total if total else None
    qc_panel_rate = (qc or {}).get("calling_rate_panel_pct")
    selection = _locus_gt_counts(selection_loci)
    gwas = _locus_gt_counts(gwas_loci)
    predictions = [
        {
            "trait": str(row.get("trait") or ""),
            "coverage": _optional_float(row.get("coverage")),
            "flag": str(row.get("flag") or ""),
        }
        for row in (gs_pred or [])
    ]
    selection_record = dict(selection)
    if not selection_record["query_gt_n"]:
        selection_record["unavailable_reason"] = "no selection locus genotype coverage"
    gwas_record = dict(gwas)
    if not gwas_record["query_gt_n"]:
        gwas_record["unavailable_reason"] = "no GWAS locus genotype coverage"
    fstats_record = {
        "query_called_sites": int(fstat_query_called_sites or 0),
    }
    if not fstats_record["query_called_sites"]:
        fstats_record["unavailable_reason"] = "no fstats query sites"
    per_sample_gs_available = bool(predictions)
    damage_record = {
        "available": bool(damage_available),
        "unavailable_reason": "" if damage_available else str(
            damage_unavailable_reason or "damage profile unavailable"
        ),
    }
    if damage_source_sample_id or damage_path:
        damage_record.update(
            {
                "source_sample_id": str(damage_source_sample_id or ""),
                "path": str(damage_path or ""),
                "path_available": bool(damage_path_available),
            }
        )
    return {
        "panel_genotype": {
            "called": called,
            "total": total,
            "coverage": panel_coverage,
            "display_metadata": {
                "qc_panel_calling_rate_pct": qc_panel_rate,
            },
        },
        "selection_locus_gt": selection_record,
        "gwas_locus_gt": gwas_record,
        "fstats": fstats_record,
        "gs_predictions": predictions,
        "damage": damage_record,
        "gs": {
            "available": per_sample_gs_available,
            "unavailable_reason": "" if per_sample_gs_available else str(
                gs_unavailable_reason or "no per-sample GS prediction available"
            ),
        },
    }


@dataclass
class ReportBundle:
    sample: str
    qc: dict[str, float]
    ibs_hits: list[IBSHit]
    pca_sample: tuple[float, float]
    ref_pca: list[tuple[str, float, float, str]]
    admix: dict[str, float] | None  # K=8 row (or max K) for backward compat
    admix_contrast: AdmixtureContrast | None
    damage_freqs: list[float] | None
    trait_hits: list[dict]
    fst: float | None
    gea_r: float | None
    purity_note: str
    conclusions: list[str]
    gwas_nlp: np.ndarray | None = None
    gwas_chrom: list[str] = field(default_factory=list)
    gwas_pos: list[int] = field(default_factory=list)
    gwas_blocks: list[tuple[int, int]] = field(default_factory=list)
    gs: dict[str, float] = field(default_factory=dict)
    coresnp: list[str] = field(default_factory=list)
    kinship_top: list[dict] = field(default_factory=list)
    ibs_relationships: list[dict] = field(default_factory=list)
    ibs_summary: dict[str, int] = field(default_factory=dict)
    pca_color: str = "Grp"
    merged_vcf_note: str = ""
    gwas_trait: str = ""
    # New: selection / f-stats / tree / clone hits
    selection_outliers: list[dict] = field(default_factory=list)
    selection_het: np.ndarray | None = None
    selection_sites: list[str] = field(default_factory=list)
    selection_named: list[dict] = field(default_factory=list)
    selection_by_grp: list[dict] = field(default_factory=list)
    selection_vs_science: list[dict] = field(default_factory=list)
    selection_vs_summary: list[dict] = field(default_factory=list)
    selection_loci: list[dict] = field(default_factory=list)
    selection_manhattan: dict = field(default_factory=dict)
    selection_heatmap: dict = field(default_factory=dict)
    selection_s29_scatter: dict = field(default_factory=dict)
    selection_fst_het_scatter: dict = field(default_factory=dict)
    f3_rows: list[dict] = field(default_factory=list)
    f4_rows: list[dict] = field(default_factory=list)
    f3_out_rows: list[dict] = field(default_factory=list)
    tree_ids: list[str] = field(default_factory=list)
    tree_obj: object | None = None
    clone_hits: list[dict] = field(default_factory=list)
    tip_groups: dict[str, str] = field(default_factory=dict)
    # Multi-PC for interactive switch / 3D (iid → [PC1, PC2, PC3, ...])
    pca_coords: dict[str, list[float]] = field(default_factory=dict)
    pca_evals: list[float] = field(default_factory=list)
    pca_method: str = ""
    gwas_index: list[dict] = field(default_factory=list)
    gwas_figs: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)
    gwas_loci: list[dict] = field(default_factory=list)
    gs_index: list[dict] = field(default_factory=list)
    gs_pred: list[dict] = field(default_factory=list)
    cross_top: list[dict] = field(default_factory=list)
    methods_html: str = ""
    gwas_skip: str = ""
    damage_profile: dict | None = None
    fstat_pop: str = "Grp"
    fstat_query_called_sites: int = 0
    outgroup_n: int = 0
    source_sample_id: str | None = None
    report_meta: dict = field(default_factory=dict)
    query_evidence: list[dict] = field(default_factory=list)
    method_coverage: dict = field(default_factory=dict)


def load_grp_colors(path: Path) -> dict[str, str]:
    """Load Grp→hex. Source: 3k Science palette (smartPCA.md / legendnew.py)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with path.open() as fh:
        next(fh, None)
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            g, hexv = parts[0], parts[1]
            out[g] = hexv
    return out


def load_report_pca_seed(
    path: Path,
    *,
    sample: str,
    expected_ref_ids: list[str],
    cache_name: str,
    n_sites: int,
) -> SVDCacheResult | None:
    """Accept prior report coordinates only when their SVD provenance matches."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        method = str(payload.get("pca_method") or "")
        points = payload.get("pca_points") or []
        if (
            payload.get("query") != sample
            or payload.get("cache_name") != cache_name
            or cache_name not in method
            or int(payload.get("n_sites")) != n_sites
            or int(payload.get("pca_n")) < 3
            or "svd" not in method.lower()
        ):
            return None
        point_map: dict[str, list[float]] = {}
        query_flags: set[str] = set()
        for point in points:
            sid = str(point.get("iid") or "")
            pcs = point.get("pcs")
            if not sid or sid in point_map or not isinstance(pcs, list) or len(pcs) < 3:
                return None
            coords = [float(x) for x in pcs[:3]]
            if not np.isfinite(coords).all():
                return None
            point_map[sid] = coords
            if point.get("query"):
                query_flags.add(sid)
        if set(point_map) != set(expected_ref_ids) | {sample}:
            return None
        if query_flags and query_flags != {sample}:
            return None
        evals_raw = payload.get("pca_evals") or []
        evals = [float(x) for x in evals_raw if np.isfinite(float(x))]
        if evals and max(evals) > 1.0 + 1e-9:
            evals = normalize_eigenvalues(evals)
        return SVDCacheResult(
            ref_ids=list(expected_ref_ids),
            ref_coords=np.asarray([point_map[sid] for sid in expected_ref_ids], dtype=float),
            query_ids=[sample],
            query_coords=np.asarray([point_map[sample]], dtype=float),
            evals=evals,
            method=method,
            cache_name=cache_name,
            n_sites=n_sites,
        )
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _evenly_spaced_ids(ids: list[str], max_items: int) -> list[str]:
    if max_items <= 0 or len(ids) <= max_items:
        return list(ids)
    positions = np.linspace(0, len(ids) - 1, max_items, dtype=int)
    return [ids[i] for i in dict.fromkeys(positions)]


def _pca_source_is_compatible(
    root: Path,
    result: SVDCacheResult,
    *,
    sample: str,
    expected_ref_ids: list[str],
) -> bool:
    """Validate a cached PCA source independently from the analysis cache."""
    source_name = Path(result.cache_name).name
    source_path = root / "results" / "cache" / source_name
    if not source_path.exists():
        return False
    try:
        _matrix, source_ids, source_sites = load_cache(source_path)
    except (OSError, ValueError):
        return False
    return (
        len(source_sites) == result.n_sites
        and [sid for sid in source_ids if sid != sample] == expected_ref_ids
    )


def collect_ibs(
    query: np.ndarray,
    mat: np.ndarray,
    ref_ids: list[str],
    sample: str,
    top_n: int = 10,
) -> list[IBSHit]:
    hits = nearest_neighbors(query, mat, ref_ids, top_n=top_n + 5)
    filtered = [h for h in hits if h.ref_id != sample]
    return filtered[:top_n]


def purity_check(query: np.ndarray, mat: np.ndarray, mean_depth: float | None = None) -> str:
    q = query.astype(float)
    qhet = float(np.mean(q[q >= 0] == 1)) if np.any(q >= 0) else float("nan")
    panel_het = []
    for i in range(min(mat.shape[0], 500)):
        row = mat[i].astype(float)
        ok = row >= 0
        if ok.sum() < 50:
            continue
        panel_het.append(float(np.mean(row[ok] == 1)))
    if not panel_het or qhet != qhet:
        return "Purity: insufficient calls."
    mu, sd = float(np.mean(panel_het)), float(np.std(panel_het) + 1e-9)
    z = (qhet - mu) / sd
    depth_note = ""
    if mean_depth is not None and mean_depth == mean_depth and mean_depth < 8:
        depth_note = (
            f" Low mean depth ({mean_depth:.1f}×) can under-call heterozygotes — "
            "not necessarily genetic purity."
        )
    if z > 3:
        return (
            f"Purity WARNING: excess het={qhet:.3f} (panel mean {mu:.3f}, z={z:.1f}) — "
            f"possible mixture.{depth_note}"
        )
    if z < -3:
        return f"Purity note: low het={qhet:.3f} (panel mean {mu:.3f}).{depth_note}"
    return f"Purity OK: het={qhet:.3f} within panel range (mean {mu:.3f} ± {sd:.3f}).{depth_note}"


def _mas_indexes() -> tuple[dict[str, dict], dict[str, dict]]:
    from grapeancestry.cloud.mas import MAS_LOCI

    by_site = {r["site"]: r for r in MAS_LOCI}
    by_gene = {
        r["gene"]: r for r in MAS_LOCI if str(r.get("gene") or "").startswith("Vvsyl")
    }
    return by_site, by_gene


def _pick_trait_hits(
    rows: list[dict],
    *,
    limit: int,
    per_trait: int,
    priority_sites: set[str],
) -> list[dict]:
    picked: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        site = row["site"]
        if site in priority_sites and site not in seen:
            picked.append(row)
            seen.add(site)
    from collections import defaultdict

    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["site"] in seen:
            continue
        buckets[str(row.get("trait") or "")].append(row)
    keys = sorted(buckets, key=lambda k: (-len(buckets[k]), k))
    used: dict[str, int] = defaultdict(int)
    progressed = True
    while len(picked) < limit and progressed:
        progressed = False
        for trait in keys:
            if len(picked) >= limit:
                break
            if used[trait] >= per_trait or not buckets[trait]:
                continue
            row = buckets[trait].pop(0)
            picked.append(row)
            seen.add(row["site"])
            used[trait] += 1
            progressed = True
    return picked[:limit]


def trait_overlap(
    site_keys: list[str],
    trait_tsv: Path,
    genes: dict | None = None,
    features: dict | None = None,
    oiv: dict | None = None,
    sprot: dict | None = None,
    limit: int = 40,
    per_trait: int = 2,
) -> tuple[list[dict], int]:
    if not trait_tsv.exists():
        return [], 0
    want = set(site_keys)
    raw: list[dict] = []
    with trait_tsv.open() as fh:
        r = csv.DictReader(fh, delimiter="\t")
        for row in r:
            chrom = row.get("chrom") or row.get("chr") or ""
            pos = row.get("pos") or ""
            key = f"{chrom}:{pos}"
            if key not in want:
                continue
            raw.append(
                {
                    "site": key,
                    "chrom": chrom,
                    "pos": pos,
                    "trait": row.get("trait", ""),
                    "note": row.get("note", ""),
                }
            )
    mas_site, mas_gene = _mas_indexes()
    n_gwas = len(raw)
    have = {r["site"] for r in raw}
    for loc in mas_site.values():
        site = loc.get("site") or ""
        if site not in want or site in have:
            continue
        chrom, pos = site.split(":", 1)
        raw.append(
            {
                "site": site,
                "chrom": chrom,
                "pos": pos,
                "trait": loc.get("trait") or "",
                "note": loc.get("note") or "",
            }
        )
    picked = _pick_trait_hits(
        raw,
        limit=limit,
        per_trait=per_trait,
        priority_sites=set(mas_site),
    )
    oiv = oiv or {}
    hits = []
    for row in picked:
        chrom, pos = row["chrom"], row["pos"]
        ann = annotate_site(
            chrom,
            int(pos),
            genes,
            features,
            mas_by_site=mas_site,
            mas_by_gene=mas_gene,
            sprot_by_gene=sprot,
        ) if chrom and pos else {}
        descriptor = describe_trait(row.get("trait") or "", oiv)
        note = row.get("note") or ""
        science = ann.get("science_note") or ""
        if science and science not in note:
            note = f"{note}; {science}".strip("; ")
        gid = ann.get("gene") or ""
        dist = ann.get("dist") or ""
        hits.append(
            {
                "site": row["site"],
                "trait": row.get("trait", ""),
                "descriptor": descriptor,
                "note": note,
                "gene": gid,
                "dist": dist,
                "strand": ann.get("strand") or "",
                "region": ann.get("region") or "",
                "span": ann.get("span") or "",
                "alias": ann.get("alias") or "",
                "biotype": ann.get("biotype") or "",
                "n_cds": ann.get("n_cds") or "",
            }
        )
        attach_func_fields(hits[-1], ann)
    return hits, n_gwas


def _read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _load_precomputed_breeding(root: Path, sample: str) -> dict:
    gwas_index = _read_tsv(root / "results" / "gwas" / "index.tsv")
    gs_index = _read_tsv(root / "results" / "gs" / "index.tsv")
    for row in gwas_index:
        if str(row.get("scale") or "").strip().lower() != "binary":
            continue
        source = str(row.get("source") or "").strip()
        slug = str(row.get("slug") or "").strip()
        summary_path = root / "results" / "gwas" / source / slug / "summary.json"
        try:
            summary = json.loads(summary_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for field, aliases in {
            "case_n": ("case_n", "n_cases", "cases"),
            "control_n": ("control_n", "n_controls", "controls"),
        }.items():
            value = next(
                (summary.get(key) for key in aliases if summary.get(key) is not None),
                None,
            )
            if value is None:
                continue
            try:
                row[field] = int(value)
            except (TypeError, ValueError):
                row[field] = value
    gs_pred = _read_tsv(root / "results" / f"{sample}.gs_pred.tsv")
    lz_json = root / "results" / "gwas" / "locuszoom.json"
    if lz_json.exists():
        from grapeancestry.breeding.gwas import attach_query_gt_to_loci

        gwas_loci = json.loads(lz_json.read_text())
        attach_query_gt_to_loci(gwas_loci, root / "results" / f"{sample}.vcf.gz", sample)
        gwas_loci_source = "results/gwas/locuszoom.json"
    else:
        gwas_loci = _read_tsv(root / "results" / "gwas" / "locuszoom.tsv")
        gwas_loci_source = "results/gwas/locuszoom.tsv"
    cross_top = _read_tsv(root / "results" / "cross" / f"{sample}_mates.tsv")
    if not cross_top:
        cross_top = _read_tsv(root / "results" / "cross" / "panel_mates.tsv")
    pheno = root / "data" / "phenotype.tsv"
    skip = ""
    if not gwas_index:
        n_pheno = 0
        if pheno.exists():
            n_pheno = max(sum(1 for _ in pheno.open()) - 1, 0)
        skip = (
            f"GWAS/GS using precomputed results/gwas/index.tsv "
            f"(empty). phenotype.tsv lines≈{n_pheno}. Uti is not a breeding trait."
        )
    methods_html = ""
    try:
        from grapeancestry.breeding.methods_doc import methods_html_section

        methods_html = methods_html_section(
            root / "results" / "provenance",
            root / "docs" / "REFERENCES.bib",
        )
    except Exception:
        methods_html = ""
    gs_stats: dict[str, float] = {}
    for row in gs_index:
        raw_cv = row.get("cv_r")
        if raw_cv in (None, ""):
            continue
        try:
            cv_r = float(raw_cv)
        except (TypeError, ValueError):
            continue
        source = str(row.get("source") or "unknown").strip()
        trait = str(row.get("trait") or "unknown").strip()
        gs_stats[f"{source}::{trait}"] = cv_r
    return {
        "gwas_index": gwas_index,
        "gs_index": gs_index,
        "gs_pred": gs_pred,
        "gwas_loci": gwas_loci,
        "gwas_loci_source": gwas_loci_source,
        "cross_top": cross_top[:10],
        "gwas_figs": {},
        "gwas_skip": skip,
        "methods_html": methods_html,
        "gwas_trait": gwas_index[0]["trait"] if gwas_index else "",
        "gs": gs_stats,
    }


def _demo_gwas_gs(mat: np.ndarray, sites: list[str], seed: int = 0) -> dict:
    """Panel-context GWAS Manhattan + GS CV (Italy-style companion figures). Kept, unused."""
    rng = np.random.default_rng(seed)
    n, p = mat.shape
    # plant a small causal block
    causal = slice(100, 108) if p > 120 else slice(0, min(5, p))
    X = mat.astype(float).copy()
    X[X < 0] = np.nan
    col_mu = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_mu, inds[1])
    y = X[:, causal].sum(axis=1) + rng.normal(0, 0.5, size=n)
    _b, nlp = gwas_lm(X, y)
    blocks = haploblocks(nlp, threshold=max(3.0, float(np.percentile(nlp, 99))), min_run=2)
    chroms, positions = [], []
    for s in sites:
        c, _, pos = s.partition(":")
        chroms.append(c)
        positions.append(int(pos) if pos.isdigit() else 0)
    # GS holdout
    idx = rng.permutation(n)
    tr, te = idx[: int(0.8 * n)], idx[int(0.8 * n) :]
    pred_rr = rrblup_predict(X[tr], y[tr], X[te])
    pred_gb = gblup_predict(X[tr], y[tr], X[te])
    m_rr = gs_metrics(y[te], pred_rr)
    m_gb = gs_metrics(y[te], pred_gb)
    return {
        "nlp": nlp,
        "chrom": chroms,
        "pos": positions,
        "blocks": blocks,
        "gs": {
            "rrblup_r": m_rr["r"],
            "rrblup_rmse": m_rr["rmse"],
            "gblup_r": m_gb["r"],
            "gblup_rmse": m_gb["rmse"],
        },
    }


def build_bundle(
    sample: str,
    root: Path,
    *,
    admix_dir: Path | None = None,
    damage_tsv: Path | None = None,
    pca_color: str = "Grp",
    merged_vcf: Path | None = None,
    admix_mode: str = "auto",
    admix_all_k: bool = True,
    source_sample_id: str | None = None,
) -> ReportBundle:
    from grapeancestry.core.dosage import resolve_cache

    source_id = source_sample_id or sample
    cache = resolve_cache(root)
    mat, ref_ids, sites = load_cache(cache)
    vcf = root / "results" / f"{sample}.vcf.gz"
    query = load_sample_dosage(vcf, sample, sites)

    qc: dict[str, float] = {}
    qc_path = root / "results" / f"{sample}.qc.tsv"
    if qc_path.exists():
        with qc_path.open() as fh:
            row = next(csv.DictReader(fh, delimiter="\t"))
            for k, v in row.items():
                if k == "sample":
                    continue
                try:
                    qc[k] = float(v) if v not in {"", "NA", "nan", "NaN"} else float("nan")
                except ValueError:
                    continue

    ibs = collect_ibs(query, mat, ref_ids, sample)
    ibs_relationships: list[dict] = []
    ibs_summary: dict[str, int] = {}
    ibs_schema_error: str | None = None
    ibs_path = root / "results" / f"{sample}.ibs.tsv"
    if ibs_path.exists():
        from grapeancestry.identity.run_ibs import read_ibs_table

        try:
            ibs_relationships = read_ibs_table(ibs_path)
        except ValueError as exc:
            ibs_schema_error = str(exc)
            ibs_relationships = []
        hits = []
        others = [r for r in ibs_relationships if r.get("ref") != sample]
        for row in others[:10]:
            try:
                hits.append(
                    IBSHit(
                        ref_id=row["ref"],
                        ibs=float(row.get("R1") or row.get("kinship") or 0),
                        n_comparable=0,
                    )
                )
            except (KeyError, ValueError):
                continue
        if hits:
            ibs = hits
        sum_path = root / "results" / f"{sample}.ibs_summary.tsv"
        if sum_path.exists():
            with sum_path.open() as fh:
                for row in csv.DictReader(fh, delimiter="\t"):
                    ibs_summary[row["relationship"]] = int(row["count"])

    # PCA: GCTA64 freeze for 2449; new samples lsq-projected onto those axes.
    ok = (mat >= 0).sum(axis=0) > mat.shape[0] * 0.5
    mat_pca = mat[:, ok]
    sites_pca = [s for s, keep in zip(sites, ok) if keep]
    q_pca = query[ok]
    info = root / "data" / "panel" / "2449.info"
    meta: dict[str, str] = {}
    meta_full: dict[str, dict[str, str]] = {}
    color_col = pca_color if pca_color in {"Grp", "CON", "GEO", "Uti"} else "Grp"
    if info.exists():
        with info.open() as fh:
            hdr = fh.readline().rstrip().split("\t")
            for line in fh:
                p = line.rstrip().split("\t")
                row = dict(zip(hdr, p))
                meta[row["ID"]] = row.get(color_col, "") or row.get("Grp", "")
                meta_full[row["ID"]] = row
    pops = [meta_full.get(i, {}).get("Grp", "REF") or "REF" for i in ref_ids]
    annot = root / "data" / "panel" / "locus_annot.tsv"
    workdir_pca = root / "results" / "smartpca" / sample
    evec_path = workdir_pca / "all.evec"
    svd_cache_path = workdir_pca / "svd3.npz"
    expected_ref_ids = [sid for sid in ref_ids if sid != sample]
    pca_coords: dict[str, list[float]] = {}
    pca_evals: list[float] = []
    pca_method = ""
    sp = None
    from grapeancestry.adna.pca_lock import locked_pca_for_sample

    nogwas_sites = load_family_sites(root / "data" / "panel" / "admixture")
    if nogwas_sites:
        try:
            sp = locked_pca_for_sample(
                root, sample, ref_ids, mat, query, sites, nogwas_sites
            )
        except (OSError, ValueError):
            sp = None
        if sp is not None:
            pca_method = sp.method

    # EIGENSOFT smartPCA (https://github.com/DReichLab/EIG) is authoritative
    # only when the evec is non-empty, finite, and contains expected IDs.
    if evec_path.exists() and evec_path.stat().st_size > 100:
        from grapeancestry.adna.smartpca_project import _parse_evec

        ids_e, xy_e, pops_e = _parse_evec(evec_path, n_pcs=3)
        qset = {sample}
        ref_i = [i for i, (s, p) in enumerate(zip(ids_e, pops_e)) if s not in qset and p != "QUERY"]
        qry_i = [i for i, s in enumerate(ids_e) if s in qset] or [
            i for i, p in enumerate(pops_e) if p == "QUERY"
        ]
        candidate_ref_ids = [ids_e[i] for i in ref_i]
        if (
            qry_i
            and xy_e.shape[1] >= 3
            and set(candidate_ref_ids) == set(expected_ref_ids)
        ):
            sp = SVDCacheResult(
                ref_ids=candidate_ref_ids,
                ref_coords=xy_e[ref_i],
                query_ids=[ids_e[i] for i in qry_i],
                query_coords=xy_e[qry_i],
                evals=parse_eigenvalue_ratios(
                    workdir_pca / "all.eval", max(3, xy_e.shape[1])
                ),
                workdir=workdir_pca,
                method="smartPCA lsqproject (cached evec)",
            )
            pca_method = sp.method

    # Avoid repeating the expensive decomposition when a compatible cache exists.
    if sp is None:
        sp = load_svd_cache(
            svd_cache_path,
            expected_ref_ids=expected_ref_ids,
            query_id=sample,
            cache_name=cache.name,
            n_sites=len(sites),
            n_components=3,
        )
        if sp is not None:
            pca_method = sp.method

    # The existing HUN89 report contains compatible three-PC SVD coordinates.
    if sp is None:
        seed = load_report_pca_seed(
            root / "results" / f"{sample}.report.data.json",
            sample=sample,
            expected_ref_ids=expected_ref_ids,
            cache_name=cache.name,
            n_sites=len(sites),
        )
        if seed is not None:
            seed_cache_name = cache.name
            seed_n_sites = len(sites)
            method_hint = seed.method.lower()
            for candidate_cache in sorted(cache.parent.glob("panel_dosage_*.npz")):
                hint = candidate_cache.stem.replace("panel_dosage_", "").lower()
                if hint not in method_hint:
                    continue
                try:
                    _m, candidate_ids, candidate_sites = load_cache(candidate_cache)
                except (OSError, ValueError):
                    continue
                if (
                    [sid for sid in candidate_ids if sid != sample] == expected_ref_ids
                    and candidate_sites
                ):
                    seed_cache_name = candidate_cache.name
                    seed_n_sites = len(candidate_sites)
                    break
            seed.method = f"numpy SVD ({seed_cache_name}; seeded from prior report)"
            write_svd_cache(
                svd_cache_path,
                ref_ids=seed.ref_ids,
                ref_coords=seed.ref_coords,
                query_ids=seed.query_ids,
                query_coords=seed.query_coords,
                evals=seed.evals,
                method=seed.method,
                cache_name=seed_cache_name,
                n_sites=seed_n_sites,
            )
            sp = seed
            pca_method = seed.method

    # Same visual standard as the HUN89 dashboard: 5k SVD, not 167k numpy SVD
    # and not a leftover multi-GB smartPCA PED.
    if sp is None:
        five = root / "results" / "cache" / "panel_dosage_5k.npz"
        if five.exists() and len(sites) > 10_000:
            try:
                from grapeancestry.adna.project import fit_pca, project

                mat5, ids5, sites5 = load_cache(five)
                query5 = load_sample_dosage(vcf, sample, sites5)
                ok5 = (mat5 >= 0).sum(axis=0) > mat5.shape[0] * 0.5
                model = fit_pca(mat5[:, ok5], ids5, n_components=3)
                qxy = project(model, query5[ok5])
                keep = [i for i, sid in enumerate(ids5) if sid != sample]
                sp = SVDCacheResult(
                    ref_ids=[ids5[i] for i in keep],
                    ref_coords=model.ref_coords[keep],
                    query_ids=[sample],
                    query_coords=qxy[:, :3],
                    evals=[
                        float(x)
                        for x in (
                            model.explained_variance_ratio
                            if model.explained_variance_ratio is not None
                            else []
                        )
                    ],
                    workdir=workdir_pca,
                    method=f"numpy SVD ({five.name})",
                    cache_name=five.name,
                    n_sites=len(sites5),
                )
                write_svd_cache(
                    svd_cache_path,
                    ref_ids=sp.ref_ids,
                    ref_coords=sp.ref_coords,
                    query_ids=sp.query_ids,
                    query_coords=sp.query_coords,
                    evals=sp.evals,
                    method=sp.method,
                    cache_name=five.name,
                    n_sites=len(sites5),
                )
                pca_method = sp.method
            except Exception:
                sp = None

    # Official smartPCA can still run when a small/reusable PED is available.
    if sp is None:
        ped_path = workdir_pca / "all.ped"
        if not ped_path.exists() or ped_path.stat().st_size < 1_000_000:
            try:
                sp = run_smartpca_project(
                    ref_ids,
                    mat_pca,
                    [sample],
                    q_pca,
                    sites_pca,
                    annot,
                    workdir_pca,
                    n_pcs=3,
                    pop_labels=pops,
                    reuse_ped=True,
                )
                pca_method = sp.method
            except Exception:
                sp = None
    if sp is None:
        from grapeancestry.adna.project import fit_pca, project

        model = fit_pca(mat_pca, ref_ids, n_components=3)
        qxy = project(model, q_pca)
        keep = [i for i, sid in enumerate(ref_ids) if sid != sample]
        sp = SVDCacheResult(
            ref_ids=[ref_ids[i] for i in keep],
            ref_coords=model.ref_coords[keep],
            query_ids=[sample],
            query_coords=qxy[:, :3],
            evals=[
                float(x)
                for x in (
                    model.explained_variance_ratio
                    if model.explained_variance_ratio is not None
                    else []
                )
            ],
            workdir=workdir_pca,
            method=f"numpy SVD ({cache.name})",
        )
        write_svd_cache(
            svd_cache_path,
            ref_ids=sp.ref_ids,
            ref_coords=sp.ref_coords,
            query_ids=sp.query_ids,
            query_coords=sp.query_coords,
            evals=sp.evals,
            method=sp.method,
            cache_name=cache.name,
            n_sites=len(sites),
        )
        pca_method = sp.method

    coords = (float(sp.query_coords[0, 0]), float(sp.query_coords[0, 1]))
    id_to_xy = {sid: (float(sp.ref_coords[i, 0]), float(sp.ref_coords[i, 1])) for i, sid in enumerate(sp.ref_ids)}
    ref_pca = []
    for sid in ref_ids:
        xy = id_to_xy.get(sid) or id_to_xy.get(f"{sid}:{sid}")
        if xy is None:
            continue
        ref_pca.append((sid, xy[0], xy[1], meta.get(sid, "")))

    for i, sid in enumerate(sp.ref_ids):
        pca_coords[sid] = [float(x) for x in sp.ref_coords[i]]
    for i, sid in enumerate(sp.query_ids):
        pca_coords[sid] = [float(x) for x in sp.query_coords[i]]
    pca_evals = [float(x) for x in (getattr(sp, "evals", None) or [])]

    admix = None
    admix_contrast = None
    if admix_dir and admix_dir.exists():
        info = root / "data" / "panel" / "2449.info"
        locus = root / "data" / "panel" / "locus_annot.tsv"
        family = resolve_admixture_run_family(admix_dir, 2, 8)
        if family == PANEL167K_NOGWAS_FAMILY:
            panel_sites = load_family_sites(admix_dir) or None
        else:
            panel_sites = load_panel_site_index(locus) if locus.exists() else None
        admix_contrast = load_admixture_k_range(
            sample,
            admix_dir,
            k_min=2,
            k_max=8,
            info_path=info if info.exists() else None,
            dosage=query,
            cache_sites=sites,
            panel_sites=panel_sites,
            mode=admix_mode,
            all_k=admix_all_k,
        )
        if admix_contrast:
            saved_chip = load_saved_chip_projection(root, sample)
            if (
                saved_chip
                and not admix_contrast.q_by_k
                and not admix_contrast.projected_by_k
            ):
                admix_contrast.chip_projected_by_k = saved_chip
                if admix_contrast.run_family == SCIENCE_RUN_FAMILY:
                    admix_contrast.projection_status = "chip_P_projection_not_comparable"
                    admix_contrast.projection_source = (
                        "chip-P projection; not directly comparable to Science Q"
                    )
            store = admix_contrast.q_by_k or admix_contrast.projected_by_k
            if store:
                k_show = 8 if 8 in store else max(store)
                admix = store[k_show]

    from grapeancestry.adna.damage_lite import load_sample_damage

    if damage_tsv is not None:
        damage_profile = load_sample_damage(root, sample, tsv=damage_tsv)
    else:
        source_damage_tsv = root / "results" / f"{source_id}.damage.tsv"
        damage_profile = load_sample_damage(root, source_id, tsv=source_damage_tsv)
    damage = list(damage_profile["ct5"]) if damage_profile and damage_profile.get("ct5") else None

    genes = None
    features = None
    gff = root / "data" / "ref" / "VS1.final.gff3"
    if gff.exists():
        genes, features = load_gene_annotation(gff)
    oiv = load_oiv_table(root / "data" / "oiv_traits.tsv")
    sprot = load_gene_func(root)

    traits, n_traits_total = trait_overlap(
        sites,
        root / "data" / "trait_locus.tsv",
        genes=genes,
        features=features,
        oiv=oiv,
        sprot=sprot,
    )

    groups = np.array([meta_full.get(i, {}).get("Grp", "") for i in ref_ids])
    top2 = [g for g, _ in Counter(g for g in groups if g).most_common(2)]
    fst = None
    if len(top2) == 2:
        mask = np.isin(groups, top2)
        fst = weir_cockerham_fst(mat[mask][:, :800], groups[mask])
    fst_path = root / "results" / "fst_demo.tsv"
    if fst_path.exists():
        with fst_path.open() as fh:
            fd = dict(line.strip().split("\t") for line in fh if "\t" in line)
        if "fst" in fd:
            try:
                fst = float(fd["fst"])
            except ValueError:
                pass

    gea_r = None
    gea_path = root / "results" / "gea" / "index.tsv"
    if gea_path.exists():
        try:
            import csv as _csv

            with gea_path.open() as fh:
                rows = list(_csv.DictReader(fh, delimiter="\t"))
            if rows:
                gea_r = float(rows[0].get("abs_r") or rows[0].get("spearman_lon") or "nan")
        except (OSError, ValueError):
            gea_r = None
    elif (root / "data" / "cloud" / "gea_summary.json").exists():
        try:
            gjs = json.loads((root / "data" / "cloud" / "gea_summary.json").read_text())
            gea_r = gjs.get("mean_abs_spearman")
        except (OSError, json.JSONDecodeError, ValueError):
            gea_r = None

    purity = purity_check(query, mat, mean_depth=qc.get("mean_depth"))

    breeding = _load_precomputed_breeding(root, sample)
    gwas_trait = breeding["gwas_trait"]
    gs_stats = breeding["gs"]
    gwas_skip = breeding["gwas_skip"]
    gwas_res: dict = {}
    cores = greedy_coresnp(mat[:, :500], sites[:500], max_markers=20)

    kinship_top: list[dict] = []
    kin_path = root / "results" / f"{sample}.kinship_top.tsv"
    if kin_path.exists():
        with kin_path.open() as fh:
            kinship_top = list(csv.DictReader(fh, delimiter="\t"))[:10]

    # Clone-screen hits (Identical + PO) — Italy clone_4k_summary style
    clone_hits: list[dict] = []
    ch_path = root / "results" / f"{sample}.ibs_clone_hits.tsv"
    if ch_path.exists():
        with ch_path.open() as fh:
            clone_hits = list(csv.DictReader(fh, delimiter="\t"))
    elif ibs_relationships:
        clone_hits = [
            r
            for r in ibs_relationships
            if r.get("relationship") in {"Identical", "Parent-Offspring"}
        ]

    # Selection: prefer precomputed 167K chrom-aware scan (not first 2000 sites)
    from grapeancestry.popgen.selscan import (
        WINDOWS_REL,
        load_named_windows,
        load_scan_tables,
        scan_panel,
    )

    pre = load_scan_tables(root / "results" / "selection")
    named_win = load_named_windows(root / WINDOWS_REL)
    from grapeancestry.popgen.selection_viz import load_selection_viz

    sel_viz = load_selection_viz(root)
    if sel_viz.get("loci"):
        from grapeancestry.breeding.gwas import attach_query_gt_to_loci

        attach_query_gt_to_loci(sel_viz["loci"], root / "results" / f"{sample}.vcf.gz", sample)
    if pre:
        sel = {
            "outliers": [
                {
                    "site": r.get("site", ""),
                    "chrom": r.get("chrom", ""),
                    "pos": r.get("pos", ""),
                    "het": float(r["window_het"]) if r.get("window_het") else float("nan"),
                    "gene": "",
                    "dist": "",
                    "strand": "",
                    "region": "",
                    "span": "",
                    "alias": "",
                    "biotype": "",
                    "science_note": "precomputed ±50 kb windowed het; Fst in results/selection/fst_top.tsv",
                }
                for r in (pre.get("het_dips") or [])[:25]
            ],
            "het": None,
            "sites": [],
            "n_outlier": len(pre.get("het_dips") or []),
            "named": pre.get("named") or [],
            "by_grp": pre.get("by_grp_named") or [],
            "science": pre.get("science") or [],
            "vs_summary": pre.get("vs_summary") or [],
            "loci": sel_viz.get("loci") or [],
            "manhattan": sel_viz.get("manhattan") or {},
            "heatmap": sel_viz.get("heatmap") or {},
            "s29_scatter": sel_viz.get("s29_scatter") or {},
            "fst_het_scatter": sel_viz.get("fst_het_scatter") or {},
        }
    else:
        grp = [meta_full.get(i, {}).get("Grp", "") for i in ref_ids]
        scan = scan_panel(
            mat, sites, grp, named_win, half_bp=50_000, top_n=25, grp_labels=grp, min_n=20
        )
        sel = {
            "outliers": [
                {
                    "site": r["site"],
                    "chrom": r["chrom"],
                    "pos": r["pos"],
                    "het": r["value"],
                    "gene": "",
                    "dist": "",
                    "strand": "",
                    "region": "",
                    "span": "",
                    "alias": "",
                    "biotype": "",
                    "science_note": "±50 kb windowed het on this cache",
                }
                for r in scan["het_dips"]
            ],
            "het": scan["het_window"],
            "sites": sites,
            "n_outlier": len(scan["het_dips"]),
            "named": scan["named"],
            "by_grp": (scan.get("by_grp") or {}).get("named") or [],
            "science": scan.get("science") or [],
            "vs_summary": [
                {"key": k, "value": v} for k, v in (scan.get("vs_summary") or {}).items()
            ],
            "loci": sel_viz.get("loci") or [],
            "manhattan": sel_viz.get("manhattan") or {},
            "heatmap": sel_viz.get("heatmap") or {},
            "s29_scatter": sel_viz.get("s29_scatter") or {},
            "fst_het_scatter": sel_viz.get("fst_het_scatter") or {},
        }

    # f3 / f4 vs 2449.info Grp means
    from grapeancestry.popgen.fstats_report import fstat_pop_labels, fstats_for_query

    fst_pack = fstats_for_query(
        query,
        mat,
        ref_ids,
        fstat_pop_labels(meta_full, list(ref_ids)),
        sites=sites,
        min_n=20,
        n_pairwise=6,
    )

    # NJ tree: all 2449 + query (no Grp subsample)
    from grapeancestry.popgen.tree_nj import (
        assemble_tree_distance,
        build_nj_tree,
        load_or_compute_panel_ibs_d,
    )

    tree_obj = None
    tree_ids: list[str] = []
    tip_groups: dict[str, str] = {}
    try:
        panel_d_path = root / "results" / "cache" / f"ibs_d_{cache.stem}.npz"
        panel_d = load_or_compute_panel_ibs_d(panel_d_path, list(ref_ids), mat)
        tree_ids, tree_mat, tree_d = assemble_tree_distance(
            list(ref_ids), mat, query, sample, panel_d
        )
        tree_obj = build_nj_tree(tree_ids, tree_mat, D=tree_d)
        tip_groups = {rid: meta_full.get(rid, {}).get("Grp", "") for rid in tree_ids}
        if sample not in ref_ids:
            tip_groups[sample] = "QUERY"
    except Exception:  # noqa: BLE001
        tree_obj = None

    gwas_loci = breeding.get("gwas_loci") or []
    query_evidence = build_query_evidence(
        query,
        sites,
        gwas_loci,
        gwas_source=breeding.get("gwas_loci_source"),
    )
    damage_available = bool(damage_profile or damage)
    damage_path = damage_tsv or root / "results" / f"{source_id}.damage.tsv"
    method_coverage = build_method_coverage(
        query,
        sites,
        selection_loci=sel.get("loci") or [],
        gwas_loci=gwas_loci,
        fstat_query_called_sites=int(fst_pack.get("query_called_sites") or 0),
        gs_pred=breeding.get("gs_pred") or [],
        qc=qc,
        damage_available=damage_available,
        damage_unavailable_reason="damage profile unavailable",
        gs_available=bool(breeding.get("gs_pred")),
        gs_unavailable_reason="no per-sample GS prediction available",
        damage_source_sample_id=source_id,
        damage_path=_workspace_relative_path(root, damage_path),
        damage_path_available=damage_path.exists(),
    )

    merged_note = ""
    if merged_vcf and Path(merged_vcf).exists():
        merged_note = "A merged VCF of the 2449 panel plus this query is in Downloads."

    conclusions = []
    id_file = root / "data" / "panel" / "admixture" / "id_only.txt"
    panel_id_set = {
        ln.strip()
        for ln in id_file.read_text().splitlines()
        if ln.strip()
    } if id_file.exists() else set()
    if sample not in panel_id_set:
        conclusions.append(
            f"{sample} is not in the 2449 reference panel. "
            "The ADMIXTURE bars are the 2449 Q; this sample is projected onto that model."
        )
    if qc:
        panel_cr = qc.get("calling_rate_panel_pct", float("nan"))
        vcf_cr = qc.get("calling_rate_pct", float("nan"))
        conclusions.append(
            f"QC: on-target {_fmt(qc.get('on_target_pct', float('nan')))}% ; "
            f"fold-enrichment {_fmt(qc.get('fold_enrichment', float('nan')))} ; "
            f"covered≥1× {_fmt(qc.get('n_covered_1x', float('nan')), 0)}/"
            f"{_fmt(qc.get('n_panel_sites', float('nan')), 0)} "
            f"({_fmt(qc.get('pct_covered_1x', float('nan')))}%); "
            f"mean depth {_fmt(qc.get('mean_depth', float('nan')), 2)}× ; "
            f"panel calling rate {_fmt(panel_cr)}% "
            f"(called/167k panel; primary); "
            f"VCF-site calling rate {_fmt(vcf_cr)}% "
            f"({_fmt(qc.get('n_called', float('nan')), 0)} called / VCF sites; secondary); "
            f"variants {_fmt(qc.get('n_variant', float('nan')), 0)}."
        )
    panel_gt = method_coverage["panel_genotype"]
    if panel_gt["total"]:
        coverage = panel_gt["coverage"]
        coverage_text = "NA" if coverage is None else f"{coverage * 100:.2f}%"
        conclusions.append(
            f"Query genotype coverage: {panel_gt['called']}/{panel_gt['total']} "
            f"panel sites called ({coverage_text}); missing sites remain missing."
        )
    if query_evidence:
        evidence_called = sum(
            int(row.get("query_gt", -1) in {0, 1, 2}) for row in query_evidence
        )
        conclusions.append(
            f"Query evidence: {evidence_called}/{len(query_evidence)} listed sites "
            "have a called genotype; missing calls are shown explicitly."
        )
    if ibs_schema_error:
        conclusions.append(f"Identity (4K): {ibs_schema_error}")
    elif ibs_relationships:
        from grapeancestry.identity.run_ibs import format_identity_conclusion_from_rows

        conclusions.append(format_identity_conclusion_from_rows(ibs_relationships, sample))
    elif ibs:
        best = ibs[0]
        conclusions.append(
            f"Identity: nearest → {best.ref_id} (score={best.ibs:.3f})."
        )
    q_pcs = pca_coords.get(sample) or list(coords)
    pca_shown = pca_method_label(pca_method)
    if len(q_pcs) >= 3:
        conclusions.append(
            f"{pca_shown}: PC1={q_pcs[0]:.3f}, PC2={q_pcs[1]:.3f}, PC3={q_pcs[2]:.3f}; "
            f"color={color_col}."
        )
    else:
        conclusions.append(
            f"{pca_shown}: PC1={coords[0]:.3f}, PC2={coords[1]:.3f}; "
            f"color={color_col}."
        )
    if admix_contrast:
        store = admix_contrast.q_by_k or admix_contrast.projected_by_k
        k8 = (store.get(8) if store else None) or (store[max(store)] if store else {})
        topk = max(k8, key=k8.get) if k8 else "unavailable"
        # Resolve the displayed component from the selected run family.
        admix_dir_p = admix_dir or (root / "data" / "panel" / "admixture")
        if (
            admix_contrast.run_family
            and 8 in (store or {})
            and str(topk).startswith("K")
        ):
            try:
                labels, _colors, _aliases = component_labels_colors(
                    admix_dir_p,
                    8,
                    run_family=admix_contrast.run_family,
                )
                lab = labels[int(str(topk)[1:]) - 1]
                topk = f"{topk}/{lab}"
            except (ValueError, IndexError):
                pass
        conclusions.append(
            f"ADMIXTURE K=8 on 2449; dominant {topk}."
            + (f" Grp={admix_contrast.grp_value}." if admix_contrast.grp_value else "")
        )
    if tree_obj is not None:
        conclusions.append(
            f"NJ tree: {len(tree_ids)} tips (all panel"
            + ("" if sample in ref_ids else " + query")
            + "; IBS genotype identity; no Grp subsample)."
        )
    library_info = resolve_sample_library_type(
        root, source_sample_id=source_id, query_id=sample
    )
    if library_info["library_class"] == "modern":
        conclusions.append(MODERN_DAMAGE_CONCLUSION)
    elif damage_profile and damage_profile.get("ct5"):
        ct1 = float(damage_profile["ct5"][0])
        ga = damage_profile.get("ga3") or []
        if ga:
            conclusions.append(
                f"Damage: 5′ C→T pos1={ct1:.3f}; 3′ G→A pos1={float(ga[0]):.3f}."
            )
        else:
            conclusions.append(f"Damage 5′ C→T pos1={ct1:.3f}.")
    elif damage:
        conclusions.append(f"Damage 5′ C→T pos1={damage[0]:.3f}.")
    conclusions.append(purity)
    gs_pred = breeding.get("gs_pred") or []
    if gs_pred:
        summary_rows = []
        for row in gs_pred[:4]:
            trait = str(row.get("trait") or "trait")
            pred = row.get("pred")
            cv_r = row.get("cv_r")
            flag = str(row.get("flag") or "")
            bits = [trait]
            if pred not in (None, ""):
                bits.append(f"pred={pred}")
            if cv_r not in (None, ""):
                bits.append(f"cv_r={cv_r}")
            if flag:
                bits.append(f"flag={flag}")
            summary_rows.append(" ".join(bits))
        conclusions.append(
            f"Query GS predictions: {len(gs_pred)} per-query row(s); "
            + "; ".join(summary_rows)
            + "."
        )
    if merged_note:
        conclusions.append(merged_note)
    conclusions = [x for x in (sanitize_conclusion_text(c) for c in conclusions) if x]

    report_meta = build_report_meta(
        root,
        query_id=sample,
        source_sample_id=source_id,
        panel_cache=cache,
        query_vcf=vcf,
        source_bam=root / "results" / "bam" / f"{source_id}.markdup.bam",
        source_damage_tsv=damage_path,
    )

    return ReportBundle(
        sample=sample,
        qc=qc,
        ibs_hits=ibs,
        pca_sample=(float(coords[0]), float(coords[1])),
        ref_pca=ref_pca,
        admix=admix,
        admix_contrast=admix_contrast,
        damage_freqs=damage,
        damage_profile=damage_profile,
        trait_hits=traits,
        fst=fst,
        gea_r=gea_r,
        purity_note=purity,
        conclusions=conclusions,
        pca_coords=pca_coords,
        pca_evals=pca_evals,
        pca_method=pca_method,
        gwas_nlp=gwas_res.get("nlp"),
        gwas_chrom=gwas_res.get("chrom") or [],
        gwas_pos=gwas_res.get("pos") or [],
        gwas_blocks=gwas_res.get("blocks") or [],
        gs=gs_stats,
        coresnp=cores,
        kinship_top=kinship_top,
        ibs_relationships=ibs_relationships[:20],
        ibs_summary=ibs_summary,
        pca_color=color_col,
        merged_vcf_note=merged_note,
        gwas_trait=gwas_trait,
        gwas_index=breeding["gwas_index"],
        gwas_figs=breeding["gwas_figs"],
        gwas_loci=breeding.get("gwas_loci") or [],
        gs_index=breeding["gs_index"],
        gs_pred=breeding["gs_pred"],
        cross_top=breeding["cross_top"],
        methods_html=breeding["methods_html"],
        gwas_skip=gwas_skip,
        selection_outliers=sel["outliers"],
        selection_het=sel["het"],
        selection_sites=sel["sites"],
        selection_named=sel.get("named") or [],
        selection_by_grp=sel.get("by_grp") or [],
        selection_vs_science=sel.get("science") or [],
        selection_vs_summary=sel.get("vs_summary") or [],
        selection_loci=sel.get("loci") or [],
        selection_manhattan=sel.get("manhattan") or {},
        selection_heatmap=sel.get("heatmap") or {},
        selection_s29_scatter=sel.get("s29_scatter") or {},
        selection_fst_het_scatter=sel.get("fst_het_scatter") or {},
        f3_rows=fst_pack.get("f3") or [],
        f4_rows=fst_pack.get("f4") or [],
        f3_out_rows=fst_pack.get("f3_out") or [],
        fstat_pop=str(fst_pack.get("fstat_pop") or "Grp"),
        fstat_query_called_sites=int(fst_pack.get("query_called_sites") or 0),
        outgroup_n=int(fst_pack.get("outgroup_n") or 0),
        tree_ids=tree_ids,
        tree_obj=tree_obj,
        clone_hits=clone_hits[:50],
        tip_groups=tip_groups,
        source_sample_id=source_id,
        report_meta=report_meta,
        query_evidence=query_evidence,
        method_coverage=method_coverage,
    )


def _plot_pca(bundle: ReportBundle) -> str:
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    order = list(REPORT_GRP_ORDER)
    suite_root = Path(__file__).resolve().parents[3]
    grp_colors = load_grp_colors(suite_root / "data" / "panel" / "grp_colors.tsv")
    present = {g for *_a, g in bundle.ref_pca if g}
    bg = {"C-Ad", "W-Ad", "OUT"}
    grps = [g for g in order if g in present and g in bg] + [
        g for g in order if g in present and g not in bg
    ] + sorted(present - set(order))
    cmap = plt.get_cmap("tab20")
    for i, g in enumerate(grps):
        pts = [(x, y) for _id, x, y, gg in bundle.ref_pca if gg == g]
        if not pts:
            continue
        xs, ys = zip(*pts)
        color = grp_colors.get(g) if bundle.pca_color == "Grp" else cmap(i % 20)
        is_bg = g in bg
        is_wild = g.startswith("WWE") or g.startswith("WEE")
        ax.scatter(
            xs,
            ys,
            s=10 if is_bg else 14,
            alpha=0.4 if is_bg else 0.75,
            color=color,
            label=g,
            linewidths=0.3 if is_bg else 0,
            edgecolors="#999" if is_bg else color,
            marker="s" if is_wild else "o",
            zorder=1 if is_bg else 2,
        )
    ax.scatter(
        [bundle.pca_sample[0]],
        [bundle.pca_sample[1]],
        s=140,
        c="black",
        marker="*",
        zorder=5,
        label=f"{bundle.sample} (query)",
    )
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title(f"{pca_method_label(bundle.pca_method)} · color={bundle.pca_color}")
    from grapeancestry.adna.pca_lock import pca_focus_range

    xs = [x for _i, x, _y, _g in bundle.ref_pca]
    ys = [y for _i, _x, y, _g in bundle.ref_pca]
    xr = pca_focus_range(np.asarray(xs, float), extra=np.array([bundle.pca_sample[0]]))
    yr = pca_focus_range(np.asarray(ys, float), extra=np.array([bundle.pca_sample[1]]))
    if xr:
        ax.set_xlim(*xr)
    if yr:
        ax.set_ylim(*yr)
    ax.legend(fontsize=6, loc="best", frameon=False, ncol=2, title=bundle.pca_color)
    return _fig_b64()


def _plot_ibs(bundle: ReportBundle) -> str:
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    if bundle.ibs_relationships:
        rows = bundle.ibs_relationships[:10][::-1]
        names = [r.get("ref", "") for r in rows]
        vals = []
        for r in rows:
            try:
                vals.append(float(r.get("KING_Robust") or 0))
            except ValueError:
                vals.append(0.0)
        ax.barh(names, vals, color="#2f5d3a")
        ax.axvline(0.3426, color="#b33", ls="--", lw=1, label="Identical KING≥0.3426")
        ax.axvline(0.21, color="#c47a00", ls=":", lw=1, label="PO KING≥0.21")
        ax.set_xlabel("KING_Robust")
        ax.set_title("Top pairs (4K: Identical + PO)")
    else:
        names = [h.ref_id for h in bundle.ibs_hits][::-1]
        vals = [h.ibs for h in bundle.ibs_hits][::-1]
        ax.barh(names, vals, color="#2f5d3a")
        ax.set_xlabel("score")
        ax.set_title("Nearest neighbors")
    ax.legend(fontsize=8, frameon=False)
    return _fig_b64()


def _plot_admix(bundle: ReportBundle) -> str | None:
    """K=2..8 stacked bars: lookup / projected / Grp mean / panel mean."""
    c = bundle.admix_contrast
    if not c:
        return None
    ks = sorted(set(c.q_by_k) | set(c.projected_by_k) | set(c.panel_mean_by_k))
    if not ks:
        return None
    suite_root = Path(__file__).resolve().parents[3]
    admix_dir = suite_root / "data" / "panel" / "admixture"
    fallback_colors = list(plt.get_cmap("tab10").colors)
    panels = []
    if c.q_by_k:
        panels.append((c.q_by_k, f"{bundle.sample} lookup"))
    if c.projected_by_k:
        panels.append((c.projected_by_k, f"{bundle.sample} projected"))
    if c.grp_mean_by_k:
        panels.append((c.grp_mean_by_k, f"Grp={c.grp_value or '?'} mean"))
    if c.panel_mean_by_k:
        panels.append((c.panel_mean_by_k, f"panel mean (n={c.n_panel})"))
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(3.1 * n, 3.6), sharey=True)
    if n == 1:
        axes = [axes]
    for ax, (store, title) in zip(axes, panels):
        for yi, k in enumerate(ks):
            left = 0.0
            comps = store.get(k, {})
            _labels, colors, _aliases = component_labels_colors(
                admix_dir, k, run_family=c.run_family
            )
            order = plot_order_indices(admix_dir, k, run_family=c.run_family)
            keys = [f"K{i + 1}" for i in order]
            for j, key in enumerate(keys):
                color = (
                    colors[order[j]]
                    if order[j] < len(colors) and colors[order[j]]
                    else fallback_colors[j % len(fallback_colors)]
                )
                ax.barh(yi, comps.get(key, 0.0), left=left, color=color, height=0.7)
                left += comps.get(key, 0.0)
        ax.set_yticks(range(len(ks)))
        ax.set_yticklabels([f"K={k}" for k in ks], fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("Q")
    fig.suptitle("ADMIXTURE K=2–8", fontsize=11)
    fig.tight_layout()
    return _fig_b64()


def _plot_admix_structure(bundle: ReportBundle, k: int = 8) -> str | None:
    """Panel structure strip sorted by Grp order (Science / Italy-style). K=8 fixed."""
    c = bundle.admix_contrast
    if not c:
        return None
    suite_root = Path(__file__).resolve().parents[3]
    suite = suite_root / "data" / "panel" / "admixture"
    legacy = suite_root.parent / "stat_vcf_from_3527" / "ADMIXTURE"
    admix_dir = suite if (suite / "science_manifest.json").exists() else legacy
    from grapeancestry.adna.admixture import _q_path

    run_family = display_run_family(admix_dir, c, k, k)
    q_file = _q_path(admix_dir, k, run_family=run_family)
    id_file = id_path_for_family(admix_dir, run_family)
    info = suite_root / "data" / "panel" / "2449.info"
    if not q_file.exists() or not id_file.exists() or not info.exists():
        return None
    ids = [ln.strip() for ln in id_file.read_text().splitlines() if ln.strip()]
    Q = load_admixture_matrix(admix_dir, k, run_family=run_family)
    plot_order = plot_order_indices(admix_dir, k, run_family=run_family)
    Q = Q[:, plot_order]
    meta: dict[str, str] = {}
    with info.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            r = dict(zip(hdr, line.rstrip().split("\t")))
            meta[r["ID"]] = r.get("Grp", "")
    order = list(REPORT_GRP_ORDER)
    rows: list[tuple[str, np.ndarray]] = []
    for g in order:
        idxs = sorted(
            (i for i, s in enumerate(ids) if meta.get(s) == g),
            key=lambda i: ids[i],
        )
        if not idxs:
            continue
        take = idxs if len(idxs) <= 40 else [
            int(i)
            for i in _evenly_spaced_ids([str(i) for i in idxs], 40)
        ]
        for i in take:
            rows.append((g, Q[i]))
    if not rows:
        return None
    qvec = _query_q_vector(c, k, plot_order, strip_family=run_family)
    if qvec is not None:
        fig, (ax, axq) = plt.subplots(
            1,
            2,
            figsize=(13.2, 3.2),
            gridspec_kw={"width_ratios": [14.0, 0.62], "wspace": 0.08},
            layout="constrained",
        )
    else:
        fig, ax = plt.subplots(figsize=(10.2, 2.8), layout="constrained")
        axq = None
    labels, colors, _aliases = component_labels_colors(
        admix_dir, k, run_family=run_family
    )
    labels = [labels[i] for i in plot_order]
    colors = [colors[i] for i in plot_order]
    if not any(colors):
        colors = [
            "#E41A1C",
            "#377EB8",
            "#4DAF4A",
            "#984EA3",
            "#FF7F00",
            "#A65628",
            "#F781BF",
            "#66C2A5",
        ]
    for x, (_g, qrow) in enumerate(rows):
        left = 0.0
        for j, v in enumerate(qrow):
            ax.bar(x, v, bottom=left, width=1.0, color=colors[j % len(colors)], linewidth=0)
            left += float(v)
    if bundle.sample in ids:
        g0 = meta.get(bundle.sample, "")
        pos = [i for i, (g, _) in enumerate(rows) if g == g0]
        if pos:
            ax.axvline(pos[len(pos) // 2], color="black", lw=1.2, ls="--", label=bundle.sample)
            ax.legend(fontsize=7, frameon=False, loc="upper right")
    ax.set_ylim(0, 1)
    ax.set_xlim(-0.5, len(rows) - 0.5)
    ax.set_ylabel(f"K={k} Q · Science components")
    ax.set_title(
        f"2449 structure (≤40/group) · {' / '.join(labels)}"
        + (f" · right = {bundle.sample}" if qvec is not None else "")
    )
    seen: set[str] = set()
    tick_pos, tick_lab = [], []
    for i, (g, _) in enumerate(rows):
        if g not in seen:
            seen.add(g)
            tick_pos.append(i)
            tick_lab.append(g)
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_lab, fontsize=7, rotation=45, ha="right")
    if axq is not None and qvec is not None:
        left = 0.0
        for j, v in enumerate(qvec):
            axq.bar(
                0,
                float(v),
                bottom=left,
                width=0.92,
                color=colors[j % len(colors)],
                edgecolor="black",
                linewidth=0.6,
            )
            left += float(v)
        axq.set_ylim(0, 1)
        axq.set_xlim(-0.6, 0.6)
        axq.set_xticks([0])
        axq.set_xticklabels([bundle.sample], fontsize=8, rotation=90)
        axq.set_yticks([])
        axq.set_title("query", fontsize=9)
    return _fig_b64()


def _hex_to_rgb(color: str) -> np.ndarray:
    h = (color or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) < 6:
        h = "888888"
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=float) / 255.0


QUERY_STRIP_GAP = 12
QUERY_STRIP_WIDTH = 48


def _query_q_vector(
    contrast: AdmixtureContrast | None,
    k: int,
    plot_order: list[int],
    *,
    strip_family: str,
) -> np.ndarray | None:
    """Q on the same family as the 2449 strip. Lookup first; projected only if same family.

    Chip-P Q is a different coordinate system and must not be painted with
    Science / panel167k strip colours (Dong et al. 2023 doi:10.1126/science.add8655 Fig. 1D).
    """
    if contrast is None:
        return None
    store = contrast.q_by_k
    same_strip = contrast.run_family == strip_family or (
        strip_family == SCIENCE_RUN_FAMILY
        and contrast.run_family in {SCIENCE_RUN_FAMILY, "science"}
    )
    if not store and same_strip:
        store = contrast.projected_by_k
    row = store.get(k) if store else None
    if not row:
        return None
    vec = np.array([float(row.get(f"K{i + 1}", 0.0)) for i in range(k)], dtype=float)
    if vec.shape[0] != k or not np.isfinite(vec).all():
        return None
    order = [int(i) for i in plot_order]
    if sorted(order) != list(range(k)):
        return vec
    return vec[np.asarray(order, dtype=int)]


def _append_query_strip(
    img: np.ndarray,
    qrow: np.ndarray,
    colors: list[str],
    *,
    gap: int = QUERY_STRIP_GAP,
    width: int = QUERY_STRIP_WIDTH,
) -> np.ndarray:
    """White gap + a fat query column so one sample is visible next to 2449 people."""
    height = int(img.shape[0])
    gap_img = np.ones((height, max(1, int(gap)), 3))
    q_one = _q_strip_image(np.asarray(qrow, float).reshape(1, -1), colors, height=height)
    q_img = np.repeat(q_one, max(1, int(width)), axis=1)
    return np.concatenate([img, gap_img, q_img], axis=1)


def _q_strip_image(
    q: np.ndarray,
    colors: list[str],
    height: int = 36,
    cell_hex: list[list[str]] | None = None,
) -> np.ndarray:
    """One ADMIXTURE row as an RGB image (samples × stacked colours)."""
    n, k = q.shape
    rgb = np.stack(
        [_hex_to_rgb(colors[j] if j < len(colors) else "#888888") for j in range(k)]
    )
    img = np.ones((height, n, 3))
    for i in range(n):
        frac = np.clip(np.asarray(q[i], float), 0.0, 1.0)
        total = float(frac.sum())
        if total <= 0:
            continue
        frac = frac / total
        edges = np.round(np.cumsum(frac) * height).astype(int)
        y0 = 0
        row_hex = cell_hex[i] if cell_hex is not None and i < len(cell_hex) else None
        for j, y1 in enumerate(edges):
            if y1 > y0:
                if row_hex is not None and j < len(row_hex):
                    img[y0:y1, i] = _hex_to_rgb(row_hex[j])
                else:
                    img[y0:y1, i] = rgb[j]
            y0 = max(y0, y1)
    return img


def _plot_admix_k2_8(bundle: ReportBundle) -> str | None:
    """Science-style K=2..8 strips, same sample order, K=8 colours."""
    c = bundle.admix_contrast
    if not c:
        return None
    suite_root = Path(__file__).resolve().parents[3]
    admix_dir = suite_root / "data" / "panel" / "admixture"
    info_path = suite_root / "data" / "panel" / "2449.info"
    run_family = display_run_family(admix_dir, c, 2, 8)
    id_file = id_path_for_family(admix_dir, run_family)
    if not id_file.exists() or not info_path.exists():
        return None
    ids = [ln.strip() for ln in id_file.read_text().splitlines() if ln.strip()]
    meta: dict[str, str] = {}
    with info_path.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            r = dict(zip(hdr, line.rstrip().split("\t")))
            meta[r["ID"]] = r.get("Grp", "")
    col_index: list[int] = []
    groups: list[tuple[str, int]] = []
    for g in REPORT_GRP_ORDER:
        idxs = sorted(
            (i for i, s in enumerate(ids) if meta.get(s) == g),
            key=lambda i: ids[i],
        )
        if not idxs:
            continue
        groups.append((g, len(idxs)))
        col_index.extend(idxs)
    if not col_index:
        return None
    n = len(col_index)
    q_by_k: dict[int, np.ndarray] = {}
    for k in range(2, 9):
        order_k = plot_order_indices(admix_dir, k, run_family=run_family)
        qrow = _query_q_vector(c, k, order_k, strip_family=run_family)
        if qrow is not None:
            q_by_k[k] = qrow
    show_query = bool(q_by_k)
    fig = plt.figure(figsize=(18.6, 10.4))
    gs = fig.add_gridspec(
        7,
        2 if show_query else 1,
        width_ratios=[16.0, 0.62] if show_query else [1.0],
        wspace=0.05,
        hspace=0.07,
        left=0.07,
        right=0.99,
        top=0.88,
        bottom=0.13,
    )
    panel_axes: list = []
    query_pos = None
    if bundle.sample in ids:
        qi = ids.index(bundle.sample)
        if qi in col_index:
            query_pos = col_index.index(qi)
    for i, k in enumerate(range(2, 9)):
        ax = fig.add_subplot(gs[i, 0])
        panel_axes.append(ax)
        Q = load_admixture_matrix(admix_dir, k, run_family=run_family)
        order = plot_order_indices(admix_dir, k, run_family=run_family)
        Q = Q[:, order][col_index]
        _labels, colors, _a = component_labels_colors(
            admix_dir, k, run_family=run_family
        )
        colors = [colors[j] for j in order] if colors else ["#888888"] * k
        img = _q_strip_image(Q, colors, height=52)
        ax.imshow(img, aspect="auto", interpolation="nearest", origin="upper")
        ax.set_ylabel(f"K={k}", rotation=0, ha="right", va="center", fontsize=9)
        ax.set_yticks([])
        x0 = 0
        for gi, (_g, count) in enumerate(groups):
            if gi:
                ax.axvline(x0 - 0.5, color="white", lw=0.5)
            x0 += count
        if (not show_query) and query_pos is not None:
            ax.axvline(query_pos, color="black", lw=0.8, ls="--")
        ax.set_xlim(-0.5, n - 0.5)
        ax.tick_params(axis="x", bottom=False, labelbottom=False)
        if show_query:
            axq = fig.add_subplot(gs[i, 1])
            qrow = q_by_k.get(k)
            if qrow is not None:
                q_img = _q_strip_image(np.asarray(qrow, float).reshape(1, -1), colors, height=52)
                axq.imshow(q_img, aspect="auto", interpolation="nearest", origin="upper")
            axq.set_yticks([])
            axq.set_xticks([])
            for spine in axq.spines.values():
                spine.set_color("black")
                spine.set_linewidth(0.9)
            if k == 8:
                axq.set_xticks([0])
                axq.set_xticklabels(
                    [bundle.sample], fontsize=7, rotation=90, ha="center", va="top"
                )
    ticks, tick_lab = [], []
    x0 = 0
    for g, count in groups:
        ticks.append(x0 + count / 2.0)
        tick_lab.append(f"{g}\n(n={count})")
        x0 += count
    panel_axes[-1].tick_params(axis="x", bottom=True, labelbottom=True)
    panel_axes[-1].set_xticks(ticks)
    panel_axes[-1].set_xticklabels(tick_lab, fontsize=7)
    if run_family == PANEL167K_NOGWAS_FAMILY:
        legend_colors = COMPONENT_COLORS[:8]
        legend_labels = [f"C{i + 1}" for i in range(8)]
    else:
        legend_colors = SCIENCE_K8_COLORS
        legend_labels = SCIENCE_K8_LEGEND_LABELS
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=legend_colors[i])
        for i in range(8)
    ]
    fig.legend(
        handles,
        legend_labels,
        loc="upper center",
        ncol=8,
        fontsize=7,
        frameon=False,
        bbox_to_anchor=(0.5, 1.02),
    )
    fig.suptitle(
        f"ADMIXTURE K=2–8 · n={n} · query={bundle.sample}"
        + ("  (right column = query)" if show_query else ""),
        fontsize=11,
        y=0.995,
    )
    return _fig_b64()


def _plot_damage(bundle: ReportBundle) -> str | None:
    prof = getattr(bundle, "damage_profile", None) or {}
    ct5 = list(prof.get("ct5") or bundle.damage_freqs or [])
    ga3 = list(prof.get("ga3") or [])
    if not ct5 and not ga3:
        return None
    subs5 = prof.get("subs5") or {}
    subs3 = prof.get("subs3") or {}
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.1), sharey=True)
    ymax = 0.05
    for seq in list(subs5.values()) + list(subs3.values()) + [ct5, ga3]:
        if seq:
            ymax = max(ymax, max(seq) * 1.15)
    ymax = min(max(ymax, 0.08), 0.5)

    def _panel(ax, subs: dict, hero: str, hero_y: list[float], color: str, xlabel: str) -> None:
        xs_n = len(hero_y) or 25
        for name, ys in subs.items():
            if name == hero or not ys:
                continue
            ax.plot(range(1, len(ys) + 1), ys, color="#9aa4b2", lw=0.8, alpha=0.85)
        if hero_y:
            ax.plot(range(1, len(hero_y) + 1), hero_y, color=color, lw=2.2, label=hero)
        ax.set_xlabel(xlabel)
        ax.set_xlim(1, xs_n)
        ax.set_ylim(0, ymax)
        ax.legend(frameon=False, fontsize=8, loc="upper right")

    _panel(axes[0], subs5, "C>T", ct5, "#c0392b", "Position from 5′")
    axes[1].set_xlim(1, len(ga3) or 25)
    _panel(axes[1], subs3, "G>A", ga3, "#2471a3", "Position from 3′")
    axes[1].invert_xaxis()
    axes[0].set_ylabel("Frequency")
    fig.suptitle("mapDamage misincorporation", fontsize=11, y=1.02)
    fig.tight_layout()
    return _fig_b64()


def _plot_qc(bundle: ReportBundle) -> str | None:
    if not bundle.qc:
        return None
    # Compact panel: coverage + depth + calling
    labels = [
        "Covered≥1× %",
        "Covered≥5× %",
        "Mean depth",
        "Call rate %",
        "Variant %",
    ]
    vals = [
        bundle.qc.get("pct_covered_1x", bundle.qc.get("breadth_1x", 0) * 100),
        bundle.qc.get("pct_covered_5x", bundle.qc.get("breadth_5x", 0) * 100),
        bundle.qc.get("mean_depth", 0),
        bundle.qc.get("calling_rate_pct", bundle.qc.get("calling_rate", 0) * 100),
        100.0 * bundle.qc.get("variant_rate", 0),
    ]
    fig, ax = plt.subplots(figsize=(6.2, 2.8))
    ax.bar(labels, vals, color=["#2f5d3a", "#4a7c59", "#6b8f71", "#8b7355", "#a3b18a"])
    ax.set_ylabel("% or depth (×)")
    ax.set_title("Capture / calling QC")
    ax.tick_params(axis="x", labelsize=8, rotation=15)
    return _fig_b64()


def _plot_manhattan(bundle: ReportBundle) -> str | None:
    """Embed the first available precomputed Manhattan PNG."""
    for _k, (man, _qq) in bundle.gwas_figs.items():
        if man:
            return man
    if bundle.gwas_nlp is None:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    chroms = sorted(set(bundle.gwas_chrom), key=lambda c: (len(c), c))
    x = 0
    ticks, ticklabels = [], []
    colors = ["#2f5d3a", "#8b7355"]
    for i, c in enumerate(chroms):
        idx = [j for j, cc in enumerate(bundle.gwas_chrom) if cc == c]
        xs = np.arange(len(idx)) + x
        ys = bundle.gwas_nlp[idx]
        ax.scatter(xs, ys, s=4, c=colors[i % 2], alpha=0.7)
        ticks.append(x + len(idx) / 2)
        ticklabels.append(c)
        x += len(idx)
    ax.set_xticks(ticks)
    ax.set_xticklabels(ticklabels, fontsize=6, rotation=90)
    ax.set_ylabel("-log10 p")
    ax.set_title(f"GWAS Manhattan ({bundle.gwas_trait})")
    return _fig_b64()


def _plot_selection(bundle: ReportBundle) -> str | None:
    if bundle.selection_het is None or not len(bundle.selection_sites):
        return None
    het = bundle.selection_het
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    ax.plot(np.arange(len(het)), het, color="#5e6a6e", lw=0.8, alpha=0.85)
    if bundle.selection_outliers:
        idxs = []
        for o in bundle.selection_outliers:
            try:
                idxs.append(bundle.selection_sites.index(o["site"]))
            except ValueError:
                continue
        if idxs:
            ax.scatter(idxs, [het[i] for i in idxs], s=18, c="#dc1f26", zorder=3, label="low-het outliers")
            ax.legend(fontsize=7, frameon=False)
    ax.set_xlabel("Site index")
    ax.set_ylabel("Windowed het (±50 kb)")
    ax.set_title("Windowed heterozygosity (unphased; not XP-CLR/iHS)")
    return _fig_b64()


def _plot_fstats(bundle: ReportBundle) -> str | None:
    f3_out = getattr(bundle, "f3_out_rows", None) or []
    f4 = (bundle.f4_rows or [])[:15]
    f3 = (bundle.f3_rows or [])[:15]
    if not f3_out and not f4 and not f3:
        return None
    n_aff = max(len(f3_out), 1)
    fig_h = max(3.2, 0.32 * n_aff + 1.2)
    if f4:
        fig, axes = plt.subplots(1, 2, figsize=(11.2, fig_h), gridspec_kw={"width_ratios": [1.15, 1]})
        ax0, ax1 = axes
    else:
        fig, ax0 = plt.subplots(figsize=(6.4, fig_h))
        ax1 = None
    rows = f3_out or f3
    labels = [r.get("grp") or r["label"] for r in rows]
    vals = [float(r["value"]) for r in rows]
    ses = []
    for r in rows:
        se = r.get("se")
        try:
            x = float(se)
        except (TypeError, ValueError):
            x = 0.0
        ses.append(0.0 if x != x else x)
    order = np.argsort(vals)
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    ses = [ses[i] for i in order]
    y = np.arange(len(vals))
    ax0.barh(y, vals, xerr=ses, color="#1d4ed8", ecolor="#94a3b8", capsize=2, height=0.62)
    ax0.axvline(0, color="#333", lw=0.7)
    ax0.set_yticks(y)
    ax0.set_yticklabels(labels, fontsize=8)
    ax0.set_xlabel("f3(OUT; Q, Grp)" if f3_out else "f3")
    ax0.set_title("Outgroup-f3  ·  higher = closer to query", fontsize=9)
    if ax1 is not None:
        labs = [f"{r.get('a')} vs {r.get('b')}" for r in f4]
        vals4 = [float(r["value"]) for r in f4]
        se4 = []
        for r in f4:
            try:
                x = float(r.get("se"))
            except (TypeError, ValueError):
                x = 0.0
            se4.append(0.0 if x != x else x)
        order4 = np.argsort(vals4)
        labs = [labs[i] for i in order4]
        vals4 = [vals4[i] for i in order4]
        se4 = [se4[i] for i in order4]
        y1 = np.arange(len(vals4))
        ax1.barh(y1, vals4, xerr=se4, color="#b2182b", ecolor="#94a3b8", capsize=2, height=0.62)
        ax1.axvline(0, color="#333", lw=0.7)
        ax1.set_yticks(y1)
        ax1.set_yticklabels(labs, fontsize=7)
        ax1.set_xlabel("f4(Q, OUT; A, B)")
        ax1.set_title("Pairwise f4", fontsize=9)
    fig.suptitle(
        "Grp-mean exploratory f-stats  ·  whiskers = chromosome-block jackknife SE",
        fontsize=10,
    )
    fig.tight_layout()
    return _fig_b64()


def _plot_tree(bundle: ReportBundle) -> str | None:
    if bundle.tree_obj is None:
        return None
    from grapeancestry.popgen.tree_nj import tip_xy_rectangular, tree_edges_rectangular

    tree = bundle.tree_obj
    segs = tree_edges_rectangular(tree)
    tips = tip_xy_rectangular(tree)
    suite_root = Path(__file__).resolve().parents[3]
    grp_colors = load_grp_colors(suite_root / "data" / "panel" / "grp_colors.tsv")
    n_tips = len(tips)
    fig_h = max(6.0, min(0.026 * n_tips, 40.0))
    fig, ax = plt.subplots(figsize=(8.2, fig_h))
    lw = 0.25 if n_tips > 200 else 0.8
    ms = 3 if n_tips > 200 else 12
    from matplotlib.collections import LineCollection

    ax.add_collection(
        LineCollection(
            [((x0, y0), (x1, y1)) for x0, y0, x1, y1 in segs],
            colors="#888888",
            linewidths=lw,
        )
    )
    from collections import defaultdict

    by_g: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    q_xy = None
    for tid, (x, y) in tips.items():
        if tid == bundle.sample:
            q_xy = (tid, x, y)
            continue
        by_g[bundle.tip_groups.get(tid, "")].append((tid, x, y))
    for g, pts in by_g.items():
        xs = [p[1] for p in pts]
        ys = [p[2] for p in pts]
        ax.scatter(xs, ys, s=ms, c=grp_colors.get(g, "#555"), zorder=3, marker="o", linewidths=0)
    if q_xy is not None:
        tid, x, y = q_xy
        ax.scatter([x], [y], s=70, c="#000", zorder=4, marker="*")
        ax.text(x + 0.002, y, tid, fontsize=8, fontweight="bold", va="center")
    ax.set_yticks([])
    ax.set_xlabel("IBS distance (NJ)")
    ax.set_title(f"NJ tree · {n_tips} tips (all panel) · query={bundle.sample} ★")
    ax.autoscale()
    return _fig_b64()


def render_full_html(bundle: ReportBundle, out_html: Path) -> Path:
    """Write interactive Plotly dashboard (Italy click/highlight logic) + keep PNG exports."""
    from grapeancestry.report.interactive_dashboard import render_interactive_dashboard

    pca_img = _plot_pca(bundle)
    admix_k28_img = _plot_admix_k2_8(bundle)
    admix_str_img = _plot_admix_structure(bundle, k=8)
    admix_img = _plot_admix(bundle)
    tree_img = _plot_tree(bundle)
    sel_img = _plot_selection(bundle)
    fstats_img = _plot_fstats(bundle)

    stem = bundle.sample
    out_dir = out_html.parent
    _save_b64_png(pca_img, out_dir / f"{stem}.pca.png")
    _save_b64_png(admix_k28_img, out_dir / f"{stem}.admixture_k2_8.png")
    _save_b64_png(admix_str_img or admix_img, out_dir / f"{stem}.admixture.png")
    _save_b64_png(tree_img, out_dir / f"{stem}.nj_tree.png")
    _save_b64_png(sel_img, out_dir / f"{stem}.selection.png")
    _save_b64_png(fstats_img, out_dir / f"{stem}.fstats.png")

    root = Path(__file__).resolve().parents[3]
    # Prefer suite root from out path if under results/
    if (out_dir.parent / "data" / "panel").exists():
        root = out_dir.parent
    return render_interactive_dashboard(bundle, out_html, root)


def write_admix_k28_report(
    sample: str,
    root: Path,
    out_html: Path,
    contrast: AdmixtureContrast,
) -> Path:
    """K=2–8 HTML + strip PNG without requiring PCA/IBS cache."""
    store = contrast.q_by_k or contrast.projected_by_k
    conclusions = []
    if contrast.run_family == "legacy_chip" and contrast.projected_by_k:
        conclusions.append(
            "The 2449 strip uses Science names and colours (Dong et al. 2023 "
            "doi:10.1126/science.add8655 Fig. 1D)."
        )
    kinship_top: list[dict] = []
    kin_path = root / "results" / f"{sample}.kinship_top.tsv"
    if kin_path.exists():
        with kin_path.open() as fh:
            kinship_top = list(csv.DictReader(fh, delimiter="\t"))[:10]
    ibs_summary: dict[str, int] = {}
    sum_path = root / "results" / f"{sample}.ibs_summary.tsv"
    if sum_path.exists():
        with sum_path.open() as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                try:
                    ibs_summary[row["relationship"]] = int(row["count"])
                except (KeyError, ValueError, TypeError):
                    continue
    bundle = ReportBundle(
        sample=sample,
        qc={},
        ibs_hits=[],
        pca_sample=(float("nan"), float("nan")),
        ref_pca=[],
        admix=store.get(8) if store else None,
        admix_contrast=contrast,
        damage_freqs=None,
        trait_hits=[],
        fst=None,
        gea_r=None,
        purity_note="",
        conclusions=conclusions,
        pca_method="not run (ADMIXTURE-only report)",
        kinship_top=kinship_top,
        ibs_summary=ibs_summary,
    )
    return render_full_html(bundle, out_html)
