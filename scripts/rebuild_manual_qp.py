#!/usr/bin/env python3
"""Build panel167k_manual.{K}.Q/.P from nogwas: align columns, then group-wise Q edits.

Does not overwrite frozen panel167k_nogwas Q/P.
P gets the same C-order permutation as Q. Sample-specific Q edits are Q-only
(P is SNP×K for all samples; it cannot encode CG1-only or W-Ad-only swaps).
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from grapeancestry.adna.admixture import live_panel167k_metadata, sequential_column_orders_core
from grapeancestry.adna.manual_qp import apply_manual_q_edits, permute_columns
from grapeancestry.adna.panel167k_nogwas import DISPLAY_Q_PATTERN, MANIFEST_NAME

SUITE = Path(__file__).resolve().parents[1]
ADMIX = SUITE / "data" / "panel" / "admixture"
INFO = SUITE / "data" / "panel" / "2449.info"
FIT = SUITE / "results" / "admixture_fit"
OUT_STEM = "panel167k_manual"


def load_grp(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    with path.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            row = dict(zip(hdr, line.rstrip().split("\t")))
            meta[row["ID"]] = row.get("Grp", "")
    return meta


def find_qp(k: int, kind: str) -> Path:
    for p in (FIT / f"panel167k_nogwas.{k}.{kind}", ADMIX / f"panel167k_nogwas.{k}.{kind}"):
        if p.exists():
            return p
    raise FileNotFoundError(f"no {kind} for K={k}")


def write_admixture_matrix(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, arr, fmt="%.6f")


def main() -> None:
    ids = [ln.strip() for ln in (ADMIX / "id_panel167k.txt").read_text().splitlines() if ln.strip()]
    meta = load_grp(INFO)
    grps = np.array([meta.get(s, "") for s in ids])
    keep = [i for i, g in enumerate(grps) if g != "OUT"]
    q_raw = {k: np.loadtxt(find_qp(k, "Q")) for k in range(2, 11)}
    p_raw = {k: np.loadtxt(find_qp(k, "P")) for k in range(2, 11)}
    for k in range(2, 11):
        if q_raw[k].shape != (len(ids), k):
            raise SystemExit(f"K={k} Q {q_raw[k].shape}")
        if p_raw[k].ndim != 2 or p_raw[k].shape[1] != k:
            raise SystemExit(f"K={k} P {p_raw[k].shape}")
    orders = sequential_column_orders_core(q_raw, ids, meta, keep=keep, k_max=10)
    perm_path = FIT / f"{OUT_STEM}_canonical_to_raw.tsv"
    with perm_path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["K", "canonical_to_raw"])
        for k in range(2, 11):
            w.writerow([k, ",".join(str(i) for i in orders[k])])
    for k in range(2, 11):
        q = permute_columns(q_raw[k], orders[k])
        p = permute_columns(p_raw[k], orders[k])
        if k >= 7:
            q = apply_manual_q_edits(q, grps, k, ids=ids)
        write_admixture_matrix(FIT / f"{OUT_STEM}.{k}.Q", q)
        write_admixture_matrix(FIT / f"{OUT_STEM}.{k}.P", p)
        write_admixture_matrix(ADMIX / f"{OUT_STEM}.{k}.Q", q)
        print(k, "Q", q.shape, "P", p.shape, "row_sum", float(q.sum(1).mean()))
    patch_display_lock_manifest(ADMIX)
    print(perm_path)
    print("wrote", FIT / f"{OUT_STEM}.{{2-10}}.Q/P and", ADMIX / DISPLAY_Q_PATTERN.format(k="{2-10}"))


def patch_display_lock_manifest(admix_dir: Path) -> None:
    """Record display Q without changing freeze sha256 / P paths."""
    import json

    path = admix_dir / MANIFEST_NAME
    if not path.exists():
        return
    man = json.loads(path.read_text())
    assets = man.get("assets") or {}
    for k in range(2, 9):
        live = live_panel167k_metadata(admix_dir, k)
        if not live:
            continue
        key = f"panel167k_nogwas.{k}.Q"
        old = assets.get(key)
        if not isinstance(old, dict):
            continue
        old["plot_order"] = live["plot_order"]
        old["components"] = live["components"]
        old["component_permutation"] = live["component_permutation"]
        assets[key] = old
    man["assets"] = assets
    path.write_text(json.dumps(man, indent=2) + "\n")


if __name__ == "__main__":
    main()
