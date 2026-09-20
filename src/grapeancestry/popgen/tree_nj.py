"""IBS-distance Neighbor-Joining tree (Italy dashboard style, pure numpy).

Italy grouping_663: PLINK --distance → ape::nj(). Here: dosage IBS → NJ.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class NJTree:
    ids: list[str]
    children: dict[int, tuple[int, int]]
    lengths: dict[tuple[int, int], float]
    root: int


def ibs_distance_to_rows(query: np.ndarray, mat: np.ndarray) -> np.ndarray:
    """Distance from one genotype vector to every row of ``mat`` (1 − genotype identity)."""
    a = np.asarray(query, dtype=np.int8).reshape(-1)
    g = np.asarray(mat, dtype=np.int8)
    if g.ndim != 2 or a.shape[0] != g.shape[1]:
        raise ValueError("query/mat site length mismatch")
    ok = (a >= 0) & (g >= 0)
    n_ok = ok.sum(axis=1)
    n_eq = ((g == a) & ok).sum(axis=1)
    sim = np.divide(n_eq, n_ok, out=np.zeros(g.shape[0], dtype=float), where=n_ok > 0)
    return np.where(n_ok > 0, np.maximum(1.0 - sim, 0.0), 1.0)


def ibs_distance_matrix(mat: np.ndarray) -> np.ndarray:
    """Pairwise 1 − genotype-identity via blocked Gram products (same as ibs_similarity)."""
    g = np.asarray(mat, dtype=np.int8)
    n, p = g.shape
    if n == 0:
        return np.zeros((0, 0), dtype=float)
    num = np.zeros((n, n), dtype=np.float64)
    den = np.zeros((n, n), dtype=np.float64)
    block = 4096
    for c0 in range(0, p, block):
        sl = g[:, c0 : c0 + block]
        called = (sl >= 0).astype(np.float64)
        den += called @ called.T
        for val in (0, 1, 2):
            m = (sl == val).astype(np.float64)
            num += m @ m.T
    with np.errstate(invalid="ignore", divide="ignore"):
        sim = np.divide(num, den, out=np.zeros_like(num), where=den > 0)
    D = np.where(den > 0, np.maximum(1.0 - sim, 0.0), 1.0)
    np.fill_diagonal(D, 0.0)
    return 0.5 * (D + D.T)


def neighbor_joining(D0: np.ndarray) -> tuple[dict[int, tuple[int, int]], dict[tuple[int, int], float], int]:
    """Saitou–Nei NJ (1987, doi:10.1093/oxfordjournals.molbev.a040454) on a numpy distance matrix."""
    D0 = np.asarray(D0, dtype=float)
    n = int(D0.shape[0])
    if n < 3:
        raise ValueError("need ≥3 tips for NJ")
    n_max = 2 * n - 1
    D = np.zeros((n_max, n_max), dtype=float)
    D[:n, :n] = D0
    active = np.arange(n, dtype=int)
    next_id = n
    children: dict[int, tuple[int, int]] = {}
    lengths: dict[tuple[int, int], float] = {}

    def edge(a: int, b: int, L: float) -> None:
        lengths[(min(int(a), int(b)), max(int(a), int(b)))] = float(max(L, 0.0))

    while active.size > 2:
        m = int(active.size)
        sub = D[np.ix_(active, active)]
        r = sub.sum(axis=1)
        q = (m - 2) * sub - r[:, None] - r[None, :]
        iu, ju = np.triu_indices(m, k=1)
        kmin = int(np.argmin(q[iu, ju]))
        ii = int(iu[kmin])
        jj = int(ju[kmin])
        i = int(active[ii])
        j = int(active[jj])
        dij = float(D[i, j])
        if m == 2:
            li = lj = dij / 2.0
        else:
            li = 0.5 * dij + (float(r[ii]) - float(r[jj])) / (2.0 * (m - 2))
            lj = dij - li
        u = next_id
        next_id += 1
        children[u] = (i, j)
        edge(u, i, li)
        edge(u, j, lj)
        rest = active[(active != i) & (active != j)]
        if rest.size:
            duk = 0.5 * (D[i, rest] + D[j, rest] - dij)
            D[u, rest] = duk
            D[rest, u] = duk
        D[u, u] = 0.0
        active = np.concatenate([rest, np.asarray([u], dtype=int)])

    a, b = int(active[0]), int(active[1])
    u = next_id
    children[u] = (a, b)
    edge(u, a, float(D[a, b]) / 2.0)
    edge(u, b, float(D[a, b]) / 2.0)
    return children, lengths, u


def to_newick(tree: NJTree) -> str:
    """Newick string (Saitou–Nei tree). Tip names are sample IDs."""

    def fmt(x: float) -> str:
        return f"{max(x, 0.0):.6f}"

    def walk(node: int) -> str:
        if node < len(tree.ids):
            return str(tree.ids[node])
        left, right = tree.children[node]
        bl = tree.lengths.get((min(node, left), max(node, left)), 0.0)
        br = tree.lengths.get((min(node, right), max(node, right)), 0.0)
        return f"({walk(left)}:{fmt(bl)},{walk(right)}:{fmt(br)})"

    return walk(tree.root) + ";"


def build_nj_tree(ids: list[str], mat: np.ndarray, D: np.ndarray | None = None) -> NJTree:
    if len(ids) != mat.shape[0]:
        raise ValueError("ids/mat length mismatch")
    if len(ids) < 3:
        raise ValueError("need ≥3 tips for NJ")
    if D is None:
        D = ibs_distance_matrix(mat)
    if D.shape != (len(ids), len(ids)):
        raise ValueError("D shape must be n×n for ids")
    children, lengths, root = neighbor_joining(D)
    return NJTree(ids=list(ids), children=children, lengths=lengths, root=root)


def all_tips_for_tree(
    ref_ids: list[str],
    ref_mat: np.ndarray,
    query: np.ndarray,
    query_id: str,
) -> tuple[list[str], np.ndarray]:
    """Every panel sample + query. An in-panel query is not duplicated."""
    q = np.asarray(query, dtype=float).reshape(-1)
    if query_id in ref_ids:
        ids = list(ref_ids)
        out = np.array(ref_mat, copy=True, dtype=float)
        out[ids.index(query_id)] = q
        return ids, out
    return list(ref_ids) + [query_id], np.vstack([np.asarray(ref_mat, dtype=float), q.reshape(1, -1)])


def assemble_tree_distance(
    ref_ids: list[str],
    ref_mat: np.ndarray,
    query: np.ndarray,
    query_id: str,
    panel_d: np.ndarray,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """ids, genotype matrix, and full IBS distance including the query."""
    ids, tree_mat = all_tips_for_tree(ref_ids, ref_mat, query, query_id)
    n = len(ref_ids)
    d_q = ibs_distance_to_rows(query, ref_mat)
    if query_id in ref_ids:
        D = np.array(panel_d, copy=True, dtype=float)
        qi = ref_ids.index(query_id)
        D[qi, :] = d_q
        D[:, qi] = d_q
        D[qi, qi] = 0.0
        return ids, tree_mat, D
    D = np.zeros((n + 1, n + 1), dtype=float)
    D[:n, :n] = panel_d
    D[n, :n] = d_q
    D[:n, n] = d_q
    return ids, tree_mat, D


def load_or_compute_panel_ibs_d(
    path: Path,
    ids: list[str],
    mat: np.ndarray,
) -> np.ndarray:
    """Cached 2449×2449 IBS distance (query-independent)."""
    path = Path(path)
    n = len(ids)
    if path.exists():
        try:
            z = np.load(path, allow_pickle=True)
            cached_ids = [str(x) for x in z["ids"].tolist()]
            D = np.asarray(z["D"], dtype=float)
            n_sites = int(z["n_sites"]) if "n_sites" in z.files else mat.shape[1]
            if cached_ids == list(ids) and D.shape == (n, n) and n_sites == int(mat.shape[1]):
                return D
        except (OSError, ValueError, KeyError):
            pass
    D = ibs_distance_matrix(mat)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        D=D,
        ids=np.asarray(ids, dtype=object),
        n_sites=np.asarray(mat.shape[1]),
    )
    return D


def subsample_for_tree(
    ref_ids: list[str],
    ref_mat: np.ndarray,
    query: np.ndarray,
    query_id: str,
    groups: list[str],
    *,
    per_group: int = 6,
    max_tips: int = 80,
    seed: int = 0,
) -> tuple[list[str], np.ndarray]:
    rng = np.random.default_rng(seed)
    by_g: dict[str, list[int]] = {}
    for i, g in enumerate(groups):
        by_g.setdefault(g or "NA", []).append(i)
    chosen: list[int] = []
    for g, idxs in sorted(by_g.items(), key=lambda x: -len(x[1])):
        take = min(per_group, len(idxs))
        if take:
            pick = rng.choice(idxs, size=take, replace=False).tolist()
            chosen.extend(pick)
        if len(chosen) >= max_tips - 1:
            break
    chosen = chosen[: max_tips - 1]
    ids = [ref_ids[i] for i in chosen] + [query_id]
    mat = np.vstack([ref_mat[chosen], query.reshape(1, -1)])
    return ids, mat


def tip_xy_rectangular(tree: NJTree) -> dict[str, tuple[float, float]]:
    n_tips = len(tree.ids)
    tip_order: list[int] = []

    def leaf_order(node: int) -> None:
        if node < n_tips:
            tip_order.append(node)
            return
        L, R = tree.children[node]
        leaf_order(L)
        leaf_order(R)

    leaf_order(tree.root)
    depth: dict[int, float] = {tree.root: 0.0}

    def assign_depth(node: int) -> None:
        if node < n_tips:
            return
        L, R = tree.children[node]
        for ch in (L, R):
            key = (min(node, ch), max(node, ch))
            depth[ch] = depth[node] + tree.lengths.get(key, 0.05)
            assign_depth(ch)

    assign_depth(tree.root)
    y_of = {tip: float(i) for i, tip in enumerate(tip_order)}
    return {tree.ids[i]: (depth.get(i, 0.0), y_of[i]) for i in range(n_tips)}


def tree_edges_rectangular(tree: NJTree) -> list[tuple[float, float, float, float]]:
    n_tips = len(tree.ids)
    tip_xy = tip_xy_rectangular(tree)
    depth: dict[int, float] = {tree.root: 0.0}

    def assign_depth(node: int) -> None:
        if node < n_tips:
            return
        L, R = tree.children[node]
        for ch in (L, R):
            key = (min(node, ch), max(node, ch))
            depth[ch] = depth[node] + tree.lengths.get(key, 0.05)
            assign_depth(ch)

    assign_depth(tree.root)
    y_of = {i: tip_xy[tree.ids[i]][1] for i in range(n_tips)}
    y_node: dict[int, float] = dict(y_of)

    def set_y(node: int) -> float:
        if node in y_node:
            return y_node[node]
        L, R = tree.children[node]
        y_node[node] = 0.5 * (set_y(L) + set_y(R))
        return y_node[node]

    set_y(tree.root)
    segs: list[tuple[float, float, float, float]] = []

    def walk(node: int) -> None:
        if node < n_tips:
            return
        L, R = tree.children[node]
        x = depth[node]
        y = y_node[node]
        for ch in (L, R):
            segs.append((x, y, x, y_node[ch]))
            segs.append((x, y_node[ch], depth[ch], y_node[ch]))
            walk(ch)

    walk(tree.root)
    return segs


def _leaf_order(tree: NJTree) -> list[int]:
    n_tips = len(tree.ids)
    order: list[int] = []

    def walk(node: int) -> None:
        if node < n_tips:
            order.append(node)
            return
        left, right = tree.children[node]
        walk(left)
        walk(right)

    walk(tree.root)
    return order


def _node_depths(tree: NJTree) -> dict[int, float]:
    n_tips = len(tree.ids)
    depth: dict[int, float] = {tree.root: 0.0}

    def walk(node: int) -> None:
        if node < n_tips:
            return
        left, right = tree.children[node]
        for ch in (left, right):
            key = (min(node, ch), max(node, ch))
            depth[ch] = depth[node] + tree.lengths.get(key, 0.05)
            walk(ch)

    walk(tree.root)
    return depth


def _polar_layout(tree: NJTree) -> tuple[dict[int, float], dict[int, float]]:
    """Equal-angle circular phylogram: θ from leaf order, r from root path length."""
    n_tips = len(tree.ids)
    order = _leaf_order(tree)
    pos = {tip: i for i, tip in enumerate(order)}
    first: dict[int, int] = {}
    last: dict[int, int] = {}

    def span(node: int) -> None:
        if node < n_tips:
            first[node] = last[node] = pos[node]
            return
        left, right = tree.children[node]
        span(left)
        span(right)
        first[node] = min(first[left], first[right])
        last[node] = max(last[left], last[right])

    span(tree.root)
    depth = _node_depths(tree)
    theta: dict[int, float] = {}
    radius: dict[int, float] = {}
    two_pi = 2.0 * np.pi
    n = max(n_tips, 1)
    nodes = set(range(n_tips)) | set(tree.children) | {tree.root}
    for node in nodes:
        mid = 0.5 * (first[node] + last[node])
        theta[node] = two_pi * mid / n
        radius[node] = float(depth.get(node, 0.0))
    return theta, radius


def _polar_xy(theta: float, radius: float) -> tuple[float, float]:
    return float(radius * np.sin(theta)), float(radius * np.cos(theta))


def tip_xy_circular(tree: NJTree) -> dict[str, tuple[float, float]]:
    theta, radius = _polar_layout(tree)
    return {tree.ids[i]: _polar_xy(theta[i], radius[i]) for i in range(len(tree.ids))}


def tree_edges_circular(tree: NJTree, n_arc: int = 10) -> list[tuple[float, float, float, float]]:
    """Parent arc at r_parent, then a radial spoke to the child."""
    theta, radius = _polar_layout(tree)
    n_tips = len(tree.ids)
    segs: list[tuple[float, float, float, float]] = []
    steps = max(4, int(n_arc))

    def walk(node: int) -> None:
        if node < n_tips:
            return
        left, right = tree.children[node]
        t0, r0 = theta[node], radius[node]
        for ch in (left, right):
            t1, r1 = theta[ch], radius[ch]
            prev = _polar_xy(t0, r0)
            dth = t1 - t0
            if dth > np.pi:
                dth -= 2 * np.pi
            elif dth < -np.pi:
                dth += 2 * np.pi
            for s in range(1, steps + 1):
                tt = t0 + dth * (s / steps)
                cur = _polar_xy(tt, r0)
                segs.append((prev[0], prev[1], cur[0], cur[1]))
                prev = cur
            end = _polar_xy(t1, r1)
            segs.append((prev[0], prev[1], end[0], end[1]))
            walk(ch)

    walk(tree.root)
    return segs
