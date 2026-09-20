#!/usr/bin/env python3
"""Copy HPC ADMIXTURE Q/P into data/panel/admixture/ as panel167k_nogwas.

Writes **column-aligned** Q and P (same permutation) and **row-aligns** P
to panel167k_nogwas.sites.txt (HPC .bim is genomic chr1→19; sites.txt is
panel-bed order). Does **not** overwrite science_k*_raw.Q / core_ld_sort,
and does not rewrite the HPC fit directory.

Alignment: WWE1-purest seeds K=2 west; Pearson K→K+1 on 2448 non-OUT samples.
Does not overwrite panel167k_manual.{K}.Q.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grapeancestry.adna.admixture import (  # noqa: E402
    apply_column_order,
    live_panel167k_metadata,
    science_k8_anchors_unique,
    sequential_orders_from_q,
)
from grapeancestry.adna.panel167k_nogwas import (  # noqa: E402
    EXPECTED_KEEP_SITES,
    ID_FILE_NAME,
    MANIFEST_NAME,
    PANEL167K_NOGWAS_FAMILY,
    P_PATTERN,
    Q_PATTERN,
    SITES_FILE_NAME,
    load_bim_site_keys,
    load_family_sites,
    reorder_p_rows_to_sites,
)

QP_FMT = "%.6f"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ids_from_fam(fam: Path) -> list[str]:
    ids: list[str] = []
    for line in fam.read_text().splitlines():
        if not line.strip():
            continue
        p = line.split()
        ids.append(p[1] if len(p) > 1 else p[0])
    return ids


def ids_from_vcf(vcf: Path) -> list[str]:
    return subprocess.check_output(["bcftools", "query", "-l", str(vcf)], text=True).splitlines()


def _load_qp(path: Path, n_row: int, k: int) -> np.ndarray:
    m = np.loadtxt(path)
    if m.ndim == 1:
        m = m.reshape(1, -1)
    if m.shape != (n_row, k):
        raise SystemExit(f"{path} shape {m.shape} != ({n_row}, {k})")
    return m


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fit-dir", type=Path, required=True)
    p.add_argument("--admix-dir", type=Path, default=ROOT / "data" / "panel" / "admixture")
    p.add_argument("--fam", type=Path, default=None)
    p.add_argument("--panel-vcf", type=Path, default=ROOT / "data" / "panel" / "panel167k_2449.vcf.gz")
    p.add_argument("--info", type=Path, default=ROOT / "data" / "panel" / "2449.info")
    p.add_argument("--best-k8", type=Path, default=None, help="Winning panel167k_nogwas.8.seed*.Q")
    p.add_argument("--qc-json", type=Path, default=None)
    args = p.parse_args()
    fit = args.fit_dir.resolve()
    dest = args.admix_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if fit == dest:
        raise SystemExit("fit-dir and admix-dir must differ; HPC raw Q/P stay in fit-dir")

    fam = args.fam or (fit / "panel167k_nogwas.fam")
    if fam.exists():
        ids = ids_from_fam(fam)
    elif args.panel_vcf.exists():
        ids = ids_from_vcf(args.panel_vcf)
    else:
        raise SystemExit("need --fam or panel VCF for ID order")
    if len(ids) != 2449:
        raise SystemExit(f"expected 2449 IDs, got {len(ids)}")
    id_path = dest / ID_FILE_NAME
    id_path.write_text("\n".join(ids) + "\n")

    sites_src = fit / SITES_FILE_NAME
    if sites_src.exists() and not (dest / SITES_FILE_NAME).exists():
        shutil.copy2(sites_src, dest / SITES_FILE_NAME)
    sites = load_family_sites(dest)
    if len(sites) != EXPECTED_KEEP_SITES:
        raise SystemExit(f"sites.txt length {len(sites)} != {EXPECTED_KEEP_SITES}")

    grp: dict[str, str] = {}
    with args.info.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            row = dict(zip(hdr, line.rstrip().split("\t")))
            grp[row["ID"]] = row.get("Grp", "")

    k8_src = args.best_k8
    if k8_src is None:
        qc_path = args.qc_json or (fit / "fit_qc.json")
        if qc_path.exists():
            qc = json.loads(qc_path.read_text())
            best_name = ((qc.get("k8_seeds") or {}).get("best") or {}).get("seed")
            if best_name:
                k8_src = fit / best_name
        if k8_src is None:
            k8_src = fit / "panel167k_nogwas.8.Q"
    if not k8_src.exists():
        raise SystemExit(f"missing K=8 Q {k8_src}")

    q_by_k: dict[int, np.ndarray] = {}
    p_by_k: dict[int, np.ndarray] = {}
    for k in range(2, 9):
        q_src = k8_src if k == 8 else (fit / Q_PATTERN.format(k=k))
        p_src = fit / k8_src.name.replace(".Q", ".P") if k == 8 else (fit / P_PATTERN.format(k=k))
        if k == 8 and not p_src.exists():
            p_src = fit / P_PATTERN.format(k=8)
        if not q_src.exists() or not p_src.exists():
            raise SystemExit(f"missing K={k} Q/P in {fit}")
        q_by_k[k] = _load_qp(q_src, 2449, k)
        p_by_k[k] = _load_qp(p_src, EXPECTED_KEEP_SITES, k)

    ok, msg = science_k8_anchors_unique(q_by_k[8], ids, grp)
    if not ok:
        print(
            "NOTE K=8 groups do not each own a unique raw column "
            f"({msg}); freeze uses sequential Pearson, not greedy Science names.",
            file=sys.stderr,
        )

    orders = sequential_orders_from_q(q_by_k, ids, grp, k_max=8)
    canonical_to_raw = {str(k): [int(i) for i in orders[k]] for k in range(2, 9)}
    bim = fit / "panel167k_nogwas.bim"
    if not bim.exists():
        raise SystemExit(f"missing {bim} (needed to place P rows in sites.txt order)")
    bim_keys = load_bim_site_keys(bim)
    if bim_keys != sites and set(bim_keys) != set(sites):
        raise SystemExit("bim SNP set does not match sites.txt")
    for k in range(2, 9):
        q_aln = apply_column_order(q_by_k[k], orders[k])
        p_aln = apply_column_order(p_by_k[k], orders[k])
        if bim_keys != sites:
            p_aln = reorder_p_rows_to_sites(p_aln, bim_keys, sites)
        np.savetxt(dest / Q_PATTERN.format(k=k), q_aln, fmt=QP_FMT)
        np.savetxt(dest / P_PATTERN.format(k=k), p_aln, fmt=QP_FMT)

    stub = {
        "schema_version": 1,
        "run_family": PANEL167K_NOGWAS_FAMILY,
        "on_disk_aligned": True,
        "canonical_to_raw": canonical_to_raw,
        "p_row_order": SITES_FILE_NAME,
        "p_counted_allele": "REF",
        "assets": {},
    }
    (dest / MANIFEST_NAME).write_text(json.dumps(stub, indent=2) + "\n")

    assets = {}
    for k in range(2, 9):
        meta = live_panel167k_metadata(dest, k)
        if not meta:
            raise SystemExit(f"could not build sequential metadata for K={k}")
        qpath = dest / Q_PATTERN.format(k=k)
        ppath = dest / P_PATTERN.format(k=k)
        meta.update(
            {
                "path": qpath.name,
                "run_family": PANEL167K_NOGWAS_FAMILY,
                "k": k,
                "rows": 2449,
                "columns": k,
                "sha256": _sha256(qpath),
                "p_path": ppath.name,
                "p_sha256": _sha256(ppath),
                "p_rows": EXPECTED_KEEP_SITES,
            }
        )
        assets[qpath.name] = meta

    manifest = {
        "schema_version": 1,
        "run_family": PANEL167K_NOGWAS_FAMILY,
        "k_range": [2, 8],
        "on_disk_aligned": True,
        "canonical_to_raw": canonical_to_raw,
        "p_row_order": SITES_FILE_NAME,
        "p_counted_allele": "REF",
        "column_order": "sequential_purest_wwe1_pearson",
        "row_id_source": ID_FILE_NAME,
        "row_id_alignment": "Line i in id_panel167k.txt is row i of every panel167k_nogwas.K.Q",
        "snp_set": {
            "panel_sites": 167433,
            "gwas_dropped": 13950,
            "keep_sites": EXPECTED_KEEP_SITES,
            "sites_file": SITES_FILE_NAME,
            "extra_ld_prune": False,
            "le_assumption_violated": True,
        },
        "projection_availability": {
            "status": "enabled",
            "method": "admixture -P",
            "science_p_matrix": False,
            "p_columns_match_q": True,
        },
        "fit_status": {
            "panel_q_refit_in_suite": True,
            "k8_anchor_unique": ok,
            "k8_anchor_note": msg,
            "human_note": (
                "Unsupervised ADMIXTURE on 2449 × 153483 (167k minus GWAS). "
                "Dest Q/P columns are sequential C1…CK; P rows follow sites.txt "
                "(not BIM genomic order); P values are VCF REF frequencies on this "
                "freeze. HPC raw stays in fit-dir. "
                "Archive science_k* untouched."
            ),
        },
        "assets": assets,
    }
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    print("ingested aligned", dest, "ids", len(ids))
    print("canonical_to_raw", canonical_to_raw)


if __name__ == "__main__":
    main()
