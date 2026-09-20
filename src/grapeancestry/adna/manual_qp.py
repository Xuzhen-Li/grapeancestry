"""Manual Q edits on aligned C1…CK (display / experiment family).

Does not overwrite frozen panel167k_nogwas Q/P. Column indices are canonical:
C1 blue, C2 red, C6 pink, C7 yellow, C9 green (COMPONENT_COLORS).
P is only column-permuted to the same C order; row-wise Q edits cannot be
represented as a single P column swap.
"""
from __future__ import annotations

import hashlib

import numpy as np

# 0-based canonical columns after sequential_column_orders_core
C_BLUE = 0
C_RED = 1
C_PINK = 5
C_YELLOW = 6
C_GREEN = 8

# Query IDs whose projection uses freeze P with C6↔C7 swapped (k≥7).
# Freeze files on disk stay untouched. Equivalent to swapping those Q columns.
PINK_YELLOW_P_SWAP_IDS = frozenset({"Ages"})


def sample_swaps_pink_yellow(sample: str) -> bool:
    return str(sample) in PINK_YELLOW_P_SWAP_IDS


def swap_pink_yellow_columns(arr: np.ndarray) -> np.ndarray:
    """Swap canonical C6 (pink) and C7 (yellow) on a Q or P matrix."""
    out = np.asarray(arr, float).copy()
    if out.ndim != 2 or out.shape[1] <= C_YELLOW:
        return out
    a = out[:, C_PINK].copy()
    out[:, C_PINK] = out[:, C_YELLOW]
    out[:, C_YELLOW] = a
    return out


def projection_p_for_sample(P: np.ndarray, k: int, sample: str) -> np.ndarray:
    """P used for one sample's -P / NNLS. Does not write freeze P."""
    arr = np.asarray(P, float)
    if k >= 7 and sample_swaps_pink_yellow(sample):
        return swap_pink_yellow_columns(arr)
    return arr


def blue_to_pink_frac(iid: str) -> float:
    """Per-sample fraction of blue moved to pink. Not a constant 1/2."""
    h = hashlib.sha256(f"manual-qp-blue-pink:{iid}".encode()).digest()
    u = int.from_bytes(h[:8], "little") / float(2**64)
    return 0.12 + 0.76 * u


def apply_manual_q_edits(
    q: np.ndarray,
    grps: np.ndarray,
    k: int,
    ids: list[str] | np.ndarray | None = None,
) -> np.ndarray:
    """Apply the K=7–10 group-wise Q edits. Rows still sum to 1."""
    if q.ndim != 2 or q.shape[1] != k:
        raise ValueError(f"Q shape {q.shape} vs K={k}")
    if len(grps) != q.shape[0]:
        raise ValueError("grps length must match Q rows")
    out = np.asarray(q, float).copy()
    grps = np.asarray(grps)
    if ids is None:
        id_arr = np.array([str(i) for i in range(q.shape[0])])
    else:
        id_arr = np.asarray(ids, str)
        if len(id_arr) != q.shape[0]:
            raise ValueError("ids length must match Q rows")

    if k >= 7:
        if q.shape[1] <= C_YELLOW:
            raise ValueError(f"K={k} needs C7 (yellow)")
        m = grps == "CG1"
        if m.any():
            a = out[m, C_RED].copy()
            b = out[m, C_YELLOW].copy()
            out[m, C_RED] = b
            out[m, C_YELLOW] = a
        m5 = grps == "CG5"
        if m5.any():
            a = out[m5, C_PINK].copy()
            b = out[m5, C_YELLOW].copy()
            out[m5, C_PINK] = b
            out[m5, C_YELLOW] = a

    if 7 <= k <= 9:
        if q.shape[1] <= C_PINK:
            raise ValueError(f"K={k} needs C6 (pink)")
        m = np.isin(grps, ["WWE2", "W-Ad"])
        if m.any():
            frac = np.array([blue_to_pink_frac(s) for s in id_arr[m]], float)
            moved = frac * out[m, C_BLUE]
            out[m, C_BLUE] = out[m, C_BLUE] - moved
            out[m, C_PINK] = out[m, C_PINK] + moved

    if k == 10:
        if q.shape[1] <= C_GREEN:
            raise ValueError("K=10 needs C9 (green)")
        m = np.isin(grps, ["WWE2", "W-Ad"])
        if m.any():
            a = out[m, C_PINK].copy()
            b = out[m, C_GREEN].copy()
            out[m, C_PINK] = b
            out[m, C_GREEN] = a

    tot = out.sum(axis=1, keepdims=True)
    tot = np.clip(tot, 1e-12, None)
    out = out / tot
    return out


def apply_q_dict_edits(
    q: dict[str, float],
    k: int,
    sample: str,
    grp: str = "",
) -> dict[str, float]:
    """Same row rules as ``apply_manual_q_edits`` for one K1..Kk dict."""
    vec = np.array([float(q.get(f"K{j + 1}", 0.0)) for j in range(k)], float)
    if vec.shape[0] != k:
        return q
    out = apply_manual_q_edits(vec.reshape(1, -1), np.array([grp]), k, ids=[sample])[0]
    return {f"K{j + 1}": float(out[j]) for j in range(k)}


def permute_columns(arr: np.ndarray, order: list[int]) -> np.ndarray:
    """Reorder K columns of Q (n×K) or P (m×K) to canonical C1…CK."""
    order_a = np.asarray(order, int)
    if arr.ndim != 2 or arr.shape[1] != len(order_a):
        raise ValueError(f"column order {order} vs shape {arr.shape}")
    if sorted(order_a.tolist()) != list(range(arr.shape[1])):
        raise ValueError(f"order is not a permutation: {order}")
    return np.asarray(arr)[:, order_a]
