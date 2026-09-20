#!/usr/bin/env python3
"""Science-style K=8 (and K=2–8) check plots for panel167k_nogwas.

Does not rewrite Q/P. Uses in-memory Science colour permutation from the
panel167k manifest. Compare against science_core_ld_sort on the same
sample order (REPORT_GRP_ORDER, then ID).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from grapeancestry.adna.admixture import (
    PANEL167K_NOGWAS_FAMILY,
    SCIENCE_K8_COLORS,
    SCIENCE_K8_GROUP_ANCHORS,
    SCIENCE_K8_LABELS,
    SCIENCE_RUN_FAMILY,
    assign_qk_columns_to_k8,
    component_labels_colors,
    id_path_for_family,
    infer_science_k8_permutation,
    k_plot_order_from_k8,
    load_admixture_matrix,
    plot_order_indices,
)
from grapeancestry.adna.grp_order import REPORT_GRP_ORDER

SUITE = Path(__file__).resolve().parents[1]
ADMIX = SUITE / "data" / "panel" / "admixture"
INFO = SUITE / "data" / "panel" / "2449.info"
FIT = SUITE / "results" / "admixture_fit"
K9_NEW_COLOR = "#1a7a4c"
K9_LABELS = SCIENCE_K8_LABELS + ["K9-new"]
K9_COLORS = SCIENCE_K8_COLORS + [K9_NEW_COLOR]

# Grp names that share a named K=8 ancestry (Fig. 1D / fig. S8).
GROUP_CANONICAL_COL: dict[str, int] = {
    grp: col for grp, col in SCIENCE_K8_GROUP_ANCHORS
}
GROUP_CANONICAL_COL["CG1"] = 1  # same colour as WEE1 / Syl-E1
GROUP_CANONICAL_COL["CG2"] = 5  # same colour as WEE2 / Syl-E2


def load_grp(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    with path.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            row = dict(zip(hdr, line.rstrip().split("\t")))
            meta[row["ID"]] = row.get("Grp", "")
    return meta


def hex_to_rgb(color: str) -> np.ndarray:
    h = (color or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) < 6:
        h = "888888"
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=float) / 255.0


def q_strip_image(q: np.ndarray, colors: list[str], height: int = 48) -> np.ndarray:
    n, k = q.shape
    rgb = np.stack(
        [hex_to_rgb(colors[j] if j < len(colors) else "#888888") for j in range(k)]
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
        for j, y1 in enumerate(edges):
            if y1 > y0:
                img[y0:y1, i] = rgb[j]
            y0 = max(y0, y1)
    return img


def _by_grp(ids: list[str], meta: dict[str, str]) -> tuple[dict[str, list[int]], list[int]]:
    by_grp: dict[str, list[int]] = {g: [] for g in REPORT_GRP_ORDER}
    extra: list[int] = []
    for i, sid in enumerate(ids):
        g = meta.get(sid, "")
        if g in by_grp:
            by_grp[g].append(i)
        else:
            extra.append(i)
    return by_grp, extra


def sample_order_id(ids: list[str], meta: dict[str, str]) -> list[int]:
    """Same person x-position across run families (Grp, then ID)."""
    by_grp, extra = _by_grp(ids, meta)
    out: list[int] = []
    for g in REPORT_GRP_ORDER:
        out.extend(sorted(by_grp[g], key=lambda i: ids[i]))
    out.extend(sorted(extra, key=lambda i: ids[i]))
    return out


def sample_order_q(ids: list[str], meta: dict[str, str], qk8: np.ndarray) -> list[int]:
    """REPORT_GRP_ORDER; within group, sort by that group's named K=8 Q."""
    by_grp, extra = _by_grp(ids, meta)
    out: list[int] = []
    for g in REPORT_GRP_ORDER:
        idxs = by_grp[g]
        if not idxs:
            continue
        col = GROUP_CANONICAL_COL.get(g)
        if col is not None:
            idxs = sorted(idxs, key=lambda i: (-float(qk8[i, col]), ids[i]))
        else:
            idxs = sorted(idxs, key=lambda i: ids[i])
        out.extend(idxs)
    out.extend(sorted(extra, key=lambda i: ids[i]))
    return out


def group_blocks(ids: list[str], meta: dict[str, str], col_index: list[int]) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    for g in REPORT_GRP_ORDER:
        n = sum(1 for i in col_index if meta.get(ids[i]) == g)
        if n:
            blocks.append((g, n))
    return blocks


def load_canonical_q(family: str, k: int) -> np.ndarray:
    q = load_admixture_matrix(ADMIX, k, run_family=family)
    order = plot_order_indices(ADMIX, k, run_family=family)
    return q[:, order]


def colors_for(family: str, k: int) -> list[str]:
    _labels, colors, _a = component_labels_colors(ADMIX, k, run_family=family)
    order = plot_order_indices(ADMIX, k, run_family=family)
    return [colors[i] for i in order] if colors else ["#888888"] * k


def plot_k2_8(
    family: str,
    ids: list[str],
    meta: dict[str, str],
    col_index: list[int],
    out: Path,
    title: str,
) -> None:
    blocks = group_blocks(ids, meta, col_index)
    n = len(col_index)
    fig, axes = plt.subplots(
        7, 1, figsize=(18.0, 8.6), sharex=True, gridspec_kw={"hspace": 0.05}
    )
    k8_labels, k8_colors, _ = component_labels_colors(ADMIX, 8, run_family=family)
    for ax, k in zip(axes, range(2, 9)):
        q = load_canonical_q(family, k)[col_index]
        img = q_strip_image(q, colors_for(family, k), height=44)
        ax.imshow(img, aspect="auto", interpolation="nearest", origin="upper")
        ax.set_ylabel(f"K={k}", rotation=0, ha="right", va="center", fontsize=9)
        ax.set_yticks([])
        x0 = 0
        for gi, (_g, count) in enumerate(blocks):
            if gi:
                ax.axvline(x0 - 0.5, color="white", lw=0.4)
            x0 += count
        ax.set_xlim(-0.5, n - 0.5)
        ax.tick_params(bottom=False)
    ticks, labs = [], []
    x0 = 0
    for g, count in blocks:
        ticks.append(x0 + count / 2.0)
        labs.append(f"{g}\n(n={count})")
        x0 += count
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels(labs, fontsize=7)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in k8_colors]
    fig.legend(
        handles,
        k8_labels,
        loc="upper center",
        ncol=4,
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, 1.03),
    )
    fig.suptitle(title, fontsize=11, y=1.07)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_k8_compare(
    sci_ids: list[str],
    new_ids: list[str],
    meta: dict[str, str],
    sci_q: np.ndarray,
    new_q: np.ndarray,
    sci_order: list[int],
    new_order: list[int],
    out: Path,
) -> None:
    fig, axes = plt.subplots(
        2, 1, figsize=(18.0, 3.8), sharex=True, gridspec_kw={"hspace": 0.18}
    )
    pairs = [
        (axes[0], sci_q[sci_order], SCIENCE_RUN_FAMILY, sci_ids, sci_order),
        (axes[1], new_q[new_order], PANEL167K_NOGWAS_FAMILY, new_ids, new_order),
    ]
    for ax, q, family, ids, col_index in pairs:
        colors = colors_for(family, 8)
        img = q_strip_image(q, colors, height=56)
        ax.imshow(img, aspect="auto", interpolation="nearest", origin="upper")
        ax.set_yticks([])
        ax.set_ylabel(family.replace("_", "\n"), fontsize=8)
        x0 = 0
        for gi, (_g, count) in enumerate(group_blocks(ids, meta, col_index)):
            if gi:
                ax.axvline(x0 - 0.5, color="white", lw=0.4)
            x0 += count
        ax.set_xlim(-0.5, len(col_index) - 0.5)
        ax.tick_params(bottom=False)
    blocks = group_blocks(new_ids, meta, new_order)
    ticks, labs = [], []
    x0 = 0
    for g, count in blocks:
        ticks.append(x0 + count / 2.0)
        labs.append(f"{g}\n(n={count})")
        x0 += count
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels(labs, fontsize=7)
    labels, k8_colors, _ = component_labels_colors(
        ADMIX, 8, run_family=PANEL167K_NOGWAS_FAMILY
    )
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in k8_colors]
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=4,
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, 1.08),
    )
    fig.suptitle(
        "K=8 Science colours · same Grp/ID order · archive vs panel167k_nogwas",
        fontsize=11,
        y=1.14,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def group_means(ids: list[str], meta: dict[str, str], q: np.ndarray) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for g in REPORT_GRP_ORDER:
        idx = [i for i, sid in enumerate(ids) if meta.get(sid) == g]
        if idx:
            out[g] = q[idx].mean(axis=0)
    return out


def plot_means(
    sci_means: dict[str, np.ndarray],
    new_means: dict[str, np.ndarray],
    labels: list[str],
    colors: list[str],
    out: Path,
) -> None:
    groups = [g for g in REPORT_GRP_ORDER if g in sci_means and g in new_means]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.4), sharey=True)
    for ax, means, title in (
        (axes[0], sci_means, "science_core_ld_sort"),
        (axes[1], new_means, "panel167k_nogwas (greedy colour lock)"),
    ):
        mat = np.vstack([means[g] for g in groups])
        im = ax.imshow(mat, vmin=0, vmax=1, cmap="Greys", aspect="auto")
        ax.set_yticks(range(len(groups)))
        ax.set_yticklabels(groups, fontsize=8)
        ax.set_xticks(range(8))
        ax.set_xticklabels(SCIENCE_K8_LABELS, rotation=45, ha="right", fontsize=8)
        ax.set_title(title, fontsize=9)
        for i in range(len(groups)):
            for j in range(8):
                v = mat[i, j]
                ax.text(
                    j,
                    i,
                    f"{v:.2f}",
                    ha="center",
                    va="center",
                    fontsize=6,
                    color="white" if v > 0.45 else "black",
                )
        for j, c in enumerate(colors):
            ax.add_patch(
                plt.Rectangle(
                    (j - 0.5, -0.5),
                    1,
                    0.12,
                    color=c,
                    clip_on=False,
                    transform=ax.transData,
                )
            )
    fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="mean Q")
    fig.suptitle("K=8 group-mean Q after Science colour permutation", fontsize=11)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    _ = labels


def write_means_tsv(
    sci_means: dict[str, np.ndarray],
    new_means: dict[str, np.ndarray],
    path: Path,
) -> None:
    groups = [g for g in REPORT_GRP_ORDER if g in sci_means and g in new_means]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        hdr = ["Grp", "family"] + [f"K{i+1}_{SCIENCE_K8_LABELS[i]}" for i in range(8)]
        w.writerow(hdr)
        for g in groups:
            w.writerow([g, SCIENCE_RUN_FAMILY] + [f"{x:.4f}" for x in sci_means[g]])
            w.writerow([g, PANEL167K_NOGWAS_FAMILY] + [f"{x:.4f}" for x in new_means[g]])


def _purest_index(q: np.ndarray, idx: list[int]) -> int:
    sub = np.asarray(idx, int)
    pur = q[sub].max(axis=1)
    return int(sub[int(np.argmax(pur))])


def plot_purest_prototypes(
    ids: list[str],
    meta: dict[str, str],
    q_raw: np.ndarray,
    perm: list[int],
    out: Path,
) -> None:
    q = q_raw[:, np.asarray(perm, int)]
    groups = [g for g in REPORT_GRP_ORDER if any(meta.get(s) == g for s in ids)]
    fig, ax = plt.subplots(figsize=(8.4, 5.6))
    ylabels = []
    for yi, g in enumerate(groups):
        idx = [i for i, s in enumerate(ids) if meta.get(s) == g]
        pi = _purest_index(q_raw, idx)
        row = q[pi]
        left = 0.0
        for j, v in enumerate(row):
            ax.barh(yi, float(v), left=left, height=0.7, color=SCIENCE_K8_COLORS[j], linewidth=0)
            left += float(v)
        ylabels.append(f"{g}  {ids[pi]}  max={q_raw[pi].max():.2f}  raw{int(q_raw[pi].argmax())}")
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels(ylabels, fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Q (Science colour order after purity lock)")
    ax.invert_yaxis()
    ax.set_title("One purest individual per Grp · panel167k_nogwas K=8")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in SCIENCE_K8_COLORS]
    ax.legend(handles, SCIENCE_K8_LABELS, loc="lower right", fontsize=7, frameon=False, ncol=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_cg1_wee1(
    ids: list[str],
    meta: dict[str, str],
    q_raw: np.ndarray,
    perm: list[int],
    out: Path,
) -> None:
    """raw column claimed by WEE1 (K2) vs leftover K8 (CG1 majority)."""
    wee1_raw = int(perm[1])
    leftover_raw = int(perm[7])
    fig, ax = plt.subplots(figsize=(6.2, 5.8))
    for g, color, z in (("CG1", "#f6a3b1", 2), ("WEE1", "#dc1f26", 3)):
        idx = [i for i, s in enumerate(ids) if meta.get(s) == g]
        x = q_raw[idx, wee1_raw]
        y = q_raw[idx, leftover_raw]
        ax.scatter(x, y, s=12, c=color, alpha=0.65, linewidths=0, label=f"{g} n={len(idx)}", zorder=z)
        pi = _purest_index(q_raw, idx)
        ax.scatter(
            [q_raw[pi, wee1_raw]],
            [q_raw[pi, leftover_raw]],
            s=80,
            facecolors="none",
            edgecolors="black",
            linewidths=1.2,
            zorder=4,
        )
        ax.annotate(ids[pi], (q_raw[pi, wee1_raw], q_raw[pi, leftover_raw]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.plot([0, 1], [0, 1], color="#888888", lw=0.6, ls="--")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_aspect("equal")
    ax.set_xlabel(f"Q on WEE1-locked column (raw {wee1_raw} → K2 red)")
    ax.set_ylabel(f"Q on leftover column (raw {leftover_raw} → painted WWE2 pink)")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("CG1 vs WEE1 are two clusters, not a mean artifact")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_purest_tsv(
    ids: list[str],
    meta: dict[str, str],
    q_raw: np.ndarray,
    perms: dict[str, list[int]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["score", "canonical_to_raw"])
        for name, perm in perms.items():
            w.writerow([name, ",".join(str(i) for i in perm)])
        w.writerow([])
        w.writerow(["Grp", "n", "purest_ID", "purity", "argmax_raw", *[f"raw{j}" for j in range(8)]])
        for g in REPORT_GRP_ORDER:
            idx = [i for i, s in enumerate(ids) if meta.get(s) == g]
            if not idx:
                continue
            pi = _purest_index(q_raw, idx)
            w.writerow(
                [g, len(idx), ids[pi], f"{q_raw[pi].max():.4f}", int(q_raw[pi].argmax())]
                + [f"{x:.4f}" for x in q_raw[pi]]
            )


def align_k9(q8_canonical: np.ndarray, q9_raw: np.ndarray) -> tuple[np.ndarray, list[int]]:
    assigned = assign_qk_columns_to_k8(q9_raw, q8_canonical)
    leftovers = [i for i, a in enumerate(assigned) if a < 0]
    if len(leftovers) != 1:
        raise SystemExit(f"K=9 expected one leftover column, got {assigned}")
    order = k_plot_order_from_k8(assigned)
    return q9_raw[:, np.asarray(order, int)], order


def plot_k8_k9(
    ids: list[str],
    meta: dict[str, str],
    col_index: list[int],
    q8: np.ndarray,
    q9: np.ndarray,
    out: Path,
) -> None:
    fig, axes = plt.subplots(
        2, 1, figsize=(18.0, 3.8), sharex=True, gridspec_kw={"hspace": 0.18}
    )
    pairs = (
        (axes[0], q8[col_index], SCIENCE_K8_COLORS, "K=8"),
        (axes[1], q9[col_index], K9_COLORS, "K=9"),
    )
    n = len(col_index)
    for ax, q, colors, ylab in pairs:
        ax.imshow(q_strip_image(q, colors, height=56), aspect="auto", interpolation="nearest", origin="upper")
        ax.set_yticks([])
        ax.set_ylabel(ylab, fontsize=9)
        x0 = 0
        for gi, (_g, count) in enumerate(group_blocks(ids, meta, col_index)):
            if gi:
                ax.axvline(x0 - 0.5, color="white", lw=0.4)
            x0 += count
        ax.set_xlim(-0.5, n - 0.5)
        ax.tick_params(bottom=False)
    ticks, labs = [], []
    x0 = 0
    for g, count in group_blocks(ids, meta, col_index):
        ticks.append(x0 + count / 2.0)
        labs.append(f"{g}\n(n={count})")
        x0 += count
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels(labs, fontsize=7)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in K9_COLORS]
    fig.legend(
        handles,
        K9_LABELS,
        loc="upper center",
        ncol=5,
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, 1.08),
    )
    fig.suptitle(
        "panel167k_nogwas · K=8 vs K=9 (K9-new = unmatched extra column)",
        fontsize=11,
        y=1.14,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def sample_order_k9(ids: list[str], meta: dict[str, str], q9: np.ndarray) -> list[int]:
    """Within-group sort: K9-new first so the extra column is visible as a block."""
    by_grp, extra = _by_grp(ids, meta)
    out: list[int] = []
    for g in REPORT_GRP_ORDER:
        idxs = by_grp[g]
        if not idxs:
            continue
        named = GROUP_CANONICAL_COL.get(g)
        idxs = sorted(
            idxs,
            key=lambda i: (
                -float(q9[i, 8]),
                -float(q9[i, named] if named is not None else q9[i].max()),
                ids[i],
            ),
        )
        out.extend(idxs)
    out.extend(sorted(extra, key=lambda i: ids[i]))
    return out


def plot_k9_cg3_zoom(ids: list[str], meta: dict[str, str], q9: np.ndarray, out: Path) -> None:
    idx = [i for i, s in enumerate(ids) if meta.get(s) == "CG3"]
    idx = sorted(idx, key=lambda i: (-float(q9[i, 8]), ids[i]))
    n = len(idx)
    fig, ax = plt.subplots(figsize=(14.0, 3.2))
    ax.imshow(q_strip_image(q9[idx], K9_COLORS, height=64), aspect="auto", interpolation="nearest", origin="upper")
    ax.set_yticks([])
    step = max(1, n // 20)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([ids[idx[i]] for i in range(0, n, step)], rotation=90, fontsize=6)
    ax.set_xlim(-0.5, n - 0.5)
    n_new = int((q9[idx, 8] >= 0.5).sum())
    ax.set_title(f"CG3 only (n={n}), sorted by K9-new · {n_new} with K9-new≥0.5")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in K9_COLORS]
    ax.legend(handles, K9_LABELS, loc="upper right", fontsize=7, frameon=False, ncol=3)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def two_group_col_index(
    ids: list[str],
    meta: dict[str, str],
    q8: np.ndarray,
    left: str = "CG1",
    right: str = "WEE1",
) -> tuple[list[int], int]:
    """CG1 then WEE1; within group sort by K2 Q so followers sit at the join."""

    def _idxs(g: str) -> list[int]:
        return sorted(
            (i for i, s in enumerate(ids) if meta.get(s) == g),
            key=lambda i: (-float(q8[i, 1]), ids[i]),
        )

    left_i = _idxs(left)
    right_i = _idxs(right)
    return left_i + right_i, len(left_i)


def plot_cg1_follows_wee1(
    sci_ids: list[str],
    new_ids: list[str],
    meta: dict[str, str],
    sci_q8: np.ndarray,
    new_q8: np.ndarray,
    out: Path,
) -> None:
    fig, axes = plt.subplots(
        7, 2, figsize=(12.4, 8.8), sharex="col", gridspec_kw={"hspace": 0.06, "wspace": 0.08}
    )
    specs = (
        (0, SCIENCE_RUN_FAMILY, sci_ids, sci_q8, "science archive"),
        (1, PANEL167K_NOGWAS_FAMILY, new_ids, new_q8, "panel167k_nogwas"),
    )
    for col, family, ids, q8, title in specs:
        col_index, n_left = two_group_col_index(ids, meta, q8)
        n = len(col_index)
        axes[0, col].set_title(title, fontsize=10)
        for row, k in enumerate(range(2, 9)):
            ax = axes[row, col]
            q = load_canonical_q(family, k)[col_index]
            ax.imshow(
                q_strip_image(q, colors_for(family, k), height=40),
                aspect="auto",
                interpolation="nearest",
                origin="upper",
            )
            ax.axvline(n_left - 0.5, color="white", lw=0.8)
            ax.set_yticks([])
            ax.set_xlim(-0.5, n - 0.5)
            ax.tick_params(bottom=False)
            if col == 0:
                ax.set_ylabel(f"K={k}", rotation=0, ha="right", va="center", fontsize=8)
        axes[-1, col].tick_params(bottom=True)
        axes[-1, col].set_xticks([n_left / 2.0, n_left + (n - n_left) / 2.0])
        axes[-1, col].set_xticklabels(
            [f"CG1\n(n={n_left})", f"WEE1\n(n={n - n_left})"], fontsize=8
        )
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in SCIENCE_K8_COLORS]
    fig.legend(
        handles,
        SCIENCE_K8_LABELS,
        loc="upper center",
        ncol=4,
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, 1.02),
    )
    fig.suptitle(
        "CG1 vs WEE1 · Science keeps one colour; chip-nogwas splits at K=7",
        fontsize=11,
        y=1.06,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_k9_means(
    ids: list[str],
    meta: dict[str, str],
    q9: np.ndarray,
    out: Path,
) -> None:
    groups = [g for g in REPORT_GRP_ORDER if any(meta.get(s) == g for s in ids)]
    mat = np.vstack(
        [q9[[i for i, s in enumerate(ids) if meta.get(s) == g]].mean(axis=0) for g in groups]
    )
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    im = ax.imshow(mat, vmin=0, vmax=1, cmap="Greys", aspect="auto")
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels(groups, fontsize=8)
    ax.set_xticks(range(9))
    ax.set_xticklabels(K9_LABELS, rotation=45, ha="right", fontsize=8)
    for i in range(len(groups)):
        for j in range(9):
            v = mat[i, j]
            ax.text(
                j, i, f"{v:.2f}", ha="center", va="center", fontsize=6,
                color="white" if v > 0.45 else "black",
            )
    for j, c in enumerate(K9_COLORS):
        ax.add_patch(
            plt.Rectangle((j - 0.5, -0.5), 1, 0.12, color=c, clip_on=False, transform=ax.transData)
        )
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, label="mean Q")
    ax.set_title("K=9 group-mean Q after matching 8 columns to Science names")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_k9_means_tsv(ids: list[str], meta: dict[str, str], q9: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["Grp", "n", *K9_LABELS, "argmax"])
        for g in REPORT_GRP_ORDER:
            idx = [i for i, s in enumerate(ids) if meta.get(s) == g]
            if not idx:
                continue
            m = q9[idx].mean(axis=0)
            w.writerow([g, len(idx), *[f"{x:.4f}" for x in m], K9_LABELS[int(np.argmax(m))]])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=SUITE / "results" / "admixture_fit",
    )
    parser.add_argument("--only-purity", action="store_true")
    parser.add_argument("--only-k9", action="store_true")
    parser.add_argument("--only-cg1-wee1", action="store_true")
    args = parser.parse_args()
    out_dir: Path = args.out_dir

    meta = load_grp(INFO)
    sci_ids = [ln.strip() for ln in id_path_for_family(ADMIX, SCIENCE_RUN_FAMILY).read_text().splitlines() if ln.strip()]
    new_ids = [ln.strip() for ln in id_path_for_family(ADMIX, PANEL167K_NOGWAS_FAMILY).read_text().splitlines() if ln.strip()]
    sci_q8 = load_canonical_q(SCIENCE_RUN_FAMILY, 8)
    new_q8 = load_canonical_q(PANEL167K_NOGWAS_FAMILY, 8)
    if sci_q8.shape[0] != len(sci_ids) or new_q8.shape[0] != len(new_ids):
        raise SystemExit(
            f"Q/ID mismatch science {sci_q8.shape}/{len(sci_ids)} "
            f"panel167k {new_q8.shape}/{len(new_ids)}"
        )
    sci_order = sample_order_q(sci_ids, meta, sci_q8)
    new_order = sample_order_q(new_ids, meta, new_q8)
    sci_align = sample_order_id(sci_ids, meta)
    new_align = sample_order_id(new_ids, meta)

    if args.only_cg1_wee1:
        plot_cg1_follows_wee1(
            sci_ids,
            new_ids,
            meta,
            sci_q8,
            new_q8,
            out_dir / "cg1_wee1_follow_science_vs_panel167k.png",
        )
        print(out_dir / "cg1_wee1_follow_science_vs_panel167k.png")
        return

    k9_path = FIT / "panel167k_nogwas.9.Q"
    if k9_path.exists():
        q9_raw = np.loadtxt(k9_path)
        if q9_raw.ndim == 1:
            q9_raw = q9_raw.reshape(1, -1)
        if q9_raw.shape != (len(new_ids), 9):
            raise SystemExit(f"K=9 Q {q9_raw.shape} vs n_ids={len(new_ids)}")
        q9, k9_order = align_k9(new_q8, q9_raw)
        print("K9 plot-order raw columns", k9_order)
        k9_sort = sample_order_k9(new_ids, meta, q9)
        plot_k8_k9(new_ids, meta, new_align, new_q8, q9, out_dir / "panel167k_k8_vs_k9.png")
        plot_k8_k9(new_ids, meta, k9_sort, new_q8, q9, out_dir / "panel167k_k8_vs_k9_sorted.png")
        plot_k9_cg3_zoom(new_ids, meta, q9, out_dir / "panel167k_k9_cg3_zoom.png")
        plot_k9_means(new_ids, meta, q9, out_dir / "k9_group_means.png")
        write_k9_means_tsv(new_ids, meta, q9, out_dir / "k9_group_means.tsv")
        print(out_dir / "panel167k_k8_vs_k9.png")
        print(out_dir / "panel167k_k8_vs_k9_sorted.png")
        print(out_dir / "panel167k_k9_cg3_zoom.png")
        print(out_dir / "k9_group_means.png")
        print(out_dir / "k9_group_means.tsv")
    if args.only_k9:
        return

    q_raw = np.loadtxt(ADMIX / "panel167k_nogwas.8.Q")
    if q_raw.ndim == 1:
        q_raw = q_raw.reshape(1, -1)
    perms = {
        name: infer_science_k8_permutation(q_raw, new_ids, meta, score=name)
        for name in ("mean", "max", "purest")
    }
    write_purest_tsv(new_ids, meta, q_raw, perms, out_dir / "k8_purest_prototypes.tsv")
    plot_purest_prototypes(
        new_ids, meta, q_raw, perms["purest"], out_dir / "panel167k_k8_purest_prototypes.png"
    )
    plot_cg1_wee1(
        new_ids, meta, q_raw, perms["purest"], out_dir / "panel167k_cg1_vs_wee1_purity.png"
    )
    print("perms", perms)
    print(out_dir / "panel167k_k8_purest_prototypes.png")
    print(out_dir / "panel167k_cg1_vs_wee1_purity.png")
    print(out_dir / "k8_purest_prototypes.tsv")
    if args.only_purity:
        return

    plot_k2_8(
        PANEL167K_NOGWAS_FAMILY,
        new_ids,
        meta,
        new_order,
        out_dir / "panel167k_nogwas_k2_8_science_colors.png",
        "ADMIXTURE K=2–8 · panel167k_nogwas · Science K=8 colours (greedy lock) · n=2449",
    )
    plot_k2_8(
        SCIENCE_RUN_FAMILY,
        sci_ids,
        meta,
        sci_order,
        out_dir / "science_core_ld_sort_k2_8.png",
        "ADMIXTURE K=2–8 · science_core_ld_sort (archive) · n=2449",
    )
    plot_k8_compare(
        sci_ids,
        new_ids,
        meta,
        sci_q8,
        new_q8,
        sci_align,
        new_align,
        out_dir / "science_vs_panel167k_k8.png",
    )
    labels, colors, _ = component_labels_colors(
        ADMIX, 8, run_family=PANEL167K_NOGWAS_FAMILY
    )
    sci_means = group_means(sci_ids, meta, sci_q8)
    new_means = group_means(new_ids, meta, new_q8)
    plot_means(
        sci_means,
        new_means,
        labels,
        colors,
        out_dir / "k8_group_means_science_vs_panel167k.png",
    )
    write_means_tsv(sci_means, new_means, out_dir / "k8_group_means_science_vs_panel167k.tsv")
    print(out_dir / "panel167k_nogwas_k2_8_science_colors.png")
    print(out_dir / "science_core_ld_sort_k2_8.png")
    print(out_dir / "science_vs_panel167k_k8.png")
    print(out_dir / "k8_group_means_science_vs_panel167k.png")
    print(out_dir / "k8_group_means_science_vs_panel167k.tsv")


if __name__ == "__main__":
    main()
