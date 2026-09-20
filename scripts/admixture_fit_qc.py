#!/usr/bin/env python3
"""QC unsupervised panel167k_nogwas ADMIXTURE (CV + K=8 seeds vs core_ld_sort).

Run after Slurm jobs finish, before or as part of ingest.
Does not overwrite science_k*_raw.Q.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grapeancestry.adna.admixture import (  # noqa: E402
    infer_science_k8_permutation,
    science_k8_anchors_unique,
)
from grapeancestry.adna.panel167k_nogwas import (  # noqa: E402
    cv_story_ok,
    parse_cv_errors,
    pearson_cols,
)


def _read_ids(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]


def _grp_of(info: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with info.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            row = dict(zip(hdr, line.rstrip().split("\t")))
            if "ID" in row:
                out[row["ID"]] = row.get("Grp", "")
    return out


def collect_cv(log_dir: Path) -> dict[int, float]:
    cv: dict[int, float] = {}
    tsv = log_dir / "cv_error.tsv"
    if tsv.exists():
        with tsv.open() as fh:
            for line in fh:
                if not line.strip() or line.startswith("#"):
                    continue
                a = line.split()
                if len(a) >= 2:
                    k, val = int(a[0]), float(a[-1])
                    if k not in cv or val < cv[k]:
                        cv[k] = val
    for path in sorted(log_dir.glob("*.out")) + sorted(log_dir.glob("*.log")):
        text = path.read_text(errors="replace")
        val = parse_cv_errors(text)
        if val is None:
            continue
        k = None
        for token in path.stem.replace("-", "_").split("_"):
            if token.isdigit() and 2 <= int(token) <= 8:
                k = int(token)
                break
        if k is not None and k not in cv:
            cv[k] = val
    return cv


def pick_k8_seed(
    seed_qs: list[tuple[str, np.ndarray]],
    ids: list[str],
    grp_of: dict[str, str],
    q_ref_aligned: np.ndarray | None,
) -> dict:
    """Keep the seed whose Science-aligned Q has highest mean |r| to core_ld_sort."""
    best: dict | None = None
    rows = []
    for name, q in seed_qs:
        ok, msg = science_k8_anchors_unique(q, ids, grp_of)
        if not ok:
            rows.append({"seed": name, "ok": False, "reason": msg})
            continue
        perm = infer_science_k8_permutation(q, ids, grp_of)
        q_aln = q[:, np.asarray(perm, dtype=int)]
        r = float("nan")
        if q_ref_aligned is not None and q_ref_aligned.shape == q_aln.shape:
            r = pearson_cols(q_aln, q_ref_aligned)
        rec = {"seed": name, "ok": True, "perm": perm, "r_core_ld_sort": r}
        rows.append(rec)
        if best is None:
            best = rec
        else:
            r_best = best.get("r_core_ld_sort")
            r_best_f = float(r_best) if r_best == r_best else -1.0  # noqa: PLR0124
            r_f = float(r) if r == r else -1.0  # noqa: PLR0124
            if r_f > r_best_f:
                best = rec
    if best is None:
        raise SystemExit("no K=8 seed passed unique Science group-majority anchors")
    return {"best": best, "seeds": rows}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fit-dir", type=Path, required=True, help="Directory with Q/P and logs")
    p.add_argument("--ids", type=Path, default=None)
    p.add_argument("--info", type=Path, default=ROOT / "data" / "panel" / "2449.info")
    p.add_argument(
        "--core-ld-sort8",
        type=Path,
        default=ROOT.parent
        / "stat_vcf_from_3527"
        / "ADMIXTURE"
        / "new_final"
        / "core_ld_sort.8.Q",
    )
    p.add_argument("--science-q8", type=Path, default=ROOT / "data" / "panel" / "admixture" / "science_k8_raw.Q")
    p.add_argument("--out-json", type=Path, default=None)
    args = p.parse_args()
    fit = args.fit_dir
    ids_path = args.ids or (fit / "id_panel167k.txt")
    if not ids_path.exists():
        fam = fit / "panel167k_nogwas.fam"
        if not fam.exists():
            raise SystemExit(f"missing ids {ids_path} and fam {fam}")
        ids = [ln.split()[1] for ln in fam.read_text().splitlines() if ln.strip()]
    else:
        ids = _read_ids(ids_path)
    grp = _grp_of(args.info)
    cv = collect_cv(fit)
    ok_cv, cv_msg = cv_story_ok(cv) if cv else (False, "no CV values")
    print("cv", cv, cv_msg)

    seed_files = sorted(fit.glob("panel167k_nogwas.8.seed*.Q"))
    if not seed_files:
        one = fit / "panel167k_nogwas.8.Q"
        if one.exists():
            seed_files = [one]
    seed_qs = []
    for path in seed_files:
        q = np.loadtxt(path)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        seed_qs.append((path.name, q))

    q_ref = None
    ref_path = args.core_ld_sort8 if args.core_ld_sort8.exists() else args.science_q8
    if ref_path.exists():
        q_raw = np.loadtxt(ref_path)
        if q_raw.ndim == 1:
            q_raw = q_raw.reshape(1, -1)
        n = min(q_raw.shape[0], len(ids))
        # Align reference with the same group-majority rule (science perm on this ID order).
        try:
            perm_ref = infer_science_k8_permutation(q_raw[:n], ids[:n], grp)
            q_ref = q_raw[:n][:, np.asarray(perm_ref, dtype=int)]
        except ValueError as exc:
            print(f"[warn] could not align reference Q: {exc}")

    seed_report = pick_k8_seed(seed_qs, ids, grp, q_ref) if seed_qs else {}
    report = {
        "cv": {str(k): v for k, v in sorted(cv.items())},
        "cv_ok": ok_cv,
        "cv_msg": cv_msg,
        "le_caveat": True,
        "k8_seeds": seed_report,
    }
    if not ok_cv:
        raise SystemExit(f"CV gate failed: {cv_msg}")
    out = args.out_json or (fit / "fit_qc.json")
    out.write_text(json.dumps(report, indent=2))
    print("wrote", out)
    print("best seed", seed_report.get("best"))


if __name__ == "__main__":
    main()
