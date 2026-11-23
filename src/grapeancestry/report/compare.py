"""167K versus 8K comparison page, with a deterministic bilingual verdict.

Single-sample payloads (one query) omit the query–query KING section.
Batch payloads keep it. The verdict uses only numbers from this run.
"""

from __future__ import annotations

import csv
import html
import json
import math
import statistics
from pathlib import Path

CATEGORIES = ("clone", "PO", "full_sib", "2nd", "3rd", "unrelated")
K_RANGE = tuple(range(2, 9))
RELATED = {"clone", "PO", "full_sib", "2nd", "3rd"}
EIGHT_K_SITE_MAX = 12_000
CALL_RATIO_SAME = 1.15
PCA_CLOSE = 0.02
Q_CORR_CLOSE = 0.95
Q_RMSE_CLOSE = 0.05
KING_CLOSE = 90.0
UPGRADE_CLOSE = 5.0
TOP1_CLOSE = 0.5

_BANNED = ("样本优先", "当前计算", "范围边界", "overlay", "保持对", "读者区域")


def as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number or math.isinf(number):
        return None
    return number


def fmt_num(value: object) -> str:
    number = as_float(value)
    if number is None:
        return ""
    if number == 0:
        return "0"
    nearest = round(number)
    if abs(number) >= 1 and abs(number - nearest) <= 1e-9 * max(1.0, abs(number)):
        return str(int(nearest))
    return f"{number:.6g}"


def fmt_pct(value: object) -> str:
    number = as_float(value)
    if number is None:
        return ""
    return f"{number:.2f}"


def _fmt_prose(value: float | None, digits: int = 3) -> str:
    if value is None:
        return ""
    if abs(value) >= 100:
        return f"{value:.0f}"
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text or "0"


def category_of(value: object) -> str:
    if value is None:
        return ""
    key = " ".join(str(value).strip().lower().replace("_", " ").replace("-", " ").split())
    table = {
        "identical": "clone",
        "identical clone": "clone",
        "clone": "clone",
        "parent offspring": "PO",
        "po": "PO",
        "full sib": "full_sib",
        "2nd": "2nd",
        "second": "2nd",
        "3rd": "3rd",
        "third": "3rd",
        "unrelated": "unrelated",
    }
    return table.get(key, "")


def confusion_matrix(pairs: list[tuple[str, str]]) -> dict:
    labels = list(CATEGORIES)
    extra = sorted({item for pair in pairs for item in pair if item and item not in labels})
    labels.extend(extra)
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for left, right in pairs:
        if left in index and right in index:
            matrix[index[left]][index[right]] += 1
    n = sum(sum(row) for row in matrix)
    n_agree = sum(matrix[i][i] for i in range(len(labels)))
    pct = None if n == 0 else 100.0 * n_agree / n
    return {"labels": labels, "matrix": matrix, "n": n, "n_agree": n_agree, "agreement_pct": pct}


def topn_overlap(left_ids: list[str], right_ids: list[str], n: int) -> float:
    left = list(left_ids)[:n]
    right = list(right_ids)[:n]
    if not left and not right:
        return 1.0
    return len(set(left) & set(right)) / max(len(left), len(right))


def pca_distance(x0: object, y0: object, x1: object, y1: object) -> float | None:
    a, b, c, d = as_float(x0), as_float(y0), as_float(x1), as_float(y1)
    if None in (a, b, c, d):
        return None
    return math.hypot(c - a, d - b)  # type: ignore[arg-type]


def q_correlation_rmse(
    left_rows: list[list[float]],
    right_rows: list[list[float]],
) -> tuple[float | None, float | None]:
    xs: list[float] = []
    ys: list[float] = []
    for left, right in zip(left_rows, right_rows):
        for u, v in zip(left, right):
            xs.append(float(u))
            ys.append(float(v))
    if not xs:
        return None, None
    if xs == ys:
        return 1.0, 0.0
    return _pearson(xs, ys), _rmse(xs, ys)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n == 0:
        return None
    if n == 1:
        return 1.0 if xs[0] == ys[0] else None
    mx = sum(xs) / n
    my = sum(ys) / n
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    vx = sum(v * v for v in dx)
    vy = sum(v * v for v in dy)
    if vx == 0 and vy == 0:
        return 1.0
    if vx == 0 or vy == 0:
        return None
    cov = sum(a * b for a, b in zip(dx, dy))
    return cov / math.sqrt(vx * vy)


def _rmse(xs: list[float], ys: list[float]) -> float | None:
    if not xs:
        return None
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(xs, ys)) / len(xs))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def sample_ids(payload: dict) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for row in payload.get("queries") or []:
        sid = str(row.get("id") or "")
        if sid and sid not in seen:
            ids.append(sid)
            seen.add(sid)
    for sid in payload.get("per_query") or {}:
        sid = str(sid)
        if sid and sid not in seen:
            ids.append(sid)
            seen.add(sid)
    if not ids:
        sid = str(payload.get("query") or payload.get("sample") or "")
        if sid:
            ids.append(sid)
    return ids


def normalize_payload(payload: dict) -> dict:
    """Accept a batch payload or a single-sample dashboard payload."""
    if not isinstance(payload, dict):
        raise TypeError("comparison payload must be a dict")
    if payload.get("per_query") or payload.get("queries"):
        out = dict(payload)
        if not out.get("queries"):
            out["queries"] = [{"id": sid} for sid in sample_ids(out)]
        return out
    sid = str(payload.get("query") or payload.get("sample") or "query")
    out = dict(payload)
    out["queries"] = [{"id": sid}]
    out["per_query"] = {sid: payload}
    return out


def _union_ids(left: dict, right: dict) -> list[str]:
    ids = sample_ids(left)
    seen = set(ids)
    for sid in sample_ids(right):
        if sid not in seen:
            ids.append(sid)
            seen.add(sid)
    return ids


def _query_rows(payload: dict) -> dict[str, dict]:
    wanted = set(sample_ids(payload))
    found: dict[str, dict] = {}
    for row in payload.get("srows") or []:
        sid = str(row.get("iid") or "")
        if sid not in wanted:
            continue
        if row.get("query") or sid not in found:
            found[sid] = row
    return found


def _coverage(slice_: dict | None) -> tuple[float | None, float | None, float | None, float | None]:
    slice_ = slice_ or {}
    qc = slice_.get("qc") or {}
    panel = ((slice_.get("method_coverage") or {}).get("panel_genotype") or {})
    total = as_float(panel.get("total"))
    called = as_float(panel.get("called"))
    coverage = as_float(panel.get("coverage"))
    qc_rate = as_float(qc.get("calling_rate_panel_pct"))
    if total is None:
        total = as_float(qc.get("n_panel_sites"))
    if called is None:
        called = as_float(qc.get("n_called"))
    rate = coverage * 100.0 if coverage is not None else qc_rate
    return total, called, rate, qc_rate


def _ranked_refs(payload: dict, sid: str) -> list[str]:
    slice_ = (payload.get("per_query") or {}).get(sid) or {}
    rows = list(slice_.get("kinship_top") or [])

    def sort_key(item: tuple[int, dict]) -> tuple[float, int]:
        index, row = item
        rank = as_float(row.get("rank"))
        return (rank if rank is not None else float(index + 1), index)

    refs: list[str] = []
    for _, row in sorted(enumerate(rows), key=sort_key):
        ref = str(row.get("ref") or "")
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def _qp_map(payload: dict) -> dict[tuple[str, str], dict]:
    qids = set(sample_ids(payload))
    out: dict[tuple[str, str], dict] = {}
    per_query = payload.get("per_query") or {}
    for sid in sample_ids(payload):
        for row in (per_query.get(sid) or {}).get("kinship_top") or []:
            ref = str(row.get("ref") or "")
            if not ref:
                continue
            out[(sid, ref)] = {
                "king": as_float(row.get("king") if row.get("king") not in (None, "") else row.get("KING_Robust")),
                "cat": category_of(row.get("rel") or row.get("relationship")),
                "n": row.get("n") if row.get("n") not in (None, "") else row.get("n_comparable"),
            }
    for edge in (payload.get("graph") or {}).get("edges") or []:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in qids and target in qids:
            continue
        if source in qids and target:
            key = (source, target)
        elif target in qids and source:
            key = (target, source)
        else:
            continue
        if key in out:
            continue
        out[key] = {
            "king": as_float(edge.get("king")),
            "cat": category_of(edge.get("class")),
            "n": edge.get("n"),
        }
    return out


def _qq_map(payload: dict) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for row in payload.get("pairs") or []:
        left = str(row.get("sample_a") or "")
        right = str(row.get("sample_b") or "")
        if not left or not right or left == right:
            continue
        key = tuple(sorted((left, right)))
        out[key] = {
            "king": as_float(row.get("KING_Robust") if row.get("KING_Robust") not in (None, "") else row.get("king")),
            "cat": category_of(row.get("relationship") or row.get("rel")),
            "n": row.get("n_comparable") if row.get("n_comparable") not in (None, "") else row.get("n"),
        }
    return out


def _pair_record(key: tuple[str, str], left: dict | None, right: dict | None, kind: str) -> dict:
    if kind == "qp":
        record: dict = {"query": key[0], "ref": key[1]}
    else:
        record = {"sample_a": key[0], "sample_b": key[1]}
    record["king_167k"] = fmt_num(None if left is None else left.get("king"))
    record["king_10k"] = fmt_num(None if right is None else right.get("king"))
    record["cat_167k"] = "" if left is None else str(left.get("cat") or "")
    record["cat_10k"] = "" if right is None else str(right.get("cat") or "")
    record["n_167k"] = fmt_num(None if left is None else left.get("n"))
    record["n_10k"] = fmt_num(None if right is None else right.get("n"))
    record["_x"] = None if left is None else left.get("king")
    record["_y"] = None if right is None else right.get("king")
    return record


def _cats(rows: list[dict]) -> list[tuple[str, str]]:
    pairs = []
    for row in rows:
        left = row.get("cat_167k") or ""
        right = row.get("cat_10k") or ""
        if left and right:
            pairs.append((left, right))
    return pairs


def _upgrade_pct(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    upgraded = sum(1 for left, right in pairs if left == "unrelated" and right in RELATED)
    return 100.0 * upgraded / len(pairs)


def _king_tally(pairs: list[tuple[str, str]]) -> dict:
    """Counts over pairs classified on both panels. Upgrade uses that same denominator."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "agree": 0, "upgrade": 0, "agree_pct": None, "upgrade_pct": None}
    agree = sum(1 for left, right in pairs if left == right)
    upgrade = sum(1 for left, right in pairs if left == "unrelated" and right in RELATED)
    return {
        "n": n,
        "agree": agree,
        "upgrade": upgrade,
        "agree_pct": 100.0 * agree / n,
        "upgrade_pct": 100.0 * upgrade / n,
    }


def _add_hit(store: dict, scope: str, left: object, right: object, cat: str) -> None:
    if cat not in {"clone", "PO"}:
        return
    a = str(left or "")
    b = str(right or "")
    if not a or not b:
        return
    if scope == "qq":
        pair = tuple(sorted((a, b)))
        key = ("qq", pair[0], pair[1])
    else:
        key = ("qp", a, b)
    previous = store.get(key)
    if previous is None or (previous != "clone" and cat == "clone"):
        store[key] = cat


def _hits(payload: dict) -> dict:
    store: dict = {}
    qids = set(sample_ids(payload))
    for sid, slice_ in (payload.get("per_query") or {}).items():
        sid = str(sid)
        if not isinstance(slice_, dict):
            continue
        for row in slice_.get("clones") or []:
            _add_hit(store, "qp", sid, row.get("ref"), category_of(row.get("rel") or row.get("relationship")))
        for row in slice_.get("kinship_top") or []:
            _add_hit(store, "qp", sid, row.get("ref"), category_of(row.get("rel") or row.get("relationship")))
        for row in slice_.get("ibs_top") or []:
            _add_hit(store, "qp", sid, row.get("ref"), category_of(row.get("rel") or row.get("relationship")))
    for row in payload.get("pairs") or []:
        _add_hit(store, "qq", row.get("sample_a"), row.get("sample_b"), category_of(row.get("relationship")))
    for edge in (payload.get("graph") or {}).get("edges") or []:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        cat = category_of(edge.get("class"))
        if source in qids and target in qids:
            _add_hit(store, "qq", source, target, cat)
        elif source in qids:
            _add_hit(store, "qp", source, target, cat)
        elif target in qids:
            _add_hit(store, "qp", target, source, cat)
    return store


def _q_vector(row: dict | None, k: int) -> list[float] | None:
    if not row:
        return None
    raw = (row.get("qvals") or {}).get(str(k))
    if not isinstance(raw, list) or len(raw) != k:
        return None
    values = []
    for item in raw:
        number = as_float(item)
        if number is None:
            return None
        values.append(number)
    return values


def _component_style(payload: dict, k: int) -> tuple[list[str], list[str]]:
    meta = (payload.get("admix_meta") or {}).get(str(k)) or {}
    labels = [str(item) for item in (meta.get("labels") or [])]
    colors = [str(item) for item in (meta.get("colors") or [])]
    while len(labels) < k:
        labels.append(f"K{len(labels) + 1}")
    fallback = ["#dc1f26", "#4470b7", "#f7922c", "#835ca6", "#15803d", "#a16207", "#0b5475", "#981b1e"]
    while len(colors) < k:
        colors.append(fallback[len(colors) % len(fallback)])
    return labels[:k], colors[:k]


def _pcs(payload: dict, sid: str, rows: dict[str, dict]) -> tuple[float | None, float | None]:
    point = ((payload.get("per_query") or {}).get(sid) or {}).get("pca_query") or {}
    coords = point.get("pcs")
    if isinstance(coords, list) and len(coords) >= 2:
        x = as_float(coords[0])
        y = as_float(coords[1])
        if x is not None and y is not None:
            return x, y
    row = rows.get(sid) or {}
    return as_float(row.get("pc1")), as_float(row.get("pc2"))


def _panel_points(payload: dict, qids: set[str]) -> list[dict]:
    points = []
    for point in payload.get("pca_points") or []:
        iid = str(point.get("iid") or "")
        if not iid or iid in qids or point.get("query"):
            continue
        coords = point.get("pcs") or []
        if len(coords) < 2:
            continue
        x = as_float(coords[0])
        y = as_float(coords[1])
        if x is None or y is None:
            continue
        points.append({"iid": iid, "grp": str(point.get("grp") or ""), "pc1": x, "pc2": y})
    return points


def _trait_rows(payload: dict) -> list[tuple[str, str, str]]:
    rows = payload.get("traits") or payload.get("panel_trait_catalog") or []
    found = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        rec = (str(row.get("site") or ""), str(row.get("trait") or ""), str(row.get("gene") or ""))
        if rec in seen or not any(rec):
            continue
        seen.add(rec)
        found.append(rec)
    return found


def _windows(payload: dict) -> list[dict]:
    found = []
    seen = set()
    for row in payload.get("selection_named") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        n_sites = as_float(row.get("n_sites"))
        found.append(
            {
                "name": name,
                "chrom": str(row.get("chrom") or ""),
                "start": str(row.get("start") or ""),
                "end": str(row.get("end") or ""),
                "n_sites": None if n_sites is None else int(round(n_sites)),
            }
        )
    return found


def _store(tables: dict, name: str, fields: list[str], rows: list[dict]) -> None:
    tables[name] = {"fields": fields, "rows": rows}


def _put_summary(tables: dict, name: str, pairs: list[tuple[str, str]]) -> None:
    _store(tables, name, ["metric", "value"], [{"metric": key, "value": value} for key, value in pairs])


def compare_payloads(payload_167k: dict, payload_8k: dict) -> dict:
    left = normalize_payload(payload_167k)
    right = normalize_payload(payload_8k)
    ids = _union_ids(left, right)
    qids = set(ids)
    is_single = len(ids) <= 1
    left_rows = _query_rows(left)
    right_rows = _query_rows(right)
    left_slice = left.get("per_query") or {}
    right_slice = right.get("per_query") or {}
    tables: dict[str, dict] = {}

    called_l: list[float] = []
    called_r: list[float] = []
    site_rows = []
    for sid in ids:
        lt, lc, lr, lq = _coverage(left_slice.get(sid))
        rt, rc, rr, rq = _coverage(right_slice.get(sid))
        if lc is not None:
            called_l.append(lc)
        if rc is not None:
            called_r.append(rc)
        site_rows.append(
            {
                "sample": sid,
                "sites_167k": fmt_num(lt),
                "called_167k": fmt_num(lc),
                "call_rate_167k": fmt_num(lr),
                "qc_call_rate_167k": fmt_num(lq),
                "sites_8k": fmt_num(rt),
                "called_8k": fmt_num(rc),
                "call_rate_8k": fmt_num(rr),
                "qc_call_rate_8k": fmt_num(rq),
            }
        )
    _store(
        tables,
        "sites_callrate.tsv",
        [
            "sample",
            "sites_167k",
            "called_167k",
            "call_rate_167k",
            "qc_call_rate_167k",
            "sites_8k",
            "called_8k",
            "call_rate_8k",
            "qc_call_rate_8k",
        ],
        site_rows,
    )

    qp_left, qp_right = _qp_map(left), _qp_map(right)
    qq_left, qq_right = _qq_map(left), _qq_map(right)
    qp_rows = [_pair_record(key, qp_left.get(key), qp_right.get(key), "qp") for key in sorted(set(qp_left) | set(qp_right))]
    qq_rows = [] if is_single else [
        _pair_record(key, qq_left.get(key), qq_right.get(key), "qq") for key in sorted(set(qq_left) | set(qq_right))
    ]
    _store(
        tables,
        "king_query_panel.tsv",
        ["query", "ref", "king_167k", "king_8k", "cat_167k", "cat_8k", "n_167k", "n_8k"],
        [{**row, "king_8k": row["king_10k"], "cat_8k": row["cat_10k"], "n_8k": row["n_10k"]} for row in qp_rows],
    )
    if not is_single:
        _store(
            tables,
            "king_query_query.tsv",
            ["sample_a", "sample_b", "king_167k", "king_8k", "cat_167k", "cat_8k", "n_167k", "n_8k"],
            [{**row, "king_8k": row["king_10k"], "cat_8k": row["cat_10k"], "n_8k": row["n_10k"]} for row in qq_rows],
        )
    conf_qp = confusion_matrix(_cats(qp_rows))
    conf_qq = confusion_matrix(_cats(qq_rows)) if qq_rows else confusion_matrix([])
    qp_pairs = _cats(qp_rows)
    qq_pairs = [] if is_single else _cats(qq_rows)
    cat_pool = qp_pairs + qq_pairs
    conf_all = confusion_matrix(cat_pool)
    qp_tally = _king_tally(qp_pairs)
    qq_tally = _king_tally(qq_pairs)
    pool_tally = _king_tally(qp_pairs if is_single else cat_pool)
    king_agreement = conf_qp["agreement_pct"] if is_single or conf_all["n"] == 0 else conf_all["agreement_pct"]
    king_upgrade = _upgrade_pct(qp_pairs if is_single else cat_pool)

    top_rows = []
    top_values: dict[int, list[float]] = {1: [], 5: [], 10: []}
    for sid in ids:
        left_refs = _ranked_refs(left, sid)
        right_refs = _ranked_refs(right, sid)
        scores = {n: topn_overlap(left_refs, right_refs, n) for n in (1, 5, 10)}
        for n, score in scores.items():
            top_values[n].append(score)
        top_rows.append(
            {
                "sample": sid,
                "top1": fmt_num(scores[1]),
                "top5": fmt_num(scores[5]),
                "top10": fmt_num(scores[10]),
                "top1_167k": ",".join(left_refs[:1]),
                "top1_8k": ",".join(right_refs[:1]),
                "top5_167k": ",".join(left_refs[:5]),
                "top5_8k": ",".join(right_refs[:5]),
            }
        )
    _store(
        tables,
        "topn_overlap.tsv",
        ["sample", "top1", "top5", "top10", "top1_167k", "top1_8k", "top5_167k", "top5_8k"],
        top_rows,
    )
    top_med = {n: _median(values) for n, values in top_values.items()}
    top1_scores = top_values[1]
    top1_exact_hits = sum(1 for score in top1_scores if score >= 1.0 - 1e-9)

    panel = _panel_points(left, qids)
    pca_rows = []
    distances: list[float] = []
    for sid in ids:
        x0, y0 = _pcs(left, sid, left_rows)
        x1, y1 = _pcs(right, sid, right_rows)
        dist = pca_distance(x0, y0, x1, y1)
        if dist is not None:
            distances.append(dist)
        pca_rows.append(
            {
                "sample": sid,
                "pc1_167k": fmt_num(x0),
                "pc2_167k": fmt_num(y0),
                "pc1_8k": fmt_num(x1),
                "pc2_8k": fmt_num(y1),
                "dist": fmt_num(dist),
                "_x0": x0,
                "_y0": y0,
                "_x1": x1,
                "_y1": y1,
            }
        )
    _store(
        tables,
        "pca_displacement.tsv",
        ["sample", "pc1_167k", "pc2_167k", "pc1_8k", "pc2_8k", "dist"],
        pca_rows,
    )
    pca_med = _median(distances)

    q_summary = []
    admix_ks: dict = {}
    pearsons: list[float] = []
    rmses: list[float] = []
    for k in K_RANGE:
        labels, colors = _component_style(left, k)
        samples_k, vectors_l, vectors_r = [], [], []
        for sid in ids:
            lv = _q_vector(left_rows.get(sid), k)
            rv = _q_vector(right_rows.get(sid), k)
            if lv is None or rv is None:
                continue
            samples_k.append(sid)
            vectors_l.append(lv)
            vectors_r.append(rv)
        pearson, rmse = q_correlation_rmse(vectors_l, vectors_r)
        if pearson is not None:
            pearsons.append(pearson)
        if rmse is not None:
            rmses.append(rmse)
        q_summary.append(
            {
                "k": str(k),
                "n_samples": str(len(samples_k)),
                "pearson": fmt_num(pearson),
                "rmse": fmt_num(rmse),
            }
        )
        if samples_k:
            admix_ks[str(k)] = {
                "samples": samples_k,
                "labels": labels,
                "colors": colors,
                "q167": vectors_l,
                "q8k": vectors_r,
            }
    _store(tables, "q_summary.tsv", ["k", "n_samples", "pearson", "rmse"], q_summary)

    left_hits, right_hits = _hits(left), _hits(right)
    hit_rows = []
    for key in sorted(set(left_hits) | set(right_hits), key=lambda item: tuple(str(x) for x in item)):
        if is_single and key[0] == "qq":
            continue
        if key in left_hits and key in right_hits:
            side = "both"
        elif key in left_hits:
            side = "only_167k"
        else:
            side = "only_8k"
        hit_rows.append(
            {
                "scope": key[0],
                "sample_a": key[1],
                "sample_b": key[2],
                "class_167k": left_hits.get(key, ""),
                "class_8k": right_hits.get(key, ""),
                "side": side,
            }
        )
    _store(
        tables,
        "clone_po_hits.tsv",
        ["scope", "sample_a", "sample_b", "class_167k", "class_8k", "side"],
        hit_rows,
    )

    left_traits, right_traits = _trait_rows(left), _trait_rows(right)
    trait_rows = []
    for rec in sorted(set(left_traits) | set(right_traits)):
        trait_rows.append(
            {
                "site": rec[0],
                "trait": rec[1],
                "gene": rec[2],
                "in_167k": "1" if rec in left_traits else "0",
                "in_8k": "1" if rec in right_traits else "0",
            }
        )
    _store(tables, "traits.tsv", ["site", "trait", "gene", "in_167k", "in_8k"], trait_rows)

    left_windows = {row["name"]: row for row in _windows(left)}
    right_windows = {row["name"]: row for row in _windows(right)}
    window_rows = []
    for name in list(dict.fromkeys(list(left_windows) + list(right_windows))):
        lw = left_windows.get(name) or {}
        rw = right_windows.get(name) or {}
        window_rows.append(
            {
                "name": name,
                "chrom": lw.get("chrom") or rw.get("chrom") or "",
                "n_sites_167k": fmt_num(lw.get("n_sites")),
                "n_sites_8k": fmt_num(rw.get("n_sites")),
                "_n167": lw.get("n_sites"),
                "_n8": rw.get("n_sites"),
            }
        )
    _store(
        tables,
        "selection_windows.tsv",
        ["name", "chrom", "n_sites_167k", "n_sites_8k"],
        [{k: v for k, v in row.items() if not k.startswith("_")} for row in window_rows],
    )

    def _positive(rows: dict, field: str) -> tuple[int, int]:
        positive = zero = 0
        for row in rows.values():
            n_sites = row.get("n_sites")
            if n_sites is None:
                continue
            if int(n_sites) > 0:
                positive += 1
            else:
                zero += 1
        return positive, zero

    pos_l, _zero_l = _positive(left_windows, "n_sites")
    pos_r, zero_r = _positive(right_windows, "n_sites")
    sites_167 = as_float(left.get("n_sites"))
    sites_8 = as_float(right.get("n_sites"))
    metrics = {
        "n_query": len(ids),
        "called_167k": _median(called_l),
        "called_8k": _median(called_r),
        "sites_167k": sites_167,
        "sites_8k": sites_8,
        "pca_median_dist": pca_med,
        "q_pearson_min": min(pearsons) if pearsons else None,
        "q_rmse_max": max(rmses) if rmses else None,
        "king_agreement_pct": king_agreement,
        "king_agreement_qp_pct": conf_qp["agreement_pct"],
        "king_agreement_qq_pct": None if is_single else conf_qq["agreement_pct"],
        "king_upgrade_pct": king_upgrade,
        "king_total_pairs": pool_tally["n"],
        "king_agree_pairs": pool_tally["agree"],
        "king_upgrade_pairs": pool_tally["upgrade"],
        "qp_total": qp_tally["n"],
        "qp_agree_pct": qp_tally["agree_pct"],
        "qp_upgrade_pct": qp_tally["upgrade_pct"],
        "qq_total": None if is_single else qq_tally["n"],
        "qq_agree_pct": None if is_single else qq_tally["agree_pct"],
        "qq_upgrade_pct": None if is_single else qq_tally["upgrade_pct"],
        "top1": top_med[1],
        "top5": top_med[5],
        "top1_overlap_median": top_med[1],
        "top5_overlap_median": top_med[5],
        "top1_exact_hits": top1_exact_hits,
        "top1_total": len(top1_scores),
        "hits_both": sum(1 for row in hit_rows if row["side"] == "both"),
        "hits_only_167k": sum(1 for row in hit_rows if row["side"] == "only_167k"),
        "hits_only_8k": sum(1 for row in hit_rows if row["side"] == "only_8k"),
        "trait_sites_167k": len({row[0] for row in left_traits if row[0]}),
        "trait_sites_8k": len({row[0] for row in right_traits if row[0]}),
        "windows_positive_167k": pos_l,
        "windows_positive_8k": pos_r,
        "windows_zero_8k": zero_r,
    }
    plot = {
        "kingQp": [
            {
                "x": row["_x"],
                "y": row["_y"],
                "hover": f"{row.get('query', '')} vs {row.get('ref', '')}",
            }
            for row in qp_rows
            if row.get("_x") is not None and row.get("_y") is not None
        ],
        "kingQq": []
        if is_single
        else [
            {
                "x": row["_x"],
                "y": row["_y"],
                "hover": f"{row.get('sample_a', '')} vs {row.get('sample_b', '')}",
            }
            for row in qq_rows
            if row.get("_x") is not None and row.get("_y") is not None
        ],
        "panel": panel,
        "pca": [
            row
            for row in pca_rows
            if None not in (row["_x0"], row["_y0"], row["_x1"], row["_y1"])
        ],
        "admix": admix_ks,
        "single": is_single,
        "pcaShowLegend": len(ids) <= 12,
    }
    return {
        "ids": ids,
        "is_single": is_single,
        "metrics": metrics,
        "tables": tables,
        "confusion_qp": conf_qp,
        "confusion_qq": conf_qq,
        "plot": plot,
        "headline": {
            "king_agreement_pct": fmt_pct(king_agreement),
            "median_top1": fmt_num(top_med[1]),
            "median_pca_dist": fmt_num(pca_med),
            "q_corr_min": fmt_num(min(pearsons) if pearsons else None),
            "q_rmse_max": fmt_num(max(rmses) if rmses else None),
        },
    }


def _input_limited(metrics: dict) -> bool:
    called_l = as_float(metrics.get("called_167k"))
    called_r = as_float(metrics.get("called_8k"))
    sites_r = as_float(metrics.get("sites_8k"))
    if called_l is None or called_r is None or called_r <= 0:
        return False
    if sites_r is None or sites_r > EIGHT_K_SITE_MAX:
        return False
    return (called_l / called_r) <= CALL_RATIO_SAME


def _metric_float(metrics: dict, *keys: str) -> float | None:
    for key in keys:
        number = as_float(metrics.get(key))
        if number is not None:
            return number
    return None


def _close_placement(metrics: dict) -> bool | None:
    dist = _metric_float(metrics, "pca_median_dist", "pca_shift_median")
    corr = _metric_float(metrics, "q_pearson_min", "admix_min_r")
    rmse = _metric_float(metrics, "q_rmse_max", "admix_max_rmse")
    if dist is None and corr is None and rmse is None:
        return None
    if dist is not None and dist > PCA_CLOSE:
        return False
    if corr is not None and corr < Q_CORR_CLOSE:
        return False
    if rmse is not None and rmse > Q_RMSE_CLOSE:
        return False
    return True


def _close_king(metrics: dict) -> bool | None:
    agree = _metric_float(metrics, "king_agreement_pct", "king_agree_pct")
    upgrade = _metric_float(metrics, "king_upgrade_pct")
    top1 = _metric_float(metrics, "top1", "top1_overlap_median")
    total = metrics.get("king_total_pairs")
    total_n = as_float(total)
    if total_n == 0 and top1 is None:
        return None
    if agree is None and upgrade is None and top1 is None:
        return None
    if agree is not None and agree < KING_CLOSE:
        return False
    if upgrade is not None and upgrade > UPGRADE_CLOSE:
        return False
    if top1 is not None and top1 < TOP1_CLOSE:
        return False
    return True


def _traits_essential(metrics: dict) -> bool:
    t167 = as_float(metrics.get("trait_sites_167k"))
    t8 = as_float(metrics.get("trait_sites_8k"))
    w167 = as_float(metrics.get("windows_positive_167k"))
    w8 = as_float(metrics.get("windows_positive_8k"))
    z8 = as_float(metrics.get("windows_zero_8k"))
    if t167 is not None and t8 is not None and t167 >= 4 and t8 * 4 <= t167:
        return True
    if w167 is not None and w8 is not None and w167 >= 4 and w8 <= 1:
        return True
    if z8 is not None and z8 >= 3 and (w8 or 0) <= 2 and (w167 or 0) >= 4:
        return True
    return False


def _pct_text(value: float | None) -> str:
    return _fmt_prose(value, 1) or "—"


def _kinship_prose(metrics: dict, is_batch: bool) -> tuple[str, str]:
    """State the classified-pair denominator. Upgrade is a share of that denominator."""
    total = as_float(metrics.get("king_total_pairs"))
    agree_n = as_float(metrics.get("king_agree_pairs"))
    upgrade_n = as_float(metrics.get("king_upgrade_pairs"))
    agree = _metric_float(metrics, "king_agreement_pct", "king_agree_pct")
    upgrade = _metric_float(metrics, "king_upgrade_pct")
    agree_txt = _pct_text(agree)
    upgrade_txt = _pct_text(upgrade)
    if total is None or agree_n is None or upgrade_n is None:
        zh = (
            f"已分类配对里，两套面板类别一致率 {agree_txt}%，"
            f"其中 {upgrade_txt}% 在 167K 判为无关却在 8K 升格为近亲。"
        )
        en = (
            f"Of the classified pairs, {agree_txt}% match in kinship class, "
            f"and {upgrade_txt}% are unrelated on 167K but called as relatives on 8K."
        )
        return zh, en
    total_i = int(total)
    agree_i = int(agree_n)
    up_i = int(upgrade_n)
    zh = (
        f"{total_i} 对已分类配对中，两套面板类别一致 {agree_i} 对（{agree_txt}%），"
        f"有 {up_i} 对（{upgrade_txt}%）在 167K 判为无关却在 8K 升格为近亲"
    )
    en = (
        f"Across {total_i} classified pairs, {agree_i} ({agree_txt}%) match in kinship class, "
        f"while {up_i} ({upgrade_txt}%) are unrelated on 167K but called as relatives on 8K"
    )
    if is_batch:
        qp_up = _pct_text(_metric_float(metrics, "qp_upgrade_pct"))
        qq_up = _pct_text(_metric_float(metrics, "qq_upgrade_pct"))
        zh += f"。其中样本–参考品种 {qp_up}% 升格、样本–样本 {qq_up}% 升格。"
        en += f" (query–panel {qp_up}%, query–query {qq_up}%)."
    else:
        zh += "。"
        en += "."
    return zh, en


def _top_prose(metrics: dict) -> tuple[str, str]:
    top1 = _metric_float(metrics, "top1_overlap_median", "top1")
    top5 = _metric_float(metrics, "top5_overlap_median", "top5")
    hits = as_float(metrics.get("top1_exact_hits"))
    total = as_float(metrics.get("top1_total"))
    if top1 is None and top5 is None and hits is None and total is None:
        return (
            "Top-1 与 Top-5 没有可对照的重合中位数。",
            "Median Top-1 and Top-5 overlap are not available.",
        )
    top1_txt = _pct_text(None if top1 is None else top1 * 100)
    top5_txt = _pct_text(None if top5 is None else top5 * 100)
    if hits is not None and total is not None:
        zh = (
            f"Top-1 最近品种重合中位数 {top1_txt}%（{int(hits)}/{int(total)} 个样本一致），"
            f"Top-5 重合中位数 {top5_txt}%。"
        )
        en = (
            f"median Top-1 nearest-cultivar overlap is {top1_txt}% "
            f"({int(hits)}/{int(total)} samples exact), median Top-5 overlap is {top5_txt}%."
        )
    else:
        zh = f"Top-1 最近品种重合中位数 {top1_txt}%，Top-5 重合中位数 {top5_txt}%。"
        en = f"median Top-1 nearest-cultivar overlap is {top1_txt}%, median Top-5 overlap is {top5_txt}%."
    return zh, en


def _optional_count(metrics: dict, key: str) -> float | None:
    if key not in metrics:
        return None
    return as_float(metrics.get(key))


def synthesize_verdict(metrics: dict, is_batch: bool) -> dict:
    """Turn this run's numbers into a top-line verdict and four module cards."""
    metrics = dict(metrics or {})
    limited = _input_limited(metrics)
    who = "这些样本" if is_batch else "这个样本"
    who_en = "these samples" if is_batch else "this sample"
    called_l = as_float(metrics.get("called_167k"))
    called_r = as_float(metrics.get("called_8k"))
    ratio = (called_l / called_r) if called_l is not None and called_r else None
    dist = _metric_float(metrics, "pca_median_dist", "pca_shift_median")
    corr = _metric_float(metrics, "q_pearson_min", "admix_min_r")
    rmse = _metric_float(metrics, "q_rmse_max", "admix_max_rmse")
    both_n = _optional_count(metrics, "hits_both")
    only_l_n = _optional_count(metrics, "hits_only_167k")
    only_r_n = _optional_count(metrics, "hits_only_8k")
    hits_missing = both_n is None and only_l_n is None and only_r_n is None
    both = int(both_n or 0)
    only_l = int(only_l_n or 0)
    only_r = int(only_r_n or 0)
    t167 = metrics.get("trait_sites_167k")
    t8 = metrics.get("trait_sites_8k")
    w167 = metrics.get("windows_positive_167k")
    w8 = metrics.get("windows_positive_8k")
    trait_keys = (
        "trait_sites_167k",
        "trait_sites_8k",
        "windows_positive_167k",
        "windows_positive_8k",
        "windows_zero_8k",
    )
    traits_missing = all(as_float(metrics.get(key)) is None for key in trait_keys)

    def badge(en: str, zh: str, code: str) -> dict:
        tone = "muted" if code == "insufficient" else "accent"
        return {"badge_en": en, "badge_zh": zh, "code": code, "tone": tone}

    def from_flag(flag: bool | None, prefer_en: str, prefer_zh: str) -> dict:
        if flag is None:
            return badge("Insufficient data", "数据不足", "insufficient")
        if flag:
            return badge("Comparable", "两者接近", "comparable")
        return badge(prefer_en, prefer_zh, "preferred")

    place_flag: bool | None = None
    king_flag: bool | None = None
    if limited:
        place = badge("Comparable", "两者接近", "comparable")
        king = badge("Comparable", "两者接近", "comparable")
        clone = badge("Comparable", "两者接近", "comparable")
        traits = badge("Comparable", "两者接近", "comparable")
        code = "input_limited"
    else:
        place_flag = _close_placement(metrics)
        king_flag = _close_king(metrics)
        place = from_flag(place_flag, "167K preferred", "167K 更稳")
        king = from_flag(king_flag, "167K preferred", "167K 更可靠")
        if hits_missing:
            clone = badge("Insufficient data", "数据不足", "insufficient")
        elif only_r >= 1 and only_r > both:
            clone = badge("167K more robust", "167K 更稳健", "robust")
        elif only_l >= 3 and only_r == 0:
            clone = badge("167K more robust", "167K 更稳健", "robust")
        else:
            clone = badge("Comparable", "两者接近", "comparable")
        if traits_missing:
            traits = badge("Insufficient data", "数据不足", "insufficient")
        elif _traits_essential(metrics):
            traits = badge("167K essential", "167K 不可替代", "essential")
        else:
            traits = badge("Comparable", "两者接近", "comparable")
        if place_flag is None and king_flag is None:
            code = "insufficient"
        elif place["code"] == "comparable" and (
            king["code"] not in {"comparable", "insufficient"}
            or clone["code"] not in {"comparable", "insufficient"}
            or traits["code"] not in {"comparable", "insufficient"}
        ):
            code = "broad_only"
        elif (
            place["code"] == "preferred"
            or king["code"] == "preferred"
            or traits["code"] == "essential"
            or clone["code"] == "robust"
        ):
            code = "prefer_167k"
        elif place["code"] == "insufficient" or king["code"] == "insufficient":
            code = "insufficient"
        else:
            code = "comparable"

    ratio_txt = _fmt_prose(ratio, 2)
    dist_txt = _fmt_prose(dist, 4)
    corr_txt = _fmt_prose(corr, 3)
    rmse_txt = _fmt_prose(rmse, 3)
    king_zh, king_en = _kinship_prose(metrics, is_batch)
    top_zh, top_en = _top_prose(metrics)
    if king_flag is None and not limited:
        kin_zh = "亲缘没有可对照的已分类配对，也没有可用的 Top-1 重合中位数。"
        kin_en = "Relatedness has no classified pairs to compare, and median Top-1 overlap is unavailable."
    elif king_flag is False:
        kin_zh = "亲缘没有这么稳。" + king_zh + top_zh
        kin_en = "Relatedness does not. " + king_en + " " + top_en
    else:
        kin_zh = king_zh + top_zh
        kin_en = king_en + " " + top_en
    if place_flag is None and not limited:
        place_zh = "群体位置没有可对照的 PCA 距离或 ADMIXTURE 数值。"
        place_en = "Population placement has no PCA distance or ADMIXTURE values to compare."
    else:
        place_zh = (
            f"PCA 距离中位数 {dist_txt or '—'}，ADMIXTURE 最低相关 {corr_txt or '—'}，最高 RMSE {rmse_txt or '—'}。"
        )
        place_en = (
            f"Median PCA distance is {dist_txt or '—'}. The lowest ADMIXTURE correlation is {corr_txt or '—'}, "
            f"and the highest RMSE is {rmse_txt or '—'}."
        )
    if hits_missing and not limited:
        clone_zh = "克隆或亲子没有可对照的命中。"
        clone_en = "Clone and parent-offspring calls have nothing to compare."
    else:
        clone_zh = f"克隆或亲子里，仅 8K 命中 {only_r} 对，两侧共同命中 {both} 对。"
        clone_en = f"Clone or parent-offspring calls found only by 8K: {only_r}. Found by both: {both}."
    if traits_missing and not limited:
        trait_zh = "性状位点与选择窗口没有可对照的数。"
        trait_en = "Trait sites and selection windows have nothing to compare."
    else:
        trait_zh = (
            f"性状位点 167K 有 {t167 if t167 is not None else '—'} 个，8K 有 {t8 if t8 is not None else '—'} 个。"
        )
        trait_en = (
            f"Trait sites: {t167 if t167 is not None else '—'} on 167K, {t8 if t8 is not None else '—'} on 8K."
        )

    if code == "input_limited":
        title_zh, title_en = "两份结果几乎一样", "The two reports are nearly the same"
        sentences_zh = [
            f"167K 报告里实际分型约 {fmt_num(called_l)} 个位点，8K 报告约 {fmt_num(called_r)} 个，比值 {ratio_txt}。",
            "两边这么接近，是因为输入文件本身主要只覆盖这 8,044 个位点。",
            "167K 报告不能补出数据里没有的位点，所以群体位置、亲缘和性状会几乎相同。",
            f"若要让 167K 发挥位点数量的优势，需要{who}有覆盖捕获芯片的基因型，而不是一份只有 8K 位点的 VCF。",
        ]
        sentences_en = [
            f"The 167K report calls about {fmt_num(called_l)} sites and the 8K report about {fmt_num(called_r)} (ratio {ratio_txt}).",
            "The counts match because the input file itself mainly covers these 8,044 sites.",
            "A 167K report cannot invent genotypes that were never in the file, so placement, relatedness, and trait calls stay nearly the same.",
            f"The 167K panel helps when {who_en} actually have capture-chip genotypes, rather than a VCF limited to the 8K sites.",
        ]
    elif code == "broad_only":
        title_zh, title_en = "8K 只适合看群体大方向", "8K is only enough for a broad population placement"
        broad_place_zh = (
            place_zh
            if place_flag is None
            else f"群体位置大体还能对上：PCA 距离中位数 {dist_txt or '—'}，ADMIXTURE 最低相关 {corr_txt or '—'}。"
        )
        broad_place_en = (
            place_en
            if place_flag is None
            else (
                f"Population placement still lines up: median PCA distance {dist_txt or '—'}, "
                f"lowest ADMIXTURE correlation {corr_txt or '—'}."
            )
        )
        sentences_zh = [
            broad_place_zh,
            kin_zh,
            clone_zh,
            trait_zh,
            f"看{who}落在哪个大群体可以用 8K。判断近亲、克隆和性状时用 167K。",
        ]
        sentences_en = [
            broad_place_en,
            kin_en,
            clone_en,
            trait_en,
            f"Use 8K to see the broad population of {who_en}. Use 167K for relatives, clones, and trait genotypes.",
        ]
    elif code == "prefer_167k":
        title_zh, title_en = "建议采用 167K 报告", "Use the 167K report"
        sentences_zh = [
            "8,044 个位点大约是 167K 面板的 5%。这次两边的差别已经大到不该把 8K 当成同一份结论。",
            place_zh,
            kin_zh + ("位点变少后，KING 更容易把无关样本高估成近亲。" if king_flag is False else ""),
            clone_zh + trait_zh,
            f"读{who}的群体细位置、亲缘和性状，以 167K 为准。8K 只适合先看一个大概的群体位置。",
        ]
        sentences_en = [
            "8,044 sites are about 5% of the 167K panel. On this run the two reports diverge enough that the 8K page should not be treated as the same result.",
            place_en,
            kin_en + (
                " With far fewer sites, KING more often calls unrelated samples as relatives."
                if king_flag is False
                else ""
            ),
            clone_en + " " + trait_en,
            f"Read fine-scale placement, relatedness, and traits for {who_en} from the 167K report. Keep 8K for a first look at the broad population.",
        ]
    elif code == "insufficient":
        title_zh, title_en = (
            "对比数据不足，暂时无法判断两套面板优劣",
            "Insufficient overlap to compare the two panels",
        )
        if place_flag is None and king_flag is None:
            sentences_zh = [
                "PCA、ADMIXTURE 和已分类的 KING 配对都没有可对照的数值。",
                "缺这些数时，不能判断两套面板哪一边更合适。",
                "等两边都有主成分、群体成分和亲缘分类之后，再看这份对照。",
            ]
            sentences_en = [
                "PCA, ADMIXTURE, and classified KING pairs have no overlapping values.",
                "Without those numbers, this page cannot judge which panel is more suitable.",
                "Compare again after both sides have principal components, ancestry proportions, and kinship classes.",
            ]
        else:
            sentences_zh = [place_zh, kin_zh]
            sentences_en = [place_en, kin_en]
            sentences_zh.append("缺掉的那一组没有数，所以这次不判断两套面板哪一边更好。")
            sentences_en.append("The missing block has no numbers, so this page does not pick a panel.")
    else:
        title_zh, title_en = "两份报告接近", "The two reports agree"
        sentences_zh = [
            f"PCA 距离中位数 {dist_txt or '0'}，ADMIXTURE 最低相关 {corr_txt or '—'}，群体位置没有拉开。",
            kin_zh,
            clone_zh,
            (
                trait_zh
                + f"有位点的选择窗口分别是 {w167 if w167 is not None else '—'} 和 {w8 if w8 is not None else '—'}。"
            ),
            "这次用哪一份都能看出同样的结论。后面如果要追问克隆或性状基因型，仍以位点更多的 167K 为准。",
        ]
        sentences_en = [
            (
                f"Median PCA distance is {dist_txt or '0'} and the lowest ADMIXTURE correlation is {corr_txt or '—'}, "
                "so the population placement does not split."
            ),
            kin_en,
            clone_en,
            trait_en
            + (
                f" Selection windows with sites: {w167 if w167 is not None else '—'} and "
                f"{w8 if w8 is not None else '—'}."
            ),
            "Either report supports the same reading of this run. When a later question needs clone calls or trait genotypes, use the 167K report.",
        ]

    if limited:
        place_detail_zh = (
            f"已分型位点 167K {fmt_num(called_l)}、8K {fmt_num(called_r)}，比值 {ratio_txt}。"
            "输入主要覆盖 8,044 个位点，所以两边的 PCA 和 ADMIXTURE 几乎相同。"
        )
        place_detail_en = (
            f"Called sites are {fmt_num(called_l)} on 167K and {fmt_num(called_r)} on 8K (ratio {ratio_txt}). "
            "The input mainly covers 8,044 sites, so PCA and ADMIXTURE nearly match."
        )
    elif place_flag is None:
        place_detail_zh = "没有可对照的 PCA 距离或 ADMIXTURE 相关、RMSE。"
        place_detail_en = "No PCA distance or ADMIXTURE correlation and RMSE can be compared."
    else:
        place_detail_zh = (
            f"PCA 距离中位数 {dist_txt or '—'}。K=2–8 的最低 Pearson 相关 {corr_txt or '—'}，最高 RMSE {rmse_txt or '—'}。"
        )
        place_detail_en = (
            f"Median PCA distance {dist_txt or '—'}. Across K=2–8 the lowest Pearson correlation is {corr_txt or '—'} "
            f"and the highest RMSE is {rmse_txt or '—'}."
        )
    if limited:
        king_detail_zh = "因为输入位点几乎相同，亲缘分类也会跟着接近。" + king_zh + top_zh
        king_detail_en = "Relatedness follows the genotypes. " + king_en + " " + top_en
    elif king_flag is None:
        king_detail_zh = "没有两边都分好类的配对，也没有可用的 Top-1 重合中位数。"
        king_detail_en = "No pairs are classified on both sides, and median Top-1 overlap is unavailable."
    else:
        king_detail_zh = king_zh + top_zh
        king_detail_en = king_en + " " + top_en
    if hits_missing and not limited:
        clone_detail_zh = clone_zh
        clone_detail_en = clone_en
    else:
        clone_detail_zh = f"共同命中 {both} 对，仅 167K {only_l} 对，仅 8K {only_r} 对。"
        clone_detail_en = f"Shared hits {both}. Only 167K: {only_l}. Only 8K: {only_r}."
        if not limited and only_r > both:
            clone_detail_zh += " 8K 单独多出来的命中更像是位点变少以后的假阳性。"
            clone_detail_en += " Extra 8K-only hits are the pattern expected when fewer sites inflate kinship."
    if traits_missing and not limited:
        trait_detail_zh = trait_zh
        trait_detail_en = trait_en
    else:
        trait_detail_zh = (
            f"性状位点 167K {t167 if t167 is not None else '—'} 个，8K {t8 if t8 is not None else '—'} 个。"
            f"有位点的选择窗口：167K {w167 if w167 is not None else '—'} 个，8K {w8 if w8 is not None else '—'} 个。"
        )
        trait_detail_en = (
            f"Trait sites: {t167 if t167 is not None else '—'} on 167K, {t8 if t8 is not None else '—'} on 8K. "
            f"Selection windows that still contain sites: {w167 if w167 is not None else '—'} on 167K, "
            f"{w8 if w8 is not None else '—'} on 8K."
        )
    modules = [
        {
            "id": "placement",
            "title_zh": "群体定位（PCA 与 ADMIXTURE）",
            "title_en": "Population placement (PCA and ADMIXTURE)",
            "detail_zh": place_detail_zh,
            "detail_en": place_detail_en,
            **place,
        },
        {
            "id": "kinship",
            "title_zh": "亲缘分类与最近品种（KING 与 Top-N）",
            "title_en": "Relatedness and nearest varieties (KING and Top-N)",
            "detail_zh": king_detail_zh,
            "detail_en": king_detail_en,
            **king,
        },
        {
            "id": "clones",
            "title_zh": "克隆与亲子命中（Identical / PO）",
            "title_en": "Clone and parent-offspring calls",
            "detail_zh": clone_detail_zh,
            "detail_en": clone_detail_en,
            **clone,
        },
        {
            "id": "traits",
            "title_zh": "性状位点与选择扫描",
            "title_en": "Trait sites and selection windows",
            "detail_zh": trait_detail_zh,
            "detail_en": trait_detail_en,
            **traits,
        },
    ]
    verdict = {
        "code": code,
        "title_zh": title_zh,
        "title_en": title_en,
        "summary_zh": "".join(sentences_zh),
        "summary_en": " ".join(sentences_en),
        "sentences_zh": sentences_zh,
        "sentences_en": sentences_en,
        "modules": modules,
        "input_limited": limited,
        "is_batch": bool(is_batch),
    }
    blob = json.dumps(verdict, ensure_ascii=False)
    for word in _BANNED:
        if word in blob:
            raise RuntimeError(f"verdict text contains banned wording: {word}")
    return verdict


def build_top_nav_html(links: list[dict], active_kind: str) -> str:
    """Bilingual bar linking the 167K report, the 8K report, and the comparison."""
    parts = ['<nav id="ga-report-nav" class="ga-report-nav">']
    for link in links:
        kind = str(link.get("kind") or "")
        href = html.escape(str(link.get("href") or "#"), quote=True)
        en = html.escape(str(link.get("label_en") or kind))
        zh = html.escape(str(link.get("label_zh") or kind))
        current = "true" if kind == active_kind else "false"
        parts.append(
            f'<a href="{href}" data-kind="{html.escape(kind)}" aria-current="{current}">'
            f'<span class="en">{en}</span><span class="cn">{zh}</span></a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def inject_after_body(html_path: Path, snippet: str, marker: str) -> None:
    """Insert ``snippet`` once after ``<body>`` when ``marker`` is not already present."""
    path = Path(html_path)
    if not snippet or not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    idx = text.find("<body")
    if idx < 0:
        path.write_text(snippet + text, encoding="utf-8")
        return
    end = text.find(">", idx)
    if end < 0:
        return
    path.write_text(text[: end + 1] + snippet + text[end + 1 :], encoding="utf-8")


def _bi(en: str, zh: str) -> str:
    return f'<span class="en">{html.escape(en)}</span><span class="cn">{html.escape(zh)}</span>'


def _table(spec: dict | None) -> str:
    if not spec:
        return ""
    fields = list(spec.get("fields") or [])
    head = "".join(f"<th>{html.escape(str(field))}</th>" for field in fields)
    body = []
    for row in spec.get("rows") or []:
        cells = "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields)
        body.append(f"<tr>{cells}</tr>")
    return (
        '<div class="table-scroll"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _matrix(block: dict) -> str:
    labels = block.get("labels") or []
    matrix = block.get("matrix") or []
    if not labels:
        return ""
    head = "<tr><th></th>" + "".join(f"<th>{html.escape(str(label))}</th>" for label in labels) + "</tr>"
    body = []
    for i, label in enumerate(labels):
        cells = [f"<th>{html.escape(str(label))}</th>"]
        for j, value in enumerate(matrix[i]):
            cls = ' class="diag"' if i == j else ""
            cells.append(f"<td{cls}>{value}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return '<div class="table-scroll"><table class="matrix"><thead>' + head + "</thead><tbody>" + "".join(body) + "</tbody></table></div>"


def _section(sec_id: str, en: str, zh: str, guide_en: str, guide_zh: str, inner: str) -> str:
    return (
        f'<section id="{sec_id}"><h2>{_bi(en, zh)}</h2>'
        f'<p class="sec-guide">{_bi(guide_en, guide_zh)}</p>{inner}</section>'
    )


def _verdict_html(verdict: dict) -> str:
    sentences = []
    for en, zh in zip(verdict["sentences_en"], verdict["sentences_zh"]):
        sentences.append(f"<p>{_bi(en, zh)}</p>")
    cards = []
    for module in verdict["modules"]:
        cards.append(
            '<article class="module-card">'
            f"<h3>{_bi(module['title_en'], module['title_zh'])}</h3>"
            f'<p class="badge" data-code="{html.escape(module["code"])}">'
            f"{_bi(module['badge_en'], module['badge_zh'])}</p>"
            f"<p>{_bi(module['detail_en'], module['detail_zh'])}</p>"
            "</article>"
        )
    return (
        '<section id="verdict-card" class="verdict">'
        f"<h2>{_bi(verdict['title_en'], verdict['title_zh'])}</h2>"
        + "".join(sentences)
        + '<div class="module-grid">'
        + "".join(cards)
        + "</div></section>"
    )


def _load_plotly(root: Path) -> str:
    path = Path(root) / "assets" / "plotly-2.32.0.min.js"
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    return "/* plotly asset missing */"


def render_comparison_html(result: dict, verdict: dict, *, title: str, nav_html: str, plotly_js: str) -> str:
    tables = result["tables"]
    single = bool(result["is_single"])
    sections = [
        _section(
            "sec-sites",
            "Sites and call rate",
            "位点与检出率",
            "Each row is one sample. Called genotypes are the sites with a genotype in that report.",
            "每一行是一个样本。已分型数是该报告里写出基因型的位点数。",
            _table(tables.get("sites_callrate.tsv")),
        ),
        _section(
            "sec-king-qp",
            "KING, sample against the panel",
            "KING：样本对面板",
            "Each point compares one panel neighbour. The horizontal axis is KING on 167K and the vertical axis is KING on 8K. The matrix counts relationship classes present on both sides.",
            "每个点是一个面板近邻。横轴是 167K 的 KING，纵轴是 8K 的 KING。矩阵只统计两边都有类别的配对。",
            '<div id="plot-king-qp" class="plot-box"></div>'
            + _matrix(result["confusion_qp"])
            + _table(tables.get("king_query_panel.tsv")),
        ),
    ]
    if not single:
        sections.append(
            _section(
                "sec-king-qq",
                "KING, sample against sample",
                "KING：样本对样本",
                "These pairs are inside the batch. They are omitted when the page has only one sample.",
                "这些配对来自同一批样本。只有一个样本时，这一节不出现。",
                '<div id="plot-king-qq" class="plot-box"></div>'
                + _matrix(result["confusion_qq"])
                + _table(tables.get("king_query_query.tsv")),
            )
        )
    sections.extend(
        [
            _section(
                "sec-topn",
                "Nearest varieties",
                "最近品种",
                "Top-N overlap is the share of panel IDs that appear in both shortlists.",
                "Top-N 重合率是两份短名单里相同面板编号所占的比例。",
                _table(tables.get("topn_overlap.tsv")),
            ),
            _section(
                "sec-pca",
                "PCA displacement",
                "PCA 位移",
                "Arrows run from the 167K position to the 8K position on PC1 and PC2. Distance is the length of that arrow.",
                "箭头从 167K 的 PC1、PC2 位置指向 8K。距离是箭头的长度。",
                '<div id="plot-pca" class="plot-box"></div>' + _table(tables.get("pca_displacement.tsv")),
            ),
            _section(
                "sec-admix",
                "ADMIXTURE",
                "ADMIXTURE",
                "For each K from 2 to 8, Q vectors present on both sides are compared in the stored order. Correlation is the Pearson r of those entries.",
                "K 从 2 到 8，两边都有的 Q 按保存的顺序比较。相关系数是这些数值的 Pearson r。",
                '<div id="plot-admix" class="plot-box"></div>' + _table(tables.get("q_summary.tsv")),
            ),
            _section(
                "sec-hits",
                "Clone and parent-offspring hits",
                "克隆与亲子命中",
                "A hit is a pair classed as Identical or parent-offspring. Only 8K means the 167K report did not make that call.",
                "命中是被判为克隆（Identical）或亲子的配对。仅 8K 表示 167K 报告没有这样判。",
                _table(tables.get("clone_po_hits.tsv")),
            ),
            _section(
                "sec-traits",
                "Trait sites and selection windows",
                "性状位点与选择窗口",
                "Trait rows come from each report. A selection window counts as covered when its stored site count is above zero.",
                "性状行来自每份报告。选择窗口的保存位点数大于 0 时，算作有覆盖。",
                _table(tables.get("traits.tsv")) + _table(tables.get("selection_windows.tsv")),
            ),
        ]
    )
    plot_json = json.dumps(result["plot"], ensure_ascii=False)
    page = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)} 167K vs 8K</title>
<script>
(function() {{
  var mode = 'system';
  try {{ mode = localStorage.getItem('ga-theme') || 'system'; }} catch (err) {{}}
  if (mode !== 'light' && mode !== 'dark') mode = 'system';
  var resolved = mode;
  if (mode === 'system') {{
    var dark = false;
    try {{ dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; }} catch (err) {{}}
    resolved = dark ? 'dark' : 'light';
  }}
  document.documentElement.setAttribute('data-theme-mode', mode);
  document.documentElement.setAttribute('data-theme', resolved);
  var lang = '';
  try {{ lang = localStorage.getItem('ga-lang') || ''; }} catch (err) {{}}
  if (!lang) {{
    try {{
      var navLang = navigator.language || '';
      lang = String(navLang).toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en';
    }} catch (err) {{ lang = 'en'; }}
  }} else {{
    lang = String(lang).toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en';
  }}
  document.documentElement.setAttribute('data-lang', lang);
  document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-CN' : 'en');
  window.setTheme = function(next) {{
    next = (next === 'light' || next === 'dark') ? next : 'system';
    var use = next;
    if (next === 'system') {{
      var prefersDark = false;
      try {{ prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; }} catch (err) {{}}
      use = prefersDark ? 'dark' : 'light';
    }}
    document.documentElement.setAttribute('data-theme-mode', next);
    document.documentElement.setAttribute('data-theme', use);
    try {{ localStorage.setItem('ga-theme', next); }} catch (err) {{}}
  }};
  window.setLang = function(next) {{
    next = String(next || 'en').toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en';
    document.documentElement.setAttribute('data-lang', next);
    document.documentElement.setAttribute('lang', next === 'zh' ? 'zh-CN' : 'en');
    try {{ localStorage.setItem('ga-lang', next); }} catch (err) {{}}
  }};
}})();
</script>
<style>
:root {{ color-scheme: light; --bg:#f6f7f9; --card:#fff; --ink:#1c2430; --muted:#5c6b7a; --line:#d5dde6; --accent:#9f1239; }}
:root[data-theme="dark"] {{ color-scheme: dark; --bg:#12161c; --card:#1c2430; --ink:#e8eef5; --muted:#a8b6c4; --line:#314052; --accent:#fb7185; }}
html:not([data-lang="zh"]) .cn {{ display:none !important; }}
html[data-lang="zh"] .en {{ display:none !important; }}
body {{ margin:0; font:16px/1.55 "Source Han Sans SC","Noto Sans SC","PingFang SC",sans-serif; background:var(--bg); color:var(--ink); }}
.ga-report-nav {{ display:flex; gap:8px; flex-wrap:wrap; padding:12px 20px; background:var(--card); border-bottom:1px solid var(--line); position:sticky; top:0; }}
.ga-report-nav a {{ color:var(--ink); text-decoration:none; border:1px solid var(--line); border-radius:999px; padding:4px 10px; font-size:13px; }}
.ga-report-nav a[aria-current="true"] {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.toolbar {{ display:flex; gap:8px; padding:8px 20px; }}
.toolbar button {{ border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:6px; padding:4px 8px; }}
main {{ padding:8px 20px 40px; max-width:1100px; }}
.verdict, section, .module-card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; margin:12px 0; }}
.module-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; }}
.badge {{ display:inline-block; font-weight:700; color:var(--accent); }}
.badge[data-code="insufficient"] {{ color:var(--muted); font-weight:600; }}
h2 {{ font-size:1.25rem; margin:0 0 8px; }}
h3 {{ font-size:1rem; margin:0 0 6px; }}
.sec-guide {{ color:var(--muted); font-size:0.92rem; }}
.plot-box {{ height:360px; margin:8px 0; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th, td {{ border-bottom:1px solid var(--line); padding:4px 6px; text-align:left; }}
.table-scroll {{ overflow:auto; max-height:420px; }}
td.diag {{ font-weight:700; }}
</style>
<script>{plotly_js}</script>
</head><body>
{nav_html}
<div class="toolbar">
  <button type="button" class="lang-choice" onclick="setLang('zh')">中文</button>
  <button type="button" class="lang-choice" onclick="setLang('en')">English</button>
  <button type="button" class="theme-choice" onclick="setTheme('light')">Light</button>
  <button type="button" class="theme-choice" onclick="setTheme('dark')">Dark</button>
</div>
<main>
{_verdict_html(verdict)}
{''.join(sections)}
</main>
<script>
(function() {{
  var plot = {plot_json};
  function draw() {{
    if (!window.Plotly) return;
    var pca = document.getElementById('plot-pca');
    if (pca && plot.pca) {{
      var showLegend = plot.pcaShowLegend !== false && plot.pca.length <= 12;
      var arrows = plot.pca.map(function(row) {{
        return {{ type:'scatter', mode:'lines+markers', x:[row._x0, row._x1], y:[row._y0, row._y1], name:row.sample, hovertext:row.sample, showlegend:showLegend }};
      }});
      Plotly.newPlot(pca, arrows, {{ margin:{{ t:24, r:showLegend ? 16 : 24, b:40, l:48 }}, showlegend:showLegend, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)' }}, {{ responsive:true, displaylogo:false }});
    }}
    function king(id, rows) {{
      var node = document.getElementById(id);
      if (!node || !rows || !rows.length) return;
      Plotly.newPlot(node, [{{ type:'scatter', mode:'markers', x:rows.map(function(r) {{ return r.x; }}), y:rows.map(function(r) {{ return r.y; }}), text:rows.map(function(r) {{ return r.hover; }}) }}], {{ xaxis:{{ title:'167K KING' }}, yaxis:{{ title:'8K KING' }}, margin:{{ t:24 }}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)' }}, {{ responsive:true, displaylogo:false }});
    }}
    king('plot-king-qp', plot.kingQp);
    king('plot-king-qq', plot.kingQq);
  }}
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', draw);
  else draw();
}})();
</script>
</body></html>
"""
    searchable = page.replace(plotly_js, "", 1)
    for word in _BANNED:
        if word in searchable:
            raise RuntimeError(f"comparison HTML contains banned wording: {word}")
    return page


def _write_tables(result: dict, tsv_dir: Path) -> None:
    tsv_dir = Path(tsv_dir)
    tsv_dir.mkdir(parents=True, exist_ok=True)
    for name, spec in (result.get("tables") or {}).items():
        dest = tsv_dir / name
        if dest.exists():
            continue
        with dest.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(spec.get("fields") or []),
                delimiter="\t",
                lineterminator="\n",
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in spec.get("rows") or []:
                writer.writerow(row)


def build_comparison_report(
    payload_167k: dict,
    payload_8k: dict,
    out_html,
    *,
    root,
    title_target: str,
    tsv_dir=None,
    nav_html: str = "",
) -> dict:
    """Write ``{{target}}.167k_vs_8k.compare.html`` and return the verdict."""
    result = compare_payloads(payload_167k, payload_8k)
    is_batch = len(result["ids"]) > 1
    verdict = synthesize_verdict(result["metrics"], is_batch)
    page = render_comparison_html(
        result,
        verdict,
        title=str(title_target),
        nav_html=nav_html or "",
        plotly_js=_load_plotly(Path(root)),
    )
    out = Path(out_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    if tsv_dir:
        _write_tables(result, Path(tsv_dir))
    return {
        "html": out,
        "verdict": verdict,
        "metrics": result["metrics"],
        "is_batch": is_batch,
        "n_query": len(result["ids"]),
    }


def write_demo_entry_html(
    out_html,
    *,
    verdict: dict,
    nav_html: str = "",
    cards: list[dict] | None = None,
) -> Path:
    """Bilingual entry page that links the 167K report, the 8K report, and the comparison."""
    cards = cards or [
        {
            "href": "ramos2019_np.batch.report.html",
            "title_en": "GrapeAncestry 167K report",
            "title_zh": "GrapeAncestry 167K 报告",
            "body_en": "Full 167,433-site capture report. This file is the v1.1 archive.",
            "body_zh": "完整的 167,433 位点捕获报告。这一份是 v1.1 存档。",
        },
        {
            "href": "ramos2019_np.8k.batch.report.html",
            "title_en": "GrapeReseq 8K report",
            "title_zh": "GrapeReseq 8K 报告",
            "body_en": "The same 28 samples on the 8,044 sites shared with the capture panel.",
            "body_zh": "同样 28 个样本，用与捕获面板共有的 8,044 个位点。",
        },
        {
            "href": "ramos2019_np.167k_vs_8k.compare.html",
            "title_en": "167K vs 8K comparison",
            "title_zh": "167K 与 8K 比较",
            "body_en": "Side-by-side numbers and a verdict written from this run.",
            "body_zh": "两边的数字对照，以及根据这次结果写出的结论。",
        },
    ]
    card_html = []
    for card in cards:
        card_html.append(
            '<a class="entry-card" href="'
            + html.escape(str(card["href"]), quote=True)
            + '"><h2>'
            + _bi(str(card["title_en"]), str(card["title_zh"]))
            + "</h2><p>"
            + _bi(str(card["body_en"]), str(card["body_zh"]))
            + "</p></a>"
        )
    sentences = []
    for en, zh in zip(verdict.get("sentences_en") or [], verdict.get("sentences_zh") or []):
        sentences.append(f"<p>{_bi(str(en), str(zh))}</p>")
    title_en = html.escape(str(verdict.get("title_en") or ""))
    title_zh = html.escape(str(verdict.get("title_zh") or ""))
    page = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GrapeAncestry reports</title>
<script>
(function() {{
  var mode = 'system';
  try {{ mode = localStorage.getItem('ga-theme') || 'system'; }} catch (err) {{}}
  if (mode !== 'light' && mode !== 'dark') mode = 'system';
  var resolved = mode === 'system'
    ? ((window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light')
    : mode;
  document.documentElement.setAttribute('data-theme', resolved);
  var lang = '';
  try {{ lang = localStorage.getItem('ga-lang') || ''; }} catch (err) {{}}
  if (!lang) {{
    lang = String(navigator.language || '').toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en';
  }} else {{
    lang = String(lang).toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en';
  }}
  document.documentElement.setAttribute('data-lang', lang);
  document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-CN' : 'en');
  window.setTheme = function(next) {{
    next = (next === 'light' || next === 'dark') ? next : 'system';
    var use = next === 'system'
      ? ((window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light')
      : next;
    document.documentElement.setAttribute('data-theme', use);
    try {{ localStorage.setItem('ga-theme', next); }} catch (err) {{}}
  }};
  window.setLang = function(next) {{
    next = String(next || 'en').toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en';
    document.documentElement.setAttribute('data-lang', next);
    document.documentElement.setAttribute('lang', next === 'zh' ? 'zh-CN' : 'en');
    try {{ localStorage.setItem('ga-lang', next); }} catch (err) {{}}
  }};
}})();
</script>
<style>
:root {{ color-scheme: light; --bg:#f7f9fc; --card:#fff; --ink:#172033; --muted:#526079; --line:#cbd5e1; --accent:#b4234b; }}
:root[data-theme="dark"] {{ color-scheme: dark; --bg:#0b0f19; --card:#131b2e; --ink:#e2e8f0; --muted:#a8b3c7; --line:#2b3b59; --accent:#f06b84; }}
html:not([data-lang="zh"]) .cn {{ display:none !important; }}
html[data-lang="zh"] .en {{ display:none !important; }}
body {{ margin:0; font:16px/1.55 system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--ink); }}
.ga-report-nav {{ display:flex; gap:8px; flex-wrap:wrap; padding:12px 20px; background:var(--card); border-bottom:1px solid var(--line); }}
.ga-report-nav a {{ color:var(--ink); text-decoration:none; border:1px solid var(--line); border-radius:999px; padding:4px 10px; font-size:13px; }}
.ga-report-nav a[aria-current="true"] {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.toolbar {{ display:flex; gap:8px; padding:8px 20px; }}
.toolbar button {{ border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:6px; padding:4px 8px; }}
main {{ max-width:980px; margin:0 auto; padding:8px 20px 48px; }}
h1 {{ font-size:1.6rem; margin:12px 0; }}
.note {{ color:var(--muted); }}
.verdict {{ background:var(--card); border:1px solid var(--line); border-left:3px solid var(--accent); border-radius:12px; padding:16px 18px; margin:16px 0; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; }}
.entry-card {{ display:block; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; color:inherit; text-decoration:none; }}
.entry-card:hover {{ border-color:var(--accent); }}
.entry-card h2 {{ font-size:1.05rem; margin:0 0 8px; }}
</style>
</head><body>
{nav_html}
<div class="toolbar">
  <button type="button" onclick="setLang('zh')">中文</button>
  <button type="button" onclick="setLang('en')">English</button>
  <button type="button" onclick="setTheme('light')">Light</button>
  <button type="button" onclick="setTheme('dark')">Dark</button>
</div>
<main>
<h1>{_bi("GrapeAncestry reports", "GrapeAncestry 报告")}</h1>
<p class="note">{_bi(
    "The 167K report linked below is the v1.1 archive. That file is unchanged and has no top navigation bar. The 8K report and the comparison page are the v1.2 pages.",
    "下面链到的 167K 报告是 v1.1 存档。那一份文件保持原样，页顶没有导航条。8K 报告和比较页是 v1.2 的新页面。",
)}</p>
<section class="verdict" id="entry-verdict">
<h2><span class="en">{title_en}</span><span class="cn">{title_zh}</span></h2>
{''.join(sentences)}
</section>
<div class="cards">
{''.join(card_html)}
</div>
</main>
</body></html>
"""
    for word in _BANNED:
        if word in page:
            raise RuntimeError(f"entry page contains banned wording: {word}")
    dest = Path(out_html)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding="utf-8")
    return dest
