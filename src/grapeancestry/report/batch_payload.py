"""One interactive payload for N query samples.

Panel keys (PCA points, sample rows, GWAS index, selection Manhattan) stay
at the top level once. Keys that follow the active query live under
``per_query``.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from grapeancestry.identity.ibs import pair_stats
from grapeancestry.identity.run_ibs import read_ibs_table

GRAPH_CLASSES = frozenset({"Identical", "Parent-Offspring", "Full Sib", "2nd"})

PAIR_FIELDS = (
    "sample_a",
    "sample_b",
    "relationship",
    "KING_Robust",
    "R1",
    "R0",
    "n_comparable",
)

PER_QUERY_KEYS = (
    "qc",
    "damage",
    "query_meta",
    "clones",
    "ibs_top",
    "kinship_top",
    "ibs_summary",
    "gs_pred",
    "downloads",
    "conclusions",
    "report_meta",
    "f3",
    "f4",
    "f3_out",
    "fstat_pop",
    "fstat_query_called_sites",
    "outgroup_n",
    "query_evidence",
    "query_q8",
    "chip_projection",
    "method_coverage",
    "purity",
    "admix_query_in_panel",
    "admix_projection_status",
    "admix_projection_source",
    "admix_source",
    "merged_note",
)


def _fmt_num(value: float) -> str:
    if value != value or value in (float("inf"), float("-inf")):
        return "NA"
    return f"{value:.6f}"


def _as_float(text: object) -> float | None:
    try:
        value = float(text)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def _copy_shallow(value: object) -> object:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def pairwise_rows(samples: list[str], dosages: dict[str, np.ndarray]) -> list[dict[str, str]]:
    """Unordered within-batch pairs. Classification is ``pair_stats``."""
    rows: list[dict[str, str]] = []
    for i, left in enumerate(samples):
        for right in samples[i + 1 :]:
            stats = pair_stats(dosages[left], dosages[right], right)
            rows.append(
                {
                    "sample_a": left,
                    "sample_b": right,
                    "relationship": stats.relationship,
                    "KING_Robust": _fmt_num(stats.king_robust),
                    "R1": _fmt_num(stats.r1),
                    "R0": _fmt_num(stats.r0),
                    "n_comparable": str(stats.n_comparable),
                }
            )
    return rows


def load_query_dosages(
    root: Path,
    samples: list[str],
) -> tuple[dict[str, np.ndarray], np.ndarray, list[str]]:
    """Dosages aligned to the panel cache sites."""
    from grapeancestry.core.dosage import load_cache, load_sample_dosage, resolve_cache

    cache = resolve_cache(root)
    ref_mat, ref_ids, sites = load_cache(cache)
    dosages: dict[str, np.ndarray] = {}
    for sample in samples:
        vcf = root / "results" / f"{sample}.vcf.gz"
        dosages[sample] = load_sample_dosage(vcf, sample, sites)
    return dosages, np.asarray(ref_mat), [str(x) for x in ref_ids]


def within_batch_pairs(root: Path, samples: list[str]) -> list[dict[str, str]]:
    dosages, _mat, _ids = load_query_dosages(root, samples)
    return pairwise_rows(samples, dosages)


def write_pairwise_tsv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(PAIR_FIELDS), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in PAIR_FIELDS})
    return path


def _as_int(text: object) -> int | None:
    try:
        value = int(float(text))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value


def _edge(source: str, target: str, rel: str, king: object, r1: object, n: object = None) -> dict:
    return {
        "source": source,
        "target": target,
        "class": rel,
        "king": _as_float(king),
        "r1": _as_float(r1),
        "n": _as_int(n),
    }


def _kinship_n(root: Path, sample: str) -> dict[str, str]:
    path = root / "results" / f"{sample}.kinship_top.tsv"
    if not path.is_file():
        return {}
    with path.open(newline="") as fh:
        rows = csv.DictReader(fh, delimiter="\t")
        return {
            (row.get("ref_id") or row.get("ref") or ""): row.get("n_comparable") or ""
            for row in rows
            if (row.get("ref_id") or row.get("ref"))
        }


def relationship_graph(
    root: Path,
    samples: list[str],
    pairs: list[dict[str, str]],
) -> dict[str, list]:
    """Queries plus panel samples at Identical / PO / Full Sib / 2nd.

    Query nodes are always present. Query–query edges are the within-batch
    pairs whose 4K class is not Unrelated.
    """
    nodes: list[dict[str, str]] = [{"id": sample, "kind": "query"} for sample in samples]
    seen = set(samples)
    edges: list[dict] = []
    results = root / "results"
    for sample in samples:
        path = results / f"{sample}.ibs.tsv"
        if not path.is_file():
            continue
        kin_n = _kinship_n(root, sample)
        for row in read_ibs_table(path):
            rel = row.get("relationship") or ""
            if rel not in GRAPH_CLASSES:
                continue
            ref = row.get("ref") or ""
            if not ref or ref == sample:
                continue
            n_sites = row.get("n_comparable") or kin_n.get(ref) or ""
            edges.append(_edge(sample, ref, rel, row.get("KING_Robust"), row.get("R1"), n_sites))
            if ref not in seen:
                seen.add(ref)
                nodes.append({"id": ref, "kind": "panel"})
    for row in pairs:
        rel = row.get("relationship") or ""
        if not rel or rel == "Unrelated":
            continue
        left = row.get("sample_a") or ""
        right = row.get("sample_b") or ""
        if not left or not right:
            continue
        edges.append(
            _edge(
                left,
                right,
                rel,
                row.get("KING_Robust"),
                row.get("R1"),
                row.get("n_comparable"),
            )
        )
    return {"nodes": nodes, "edges": edges}


def _query_point(payload: dict) -> dict | None:
    qid = str(payload.get("query") or "")
    for point in payload.get("pca_points") or []:
        if point.get("query") or point.get("iid") == qid:
            row = dict(point)
            row["iid"] = qid
            row["query"] = True
            return row
    return None


def _gt_pack(loci: list | None) -> list[dict]:
    pack: list[dict] = []
    for locus in loci or []:
        snps = locus.get("snps") or {}
        gt = snps.get("gt")
        pack.append(
            {
                "slug": locus.get("slug"),
                "query_gt_sample": locus.get("query_gt_sample"),
                "query_gt_called": locus.get("query_gt_called"),
                "query_gt_n": locus.get("query_gt_n"),
                "gt": list(gt) if isinstance(gt, list) else None,
            }
        )
    return pack


def per_query_slice(payload: dict) -> dict:
    slice_: dict = {}
    for key in PER_QUERY_KEYS:
        if key in payload:
            slice_[key] = _copy_shallow(payload[key])
    slice_["pca_query"] = _query_point(payload)
    slice_["selection_query_gt"] = _gt_pack(payload.get("selection_loci"))
    slice_["gwas_query_gt"] = _gt_pack(payload.get("gwas_loci"))
    return slice_


def resolve_batch_library_type(
    source_id: str,
    report_id: str,
    *,
    cli_type: str | None,
    file_types: dict[str, str],
) -> str:
    """Per-sample YAML ``type`` overrides the batch ``--library-type`` flag."""
    for key in (source_id, report_id):
        raw = str(file_types.get(key) or "").strip()
        if raw:
            return raw
    return str(cli_type or "").strip()


def stamp_library_type(bundle: object, library_type: str) -> None:
    if not str(library_type or "").strip():
        return
    from grapeancestry.report.build_report import classify_library_type

    meta = dict(getattr(bundle, "report_meta", None) or {})
    meta["library_type"] = str(library_type).strip()
    klass = classify_library_type(library_type)
    if klass:
        meta["library_class"] = klass
    bundle.report_meta = meta  # type: ignore[attr-defined]


def annotate_panel_labels(graph: dict, srows: list[dict]) -> dict:
    by_id = {str(row.get("iid")): row for row in srows or [] if row.get("iid")}
    for node in graph.get("nodes") or []:
        if node.get("kind") != "panel":
            continue
        row = by_id.get(str(node.get("id"))) or {}
        variety = str(row.get("acc") or "").strip()
        node["label"] = f"{node['id']} · {variety}" if variety else str(node.get("id") or "")
    return graph


def _query_card(sample: str, slice_: dict) -> dict:
    kin = slice_.get("kinship_top") or []
    top = kin[0] if kin else {}
    meta = slice_.get("report_meta") or {}
    qc = slice_.get("qc") or {}
    return {
        "id": sample,
        "library_type": meta.get("library_type") or "",
        "library_class": meta.get("library_class") or "",
        "calling_rate": qc.get("calling_rate_panel_pct"),
        "nearest_id": top.get("ref") or "",
        "nearest_class": top.get("rel") or "",
        "nearest_king": top.get("king") if top else "",
    }


def _query_row(payload: dict) -> dict | None:
    qid = str(payload.get("query") or "")
    for row in payload.get("srows") or []:
        if row.get("query") or row.get("iid") == qid:
            copied = dict(row)
            copied["iid"] = qid
            copied["query"] = True
            return copied
    return None


def assemble_batch_payload(
    samples: list[str],
    payloads: list[dict],
    pairs: list[dict[str, str]],
    graph: dict[str, list],
) -> dict:
    by_query = {str(payload.get("query")): payload for payload in payloads}
    missing = [sample for sample in samples if sample not in by_query]
    if missing:
        raise ValueError(f"missing payloads for {missing}")
    ordered = [by_query[sample] for sample in samples]
    slices = {sample: per_query_slice(by_query[sample]) for sample in samples}
    shared = ordered[0]
    qset = set(samples)
    panel_points = [
        point
        for point in (shared.get("pca_points") or [])
        if not point.get("query") and point.get("iid") not in qset
    ]
    query_points = []
    for sample in samples:
        point = _query_point(by_query[sample])
        if point is not None:
            query_points.append(point)
    shared["pca_points"] = panel_points + query_points

    panel_rows = [
        row
        for row in (shared.get("srows") or [])
        if not row.get("query") and row.get("iid") not in qset
    ]
    query_rows = []
    for sample in samples:
        row = _query_row(by_query[sample])
        if row is not None:
            query_rows.append(row)
    srows = panel_rows + query_rows
    for index, row in enumerate(srows):
        row["idx"] = index
    shared["srows"] = srows
    old_sidx = shared.get("sidx") or {}
    shared["sidx"] = {
        row["iid"]: {
            "pca_idx": row["idx"],
            "heat": (old_sidx.get(row["iid"]) or {}).get("heat", {}),
        }
        for row in srows
    }
    shared["batch"] = True
    shared["query"] = samples[0]
    shared["queries"] = [_query_card(sample, slices[sample]) for sample in samples]
    shared["per_query"] = slices
    shared["pairs"] = list(pairs)
    shared["graph"] = annotate_panel_labels(graph, shared.get("srows") or [])
    for key, value in slices[samples[0]].items():
        shared[key] = value
    return shared


def _multi_query_tree(root: Path, samples: list[str], dosages: dict[str, np.ndarray], ref_mat: np.ndarray, ref_ids: list[str]):
    from grapeancestry.core.dosage import resolve_cache
    from grapeancestry.identity.catalog import load_info
    from grapeancestry.popgen.tree_nj import (
        assemble_tree_distance,
        build_nj_tree,
        load_or_compute_panel_ibs_d,
    )

    cache = resolve_cache(root)
    panel_d = load_or_compute_panel_ibs_d(
        root / "results" / "cache" / f"ibs_d_{cache.stem}.npz",
        list(ref_ids),
        ref_mat,
    )
    qmat = np.vstack([np.asarray(dosages[sample], dtype=float).reshape(1, -1) for sample in samples])
    tip_ids, tree_mat, tree_d = assemble_tree_distance(
        list(ref_ids),
        ref_mat,
        qmat,
        list(samples),
        panel_d,
    )
    tree = build_nj_tree(tip_ids, tree_mat, D=tree_d)
    info = load_info(root / "data" / "panel" / "2449.info")
    ref_set = set(ref_ids)
    tip_groups = {rid: info.get(rid, {}).get("Grp", "") for rid in tip_ids}
    for sample in samples:
        if sample not in ref_set:
            tip_groups[sample] = "QUERY"
    return tree, tip_ids, tip_groups


def payloads_from_bundles(
    root: Path,
    samples: list[str],
    bundles: list,
    dosages: dict[str, np.ndarray] | None = None,
    ref_mat: np.ndarray | None = None,
    ref_ids: list[str] | None = None,
) -> list[dict]:
    from grapeancestry.report.interactive_data import build_interactive_payload

    by_id = {bundle.sample: bundle for bundle in bundles}
    ordered = [by_id[sample] for sample in samples]
    if dosages is None or ref_mat is None or ref_ids is None:
        dosages, ref_mat, ref_ids = load_query_dosages(root, samples)
    tree, tip_ids, tip_groups = _multi_query_tree(root, samples, dosages, ref_mat, ref_ids)
    ordered[0].tree_obj = tree
    ordered[0].tree_ids = tip_ids
    ordered[0].tip_groups = tip_groups
    payloads = []
    for index, bundle in enumerate(ordered):
        payloads.append(
            build_interactive_payload(
                bundle,
                root,
                star_ids=list(samples) if index == 0 else None,
                include_tree=index == 0,
            )
        )
    return payloads


def build_batch_payload(
    root: Path,
    samples: list[str],
    *,
    bundles: list | None = None,
    payloads: list[dict] | None = None,
    pairs: list[dict[str, str]] | None = None,
) -> dict:
    """Shared panel payload plus one per-query slice and the relationship graph."""
    samples = [str(sample) for sample in samples]
    if not samples:
        raise ValueError("build_batch_payload needs at least one sample")
    dosages = None
    ref_mat = None
    ref_ids = None
    need_dosage = pairs is None or (payloads is None and bundles)
    if need_dosage:
        dosages, ref_mat, ref_ids = load_query_dosages(root, samples)
    if pairs is None:
        assert dosages is not None
        pairs = pairwise_rows(samples, dosages)
    graph = relationship_graph(root, samples, pairs)
    if payloads is None:
        if not bundles:
            raise ValueError("build_batch_payload needs payloads or bundles")
        payloads = payloads_from_bundles(root, samples, bundles, dosages, ref_mat, ref_ids)
    return assemble_batch_payload(samples, payloads, pairs, graph)
