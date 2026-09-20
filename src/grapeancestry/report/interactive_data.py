"""Build Plotly.js-ready JSON payload for interactive dashboard.

Mirrors Italy grouping_663/dashboard_src/data_plots.py form:
PCA scatter + ADMIXTURE bar + NJ tips, all with customdata=IID for click→highlight.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from grapeancestry.adna.admixture import (
    SCIENCE_RUN_FAMILY,
    admixture_methods_text,
    component_labels_colors,
    component_metadata,
    display_run_family,
    id_path_for_family,
    load_admixture_matrix,
    load_panel167k_manifest,
    load_science_manifest,
    plot_order_indices,
)
from grapeancestry.adna.panel167k_nogwas import PANEL167K_NOGWAS_FAMILY
from grapeancestry.breeding.methods_doc import sanitize_methods_html
from grapeancestry.adna.grp_order import REPORT_GRP_ORDER, order_ids_by_group
from grapeancestry.popgen.tree_nj import (
    tip_xy_circular,
    tip_xy_rectangular,
    tree_edges_circular,
    tree_edges_rectangular,
)
from grapeancestry.report.build_report import (
    ReportBundle,
    build_method_coverage,
    load_grp_colors,
    pca_method_label,
)

SET1 = ["#E41A1C", "#377EB8", "#4DAF4A", "#984EA3", "#FF7F00", "#A65628", "#F781BF", "#66C2A5"]

# Light paper layout so Science #E0E0E0 / CG5 yellow remain visible (3k figures are white-bg)
_SCIENCE_LAYOUT = {
    "paper_bgcolor": "#ffffff",
    "plot_bgcolor": "#ffffff",
    "font": {"color": "#1a1a1a", "size": 11},
    "xaxis": {"gridcolor": "#e5e5e5", "zerolinecolor": "#cccccc", "color": "#1a1a1a"},
    "yaxis": {"gridcolor": "#e5e5e5", "zerolinecolor": "#cccccc", "color": "#1a1a1a"},
}


# Query-only sidecars. No panel dump, no report JSON, no full IBS-vs-2449 matrix.
_QUERY_DOWNLOAD_REST = re.compile(
    r"^(qc|damage|pca|ibs_clone_hits|ibs_summary|kinship_top|admix\.K[2-8]\.Q)\.tsv$"
)


def _is_query_download(sample: str, href: str) -> bool:
    name = str(href or "").replace("\\", "/").split("/")[-1]
    if not sample or ".." in str(href) or "/" in str(href).replace("\\", "/"):
        return False
    prefix = f"{sample}."
    if not name.startswith(prefix):
        return False
    rest = name[len(prefix) :]
    if re.search(r"panel|2449|dosage|nogwas|manual|\.json$", rest, re.I):
        return False
    return bool(_QUERY_DOWNLOAD_REST.match(rest))


def _load_info(info_path: Path) -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    if not info_path.exists():
        return meta
    with info_path.open() as fh:
        hdr: list[str] | None = None
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = parts
                continue
            row = dict(zip(hdr, parts))
            sid = row.get("ID") or row.get("analysis_IID") or ""
            if sid:
                meta[sid] = row
    return meta


_ITALY_3057 = Path(
    "/Users/lixuzhen/Desktop/script/00_italy_2center"
    "/Final_ana_3057_adna/final_3057_sample.info"
)


def _load_dong_passport(root: Path) -> dict[str, dict[str, str]]:
    """2449-keyed names from Italy final_3057_sample.info (not 663 Library ID)."""
    local = root / "data" / "panel" / "dong_passport.tsv"
    if local.exists():
        return _load_info(local)
    if _ITALY_3057.exists():
        return _load_info(_ITALY_3057)
    return {}


_PASSPORT_KEYS = (
    "acc",
    "acc_local",
    "vivc",
    "con",
    "wild",
    "geo",
    "uti",
    "sex",
    "color",
    "muscat",
    "grp_info",
    "origin",
    "taxon",
    "contributor",
    "po",
    "comments",
    "clone_of",
    "passport_from",
)


def _nz(*vals: str) -> str:
    for v in vals:
        s = (v or "").strip()
        if s:
            return s
    return ""


def sample_passport(
    sid: str,
    info: dict[str, dict[str, str]],
    annot: dict[str, dict[str, str]],
    dong: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """Join 2449.info + Italy Dong passport + sample_annot.tsv by exact ID only.

    Primary names: ``dong_passport.tsv`` / ``final_3057_sample.info`` keyed by
    analysis_IID (Dong 2449 IDs). Do **not** join Italy ``sample_enriched.info``
    by Library ID — that table is the 663 Italian sheet (ID 1 = Ottavia).
    Do **not** strip ``_query`` and look up the stem: ``HUN89_query`` is an
    independent chip call (FASTQ ``HUN89-1-ywk``), not 2449 ID ``HUN89``.
    It has no 2449.info / VIVC row under that name. Missing cells stay empty.
    """
    dong = dong or {}
    info_row = info.get(sid) or {}
    annot_row = annot.get(sid) or {}
    dong_row = dong.get(sid) or {}
    in_3057 = bool(dong_row) and not (dong_row.get("clone_of") or "").strip()
    dong_name = _nz(dong_row.get("VIVC_Prime_Name", ""), dong_row.get("VIVC Prime Name", ""))
    dong_acc = _nz(dong_row.get("Accession_Name", ""), dong_row.get("Accession Name", ""))
    annot_name = _nz(annot_row.get("vivc_prime_name", ""))
    if in_3057:
        acc = _nz(dong_name, dong_acc, annot_name)
        acc_local = dong_acc
        if acc and acc_local.upper() == acc.upper():
            acc_local = ""
    else:
        acc = _nz(annot_name, dong_name, dong_acc)
        acc_local = dong_acc
        if acc and acc_local.upper() == acc.upper():
            acc_local = ""
    return {
        "acc": acc,
        "acc_local": acc_local,
        "vivc": _nz(dong_row.get("VIVC_Number", ""), annot_row.get("vivc_number", "")),
        "con": _nz(info_row.get("CON", "")),
        "wild": _nz(info_row.get("Wild", "")),
        "geo": _nz(info_row.get("GEO", "")),
        "uti": _nz(info_row.get("Uti", ""), dong_row.get("Utilization", "")),
        "sex": _nz(dong_row.get("Flower_Sex", ""), annot_row.get("vivc_flower_sex", "")),
        "color": _nz(annot_row.get("berry_skin_color_text", ""), dong_row.get("Color", "")),
        "muscat": _nz(dong_row.get("Muscat_Taste", ""), annot_row.get("vivc_muscat", "")),
        "grp_info": _nz(info_row.get("Grp", ""), dong_row.get("Dong_Grp", "")),
        "origin": _nz(dong_row.get("Origin", "")),
        "taxon": _nz(dong_row.get("Genetic_Background", "")),
        "contributor": _nz(dong_row.get("Sample_Contributor", "")),
        "po": _nz(dong_row.get("PO_partners", "")),
        "comments": _nz(dong_row.get("Comments", "")),
        "clone_of": _nz(dong_row.get("clone_of", "")),
        "passport_from": "",
    }


def apply_passport_fields(row: dict, pp: dict[str, str]) -> dict:
    for key in _PASSPORT_KEYS:
        row[key] = pp.get(key, "")
    return row


def apply_passport_to_payload(payload: dict, root: Path) -> dict:
    """Patch srows + query_meta on an existing report JSON (no ADMIXTURE refit)."""
    info = _load_info(root / "data" / "panel" / "2449.info")
    annot = _load_info(root / "data" / "panel" / "sample_annot.tsv")
    dong = _load_dong_passport(root)
    for row in payload.get("srows") or []:
        apply_passport_fields(row, sample_passport(str(row.get("iid") or ""), info, annot, dong))
    qid = str(payload.get("query") or "")
    pp = sample_passport(qid, info, annot, dong)
    qm = payload.setdefault("query_meta", {})
    qm["name"] = pp["acc"]
    qm["acc_local"] = pp["acc_local"]
    qm["vivc"] = pp["vivc"]
    qm["con"] = pp["con"]
    qm["wild"] = pp["wild"]
    qm["geo"] = pp["geo"]
    qm["uti"] = pp["uti"]
    qm["sex"] = pp["sex"]
    qm["color"] = pp["color"]
    qm["muscat"] = pp["muscat"]
    qm["origin"] = pp["origin"]
    qm["taxon"] = pp["taxon"]
    qm["contributor"] = pp["contributor"]
    qm["po"] = pp["po"]
    qm["comments"] = pp["comments"]
    qm["clone_of"] = pp["clone_of"]
    qm["passport_from"] = pp["passport_from"]
    # Dong Grp only if this exact ID is in 2449.info. Never keep a stale CG*.
    qm["grp"] = pp["grp_info"]
    return payload


def _panel_site_keys(root: Path) -> list[str]:
    path = root / "data" / "panel" / "locus_annot.tsv"
    if not path.exists():
        return []
    keys: list[str] = []
    with path.open() as fh:
        hdr = next(fh, "")
        cols = hdr.rstrip("\n").split("\t")
        idx = cols.index("site") if "site" in cols else 4
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) > idx and parts[idx]:
                keys.append(parts[idx])
            elif len(parts) >= 2:
                keys.append(f"{parts[0]}:{parts[1]}")
    return keys


def _enrich_site_row(row: dict, genes, features, mas_site, mas_gene, oiv=None, sprot=None) -> dict:
    from grapeancestry.resource.genes import annotate_site
    from grapeancestry.resource.oiv import describe_trait

    site = str(row.get("site") or "")
    chrom = str(row.get("chrom") or "")
    pos = str(row.get("pos") or "")
    if ":" in site and (not chrom or not pos):
        chrom, pos = site.split(":", 1)
    if not chrom or not str(pos).isdigit():
        return row
    ann = annotate_site(
        chrom,
        int(pos),
        genes,
        features,
        mas_by_site=mas_site,
        mas_by_gene=mas_gene,
        sprot_by_gene=sprot,
    )
    row["gene"] = ann.get("gene") or row.get("gene") or ""
    row["dist"] = ann.get("dist") or row.get("dist") or ""
    row["strand"] = ann.get("strand") or ""
    row["region"] = ann.get("region") or ""
    row["span"] = ann.get("span") or ""
    row["alias"] = ann.get("alias") or ""
    row["biotype"] = ann.get("biotype") or ""
    from grapeancestry.resource.sprot import attach_func_fields

    attach_func_fields(row, ann)
    if ann.get("science_note"):
        row["science_note"] = ann["science_note"]
        note = str(row.get("note") or "")
        if ann["science_note"] not in note:
            row["note"] = f"{note}; {ann['science_note']}".strip("; ")
    trait = str(row.get("trait") or "")
    if oiv is not None and trait:
        row["descriptor"] = describe_trait(trait, oiv)
    return row


def apply_gene_annot_to_payload(payload: dict, root: Path) -> dict:
    """Patch traits / selection / gwas_index gene fields (no ADMIXTURE refit)."""
    from grapeancestry.cloud.mas import MAS_LOCI
    from grapeancestry.report.build_report import trait_overlap
    from grapeancestry.resource.genes import annotate_site, load_gene_annotation
    from grapeancestry.resource.oiv import describe_trait, load_oiv_table
    from grapeancestry.resource.sprot import attach_func_fields, load_gene_func

    gff = root / "data" / "ref" / "VS1.final.gff3"
    genes, features = (None, None)
    if gff.exists():
        genes, features = load_gene_annotation(gff)
    oiv = load_oiv_table(root / "data" / "oiv_traits.tsv")
    sprot = load_gene_func(root)
    mas_site = {r["site"]: r for r in MAS_LOCI}
    mas_gene = {
        r["gene"]: r for r in MAS_LOCI if str(r.get("gene") or "").startswith("Vvsyl")
    }

    site_keys = _panel_site_keys(root)
    trait_tsv = root / "data" / "trait_locus.tsv"
    if site_keys and trait_tsv.exists():
        hits, total = trait_overlap(
            site_keys,
            trait_tsv,
            genes=genes,
            features=features,
            oiv=oiv,
            sprot=sprot,
        )
        payload["panel_trait_catalog"] = hits
        payload["traits"] = payload["panel_trait_catalog"]
        payload["n_traits_total"] = total
        payload.setdefault("query_meta", {})["n_traits"] = len(hits)
    else:
        catalog = payload.get("panel_trait_catalog")
        if catalog is None:
            catalog = payload.get("traits") or []
        for row in catalog:
            _enrich_site_row(row, genes, features, mas_site, mas_gene, oiv, sprot)

    for row in payload.get("selection") or []:
        _enrich_site_row(row, genes, features, mas_site, mas_gene, sprot=sprot)

    for row in payload.get("gwas_index") or []:
        trait = str(row.get("trait") or "")
        if trait:
            row["descriptor"] = describe_trait(trait, oiv)
        chrom = str(row.get("top_chrom") or "")
        pos = str(row.get("top_pos") or "")
        if genes and chrom and pos.isdigit():
            ann = annotate_site(
                chrom,
                int(pos),
                genes,
                features,
                mas_by_site=mas_site,
                mas_by_gene=mas_gene,
                sprot_by_gene=sprot,
            )
            if ann.get("gene"):
                row["top_gene"] = ann["gene"]
            row["top_region"] = ann.get("region") or ""
            row["top_dist"] = ann.get("dist") or ""
            row["top_alias"] = ann.get("alias") or ""
            attach_func_fields(row, ann, prefix="top_")
    return payload


def _hover_label(sid: str, pp: dict[str, str], extra: str = "") -> str:
    lines = [sid]
    if pp.get("acc"):
        lines.append(pp["acc"])
    if pp.get("acc_local"):
        lines.append(pp["acc_local"])
    bits = [pp.get(k, "") for k in ("origin", "con", "geo", "uti", "grp_info")]
    bits = [b for b in bits if b]
    if bits:
        lines.append(" · ".join(bits))
    if pp.get("taxon"):
        lines.append(pp["taxon"])
    if pp.get("vivc"):
        lines.append("VIVC " + pp["vivc"])
    if pp.get("clone_of"):
        lines.append("clone of " + pp["clone_of"])
    if extra:
        lines.append(extra)
    return "<br>".join(lines)


def _load_q(
    admix_dir: Path,
    k: int,
    ids: list[str],
    *,
    run_family: str | None = None,
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    try:
        rows = load_admixture_matrix(admix_dir, k, run_family=run_family)
    except (FileNotFoundError, ValueError):
        return out
    order = plot_order_indices(admix_dir, k, run_family=run_family)
    n = min(len(ids), rows.shape[0])
    for i in range(n):
        out[ids[i]] = [float(x) for x in rows[i, order]]
    return out


def _q_values(comps: dict[str, float], k: int) -> list[float]:
    return [float(comps.get(f"K{i}", 0.0)) for i in range(1, k + 1)]


def _component_payload(admix_dir: Path, k: int, run_family: str) -> dict:
    metadata = component_metadata(admix_dir, k, run_family=run_family)
    labels, colors, aliases = component_labels_colors(admix_dir, k, run_family=run_family)
    if not any(colors):
        colors = SET1[:k]
    permutation = metadata.get("component_permutation") or list(range(k))
    components = metadata.get("components") or []
    plot_order = plot_order_indices(admix_dir, k, run_family=run_family)
    paper_ids = [str((components[i].get("id") if i < len(components) else f"K{i + 1}")) for i in plot_order]
    def _at(i: int, key: str, default: str = "") -> str:
        if i < len(components):
            val = components[i].get(key)
            return default if val is None else val
        return default

    return {
        "run_family": run_family,
        "labels": [labels[i] for i in plot_order] if labels else labels,
        "colors": [colors[i] for i in plot_order] if colors else colors,
        "aliases": [aliases[i] for i in plot_order] if aliases else aliases,
        "owners": [_at(i, "owner") for i in plot_order],
        "inherits_k8": [
            components[i].get("inherits_k8_index") if i < len(components) else None
            for i in plot_order
        ],
        "paper_ids": paper_ids,
        "plot_order": list(plot_order),
        "permutation": list(permutation),
        "raw_component_ids": [c.get("raw_component_id", "") for c in components],
        "projection_available": bool(metadata.get("projection_available", False)),
        "projection_status": metadata.get(
            "projection_status",
            "disabled_no_matching_science_P"
            if run_family == SCIENCE_RUN_FAMILY
            else (
                "panel167k_P_available"
                if run_family == PANEL167K_NOGWAS_FAMILY
                else "chip_P_available"
            ),
        ),
    }


def build_interactive_payload(
    bundle: ReportBundle,
    root: Path,
) -> dict:
    """Assemble D / SROWS / SIDX / TREE_TIPS for the JS layer."""
    admix_dir = root / "data" / "panel" / "admixture"
    info = _load_info(root / "data" / "panel" / "2449.info")
    annot = _load_info(root / "data" / "panel" / "sample_annot.tsv")
    dong = _load_dong_passport(root)
    grp_colors = load_grp_colors(root / "data" / "panel" / "grp_colors.tsv")
    _pp: dict[str, dict[str, str]] = {}

    def pp_of(sid: str) -> dict[str, str]:
        if sid not in _pp:
            _pp[sid] = sample_passport(sid, info, annot, dong)
        return _pp[sid]

    run_family = display_run_family(admix_dir, bundle.admix_contrast)
    projection_family = (
        bundle.admix_contrast.run_family
        if bundle.admix_contrast
        else run_family
    )
    order = list(REPORT_GRP_ORDER)
    science_manifest = (
        load_science_manifest(admix_dir)
        if run_family == SCIENCE_RUN_FAMILY
        else load_panel167k_manifest(admix_dir)
        if run_family == PANEL167K_NOGWAS_FAMILY
        else {}
    )
    admix_provenance = science_manifest.get("sources") or {}

    ids_file = id_path_for_family(admix_dir, run_family)
    panel_ids = [ln.strip() for ln in ids_file.read_text().splitlines() if ln.strip()] if ids_file.exists() else []

    # Resolve every K from one selected run family.
    q_by_k: dict[int, dict[str, list[float]]] = {}
    for k in range(2, 9):
        q_by_k[k] = _load_q(admix_dir, k, panel_ids, run_family=run_family)
    admix_meta = {
        str(k): _component_payload(admix_dir, k, run_family) for k in range(2, 9)
    }
    ordered_panel_ids = order_ids_by_group(panel_ids, info, order)

    # Sample rows for browser (panel + query)
    id_to_xy = {sid: (x, y) for sid, x, y, _g in bundle.ref_pca}

    def _pc(v: float):
        return None if v != v else float(v)

    q_pcs = list(bundle.pca_coords.get(bundle.sample) or [])
    if len(q_pcs) < 2:
        q_pcs = [float(bundle.pca_sample[0]), float(bundle.pca_sample[1])]

    # Query Q values are kept only in the row source used by JavaScript.
    # Plotly bar traces are built on demand in the browser.
    query_qvals: dict[str, list[float] | str] = {}
    if bundle.admix_contrast:
        ac = bundle.admix_contrast
        store = ac.q_by_k
        same_strip = ac.run_family == run_family or (
            run_family == SCIENCE_RUN_FAMILY
            and ac.run_family in {SCIENCE_RUN_FAMILY, "science"}
        )
        # Chip-P Q must not sit on Science-coloured bars.
        if not store and same_strip:
            store = ac.projected_by_k
        for k, comps in (store or {}).items():
            if not comps:
                continue
            qv = _q_values(comps, int(k))
            porder = admix_meta[str(k)].get("plot_order") or list(range(int(k)))
            qv = [qv[i] for i in porder]
            query_qvals[str(k)] = qv
            labels = admix_meta[str(k)]["labels"]
            query_qvals[f"{k}_dom"] = labels[int(np.argmax(qv))] if qv else ""

    def _row_for(sid: str, *, is_query: bool = False) -> dict:
        meta = info.get(sid, {})
        pcs = list(q_pcs if is_query else (bundle.pca_coords.get(sid) or []))
        if len(pcs) < 2:
            xy = id_to_xy.get(sid, (float("nan"), float("nan")))
            pcs = [float(xy[0]), float(xy[1])]
        qvals: dict[str, list[float] | str] = {}
        for k, qm in q_by_k.items():
            if sid not in qm:
                continue
            qv = qm[sid]
            qvals[str(k)] = qv
            labels = admix_meta[str(k)]["labels"]
            dom_i = int(np.argmax(qv)) if qv else -1
            qvals[f"{k}_dom"] = labels[dom_i] if dom_i >= 0 else ""
        if is_query:
            qvals.update(query_qvals)
        row = {
            "iid": sid,
            "label": f"{sid} (query)" if is_query else sid,
            "grp": meta.get("Grp", "") or ("QUERY" if is_query else ""),
            "idx": len(srows),
            "pc1": _pc(pcs[0]) if len(pcs) > 0 else None,
            "pc2": _pc(pcs[1]) if len(pcs) > 1 else None,
            "pc3": _pc(pcs[2]) if len(pcs) > 2 else None,
            "qvals": qvals,
        }
        apply_passport_fields(row, pp_of(sid))
        if is_query:
            row["query"] = True
        return row

    srows: list[dict] = []
    for sid in ordered_panel_ids:
        srows.append(_row_for(sid, is_query=sid == bundle.sample))
    seen = {r["iid"] for r in srows}
    for sid, x, y, g in bundle.ref_pca:
        if sid == bundle.sample or sid in seen:
            continue
        srows.append(_row_for(sid))
        seen.add(sid)

    # An out-of-panel query is a single final row; an in-panel query was
    # already emitted at its deterministic group position above.
    if bundle.sample not in seen:
        srows.append(_row_for(bundle.sample, is_query=True))

    chip_projection = {
        str(k): _q_values(comps, k)
        for k, comps in (
            bundle.admix_contrast.chip_projected_by_k
            if bundle.admix_contrast
            else {}
        ).items()
        if comps
    }

    sidx = {r["iid"]: {"pca_idx": r["idx"], "heat": {}} for r in srows}

    # ── PCA figure (Grp color) ──
    pca_traces = []
    by_g: dict[str, list[dict]] = defaultdict(list)
    for sid, x, y, g in bundle.ref_pca:
        if sid == bundle.sample:
            continue
        by_g[g or "NA"].append({"iid": sid, "x": x, "y": y})
    # Draw background groups first so CG/Syl sit on top.
    bg = {"C-Ad", "W-Ad", "OUT", "NA", ""}
    grps = [g for g in order if g in by_g and g in bg] + [
        g for g in order if g in by_g and g not in bg
    ] + sorted(set(by_g) - set(order))
    for i, g in enumerate(grps):
        pts = by_g[g]
        is_bg = g in bg
        pca_traces.append(
            {
                "type": "scattergl",
                "mode": "markers",
                "name": g,
                "x": [p["x"] for p in pts],
                "y": [p["y"] for p in pts],
                "customdata": [p["iid"] for p in pts],
                "text": [_hover_label(p["iid"], pp_of(p["iid"])) for p in pts],
                "marker": {
                    "size": 5 if not is_bg else 4,
                    "opacity": 0.45 if is_bg else 0.85,
                    "color": grp_colors.get(g, SET1[i % len(SET1)]),
                    "line": {"width": 0.4 if is_bg else 0, "color": "#999999"},
                },
                "hovertemplate": "%{text}<extra>" + g + "</extra>",
            }
        )
    pca_traces.append(
        {
            "type": "scatter",
            "mode": "markers",
            "name": bundle.sample,
            "x": [q_pcs[0]],
            "y": [q_pcs[1]],
            "customdata": [bundle.sample],
            "text": [_hover_label(bundle.sample, pp_of(bundle.sample), "query")],
            "marker": {
                "size": 14,
                "color": "#000000",
                "symbol": "star",
                "line": {"width": 1, "color": "#000"},
            },
            "hovertemplate": "%{text} (query)<extra></extra>",
        }
    )
    pca_layout = {
        **_SCIENCE_LAYOUT,
        "height": 480,
        "margin": {"l": 50, "r": 20, "t": 40, "b": 50},
        "title": f"{pca_method_label(bundle.pca_method)} · query={bundle.sample}",
        "xaxis": {
            **_SCIENCE_LAYOUT["xaxis"],
            "title": "PC1",
            "scaleanchor": "y",
            "scaleratio": 1,
        },
        "yaxis": {**_SCIENCE_LAYOUT["yaxis"], "title": "PC2"},
        "legend": {"orientation": "h", "y": 1.08, "font": {"size": 9, "color": "#1a1a1a"}},
        "hovermode": "closest",
    }
    pca_fig = {"data": pca_traces, "layout": pca_layout}

    # Full points for JS PC-axis switch / 3D (compactness is only for bars).
    pca_points: list[dict] = []
    if bundle.pca_coords:
        point_ids = [sid for sid in ordered_panel_ids if sid in bundle.pca_coords]
        point_ids += sorted(
            sid
            for sid in bundle.pca_coords
            if sid not in point_ids and sid != bundle.sample
        )
        for sid in point_ids:
            pcs = bundle.pca_coords[sid]
            g = info.get(sid, {}).get("Grp", "") or ""
            pca_points.append({"iid": sid, "grp": g, "pcs": [float(x) for x in pcs]})
        if bundle.sample not in {p["iid"] for p in pca_points}:
            pca_points.append(
                {"iid": bundle.sample, "grp": "QUERY", "pcs": [float(x) for x in q_pcs], "query": True}
            )
        else:
            for point in pca_points:
                if point["iid"] == bundle.sample:
                    point["query"] = True
                    break
    else:
        ordered_refs = sorted(
            bundle.ref_pca,
            key=lambda row: (
                order.index(row[3]) if row[3] in order else len(order),
                row[3],
                row[0],
            ),
        )
        for sid, x, y, g in ordered_refs:
            if sid == bundle.sample:
                continue
            pca_points.append({"iid": sid, "grp": g or "", "pcs": [float(x), float(y)]})
        pca_points.append(
            {
                "iid": bundle.sample,
                "grp": info.get(bundle.sample, {}).get("Grp", "") or "QUERY",
                "pcs": [float(q_pcs[0]), float(q_pcs[1])],
                "query": True,
            }
        )
    n_pcs = max((len(p["pcs"]) for p in pca_points), default=2)

    def _tree_plotly(
        tips: dict[str, tuple[float, float]],
        segs: list[tuple[float, float, float, float]],
        *,
        circular: bool,
    ) -> dict:
        edge_x: list[float | None] = []
        edge_y: list[float | None] = []
        for x0, y0, x1, y1 in segs:
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
        tip_traces: list[dict] = []
        by_tg: dict[str, list[str]] = defaultdict(list)
        for tid in tips:
            by_tg[bundle.tip_groups.get(tid, "NA")].append(tid)
        tg_order = [g for g in ("C-Ad", "W-Ad", "OUT", "NA") if g in by_tg]
        tg_order += [g for g in order if g in by_tg and g not in tg_order]
        tg_order += [g for g in sorted(by_tg) if g not in tg_order]
        for i, g in enumerate(tg_order):
            tids = by_tg[g]
            is_wild = g.startswith("WWE") or g.startswith("WEE")
            is_bg = g in {"C-Ad", "W-Ad", "OUT", "NA"}
            tip_traces.append(
                {
                    "type": "scatter",
                    "mode": "markers",
                    "name": g,
                    "x": [tips[t][0] for t in tids],
                    "y": [tips[t][1] for t in tids],
                    "customdata": tids,
                    "text": [_hover_label(t, pp_of(t)) for t in tids],
                    "marker": {
                        "size": [12 if t == bundle.sample else (5 if is_bg else 7) for t in tids],
                        "color": [
                            "#000000" if t == bundle.sample else grp_colors.get(g, SET1[i % len(SET1)])
                            for t in tids
                        ],
                        "symbol": [
                            "star" if t == bundle.sample else ("square" if is_wild else "circle")
                            for t in tids
                        ],
                        "opacity": 0.5 if is_bg else 0.9,
                        "line": {"width": 0.4 if is_bg else 0, "color": "#999"},
                    },
                    "hovertemplate": "%{text}<extra>" + g + "</extra>",
                }
            )
        xs = [tips[t][0] for t in tips]
        ys = [tips[t][1] for t in tips]
        if circular:
            for x0, y0, x1, y1 in segs:
                xs.extend([x0, x1])
                ys.extend([y0, y1])
        span = max((abs(v) for v in xs + ys), default=1e-6) if circular else 0.0
        span = max(span, 1e-6)
        pad = span * 0.10
        lim = span + pad
        if circular:
            axis_hide = {
                "visible": False,
                "showgrid": False,
                "zeroline": False,
                "showticklabels": False,
                "range": [-lim, lim],
                "fixedrange": False,
                "automargin": False,
            }
            layout = {
                **_SCIENCE_LAYOUT,
                "height": 720,
                "autosize": False,
                "margin": {"l": 24, "r": 24, "t": 48, "b": 24},
                "title": f"NJ tree (circular) · {len(tips)} tips · query={bundle.sample}",
                "xaxis": {
                    **_SCIENCE_LAYOUT["xaxis"],
                    **axis_hide,
                    "scaleanchor": "y",
                    "scaleratio": 1,
                    "constrain": "domain",
                    "constraintoward": "center",
                },
                "yaxis": {**_SCIENCE_LAYOUT["yaxis"], **axis_hide},
                "hovermode": "closest",
                "legend": {
                    "font": {"size": 9, "color": "#1a1a1a"},
                    "x": 1,
                    "y": 1,
                    "xanchor": "right",
                    "yanchor": "top",
                    "bgcolor": "rgba(255,255,255,0.88)",
                    "borderwidth": 0,
                },
                "uirevision": "tree-circular",
            }
        else:
            layout = {
                **_SCIENCE_LAYOUT,
                "height": int(max(480, min(3.05 * len(tips), 10000))),
                "margin": {"l": 30, "r": 120, "t": 40, "b": 40},
                "title": f"NJ tree (rectangular) · {len(tips)} tips · query={bundle.sample}",
                "xaxis": {**_SCIENCE_LAYOUT["xaxis"], "title": "distance from root", "zeroline": False, "automargin": True},
                "yaxis": {"visible": False, "autorange": True},
                "hovermode": "closest",
                "legend": {"font": {"size": 9, "color": "#1a1a1a"}},
            }
        return {
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": edge_x,
                    "y": edge_y,
                    "line": {"color": "#888888", "width": 0.5 if len(tips) > 200 else 1},
                    "hoverinfo": "skip",
                    "showlegend": False,
                },
                *tip_traces,
            ],
            "layout": layout,
        }

    # ── NJ tree: circular (default) + rectangular ──
    tree_fig = None
    tree_fig_rect = None
    tree_tips: dict[str, list[float]] = {}
    tree_tips_rect: dict[str, list[float]] = {}
    if bundle.tree_obj is not None:
        tips_c = tip_xy_circular(bundle.tree_obj)
        tree_fig = _tree_plotly(tips_c, tree_edges_circular(bundle.tree_obj, n_arc=6), circular=True)
        tips_r = tip_xy_rectangular(bundle.tree_obj)
        tree_fig_rect = _tree_plotly(tips_r, tree_edges_rectangular(bundle.tree_obj), circular=False)
        tree_tips = {tid: [float(x), float(y)] for tid, (x, y) in tips_c.items()}
        tree_tips_rect = {tid: [float(x), float(y)] for tid, (x, y) in tips_r.items()}

    # clone hits compact
    clones = [
        {
            "rel": r.get("relationship", ""),
            "ref": r.get("ref", ""),
            "r1": r.get("R1", ""),
            "king": r.get("KING_Robust", ""),
        }
        for r in bundle.clone_hits[:80]
    ]

    from grapeancestry.core.dosage import resolve_cache

    cache_p = resolve_cache(root)
    n_sites = 0
    try:
        from grapeancestry.core.dosage import load_cache

        _m, _i, sites = load_cache(cache_p)
        n_sites = len(sites)
    except Exception:
        n_sites = int(bundle.qc.get("n_panel_sites") or 0)

    downloads = []
    # Query-sample sidecars only. Never the panel, never the full report JSON.
    for name, label in (
        (f"{bundle.sample}.qc.tsv", "QC TSV"),
        (f"{bundle.sample}.ibs_summary.tsv", "IBS class counts"),
        (f"{bundle.sample}.ibs_clone_hits.tsv", "Clone / PO hits"),
        (f"{bundle.sample}.kinship_top.tsv", "Kinship top"),
        (f"{bundle.sample}.pca.tsv", "PCA (this sample)"),
        (f"{bundle.sample}.damage.tsv", "Damage TSV"),
    ):
        p = root / "results" / name
        if p.exists():
            downloads.append({"href": name, "label": label})
    for k in range(2, 9):
        name = f"{bundle.sample}.admix.K{k}.Q.tsv"
        p = root / "results" / name
        if p.exists():
            downloads.append({"href": name, "label": f"ADMIXTURE K={k} Q"})
    downloads = [d for d in downloads if _is_query_download(bundle.sample, d.get("href", ""))]

    # IBS neighbors (prefer non-self; keep self as first QC row if present)
    ibs_top: list[dict] = []
    for r in bundle.ibs_relationships[:25]:
        ibs_top.append(
            {
                "ref": r.get("ref", ""),
                "rel": r.get("relationship", ""),
                "r1": r.get("R1", ""),
                "king": r.get("KING_Robust", ""),
                "ibs2p": r.get("IBS2*_pct", ""),
                "r0": r.get("R0", ""),
            }
        )
    kinship_top = [
        {
            "rank": r.get("rank", i),
            "ref": r.get("ref_id", r.get("ref", "")),
            "rel": r.get("relationship", ""),
            "king": r.get("KING_Robust", r.get("kinship", "")),
            "ibs": r.get("ibs", ""),
            "n": r.get("n_comparable", ""),
        }
        for i, r in enumerate(bundle.kinship_top[:20], 1)
    ]

    # Query K=8 breakdown from the selected run family.
    query_q8: list[dict] = []
    q8_dom = ""
    q8_values = query_qvals.get("8") or []
    k8_meta = admix_meta["8"]
    if q8_values:
        q8_dom = str(query_qvals.get("8_dom") or "")
        for j, value in enumerate(q8_values):
            query_q8.append(
                {
                    "k": k8_meta["paper_ids"][j] if j < len(k8_meta.get("paper_ids") or []) else f"K{j + 1}",
                    "label": k8_meta["labels"][j] if j < len(k8_meta["labels"]) else f"K{j + 1}",
                    "color": k8_meta["colors"][j] if j < len(k8_meta["colors"]) else "#888",
                    "value": float(value),
                }
            )

    q_pp = pp_of(bundle.sample)
    contrast_grp = (
        bundle.admix_contrast.grp_value if bundle.admix_contrast else ""
    ) or ""
    query_meta = {
        "grp": contrast_grp or q_pp["grp_info"] or "",
        "name": q_pp["acc"],
        "vivc": q_pp["vivc"],
        "con": q_pp["con"],
        "wild": q_pp["wild"],
        "geo": q_pp["geo"],
        "uti": q_pp["uti"],
        "sex": q_pp["sex"],
        "color": q_pp["color"],
        "muscat": q_pp["muscat"],
        "origin": q_pp["origin"],
        "taxon": q_pp["taxon"],
        "contributor": q_pp["contributor"],
        "po": q_pp["po"],
        "comments": q_pp["comments"],
        "clone_of": q_pp["clone_of"],
        "acc_local": q_pp["acc_local"],
        "passport_from": q_pp["passport_from"],
        "pc1": float(q_pcs[0]) if len(q_pcs) > 0 else None,
        "pc2": float(q_pcs[1]) if len(q_pcs) > 1 else None,
        "pc3": float(q_pcs[2]) if len(q_pcs) > 2 else None,
        "q8_dom": q8_dom,
        "admix_source": bundle.admix_contrast.source if bundle.admix_contrast else "",
        "admix_run_family": run_family,
        "projection_status": (
            bundle.admix_contrast.projection_status
            if bundle.admix_contrast
            else "not_requested"
        ),
        "projection_source": (
            bundle.admix_contrast.projection_source
            if bundle.admix_contrast
            else ""
        ),
        "pca_method": bundle.pca_method or "",
        "n_traits": len(bundle.trait_hits),
        "n_sel": len(bundle.selection_outliers),
        "projection_family": projection_family,
    }

    method_coverage = getattr(bundle, "method_coverage", None) or build_method_coverage(
        [],
        [],
        selection_loci=getattr(bundle, "selection_loci", None) or [],
        gwas_loci=getattr(bundle, "gwas_loci", None) or [],
        fstat_query_called_sites=getattr(bundle, "fstat_query_called_sites", 0),
        gs_pred=getattr(bundle, "gs_pred", None) or [],
        qc=bundle.qc,
        damage_available=bool(
            getattr(bundle, "damage_profile", None) or bundle.damage_freqs
        ),
        damage_unavailable_reason="damage profile unavailable",
        gs_available=bool(
            getattr(bundle, "gs_index", None)
            or getattr(bundle, "gs_pred", None)
            or bundle.gs
        ),
        gs_unavailable_reason="no per-sample GS prediction available",
    )
    query_evidence = list(getattr(bundle, "query_evidence", None) or [])
    panel_trait_catalog = list(bundle.trait_hits[:40])

    payload = {
        "query": bundle.sample,
        "report_meta": dict(getattr(bundle, "report_meta", None) or {}),
        "n_panel": len(panel_ids),
        "cache_name": cache_p.name,
        "n_sites": n_sites,
        "pca_points": pca_points,
        "pca_n": n_pcs,
        "pca_evals": [float(x) for x in (bundle.pca_evals or [])],
        "pca_method": bundle.pca_method or "",
        "grp_colors": dict(grp_colors),
        "tree": tree_fig,
        "tree_rect": tree_fig_rect,
        "tree_tips": tree_tips,
        "tree_tips_rect": tree_tips_rect,
        "srows": srows,
        "sidx": sidx,
        "clones": clones,
        "conclusions": bundle.conclusions,
        "qc": {k: (None if isinstance(v, float) and v != v else v) for k, v in bundle.qc.items()},
        "selection": bundle.selection_outliers[:25],
        "selection_named": getattr(bundle, "selection_named", None) or [],
        "selection_by_grp": getattr(bundle, "selection_by_grp", None) or [],
        "selection_vs_science": getattr(bundle, "selection_vs_science", None) or [],
        "selection_vs_summary": getattr(bundle, "selection_vs_summary", None) or [],
        "selection_loci": getattr(bundle, "selection_loci", None) or [],
        "selection_manhattan": getattr(bundle, "selection_manhattan", None) or {},
        "selection_heatmap": getattr(bundle, "selection_heatmap", None) or {},
        "selection_s29_scatter": getattr(bundle, "selection_s29_scatter", None) or {},
        "selection_fst_het_scatter": getattr(bundle, "selection_fst_het_scatter", None) or {},
        "f3": bundle.f3_rows[:20],
        "f4": bundle.f4_rows[:20],
        "f3_out": getattr(bundle, "f3_out_rows", None) or [],
        "fstat_pop": bundle.fstat_pop,
        "fstat_query_called_sites": bundle.fstat_query_called_sites,
        "outgroup_n": bundle.outgroup_n,
        "ibs_summary": bundle.ibs_summary,
        "ibs_top": ibs_top,
        "kinship_top": kinship_top,
        "merged_note": bundle.merged_vcf_note,
        "damage": getattr(bundle, "damage_profile", None)
        or (
            {
                "source": "lite",
                "version": "",
                "ct5": bundle.damage_freqs,
                "ga3": [],
                "subs5": {},
                "subs3": {},
                "length": [],
            }
            if bundle.damage_freqs
            else None
        ),
        "panel_trait_catalog": panel_trait_catalog,
        "traits": panel_trait_catalog,
        "query_evidence": query_evidence,
        "gwas_trait": bundle.gwas_trait,
        "gs": bundle.gs,
        "gwas_index": bundle.gwas_index,
        "gs_index": bundle.gs_index,
        "gs_pred": bundle.gs_pred,
        "gwas_loci": bundle.gwas_loci,
        "cross_top": bundle.cross_top,
        "gwas_figs": {},
        "gwas_skip": bundle.gwas_skip,
        "methods_html": sanitize_methods_html(bundle.methods_html),
        "downloads": downloads,
        "purity": bundle.purity_note,
        "method_coverage": method_coverage,
        "admix_source": bundle.admix_contrast.source if bundle.admix_contrast else "",
        "admix_run_family": projection_family,
        "admix_strip_family": run_family,
        "admix_projection_status": (
            bundle.admix_contrast.projection_status
            if bundle.admix_contrast
            else "not_requested"
        ),
        "admix_projection_source": (
            bundle.admix_contrast.projection_source
            if bundle.admix_contrast
            else ""
        ),
        "admix_provenance": admix_provenance,
        "admix_methods": admixture_methods_text(run_family),
        "admix_meta": admix_meta,
        "admix_group_order": order,
        "admix_query_in_panel": bundle.sample in panel_ids,
        "chip_projection": chip_projection,
        "k8_science": run_family == SCIENCE_RUN_FAMILY,
        "k8_colors": list(k8_meta["colors"]),
        "k8_labels": list(k8_meta["labels"]),
        "query_q8": query_q8,
        "query_meta": query_meta,
        "author_mode": "population"
        if len(getattr(bundle, "author_samples", None) or []) > 1
        else "sample",
        "author_samples": list(getattr(bundle, "author_samples", None) or []),
    }
    if not pca_points:
        payload["pca"] = pca_fig
    return payload


def payload_to_json(payload: dict) -> str:
    def _clean(o):
        if isinstance(o, float):
            if o != o or o in (float("inf"), float("-inf")):
                return None
            return o
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_clean(v) for v in o]
        return o

    return json.dumps(_clean(payload), ensure_ascii=False, allow_nan=False)
