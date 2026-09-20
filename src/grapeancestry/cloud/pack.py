"""Build / load the Streamlit-Cloud asset pack (fingerprint + optional GS)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from grapeancestry.cloud.mas import MAS_SITES
from grapeancestry.cloud.sites import N_PANEL_SITES, load_panel_sites
from grapeancestry.cloud.sdr import SDR_PACK, sdr_sites

# Named in-panel positive-control IDs (Dong passport / OIV).
NAMED_DEMOS: list[tuple[str, str, str]] = [
    ("HUN89", "Szekszárdi — hermaphrodite, blue-black (in-panel row)", "in_panel"),
    ("24", "Chardonnay blanc — white berry", "in_panel"),
    ("26", "Pinot noir — hold-self-out clone screen", "hold_self_out"),
    ("HUN8", "Bakator kék — female (OIV 151=4)", "in_panel"),
    ("728", "Korinthiaki / Black Corinth — seedless coverage", "in_panel"),
    ("758", "Muscat of Alexandria — muscat proxy", "in_panel"),
]


def suite_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for p in [here, *here.parents]:
        if (p / "pyproject.toml").exists() and (p / "app.py").exists():
            return p
    return here.parents[3]


FP_EVERY = 40
FP_NAME = "fingerprint.npz"
MANIFEST_NAME = "manifest.json"


def pack_dir(root: Path) -> Path:
    return root / "data" / "cloud"


def load_fingerprint(root: Path) -> tuple[np.ndarray, list[str], list[str]] | None:
    path = pack_dir(root) / FP_NAME
    if not path.exists():
        return None
    z = np.load(path, allow_pickle=True)
    return z["mat"].astype(np.int8), list(z["samples"]), list(z["sites"])


def gs_model_paths(root: Path) -> list[Path]:
    return sorted((pack_dir(root) / "gs").glob("*/*/model.npz"))


def write_manifest(root: Path, extra: dict) -> Path:
    dest = pack_dir(root) / MANIFEST_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "n_panel_sites_expected": N_PANEL_SITES,
        "fingerprint_every": FP_EVERY,
        "mas_sites": MAS_SITES,
        **extra,
    }
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def _write_hun89_demo(
    root: Path,
    mat: np.ndarray,
    ids: list[str],
    cache_sites: list[str],
    fp_sites: list[str],
) -> int:
    from grapeancestry.breeding.gs import load_model

    site_index = {s: i for i, s in enumerate(cache_sites)}
    demo_sites: list[str] = []
    seen: set[str] = set()
    from grapeancestry.cloud.card import MYBA_PAD
    from grapeancestry.cloud.loci import sites_in_window, sites_with_token

    extra = (
        list(fp_sites)
        + MAS_SITES
        + sdr_sites(root)
        + sites_with_token(root, "OIV_241")
        + sites_in_window(root, "2", 5_116_947 - MYBA_PAD, 5_116_947 + MYBA_PAD, token="OIV_225")
    )
    packed = pack_dir(root) / SDR_PACK
    if packed.exists():
        z = np.load(packed, allow_pickle=True)
        extra.extend(list(z["sites"]))
    for s in extra:
        if s in site_index and s not in seen:
            seen.add(s)
            demo_sites.append(s)
    for npz in gs_model_paths(root):
        mdl = load_model(npz)
        for s in mdl.sites:
            if s in site_index and s not in seen:
                seen.add(s)
                demo_sites.append(s)
    hun = mat[ids.index("HUN89")]
    demo_row = np.array([int(hun[site_index[s]]) for s in demo_sites], dtype=np.int8)
    np.savez_compressed(
        pack_dir(root) / "demo_HUN89.npz",
        dosages=demo_row,
        sites=np.array(demo_sites, dtype=object),
        sample=np.array(["HUN89"]),
    )
    return len(demo_sites)


def _demo_site_list(
    root: Path,
    cache_sites: list[str],
    fp_sites: list[str],
) -> list[str]:
    from grapeancestry.breeding.gs import load_model
    from grapeancestry.cloud.card import MYBA_PAD
    from grapeancestry.cloud.loci import sites_in_window, sites_with_token

    site_index = set(cache_sites)
    extra = (
        list(fp_sites)
        + MAS_SITES
        + sdr_sites(root)
        + sites_with_token(root, "OIV_241")
        + sites_in_window(root, "2", 5_116_947 - MYBA_PAD, 5_116_947 + MYBA_PAD, token="OIV_225")
    )
    packed = pack_dir(root) / SDR_PACK
    if packed.exists():
        z = np.load(packed, allow_pickle=True)
        extra.extend(list(z["sites"]))
    for npz in gs_model_paths(root):
        mdl = load_model(npz)
        extra.extend(list(mdl.sites))
    seen: set[str] = set()
    out: list[str] = []
    for s in extra:
        if s in site_index and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _write_named_demos(
    root: Path,
    mat: np.ndarray,
    ids: list[str],
    cache_sites: list[str],
    demo_sites: list[str],
) -> list[dict]:
    site_index = {s: i for i, s in enumerate(cache_sites)}
    cols = [site_index[s] for s in demo_sites]
    keep_ids: list[str] = []
    kinds: list[str] = []
    labels: list[str] = []
    rows = []
    catalog: list[dict] = []
    for sid, label, kind in NAMED_DEMOS:
        if sid not in ids:
            continue
        keep_ids.append(sid)
        kinds.append(kind)
        labels.append(label)
        rows.append(mat[ids.index(sid)][cols].astype(np.int8))
        catalog.append({"id": sid, "label": label, "kind": kind})
    if rows:
        np.savez_compressed(
            pack_dir(root) / "demos.npz",
            mat=np.vstack(rows),
            samples=np.array(keep_ids, dtype=object),
            sites=np.array(demo_sites, dtype=object),
            kinds=np.array(kinds, dtype=object),
            labels=np.array(labels, dtype=object),
        )
    hun_query = root / "results" / "HUN89_query.vcf.gz"
    hun_raw = root / "results" / "HUN89.vcf.gz"
    hun_vcf = hun_query if hun_query.exists() else hun_raw
    capture_rows = [
        (
            "HUN89-capture",
            hun_vcf,
            "HUN89_query",
            "independent chip VCF (FASTQ HUN89-1-ywk), not 2449 ID HUN89",
        ),
        ("Ages", root / "results" / "Ages.vcf.gz", "Ages", "aDNA capture VCF"),
    ]
    for demo_id, vcf, sid, label in capture_rows:
        if not vcf.exists():
            continue
        row = _vcf_demo_row(vcf, sid, demo_sites)
        if row is None:
            continue
        dest = (
            pack_dir(root) / "demo_HUN89_capture.npz"
            if demo_id == "HUN89-capture"
            else pack_dir(root) / f"demo_{demo_id}.npz"
        )
        packed_id = "HUN89_query" if demo_id == "HUN89-capture" else sid
        np.savez_compressed(
            dest,
            dosages=row,
            sites=np.array(demo_sites, dtype=object),
            sample=np.array([packed_id]),
        )
        catalog.append({"id": demo_id, "label": f"{sid} — {label}", "kind": "capture"})
    (pack_dir(root) / "demos.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )
    return catalog


def _vcf_demo_row(vcf: Path, sample: str, sites: list[str]) -> np.ndarray | None:
    from grapeancestry.cloud.vcf_py import parse_vcf_path

    panel = set(sites)
    parsed = parse_vcf_path(vcf, panel_sites=panel)
    if sample not in parsed.dosages:
        if len(parsed.samples) != 1:
            return None
        sample = parsed.samples[0]
    smap = parsed.dosages[sample]
    return np.array([int(smap.get(s, -1)) for s in sites], dtype=np.int8)


def _write_gea_pack(root: Path, fp_mat: np.ndarray, ids: list[str], fp_sites: list[str]) -> dict:
    from grapeancestry.identity.catalog import catalog_row, load_info, load_passport, passport_path
    from grapeancestry.popgen.gea import gea_panel, load_lonlat, write_gea_tables

    info = load_info(root / "data" / "panel" / "2449.info")
    passp = load_passport(str(passport_path(root)))
    groups = [info.get(i, {}).get("GEO", "") for i in ids]
    origins = [passp.get(i, {}).get("Origin", "") for i in ids]
    lonlat = load_lonlat(root / "data" / "panel" / "country_lonlat.tsv")
    payload = gea_panel(fp_mat, fp_sites, origins, groups, lonlat, top_n=30)
    write_gea_tables(payload, root / "results" / "gea")
    mean_abs = payload["mean_abs_spearman"]
    if isinstance(mean_abs, float) and mean_abs != mean_abs:
        mean_abs = None
    overall = payload["fst"]["overall_fst"]
    if isinstance(overall, float) and overall != overall:
        overall = None
    pairs = []
    for row in payload["fst"]["pairs"][:8]:
        fst = row["fst"]
        if isinstance(fst, float) and fst != fst:
            fst = None
        pairs.append({**row, "fst": fst})
    slim = {
        "n_with_origin_lon": payload["n_with_origin_lon"],
        "n_sites": payload["n_sites"],
        "mean_abs_spearman": mean_abs,
        "top": payload["top"][:15],
        "fst": {
            "overall_fst": overall,
            "n_groups": payload["fst"]["n_groups"],
            "pairs": pairs,
        },
        "method": payload["method"],
        "climate": payload["climate"],
    }
    (pack_dir(root) / "gea_summary.json").write_text(
        json.dumps(slim, indent=2) + "\n", encoding="utf-8"
    )
    return slim


def build_cloud_pack(root: Path, *, every: int = FP_EVERY) -> dict:
    """Subset the local 167K dosage cache into ``data/cloud/``.

    Always writes site-count metadata. Fingerprint + GS copies need the cache
    / ``results/gs`` on the build machine; Cloud then ships only this folder.
    """
    from grapeancestry.core.dosage import load_cache, resolve_cache

    out = pack_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    sites = load_panel_sites(root)
    counts: dict = {
        "n_panel_sites_listed": len(sites),
        "fingerprint": False,
        "gs_copied": 0,
        "demo_id": None,
    }
    cache = resolve_cache(root)
    fp_sites: list[str] = []
    mat = ids = cache_sites = None
    fp = None
    if cache.exists():
        mat, ids, cache_sites = load_cache(cache)
        want = [i for i, s in enumerate(cache_sites) if i % every == 0 or s in MAS_SITES]
        seen: set[int] = set()
        idx: list[int] = []
        for i in want:
            if i not in seen:
                seen.add(i)
                idx.append(i)
        fp = mat[:, idx].astype(np.int8)
        fp_sites = [cache_sites[i] for i in idx]
        np.savez_compressed(
            out / FP_NAME,
            mat=fp,
            samples=np.array(ids, dtype=object),
            sites=np.array(fp_sites, dtype=object),
        )
        counts["fingerprint"] = True
        counts["n_fingerprint_sites"] = len(fp_sites)
        counts["n_ref"] = len(ids)
        if "HUN89" in ids:
            counts["demo_id"] = "HUN89"
        sdr_set = set(sdr_sites(root))
        sdr_idx = [i for i, s in enumerate(cache_sites) if s in sdr_set]
        if sdr_idx:
            np.savez_compressed(
                out / SDR_PACK,
                mat=mat[:, sdr_idx].astype(np.int8),
                samples=np.array(ids, dtype=object),
                sites=np.array([cache_sites[i] for i in sdr_idx], dtype=object),
            )
            counts["n_sdr_sites"] = len(sdr_idx)
            counts["sdr_pack"] = True
        else:
            counts["sdr_pack"] = False
    gs_src = root / "results" / "gs"
    gs_dst = out / "gs"
    if gs_src.is_dir():
        for npz in gs_src.glob("*/*/model.npz"):
            dest = gs_dst / npz.parent.parent.name / npz.parent.name / "model.npz"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(npz, dest)
            counts["gs_copied"] += 1
        idxp = gs_src / "index.tsv"
        if idxp.exists():
            shutil.copy2(idxp, gs_dst / "index.tsv")
    if (
        mat is not None
        and ids is not None
        and cache_sites is not None
        and counts.get("demo_id") == "HUN89"
    ):
        counts["n_demo_sites"] = _write_hun89_demo(root, mat, ids, cache_sites, fp_sites)
        demo_sites = _demo_site_list(root, cache_sites, fp_sites)
        counts["n_named_demos"] = len(
            _write_named_demos(root, mat, ids, cache_sites, demo_sites)
        )
        if fp is not None:
            counts["gea_sites"] = _write_gea_pack(root, fp, ids, fp_sites).get("n_sites")
    write_manifest(root, {k: v for k, v in counts.items() if not isinstance(v, (dict, list))})
    return counts


def main() -> dict:
    counts = build_cloud_pack(suite_root())
    print(counts)
    return counts


if __name__ == "__main__":
    main()
