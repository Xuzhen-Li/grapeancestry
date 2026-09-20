"""Chip-companion analysis: QC + identity + in-panel ancestry lookup + GS/MAS."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from grapeancestry.cloud.card import trait_card
from grapeancestry.cloud.catalog import catalog_for_report
from grapeancestry.cloud.mas import MAS_LOCI
from grapeancestry.cloud.pack import gs_model_paths, load_fingerprint, pack_dir
from grapeancestry.cloud.sdr import sdr_report
from grapeancestry.cloud.sites import N_PANEL_SITES, load_panel_sites
from grapeancestry.cloud.vcf_py import ParsedVcf, align_dosage
from grapeancestry.identity.ibs import is_clone, nearest_neighbors, pair_stats


@dataclass
class SampleReport:
    sample: str
    n_called_panel: int
    n_panel: int
    overlap_frac: float
    n_vcf_records: int
    in_panel: bool
    ancestry: dict
    identity_top: list[dict]
    clone_flag: bool
    phenotype: list[dict]
    mas: list[dict]
    sdr: dict = field(default_factory=dict)
    trait_card: dict = field(default_factory=dict)
    catalog: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    identity_self: dict = field(default_factory=dict)
    purity: dict = field(default_factory=dict)
    parentage: list = field(default_factory=list)
    fstats: dict = field(default_factory=dict)
    local_ancestry: dict = field(default_factory=dict)
    tree: dict = field(default_factory=dict)
    gea: dict = field(default_factory=dict)
    impute: dict = field(default_factory=dict)
    phenotype_imputed: list = field(default_factory=list)


def _chip_qc(site_map: dict[str, int], panel_sites: set[str], n_records: int) -> tuple[int, float]:
    n_called = sum(1 for s, d in site_map.items() if s in panel_sites and d >= 0)
    frac = n_called / max(len(panel_sites), 1)
    return n_called, frac


def _hit_dict(h, q, mat, ids) -> dict:
    i = ids.index(h.ref_id)
    ps = pair_stats(q, mat[i], h.ref_id)
    return {
        "ref_id": h.ref_id,
        "ibs": h.ibs,
        "n_comparable": h.n_comparable,
        "relationship": ps.relationship,
        "king_robust": ps.king_robust,
    }


def _identity(
    site_map: dict[str, int],
    root: Path,
    sample: str,
    top_n: int = 10,
) -> tuple[list[dict], bool, dict, str | None]:
    packed = load_fingerprint(root)
    if packed is None:
        return [], False, {}, "no fingerprint pack (run python -m grapeancestry.cloud.pack)"
    mat, ids, sites = packed
    q = np.asarray(align_dosage(site_map, sites), np.int8)
    self_row: dict = {}
    skip = {sample} if sample in ids else set()
    if sample in ids:
        ps = pair_stats(q, mat[ids.index(sample)], sample)
        self_row = {
            "ref_id": sample,
            "ibs": ps.ibs,
            "n_comparable": ps.n_comparable,
            "relationship": ps.relationship,
            "king_robust": ps.king_robust,
            "note": "Self-in-panel QC (independently called GT), not a clone control.",
        }
    hits = nearest_neighbors(q, mat, ids, top_n=top_n, exclude_ids=skip)
    top = [_hit_dict(h, q, mat, ids) for h in hits]
    clone = bool(top) and (
        top[0].get("relationship") == "Identical" or is_clone(float(top[0]["ibs"]))
    )
    return top, clone, self_row, None


def _ancestry(sample: str, root: Path, site_map: dict[str, int] | None = None) -> dict:
    admix = root / "data" / "panel" / "admixture"
    info = root / "data" / "panel" / "2449.info"
    try:
        from grapeancestry.adna.admixture import (
            component_labels_colors,
            load_admixture_k_range,
        )
        from grapeancestry.adna.panel167k_nogwas import (
            PANEL167K_NOGWAS_FAMILY,
            load_family_sites,
            panel167k_assets_complete,
        )

        c = load_admixture_k_range(sample, admix, info_path=info, mode="lookup")
        if not (c and c.q_by_k) and site_map and panel167k_assets_complete(admix):
            panel_sites = load_family_sites(admix)
            cache_sites = list(site_map)
            dosage = np.array([float(site_map[s]) for s in cache_sites])
            c = load_admixture_k_range(
                sample,
                admix,
                info_path=info,
                dosage=dosage,
                cache_sites=cache_sites,
                panel_sites=panel_sites,
                mode="nnls",
                run_family=PANEL167K_NOGWAS_FAMILY,
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc)}
    if c is None or (not c.q_by_k and not c.projected_by_k):
        return {
            "ok": False,
            "in_panel": False,
            "reason": "ID not in 2449 keep-list and panel167k P projection did not run.",
        }
    q8 = c.q_by_k.get(8) or c.projected_by_k.get(8) or {}
    labels, colors, _aliases = ([], [], [])
    try:
        labels, colors, _aliases = component_labels_colors(
            admix, 8, run_family=c.run_family
        )
    except Exception:
        pass
    return {
        "ok": True,
        "in_panel": bool(c.q_by_k),
        "source": c.source,
        "grp": c.grp_value,
        "projection_status": c.projection_status,
        "q8": q8,
        "q_by_k": {str(k): v for k, v in (c.q_by_k or c.projected_by_k).items()},
        "labels": labels,
        "colors": colors,
        "meta": c.meta,
        "note": (
            "In-panel lookup of frozen Q."
            if c.q_by_k
            else "Projected onto frozen panel167k_nogwas P (NNLS in Cloud; not a new unsupervised fit)."
        ),
    }


def _gs_index_best(root: Path) -> dict[tuple[str, str], tuple[float, str]]:
    path = pack_dir(root) / "gs" / "index.tsv"
    out: dict[tuple[str, str], tuple[float, str]] = {}
    if not path.exists():
        return out
    import csv

    with path.open() as fh:
        r = csv.DictReader(fh, delimiter="\t")
        for row in r:
            key = (row.get("trait", ""), row.get("source", ""))
            try:
                out[key] = (float(row["cv_r"]), row.get("best_model", ""))
            except (KeyError, ValueError):
                continue
    return out


def _phenotype(site_map: dict[str, int], root: Path) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    warnings: list[str] = []
    best = _gs_index_best(root)
    try:
        from grapeancestry.breeding.gs import load_model, predict_sample
    except Exception as exc:  # noqa: BLE001
        return [], [str(exc)]
    paths = gs_model_paths(root)
    if not paths:
        warnings.append("No GS models in data/cloud/gs (pack did not copy results/gs).")
    for npz in paths:
        mdl = load_model(npz)
        q = np.asarray(align_dosage(site_map, mdl.sites), float)
        gebv, cov = predict_sample(mdl, q)
        flag = "ok"
        cv_best, best_name = best.get((mdl.trait, mdl.source), (mdl.cv_r, mdl.name))
        if cv_best != cv_best or cv_best < 0.3:
            flag = "low_cv_r"
        if cov < 0.5:
            flag = "low_coverage"
        usable = mdl.trait == "OIV 225" and cv_best == cv_best and cv_best >= 0.5
        rows.append(
            {
                "trait": mdl.trait,
                "source": mdl.source,
                "scale": mdl.scale,
                "pred": gebv,
                "cv_r_model": mdl.cv_r,
                "cv_r_best": cv_best,
                "best_model": best_name,
                "coverage": cov,
                "flag": flag,
                "usable_for_ranking": usable,
                "model": mdl.name,
                "n_train": mdl.n_train,
            }
        )
    return rows, warnings


def _mas(site_map: dict[str, int]) -> list[dict]:
    out = []
    for loc in MAS_LOCI:
        dose = site_map.get(loc["site"], -1)
        out.append({**loc, "dosage": int(dose), "called": dose >= 0})
    return out


def analyze_parsed(parsed: ParsedVcf, root: Path, *, sample: str | None = None) -> list[SampleReport]:
    from grapeancestry.cloud.extras import (
        fstats_block,
        gea_query_context,
        nj_block,
        paint_block,
        parentage_block,
        purity_block,
    )
    from grapeancestry.resource.impute import site_map_impute

    panel_list = load_panel_sites(root)
    panel_set = set(panel_list)
    n_panel = len(panel_set) or N_PANEL_SITES
    names = [sample] if sample else parsed.samples
    packed = load_fingerprint(root)
    reports: list[SampleReport] = []
    for sid in names:
        if sid not in parsed.dosages:
            continue
        smap = parsed.dosages[sid]
        n_called, frac = _chip_qc(smap, panel_set, parsed.n_records)
        ident, clone, self_row, w_id = _identity(smap, root, sid)
        anc = _ancestry(sid, root, site_map=smap)
        pheno, w_ph = _phenotype(smap, root)
        cat = catalog_for_report(sid, clone_flag=clone, identity_top=ident, root=root)
        sdr = sdr_report(smap, root)
        card = trait_card(smap, root)
        purity: dict = {}
        parentage: list = []
        fstats: dict = {}
        paint: dict = {}
        tree: dict = {}
        impute_meta: dict = {}
        pheno_imp: list = []
        if packed is not None:
            mat, ids, fp_sites = packed
            q = np.asarray(align_dosage(smap, fp_sites), np.int8)
            purity = purity_block(q, mat)
            parentage = parentage_block(q, mat, ids, ident)
            fstats = fstats_block(q, mat, ids, root)
            paint = paint_block(q, mat, ids, root)
            tree = nj_block(q, mat, ids, ident, sid)
            filled, impute_meta = site_map_impute(smap, mat, fp_sites, ref_ids=ids)
            pheno_imp, w_imp = _phenotype(filled, root)
            w_ph = [*w_ph, *[w for w in w_imp if w]]
        gea = gea_query_context(sid, root)
        warns = [w for w in (w_id, *w_ph) if w]
        demo_name = str(parsed.filename or "")
        if n_called < 1000 and not demo_name.startswith("demo"):
            warns.append(f"only {n_called} panel sites called — not a full 167K chip VCF?")
        if frac < 0.55 and sdr.get("unphased_sex_proxy") == "female_like":
            warns.append(
                "low panel overlap: female_like SDR het can be allelic dropout (aDNA), not sex"
            )
        reports.append(
            SampleReport(
                sample=sid,
                n_called_panel=n_called,
                n_panel=n_panel,
                overlap_frac=frac,
                n_vcf_records=parsed.n_records,
                in_panel=bool(anc.get("in_panel")),
                ancestry=anc,
                identity_top=ident,
                clone_flag=clone,
                phenotype=pheno,
                mas=_mas(smap),
                sdr=sdr,
                trait_card=card,
                catalog=cat,
                warnings=warns,
                identity_self=self_row,
                purity=purity,
                parentage=parentage,
                fstats=fstats,
                local_ancestry=paint,
                tree=tree,
                gea=gea,
                impute=impute_meta,
                phenotype_imputed=pheno_imp,
            )
        )
    return reports


def reports_as_dicts(reports: list[SampleReport]) -> list[dict]:
    def _jsonable(obj):
        if isinstance(obj, dict):
            return {str(k): _jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_jsonable(v) for v in obj]
        if isinstance(obj, (np.floating, np.integer)):
            x = obj.item()
            if isinstance(x, float) and x != x:
                return None
            return x
        if isinstance(obj, float) and obj != obj:
            return None
        return obj

    return [_jsonable(asdict(r)) for r in reports]


def _parsed_from_row(sample: str, sites: list[str], row, filename: str) -> ParsedVcf:
    dosages = {sites[i]: int(row[i]) for i in range(len(sites))}
    return ParsedVcf(
        samples=[sample],
        dosages={sample: dosages},
        n_records=len(sites),
        filename=filename,
    )


def demo_from_fingerprint(root: Path, sample: str = "HUN89") -> ParsedVcf | None:
    """Load a packed named demo, else a fingerprint row (in-panel control)."""
    aliases = {
        "HUN89-capture": "demo_HUN89_capture.npz",
        "Ages": "demo_Ages.npz",
    }
    alias = pack_dir(root) / aliases.get(sample, "")
    if sample in aliases and alias.exists():
        z = np.load(alias, allow_pickle=True)
        sid = str(z["sample"][0]) if "sample" in z.files else sample
        kind = "capture" if sample.endswith("capture") else "adna"
        return _parsed_from_row(sid, list(z["sites"]), z["dosages"], f"demo-{kind}")
    hun = pack_dir(root) / "demo_HUN89.npz"
    if sample == "HUN89" and hun.exists():
        z = np.load(hun, allow_pickle=True)
        return _parsed_from_row("HUN89", list(z["sites"]), z["dosages"], "demo-HUN89")
    multi = pack_dir(root) / "demos.npz"
    if multi.exists():
        z = np.load(multi, allow_pickle=True)
        ids = [str(x) for x in z["samples"]]
        if sample in ids:
            i = ids.index(sample)
            kind = str(z["kinds"][i]) if "kinds" in z.files else "in_panel"
            return _parsed_from_row(sample, list(z["sites"]), z["mat"][i], f"demo-{kind}")
    packed = load_fingerprint(root)
    if packed is None:
        return None
    mat, ids, sites = packed
    if sample not in ids:
        return None
    return _parsed_from_row(sample, sites, mat[ids.index(sample)], "demo-fingerprint")


def list_demos(root: Path) -> list[dict]:
    """Named case-study demos shipped in data/cloud/."""
    rows: list[dict] = []
    man = pack_dir(root) / "demos.json"
    if man.exists():
        import json

        try:
            rows = json.loads(man.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rows = []
    if not rows:
        packed = load_fingerprint(root)
        if packed and "HUN89" in packed[1]:
            rows = [{"id": "HUN89", "label": "HUN89 (fingerprint row)", "kind": "in_panel"}]
    return rows
