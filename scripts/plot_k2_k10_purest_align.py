#!/usr/bin/env python3
"""K=2–10 ADMIXTURE plot: people once, core Pearson C-names, unique colour per column.

Layer 1: REPORT_GRP_ORDER, within-Grp IID sort, all K share this x-axis.
Layer 2 (--science-k8-colors): core Pearson (10 Dong groups, Qmax>0.75 both K,
else that group's purest); leftover column at the right. C1…CK are names only.
Layer 3: one colour per component (C1…CK). Matched columns keep that colour.
Newest column on top. WEE1 and CG1 are two columns → two colours. Display only.
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
    COMPONENT_COLORS,
    k2_order_from_purest_wwe1,
    stack_newest_on_top,
    sequential_column_orders,
    sequential_column_orders_core,
    swap_canonical_columns,
    unique_component_colors,
)
from grapeancestry.adna.grp_order import REPORT_GRP_ORDER

SUITE = Path(__file__).resolve().parents[1]
ADMIX = SUITE / "data" / "panel" / "admixture"
INFO = SUITE / "data" / "panel" / "2449.info"
FIT = SUITE / "results" / "admixture_fit"

# Layer-3 owners: every non-OUT Grp (c_align CORE_GRP). Layer-2 cores stay 10 Dong groups.
OWNER_GRPS = [g for g in REPORT_GRP_ORDER if g != "OUT"]
SEQ_COLORS = list(COMPONENT_COLORS)


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


def q_strip_image(
    q: np.ndarray,
    colors: list[str],
    height: int = 40,
    cell_hex: list[list[str]] | None = None,
) -> np.ndarray:
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
        row_hex = cell_hex[i] if cell_hex is not None and i < len(cell_hex) else None
        for j, y1 in enumerate(edges):
            if y1 > y0:
                if row_hex is not None and j < len(row_hex):
                    img[y0:y1, i] = hex_to_rgb(row_hex[j])
                else:
                    img[y0:y1, i] = rgb[j]
            y0 = max(y0, y1)
    return img


def load_q(k: int, stem: str = "panel167k_nogwas") -> np.ndarray:
    for p in (FIT / f"{stem}.{k}.Q", ADMIX / f"{stem}.{k}.Q"):
        if p.exists():
            q = np.loadtxt(p)
            if q.ndim == 1:
                q = q.reshape(1, -1)
            return q
    raise FileNotFoundError(f"no Q for {stem} K={k}")


def keep_2448(ids: list[str], meta: dict[str, str]) -> list[int]:
    keep = [i for i, s in enumerate(ids) if meta.get(s) != "OUT"]
    if len(keep) != 2448:
        raise SystemExit(f"expected 2448 non-OUT samples, got {len(keep)}")
    return keep


def purest_index(q: np.ndarray, idx: list[int]) -> int:
    sub = np.asarray(idx, int)
    return int(sub[int(np.argmax(q[sub].max(axis=1)))])


def owners_at_k(
    q: np.ndarray,
    ids: list[str],
    meta: dict[str, str],
    keep: list[int],
) -> list[str]:
    keep_set = set(keep)
    owners: list[list[str]] = [[] for _ in range(q.shape[1])]
    for g in OWNER_GRPS:
        idx = [i for i, s in enumerate(ids) if meta.get(s) == g and i in keep_set]
        if not idx:
            continue
        pi = purest_index(q, idx)
        owners[int(np.argmax(q[pi]))].append(f"{g}:{ids[pi]}")
    labels = ["+".join(x) if x else "" for x in owners]
    for j, lab in enumerate(labels):
        if lab:
            continue
        scored = []
        for g in OWNER_GRPS:
            idx = [i for i, s in enumerate(ids) if meta.get(s) == g and i in keep_set]
            if idx:
                scored.append((float(q[idx, j].mean()), g))
        if scored:
            v, g = max(scored)
            labels[j] = f"{g}(mean {v:.2f})"
        else:
            labels[j] = "—"
    return labels


def display_index(ids: list[str], meta: dict[str, str]) -> list[int]:
    out: list[int] = []
    for g in REPORT_GRP_ORDER:
        out.extend(sorted((i for i, s in enumerate(ids) if meta.get(s) == g), key=lambda i: ids[i]))
    return out


def plot_k2_k10(
    q_by_k: dict[int, np.ndarray],
    orders: dict[int, list[int]],
    ids: list[str],
    meta: dict[str, str],
    keep: list[int],
    out: Path,
    title_note: str = "",
    science_k8_colors: bool = False,
) -> list[list[str]]:
    col_index = display_index(ids, meta)
    n = len(col_index)
    blocks: list[tuple[str, int]] = []
    for g in REPORT_GRP_ORDER:
        c = sum(1 for i in col_index if meta.get(ids[i]) == g)
        if c:
            blocks.append((g, c))
    owner_rows: list[list[str]] = []
    fig, axes = plt.subplots(
        9, 1, figsize=(18.0, 10.2), sharex=True, gridspec_kw={"hspace": 0.05}
    )
    fig.subplots_adjust(left=0.08)
    k10_owners: list[str] = []
    for ax, k in zip(axes, range(2, 11)):
        q = q_by_k[k][:, np.asarray(orders[k], int)]
        owners = owners_at_k(q, ids, meta, keep)
        owner_rows.append([str(k), *owners])
        if k == 10:
            k10_owners = owners
        if science_k8_colors:
            colors = unique_component_colors(k)
            q, colors, _ = stack_newest_on_top(q, colors)
        else:
            colors = SEQ_COLORS[:k]
        img = q_strip_image(q[col_index], colors, height=48)
        ax.imshow(img, aspect="auto", interpolation="nearest", origin="upper")
        ax.set_ylabel(f"K={k}", rotation=0, ha="right", va="center", fontsize=9)
        ax.set_yticks([])
        if science_k8_colors:
            chips = unique_component_colors(k)
            for i, col in enumerate(reversed(chips)):
                ax.add_patch(
                    plt.Rectangle(
                        (-0.055, i / k),
                        0.04,
                        1.0 / k,
                        transform=ax.transAxes,
                        facecolor=col,
                        edgecolor="white",
                        linewidth=0.4,
                        clip_on=False,
                    )
                )
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
    legend_colors = unique_component_colors(10) if science_k8_colors else SEQ_COLORS[:10]
    legend_labels = [
        f"C{i+1} {k10_owners[i]}" if i < len(k10_owners) else f"C{i+1}" for i in range(10)
    ]
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in legend_colors]
    fig.legend(
        handles,
        legend_labels,
        loc="upper center",
        ncol=5,
        fontsize=7,
        frameon=False,
        bbox_to_anchor=(0.5, 1.03),
    )
    fig.suptitle(
        "panel167k_nogwas K=2–10 · 2448 (no OUT) purest-per-Grp · sequential match · REPORT_GRP_ORDER"
        + title_note,
        fontsize=11,
        y=1.07,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return owner_rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", type=Path, default=FIT)
    p.add_argument(
        "--swap-c2-c7",
        action="store_true",
        help="Display-only: swap canonical C2 and C7 for K>=7.",
    )
    p.add_argument(
        "--science-k8-colors",
        action="store_true",
        help="Core Pearson + one colour per component C1…CK (newest on top). "
        "Different columns never share a hex. Display only.",
    )
    p.add_argument(
        "--family",
        default="panel167k_nogwas",
        help="Q file stem in results/admixture_fit or data/panel/admixture.",
    )
    p.add_argument(
        "--already-aligned",
        action="store_true",
        help="Q columns are already C1…CK; do not rematch.",
    )
    args = p.parse_args()
    ids = [ln.strip() for ln in (ADMIX / "id_panel167k.txt").read_text().splitlines() if ln.strip()]
    meta = load_grp(INFO)
    keep = keep_2448(ids, meta)
    q_full = {k: load_q(k, args.family) for k in range(2, 11)}
    for k, q in q_full.items():
        if q.shape[0] != len(ids) or q.shape[1] != k:
            raise SystemExit(f"K={k} Q {q.shape} vs n={len(ids)}")
    q_match = {k: q[keep] for k, q in q_full.items()}
    if args.already_aligned:
        orders = {k: list(range(k)) for k in range(2, 11)}
        order2 = orders[2]
    elif args.science_k8_colors:
        orders = sequential_column_orders_core(
            q_full, ids, meta, keep=keep, k_max=10
        )
        order2 = orders[2]
    else:
        order2 = k2_order_from_purest_wwe1(q_full[2], ids, meta, keep=keep)
        orders = sequential_column_orders(q_match, order2, k_max=10)
    title_note = ""
    tag = "" if args.family == "panel167k_nogwas" else f"{args.family}_"
    png_name = f"{tag}k2_10_purest_sequential.png" if tag else "panel167k_k2_10_purest_sequential.png"
    tsv_name = f"{tag}k2_10_purest_owners.tsv" if tag else "panel167k_k2_10_purest_owners.tsv"
    if args.swap_c2_c7:
        orders = {k: swap_canonical_columns(o, 1, 6) for k, o in orders.items()}
        png_name = f"{tag}k2_10_swap_c2_c7.png" if tag else "panel167k_k2_10_swap_c2_c7.png"
        tsv_name = f"{tag}k2_10_swap_c2_c7_owners.tsv" if tag else "panel167k_k2_10_swap_c2_c7_owners.tsv"
        title_note = " · TEST swap C2↔C7 (K≥7)"
    if args.science_k8_colors:
        png_name = f"{tag}k2_10_science_k8_colors.png" if tag else "panel167k_k2_10_science_k8_colors.png"
        tsv_name = f"{tag}k2_10_science_k8_colors.tsv" if tag else "panel167k_k2_10_science_k8_colors.tsv"
        title_note = " · core Pearson · one colour per component · newest on top"
        if args.already_aligned:
            title_note = " · C-aligned · one colour per component · newest on top"
    if args.family != "panel167k_nogwas":
        title_note += f" · {args.family}"
    owner_rows = plot_k2_k10(
        q_full,
        orders,
        ids,
        meta,
        keep,
        args.out_dir / png_name,
        title_note=title_note,
        science_k8_colors=args.science_k8_colors,
    )
    tsv = args.out_dir / tsv_name
    with tsv.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["K", *[f"C{i+1}" for i in range(10)]])
        w.writerows(owner_rows)
        w.writerow([])
        w.writerow(["K", "canonical_to_raw"])
        for k in range(2, 11):
            w.writerow([k, ",".join(str(i) for i in orders[k])])
    print("K=2 order (west,east raw)", order2)
    print("n_keep", len(keep))
    print(args.out_dir / png_name)
    print(tsv)
    for row in owner_rows:
        print("\t".join(row))


if __name__ == "__main__":
    main()
