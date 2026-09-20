"""GrapeAncestry Chip Companion — online tool for the 167K capture panel.

Upload a panel-site VCF (no bcftools). In-panel IDs get Science-named K=8
lookup; every sample gets chip QC, IBS vs 2449, and colour MAS / GS if packed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

st.set_page_config(page_title="GrapeAncestry Chip Companion", layout="wide")
st.title("GrapeAncestry Chip Companion")
st.caption(
    "167,433-SNP capture panel (VS-1) · VCF → QC / identity / SDR type / colour"
)
st.markdown(
    "**EN**: Companion for *this* chip, not a new GWAS cohort. "
    "Colour is the only GS trait we treat as rankable (Dong et al. 2023 *Science* "
    "[doi:10.1126/science.add8655](https://doi.org/10.1126/science.add8655)). "
    "Flower sex is an unphased SDR-window proxy.  \n"
    "**CN**: 167K 芯片配套。GS 只有皮色能排序。花性按 SDR 窗未定相代理，不是 GS。"
)
st.markdown("[VitisGDB](https://www.vitisgdb.com)")


def _run_bytes(data: bytes, name: str, sample: str | None = None):
    from grapeancestry.cloud.analyze import analyze_parsed, reports_as_dicts
    from grapeancestry.cloud.sites import load_panel_sites
    from grapeancestry.cloud.vcf_py import parse_vcf_bytes

    panel = set(load_panel_sites(ROOT))
    parsed = parse_vcf_bytes(data, filename=name, panel_sites=panel or None)
    reports = analyze_parsed(parsed, ROOT, sample=sample)
    return reports, reports_as_dicts(reports)


def _show_report(rep) -> None:
    import pandas as pd

    st.subheader(rep.sample)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Panel sites called", f"{rep.n_called_panel:,}")
    c2.metric("Panel listed", f"{rep.n_panel:,}")
    c3.metric("Overlap", f"{100 * rep.overlap_frac:.1f}%")
    c4.metric("In 2449 panel", "yes" if rep.in_panel else "no")
    for w in rep.warnings:
        st.warning(w)

    st.markdown("**Identity / 身份**")
    if getattr(rep, "identity_self", None):
        st.caption("Self-in-panel QC (excluded from clone screen).")
        st.dataframe(pd.DataFrame([rep.identity_self]), hide_index=True)
    if rep.identity_top:
        st.caption("Nearest non-self (clone screen).")
        st.dataframe(pd.DataFrame(rep.identity_top), hide_index=True)
        if rep.clone_flag:
            st.success(f"Non-self Identical / clone-level match to `{rep.identity_top[0]['ref_id']}`")
    else:
        st.info("Identity needs `data/cloud/fingerprint.npz` (run `python -m grapeancestry.cloud.pack`).")

    cat = rep.catalog or {}
    st.markdown("**Catalog phenotype / 目录表型**")
    st.caption(
        "EN: OIV from `phenotype.tsv` for this ID or an Identical hit. Not a new measurement.  \n"
        "CN: 只显示面板目录里已有的 OIV / VIVC，不是新测表型。"
    )
    if cat.get("ok"):
        st.write(f"via `{cat.get('via')}` · borrowed_from `{cat.get('borrowed_from')}`")
        if cat.get("note"):
            st.caption(cat["note"])
        if cat.get("oiv"):
            st.dataframe(pd.DataFrame(cat["oiv"]), hide_index=True)
        if cat.get("annot"):
            st.dataframe(pd.DataFrame([cat["annot"]]), hide_index=True)
    else:
        st.info(cat.get("reason") or "No catalog row.")

    sdr = rep.sdr or {}
    st.markdown("**SDR type / 花性（未定相）**")
    st.caption(
        "EN: Heterozygosity in the ~180 kb SDR window + nearest 2449 neighbour. "
        "Science sex = haplotypes H1–H5, not this SNP and not GS.  \n"
        "CN: 未定相代理。Science 花性是 SDR 单倍型，不是单个 SNP，也不是 GS。"
    )
    if sdr:
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("SDR sites called", f"{sdr.get('n_called', 0)}/{sdr.get('n_window', 0)}")
        het = sdr.get("het_frac")
        c6.metric("SDR het", "—" if het is None else f"{100 * het:.1f}%")
        c7.metric("Unphased proxy", sdr.get("unphased_sex_proxy") or "—")
        cs = sdr.get("catalog_sex") or {}
        c8.metric("Catalog sex of match", cs.get("label") or "—")
        if sdr.get("nearest"):
            st.dataframe(pd.DataFrame([sdr["nearest"]]), hide_index=True)
        st.caption(sdr.get("phase_status", ""))
        st.caption(sdr.get("het_rule", ""))
    else:
        st.info("SDR window list missing (`data/trait_locus.tsv`).")

    st.markdown("**Ancestry K=8 / 祖先成分**")
    anc = rep.ancestry or {}
    if anc.get("ok"):
        st.write(
            f"Grp `{anc.get('grp', '')}` · source `{anc.get('source', '')}` · "
            f"{anc.get('note', '')}"
        )
        q8 = anc.get("q8") or {}
        if q8:
            from grapeancestry.cloud.plot import k8_png_bytes

            st.image(k8_png_bytes(q8, title=rep.sample))
            st.dataframe(pd.DataFrame([q8]), hide_index=True)
    else:
        st.info(anc.get("reason") or "Ancestry lookup unavailable.")

    st.markdown("**Trait locus card / 位点卡**")
    st.caption(
        "EN: Colour SNPs on chip; muscat = nearest site to Science VvDXS; "
        "seedless = design-tag coverage (n=10, not AGL11); named windows = our MAS/GWAS loci.  \n"
        "CN: 皮色位点在芯片上。麝香是 VvDXS 最近位点。无核只报设计标签覆盖。命名窗是我们自己的 MAS/GWAS 位点。"
    )
    card = rep.trait_card or {}
    if card.get("colour"):
        st.write("Colour / 皮色")
        st.dataframe(pd.DataFrame(card["colour"]), hide_index=True)
    if card.get("muscat"):
        st.write("Muscat / 麝香")
        st.dataframe(pd.DataFrame([card["muscat"]]), hide_index=True)
    if card.get("seedless"):
        st.write("Seedless design tags / 无核设计标签")
        st.dataframe(pd.DataFrame([card["seedless"]]), hide_index=True)
    if card.get("sweeps"):
        st.write("Named windows / 我们的命名窗")
        st.dataframe(pd.DataFrame(card["sweeps"]), hide_index=True)
    by_grp = ROOT / "data" / "cloud" / "selection_by_grp_named.tsv"
    if by_grp.exists():
        st.write("Selection by Grp / 每个群体")
        st.caption(
            "EN: Same named windows, but het is within that Grp and Fst is that Grp vs the rest. "
            "Unphased. OUT skipped. Not XP-CLR/iHS.  \n"
            "CN: 每个 Grp 自己的窗杂合，以及该群相对其余样本的 Fst。OUT 不算。"
        )
        st.dataframe(pd.read_csv(by_grp, sep="\t"), hide_index=True)
    vs_s29 = ROOT / "data" / "cloud" / "selection_vs_science_s29.tsv"
    if vs_s29.exists():
        st.write("Reference: Dong 2023 shared CG1∩CG2 bins (paper Table S29)")
        st.caption(
            "EN: Dong et al. 2023 (doi:10.1126/science.add8655) scanned Syl-E1/CG1 and Syl-E2/CG2. "
            "Rule: nucleotide-diversity difference and population differentiation both top 5%. "
            "Table S28 = each group's list. Table S29 = intersection (189 genes / 31 regions in both CG1 and CG2). "
            "This table is chip het/Fst inside those published intervals — not our named-window list and not a new WGS scan.  \n"
            "CN: 表 S29 是 CG1 与 CG2 驯化扫描清单的交集（不是随便一个附表）。这里只把 167K 分数叠到这些已发表区间上核对。"
        )
        st.dataframe(pd.read_csv(vs_s29, sep="\t"), hide_index=True)
    if card.get("omitted"):
        st.caption(card["omitted"])

    st.markdown("**Phenotype from genotype / 基因型→表型（GS）**")
    st.caption(
        "EN: GS CV *r* is on the 2449∩phenotype training set. Only OIV 225 with "
        "*r*≥0.5 is flagged usable. Sex = SDR haplotype (Science), not GS. "
        "Seedlessness was not a Science GWAS trait; n_seedless=10 here.  \n"
        "CN: 只有皮色 GS 达标。花性按 Science 做 SDR 单倍型，不是基因组选择。无核 Science 没做。"
    )
    if rep.phenotype:
        st.dataframe(pd.DataFrame(rep.phenotype), hide_index=True)
    gs_idx = ROOT / "data" / "cloud" / "gs" / "index.tsv"
    if gs_idx.exists():
        st.caption("Shipped GS CV table")
        st.dataframe(pd.read_csv(gs_idx, sep="\t"), hide_index=True)

    st.markdown("**MAS SNPs (same as colour / muscat / SDR lead)**")
    st.dataframe(pd.DataFrame(rep.mas), hide_index=True)

    if getattr(rep, "purity", None):
        st.markdown("**Purity / 纯度**")
        st.dataframe(pd.DataFrame([rep.purity]), hide_index=True)
    if getattr(rep, "parentage", None):
        st.markdown("**Parentage (Mendel vs top hits)**")
        st.dataframe(pd.DataFrame(rep.parentage), hide_index=True)
    if getattr(rep, "fstats", None) and (rep.fstats.get("f3") or rep.fstats.get("f4")):
        st.markdown("**f3 / f4 (Grp means)**")
        if rep.fstats.get("f3"):
            st.dataframe(pd.DataFrame(rep.fstats["f3"]), hide_index=True)
        if rep.fstats.get("f4"):
            st.dataframe(pd.DataFrame(rep.fstats["f4"]), hide_index=True)
    if getattr(rep, "local_ancestry", None) and rep.local_ancestry.get("counts"):
        st.markdown("**Windowed local ancestry (fingerprint IBS)**")
        st.caption(rep.local_ancestry.get("note") or "")
        st.dataframe(pd.DataFrame([rep.local_ancestry["counts"]]), hide_index=True)
    if getattr(rep, "tree", None) and rep.tree.get("ok"):
        st.markdown("**NJ tree (query + top hits)**")
        st.code(rep.tree.get("newick") or "", language="text")
    if getattr(rep, "gea", None):
        st.markdown("**Geography / Fst (not WorldClim)**")
        st.caption(rep.gea.get("note") or "")
        geo_row = {k: rep.gea.get(k) for k in ("origin", "geo", "lon", "lat")}
        st.dataframe(pd.DataFrame([geo_row]), hide_index=True)
        panel = (rep.gea.get("panel") or {})
        if panel.get("fst"):
            st.write("Panel Fst by GEO")
            st.dataframe(pd.DataFrame(panel["fst"].get("pairs") or []), hide_index=True)
        if panel.get("top"):
            st.write("Top dosage~longitude sites")
            st.dataframe(pd.DataFrame(panel["top"]), hide_index=True)
    if getattr(rep, "impute", None):
        st.markdown("**k-NN imputation (fingerprint)**")
        st.caption(rep.impute.get("note") or "")
        st.write(
            f"imputed {rep.impute.get('n_imputed', 0)} / missing {rep.impute.get('n_missing', 0)} (k={rep.impute.get('k')})"
        )
        if rep.impute.get("neighbors"):
            st.dataframe(pd.DataFrame(rep.impute["neighbors"]), hide_index=True)
    if getattr(rep, "phenotype_imputed", None):
        st.caption("GS scores after k-NN fill of missing fingerprint sites")
        st.dataframe(pd.DataFrame(rep.phenotype_imputed), hide_index=True)


companion, lab = st.tabs(["Chip companion", "Lab (Docker / HPC)"])

with companion:
    from grapeancestry.cloud.analyze import list_demos

    demos = list_demos(ROOT)
    labels = {d["id"]: f"{d['id']} — {d.get('label') or d.get('kind')}" for d in demos}
    demo_id = st.selectbox(
        "Case-study demo",
        options=list(labels.keys()) or ["HUN89"],
        format_func=lambda x: labels.get(x, x),
    )
    up = st.file_uploader(
        "Panel-site VCF / VCF.gz (≤200 MB, ≤20 samples)",
        type=["vcf", "gz"],
        accept_multiple_files=False,
    )
    demo = st.button("Run selected demo")
    go = st.button("Analyze upload", type="primary", disabled=up is None)

    reports = None
    payload = None
    if demo:
        from grapeancestry.cloud.analyze import analyze_parsed, demo_from_fingerprint, reports_as_dicts

        parsed = demo_from_fingerprint(ROOT, demo_id)
        if parsed is None:
            st.error("Demo not packed. Run `python -m grapeancestry.cloud.pack` with the 167K cache.")
        else:
            reports = analyze_parsed(parsed, ROOT)
            payload = reports_as_dicts(reports)
    elif go and up is not None:
        try:
            reports, payload = _run_bytes(up.getvalue(), up.name or "query.vcf")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            reports = None

    if reports:
        for rep in reports:
            _show_report(rep)
        blob = json.dumps(payload, indent=2).encode()
        st.download_button("Download JSON", blob, file_name="chip_companion.json")

    with st.expander("Methods / 方法（必须读）"):
        st.markdown(
            """
**EN**
- Sites: 167,433 VS-1 positions (`panel167k_nogwas` ∪ design-time GWAS tags).
- Ancestry: **lookup** of frozen Q for IDs in `2449.info`. New IDs: NNLS onto frozen P in Cloud.
- Identity: IBS on fingerprint; **self is QC**, clone screen is non-self Identical.
- Catalog: Dong 2449 passport VIVC for all 2449 IDs; OIV only if in `phenotype.tsv`.
- SDR: unphased window het. Not Science H1–H5.
- GS: colour only is rankable. Imputation is panel k-NN, not GLIMPSE2.
- GEA: origin longitude Spearman + Fst by GEO. Not WorldClim rasters.

**CN**
- 身份：自身是 QC，克隆看非自身 Identical。护照 VIVC 覆盖 2449。
- 填充是面板 k-NN，不是单倍型填充。GEA 是原产地经度，不是 WorldClim。
            """
        )

with lab:
    import pandas as pd

    st.caption("Needs bcftools / linux ADMIXTURE. Catalog / GEA / GWAS tables are local files.")
    from grapeancestry.adna.panel167k_nogwas import panel167k_assets_complete

    ADMIX = ROOT / "data" / "panel" / "admixture"
    RESULTS = ROOT / "results"
    if panel167k_assets_complete(ADMIX):
        st.success("Frozen panel167k_nogwas Q+P present")
    else:
        st.warning("panel167k_nogwas Q+P not ingested — official -P disabled.")
    up_vcfs = st.file_uploader(
        "VCF(s) for official -P",
        type=["vcf", "gz"],
        accept_multiple_files=True,
        key="lab_vcf",
    )
    if st.button("Run official K=2–8 (Docker)") and up_vcfs:
        if not panel167k_assets_complete(ADMIX):
            st.error("Need ingested P matrices.")
        else:
            from grapeancestry.adna.admix_project import project_query_vcfs
            from grapeancestry.adna.admixture import load_admixture_k_range
            from grapeancestry.adna.panel167k_nogwas import PANEL167K_NOGWAS_FAMILY
            from grapeancestry.report.build_report import write_admix_k28_report

            batch = RESULTS / "upload"
            batch.mkdir(parents=True, exist_ok=True)
            paths = []
            for i, f in enumerate(up_vcfs):
                dest = batch / (f.name or f"s{i}.vcf.gz")
                dest.write_bytes(f.getvalue())
                paths.append(dest)
            try:
                projected = project_query_vcfs(
                    paths,
                    ADMIX,
                    out_dir=RESULTS / "admix_project",
                    method="auto",
                    run_family=PANEL167K_NOGWAS_FAMILY,
                    workdir=RESULTS / "admix_project" / "work",
                )
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                projected = {}
            for sid, by_k in projected.items():
                contrast = load_admixture_k_range(
                    sid,
                    ADMIX,
                    info_path=ROOT / "data" / "panel" / "2449.info",
                    mode="lookup",
                    run_family=PANEL167K_NOGWAS_FAMILY,
                )
                if contrast is None:
                    continue
                contrast.projected_by_k = by_k
                html = RESULTS / "admix_project" / f"{sid}.report.html"
                write_admix_k28_report(sid, ROOT, html, contrast)
                st.success(sid)
    st.markdown("---")
    st.markdown("**Catalog / VIVC**")
    cat_id = st.text_input("Panel ID", value="26")
    if st.button("Lookup catalog"):
        from grapeancestry.identity.catalog import catalog_row

        st.json(catalog_row(cat_id.strip(), ROOT))
    st.markdown("**Locus search**")
    q = st.text_input("Site / gene / OIV token", value="2:5116947")
    if st.button("Search loci"):
        from grapeancestry.resource.portal import search_panel

        st.dataframe(search_panel(ROOT, q, limit=20), hide_index=True)
    gwas_idx = RESULTS / "gwas" / "index.tsv"
    if gwas_idx.exists():
        st.markdown("**Precomputed GWAS index**")
        st.dataframe(pd.read_csv(gwas_idx, sep="\t"), hide_index=True)
    gs_idx = RESULTS / "gs" / "index.tsv"
    if gs_idx.exists():
        st.markdown("**Precomputed GS index**")
        st.dataframe(pd.read_csv(gs_idx, sep="\t"), hide_index=True)
    gea_idx = RESULTS / "gea" / "index.tsv"
    if gea_idx.exists():
        st.markdown("**GEA (origin longitude)**")
        st.dataframe(pd.read_csv(gea_idx, sep="\t"), hide_index=True)
    fst_geo = RESULTS / "gea" / "fst_geo.tsv"
    if fst_geo.exists():
        st.markdown("**Fst by GEO**")
        st.dataframe(pd.read_csv(fst_geo, sep="\t"), hide_index=True)
    seq_tsv = RESULTS / "seqscore" / "mas.tsv"
    if seq_tsv.exists():
        st.markdown("**Sequence window score (5 MAS SNPs)**")
        st.caption(
            "EN: Cut VS-1 DNA around 5 chip SNPs. markov_delta ≈ 0 means ALT is as typical as REF. "
            "Not a GWAS p-value.  \n"
            "CN: 只切了芯片上 5 个位点两边的 VS-1 序列。delta 接近 0 = ALT 并不比 REF 更不像葡萄基因组。"
        )
        cols = [
            "site",
            "gene",
            "vcf_ref",
            "vcf_alt",
            "center_snippet",
            "markov_delta",
            "lm_delta",
            "lm_status",
        ]
        df = pd.read_csv(seq_tsv, sep="\t")
        st.dataframe(df[[c for c in cols if c in df.columns]], hide_index=True)
    sel_named = RESULTS / "selection" / "named_windows.tsv"
    if sel_named.exists():
        st.markdown("**Selection named windows (our scan)**")
        st.caption(
            "EN: Our MAS/GWAS windows on 167K. Windowed het + Fst by Grp. Not XP-CLR/iHS.  \n"
            "CN: 我们自己的 MAS/GWAS 窗，未定相杂合与地理 Fst。不是 Science Table S29 的清单。"
        )
        st.dataframe(pd.read_csv(sel_named, sep="\t"), hide_index=True)
    sel_fst = RESULTS / "selection" / "fst_top.tsv"
    if sel_fst.exists():
        st.markdown("**Selection Fst top (GEO)**")
        st.dataframe(pd.read_csv(sel_fst, sep="\t"), hide_index=True)
    sel_grp = RESULTS / "selection" / "by_grp_named.tsv"
    if sel_grp.exists():
        st.markdown("**Selection by Grp (each population)**")
        st.caption(
            "EN: Within-Grp windowed het and Fst(this Grp vs the rest). Unphased. "
            "OUT n=1 is skipped. Not XP-CLR/iHS.  \n"
            "CN: 每个 Grp 自己的窗杂合，以及该群相对其余样本的 Fst。OUT 只有 1 个样本所以不算。"
        )
        st.dataframe(pd.read_csv(sel_grp, sep="\t"), hide_index=True)
    sel_grp_fst = RESULTS / "selection" / "by_grp_fst_top.tsv"
    if sel_grp_fst.exists():
        st.markdown("**Selection Fst top per Grp**")
        st.dataframe(pd.read_csv(sel_grp_fst, sep="\t"), hide_index=True)
    manh_png = RESULTS / "selection" / "manhattan_fst.png"
    if not manh_png.exists():
        manh_png = ROOT / "data" / "cloud" / "selection_manhattan_fst.png"
    if manh_png.exists():
        st.markdown("**Fst Manhattan (GEO)**")
        st.caption(
            "EN: Genome-wide Fst by Grp. Green in the HTML report = our named windows. Not XP-CLR.  \n"
            "CN: 全基因组地理 Fst。交互报告里的绿色带是我们的命名窗。"
        )
        st.image(str(manh_png))
    het_png = RESULTS / "selection" / "manhattan_het.png"
    if not het_png.exists():
        het_png = ROOT / "data" / "cloud" / "selection_manhattan_het.png"
    if het_png.exists():
        st.markdown("**Windowed-het Manhattan**")
        st.image(str(het_png))
    heat_png = RESULTS / "selection" / "heatmap_grp_het.png"
    if not heat_png.exists():
        heat_png = ROOT / "data" / "cloud" / "selection_heatmap_grp.png"
    if heat_png.exists():
        st.markdown("**Per-Grp het heatmap**")
        st.image(str(heat_png))
    heat_fst = RESULTS / "selection" / "heatmap_grp_fst.png"
    if not heat_fst.exists():
        heat_fst = ROOT / "data" / "cloud" / "selection_heatmap_grp_fst.png"
    if heat_fst.exists():
        st.markdown("**Per-Grp Fst vs rest**")
        st.image(str(heat_fst))
    sc_png = RESULTS / "selection" / "fst_het_scatter.png"
    if not sc_png.exists():
        sc_png = ROOT / "data" / "cloud" / "selection_fst_het_scatter.png"
    if sc_png.exists():
        st.markdown("**Fst vs windowed het**")
        st.caption(
            "EN: High Fst + low het = candidate. Green = our named windows.  \n"
            "CN: 高 Fst + 低杂合是候选。绿色是我们的命名窗。"
        )
        st.image(str(sc_png))
    lz_idx = RESULTS / "selection" / "locuszoom.tsv"
    if lz_idx.exists():
        st.markdown("**Selection LocusZoom loci**")
        st.caption(
            "EN: Same LocusZoom.js as GWAS in the HTML report (Y = Fst or windowed het).  \n"
            "CN: HTML 报告里和 GWAS 同一套 LocusZoom，纵轴是 Fst 或窗杂合。"
        )
        st.dataframe(pd.read_csv(lz_idx, sep="\t"), hide_index=True)
    vs_sum = RESULTS / "selection" / "vs_science_summary.tsv"
    vs_s29 = RESULTS / "selection" / "vs_science_s29.tsv"
    vs_ov = RESULTS / "selection" / "vs_science_overlap.tsv"
    s29_png = RESULTS / "selection" / "s29_dual.png"
    if not s29_png.exists():
        s29_png = ROOT / "data" / "cloud" / "selection_s29_dual.png"
    if vs_sum.exists() or vs_s29.exists() or vs_ov.exists() or s29_png.exists():
        with st.expander("Reference only: Dong 2023 shared CG1∩CG2 bins (paper Table S29)"):
            st.caption(
                "EN: Dong et al. 2023 (doi:10.1126/science.add8655) Fig. 3D: regions with increased "
                "nucleotide-diversity difference and population differentiation, both top 5%, in Syl-E1/CG1 "
                "and Syl-E2/CG2. Table S28 = each list. Table S29 = 189 genes in 31 regions in both groups "
                "(mostly chr 2 and 17: SDR, VvMybA, SDH). Numbers here are 167K chip scores inside those "
                "published intervals. Not our call set. Not XP-CLR.  \n"
                "CN: 表 S29 = CG1 与 CG2 共享驯化窗（两组清单的交集）。只做重合核对，不是本扫描。"
            )
            if vs_sum.exists():
                st.dataframe(pd.read_csv(vs_sum, sep="\t"), hide_index=True)
            if vs_s29.exists():
                st.dataframe(pd.read_csv(vs_s29, sep="\t"), hide_index=True)
            if vs_ov.exists():
                st.dataframe(pd.read_csv(vs_ov, sep="\t"), hide_index=True)
            if s29_png.exists():
                st.image(str(s29_png))
