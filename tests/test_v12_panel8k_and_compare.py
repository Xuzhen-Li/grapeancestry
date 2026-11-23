"""v1.2 8K projection, comparison verdict, and panel-mode command wiring."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from click.testing import CliRunner

from grapeancestry.adna.panel8k import (
    SITE_NOTE_HTML,
    GctaWeights,
    _write_dashboard,
    ensure_panel_dosage,
    estimate_q_fixed_p,
    fit_gcta_weights_from_arrays,
    load_site_keys,
    project_query_pcs,
)
from grapeancestry.cli import main
from grapeancestry.report.compare import (
    build_comparison_report,
    build_top_nav_html,
    compare_payloads,
    synthesize_verdict,
    write_demo_entry_html,
)
from grapeancestry.report.interactive_dashboard import write_dashboard_html
from grapeancestry.web_run import (
    PipelineOptions,
    batch_pipeline_commands,
    find_report_artifacts,
    pipeline_command,
)

ROOT = Path(__file__).resolve().parents[1]


def test_sites_8044_match_dosage_cache() -> None:
    keys = load_site_keys(ROOT / "data" / "panel" / "sites_8044.bed")
    assert len(keys) == 8044
    assert len(set(keys)) == 8044
    sites, mat, samples = ensure_panel_dosage(ROOT)
    assert len(sites) == 8044
    assert len(set(sites)) == 8044
    assert set(sites) == set(keys)
    assert mat.shape == (len(samples), 8044)


def test_fixed_p_nnls_recovers_q() -> None:
    rng = np.random.default_rng(1)
    raw = np.abs(rng.normal(size=(40, 3)))
    P = raw / raw.sum(axis=1, keepdims=True)
    q = np.array([0.2, 0.5, 0.3])
    dosage = 2.0 * (1.0 - P @ q)
    got = estimate_q_fixed_p(dosage, P, counted_allele="REF")
    assert np.allclose(got, q, atol=1e-6)


def test_pca_projection_round_trip() -> None:
    weights = GctaWeights(
        mu=np.zeros(3),
        sd=np.ones(3),
        ok_snp=np.ones(3, dtype=bool),
        w=np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]),
        alpha=np.array([0.5, 2.0]),
        sites=["1:1", "1:2", "1:3"],
        ref_ids=["A"],
        ref_xy=np.array([[1.0, 2.0]]),
        evals=[1.0, 0.5],
    )
    query = np.array([2.0, 3.0, 2.0])
    got = project_query_pcs(query, weights)
    assert np.allclose(got, [2.0, 6.0])
    assert np.allclose(project_query_pcs(query, weights, site_mask=np.array([True, True, True])), got)
    assert np.allclose(project_query_pcs(np.array([-1.0, -1.0, -1.0]), weights), [0.0, 0.0])

    rng = np.random.default_rng(0)
    n, p, k = 30, 12, 2
    mat = rng.integers(0, 3, size=(n, p)).astype(float)
    xy = rng.normal(size=(n, k))
    ids = [f"S{i}" for i in range(n)]
    sites = [f"1:{i + 1}" for i in range(p)]
    fitted = fit_gcta_weights_from_arrays(mat, ids, sites, ids, xy, [1.0, 0.5])
    hats = np.vstack([project_query_pcs(mat[i], fitted) for i in range(n)])
    assert hats.shape == (n, k)
    assert np.isfinite(hats).all()
    # Full-site mask matches the unmasked projection (same rule as the 167K check).
    full = np.ones(p, dtype=bool)
    assert np.allclose(project_query_pcs(mat[3], fitted, site_mask=full), hats[3])


def _qvals() -> dict:
    return {"2": [0.25, 0.75], "3": [0.2, 0.3, 0.5]}


def _payload(
    samples: list[str],
    *,
    n_sites: float,
    called: float,
    pcs: dict[str, tuple[float, float]],
    king: dict[tuple[str, str], tuple[str, float]],
    pairs: list[dict] | None = None,
    clones: dict[str, list[dict]] | None = None,
    traits: list[dict] | None = None,
    windows: list[dict] | None = None,
) -> dict:
    per_query = {}
    srows = []
    for sid in samples:
        x, y = pcs[sid]
        per_query[sid] = {
            "qc": {"n_called": called, "n_panel_sites": n_sites, "calling_rate_panel_pct": 100.0 * called / n_sites},
            "method_coverage": {"panel_genotype": {"total": n_sites, "called": called, "coverage": called / n_sites}},
            "kinship_top": [
                {"rank": i + 1, "ref": ref, "rel": rel, "king": value, "n": 100}
                for i, ((query, ref), (rel, value)) in enumerate(king.items())
                if query == sid
            ],
            "clones": (clones or {}).get(sid, []),
        }
        srows.append({"iid": sid, "query": True, "pc1": x, "pc2": y, "qvals": _qvals()})
    return {
        "n_sites": n_sites,
        "queries": [{"id": sid} for sid in samples],
        "per_query": per_query,
        "srows": srows,
        "pairs": pairs or [],
        "traits": traits if traits is not None else [{"site": f"1:{i}", "trait": "sugar", "gene": "G"} for i in range(1, 4)],
        "selection_named": windows
        if windows is not None
        else [
            {"name": "winA", "chrom": "1", "n_sites": 12},
            {"name": "winB", "chrom": "2", "n_sites": 4},
        ],
        "pca_points": [{"iid": "REF1", "grp": "W", "pcs": [0.0, 0.0], "query": False}],
    }


def test_verdict_167k_better_batch_and_single_and_input_and_identity(tmp_path: Path) -> None:
    worse_left = _payload(
        ["A", "B"],
        n_sites=167433,
        called=140000,
        pcs={"A": (0.0, 0.0), "B": (0.1, 0.0)},
        king={
            ("A", "R1"): ("Unrelated", 0.0),
            ("A", "R2"): ("Unrelated", 0.0),
            ("A", "R3"): ("Unrelated", 0.0),
            ("A", "R4"): ("Unrelated", 0.01),
            ("B", "R1"): ("Unrelated", 0.0),
        },
        pairs=[{"sample_a": "A", "sample_b": "B", "relationship": "Unrelated", "KING_Robust": 0.0, "n_comparable": 1000}],
        traits=[{"site": f"1:{i}", "trait": "berry", "gene": "G"} for i in range(1, 9)],
        windows=[{"name": f"w{i}", "chrom": "1", "n_sites": 20} for i in range(6)],
    )
    worse_right = _payload(
        ["A", "B"],
        n_sites=8044,
        called=7000,
        pcs={"A": (1.0, 1.0), "B": (1.2, -0.8)},
        king={
            ("A", "R1"): ("Parent-Offspring", 0.28),
            ("A", "R2"): ("Identical", 0.49),
            ("A", "R3"): ("2nd", 0.12),
            ("A", "R4"): ("Unrelated", 0.0),
            ("B", "R1"): ("Parent-Offspring", 0.22),
        },
        pairs=[{"sample_a": "A", "sample_b": "B", "relationship": "Parent-Offspring", "KING_Robust": 0.25, "n_comparable": 80}],
        clones={"A": [{"ref": "X", "rel": "Identical"}, {"ref": "Y", "rel": "Parent-Offspring"}, {"ref": "Z", "rel": "Identical"}]},
        traits=[{"site": "1:1", "trait": "berry", "gene": "G"}],
        windows=[{"name": f"w{i}", "chrom": "1", "n_sites": 0} for i in range(6)],
    )
    batch = compare_payloads(worse_left, worse_right)
    assert batch["is_single"] is False
    verdict = synthesize_verdict(batch["metrics"], True)
    assert verdict["code"] == "prefer_167k"
    by_id = {row["id"]: row for row in verdict["modules"]}
    assert by_id["kinship"]["code"] == "preferred"
    assert by_id["clones"]["code"] == "robust"
    assert by_id["traits"]["code"] == "essential"
    assert batch["metrics"]["hits_only_8k"] >= 3
    assert "167K" in by_id["kinship"]["badge_zh"]
    assert batch["metrics"]["king_total_pairs"] == 6
    assert batch["metrics"]["king_agree_pairs"] == 1
    assert batch["metrics"]["king_upgrade_pairs"] == 5
    prose_zh = verdict["summary_zh"] + by_id["kinship"]["detail_zh"]
    prose_en = verdict["summary_en"] + by_id["kinship"]["detail_en"]
    assert "6 对已分类配对" in prose_zh
    assert "一致 1 对（16.7%）" in prose_zh
    assert "有 5 对（83.3%）" in prose_zh
    assert "样本–参考品种" in prose_zh and "样本–样本" in prose_zh
    assert "Top-1 最近品种重合中位数" in prose_zh
    assert "个样本一致" in prose_zh
    assert "Across 6 classified pairs" in prose_en
    assert "median Top-1 nearest-cultivar overlap is" in prose_en
    assert "samples exact" in prose_en
    assert "query–panel" in prose_en and "query–query" in prose_en

    single_left = _payload(["S1"], n_sites=167433, called=120000, pcs={"S1": (0.1, 0.2)}, king={("S1", "R1"): ("Unrelated", 0.01)})
    single_right = _payload(["S1"], n_sites=8044, called=7000, pcs={"S1": (0.1, 0.21)}, king={("S1", "R1"): ("Unrelated", 0.02)})
    single = compare_payloads(single_left, single_right)
    assert single["is_single"] is True
    assert "king_query_query.tsv" not in single["tables"]
    assert synthesize_verdict(single["metrics"], False)["is_batch"] is False

    limited_left = _payload(["S1"], n_sites=167433, called=8000, pcs={"S1": (0.0, 0.0)}, king={("S1", "R1"): ("Unrelated", 0.0)})
    limited_right = _payload(["S1"], n_sites=8044, called=7900, pcs={"S1": (0.0, 0.0)}, king={("S1", "R1"): ("Unrelated", 0.0)})
    limited = synthesize_verdict(compare_payloads(limited_left, limited_right)["metrics"], False)
    assert limited["code"] == "input_limited"
    assert limited["input_limited"] is True
    assert "8,044" in limited["summary_zh"]
    assert "几乎" in limited["summary_zh"]
    assert "nearly the same" in limited["summary_en"].lower()

    same = _payload(
        ["S1"],
        n_sites=167433,
        called=150000,
        pcs={"S1": (0.2, -0.1)},
        king={("S1", "R9"): ("Unrelated", 0.001)},
    )
    identical = compare_payloads(same, json.loads(json.dumps(same)))
    assert identical["metrics"]["king_agreement_pct"] == 100.0
    assert identical["metrics"]["pca_median_dist"] == 0.0
    assert identical["metrics"]["top1"] == 1.0
    same_verdict = synthesize_verdict(identical["metrics"], False)
    assert same_verdict["code"] == "comparable"

    plotly = tmp_path / "assets" / "plotly-2.32.0.min.js"
    plotly.parent.mkdir()
    plotly.write_text("var Plotly={newPlot:function(){}};")
    nav = build_top_nav_html(
        [
            {"kind": "167k", "href": "a.html", "label_en": "GrapeAncestry (167K)", "label_zh": "GrapeAncestry（167K）"},
            {"kind": "8k", "href": "b.html", "label_en": "GrapeReseq (8K)", "label_zh": "GrapeReseq（8K）"},
            {"kind": "compare", "href": "c.html", "label_en": "167K vs 8K", "label_zh": "167K 与 8K 对照"},
        ],
        "compare",
    )
    single_html = tmp_path / "S1.167k_vs_8k.compare.html"
    batch_html = tmp_path / "batch.167k_vs_8k.compare.html"
    build_comparison_report(single_left, single_right, single_html, root=tmp_path, title_target="S1", nav_html=nav)
    build_comparison_report(worse_left, worse_right, batch_html, root=tmp_path, title_target="batch", nav_html=nav)
    single_text = single_html.read_text(encoding="utf-8")
    batch_text = batch_html.read_text(encoding="utf-8")
    for text in (single_text, batch_text):
        assert 'id="verdict-card"' in text
        assert "module-card" in text
        assert "setLang" in text
        assert 'class="en"' in text and 'class="cn"' in text
        assert "ga-report-nav" in text
        assert "/Users/" not in text
        for banned in ("样本优先", "当前计算", "范围边界", "overlay", "保持对"):
            assert banned not in text
    assert "sec-king-qq" not in single_text
    assert "sec-king-qq" in batch_text
    assert "167K 更可靠" in batch_text
    assert "167K 不可替代" in batch_text


def test_panel_mode_commands_and_artifacts(tmp_path: Path) -> None:
    root = ROOT
    vcf = {"vcf": "/tmp/q.vcf.gz"}
    for mode in ("167k", "8k", "both"):
        cmd = pipeline_command(root, "Q", "vcf", vcf, options=PipelineOptions(panel_mode=mode, as_query=True))
        assert cmd[cmd.index("--panel-mode") + 1] == mode
        assert "analyze" in cmd
        run_cmd = pipeline_command(
            root,
            "Q",
            "bam",
            {"bam": "/tmp/q.bam"},
            options=PipelineOptions(panel_mode=mode, as_query=False),
        )
        assert run_cmd[run_cmd.index("--panel-mode") + 1] == mode
        assert "run" in run_cmd
    rows = [
        {"sample": "A", "kind": "vcf", "files": {"vcf": "/tmp/a.vcf.gz"}},
        {"sample": "B", "kind": "bam", "files": {"bam": "/tmp/b.bam"}},
    ]
    both = batch_pipeline_commands(ROOT, rows, "demo", options=PipelineOptions(panel_mode="both", as_query=True))
    assert len(both) == 3
    for pre in both[:-1]:
        assert "--no-html" in pre
        assert pre[pre.index("--panel-mode") + 1] == "167k"
        assert "both" not in pre
    assert "run" in both[1]
    assert both[-1][both[-1].index("--panel-mode") + 1] == "both"
    eight = batch_pipeline_commands(ROOT, rows, "demo", options=PipelineOptions(panel_mode="8k"))
    assert eight[-1][eight[-1].index("--panel-mode") + 1] == "8k"
    assert eight[0][eight[0].index("--panel-mode") + 1] == "167k"
    plain = batch_pipeline_commands(ROOT, rows, "demo", options=PipelineOptions(panel_mode="167k"))
    assert plain[-1][plain[-1].index("--panel-mode") + 1] == "167k"
    assert "--no-html" in plain[0]

    results = tmp_path / "results"
    results.mkdir()
    (results / "Q.sample-first-v2.report.html").write_text("167")
    (results / "Q.sample-first-v2.report.data.json").write_text("{}")
    (results / "Q.8k.sample-first-v2.report.html").write_text("8k")
    (results / "Q.8k.sample-first-v2.report.data.json").write_text("{}")
    (results / "Q.167k_vs_8k.compare.html").write_text("cmp")
    (results / "demo.batch.report.html").write_text("b")
    (results / "demo.8k.batch.report.html").write_text("b8")
    (results / "demo.167k_vs_8k.compare.html").write_text("bcmp")
    assert [row["kind"] for row in find_report_artifacts(tmp_path, is_batch=False, target="Q", panel_mode="167k")] == ["167k"]
    assert [row["kind"] for row in find_report_artifacts(tmp_path, is_batch=False, target="Q", panel_mode="8k")] == ["8k"]
    both_arts = find_report_artifacts(tmp_path, is_batch=False, target="Q", panel_mode="both")
    assert [row["kind"] for row in both_arts] == ["167k", "8k", "compare"]
    assert both_arts[0]["sidecar"].name.endswith(".data.json")
    assert both_arts[2]["sidecar"] is None
    assert both_arts[1]["label_zh"].startswith("GrapeReseq")
    batch_arts = find_report_artifacts(tmp_path, is_batch=True, target="demo", panel_mode="both")
    assert [row["kind"] for row in batch_arts] == ["167k", "8k", "compare"]
    assert batch_arts[2]["sidecar"] is None


def test_iter_batch_pipeline_keeps_user_mode_on_analyze_batch_only(monkeypatch) -> None:
    import grapeancestry.web_run as web_run

    per_calls: list[dict] = []
    finals: list[list[str]] = []

    def fake_iter(*args, **kwargs):
        per_calls.append(
            {
                "sample": args[1],
                "panel_mode": kwargs["options"].panel_mode,
                "no_html": kwargs["no_html"],
            }
        )
        yield "ok\n", None
        yield None, 0

    class _Proc:
        def __init__(self) -> None:
            self.stdout = iter(())

        def wait(self) -> int:
            return 0

    def fake_popen(cmd, **kwargs):
        finals.append(list(cmd))
        return _Proc()

    monkeypatch.setattr(web_run, "iter_pipeline", fake_iter)
    monkeypatch.setattr(web_run.subprocess, "Popen", fake_popen)
    rows = [
        {"sample": "A", "kind": "vcf", "files": {"vcf": "/tmp/a.vcf.gz"}},
        {"sample": "B", "kind": "bam", "files": {"bam": "/tmp/b.bam"}},
    ]
    for mode in ("167k", "8k", "both"):
        per_calls.clear()
        finals.clear()
        lines = list(
            web_run.iter_batch_pipeline(
                ROOT,
                rows,
                "demo",
                options=PipelineOptions(panel_mode=mode, as_query=True),
            )
        )
        assert lines[-1] == (None, 0)
        assert [row["sample"] for row in per_calls] == ["A", "B"]
        assert [row["panel_mode"] for row in per_calls] == ["167k", "167k"]
        assert all(row["no_html"] is True for row in per_calls)
        assert len(finals) == 1
        final = finals[0]
        assert "analyze-batch" in final
        assert final[final.index("--panel-mode") + 1] == mode
        assert mode not in [row["panel_mode"] for row in per_calls] or mode == "167k"


def test_verdict_insufficient_when_placement_and_king_are_empty() -> None:
    empty = synthesize_verdict({}, False)
    assert empty["code"] == "insufficient"
    assert empty["title_zh"] == "对比数据不足，暂时无法判断两套面板优劣"
    assert empty["title_en"] == "Insufficient overlap to compare the two panels"
    assert "两份报告接近" not in empty["summary_zh"]
    assert "The two reports agree" not in empty["summary_en"]
    assert "Both reports are close" not in empty["summary_en"]
    badges = {row["id"]: row for row in empty["modules"]}
    for key in ("placement", "kinship", "clones", "traits"):
        assert badges[key]["code"] == "insufficient"
        assert badges[key]["badge_zh"] == "数据不足"
        assert badges[key]["badge_en"] == "Insufficient data"
        assert badges[key]["tone"] == "muted"

    nan = float("nan")
    blank = synthesize_verdict(
        {
            "pca_median_dist": nan,
            "q_pearson_min": nan,
            "q_rmse_max": float("inf"),
            "king_agreement_pct": nan,
            "king_upgrade_pct": nan,
            "top1": nan,
            "top1_overlap_median": nan,
            "called_167k": nan,
            "called_8k": nan,
            "sites_8k": nan,
        },
        True,
    )
    assert blank["code"] == "insufficient"
    assert blank["code"] != "comparable"
    assert "两份报告接近" not in blank["summary_zh"]
    assert "建议采用 167K" not in blank["title_zh"]
    by_id = {row["id"]: row for row in blank["modules"]}
    assert by_id["placement"]["badge_zh"] == "数据不足"
    assert by_id["kinship"]["badge_zh"] == "数据不足"


def test_pca_legend_hidden_when_more_than_12_samples(tmp_path: Path) -> None:
    ids = [f"S{i}" for i in range(13)]
    pcs = {sid: (index * 0.01, 0.0) for index, sid in enumerate(ids)}
    king = {(ids[0], "R1"): ("Unrelated", 0.0)}
    left = _payload(ids, n_sites=167433, called=100000, pcs=pcs, king=king)
    right = _payload(ids, n_sites=8044, called=7000, pcs=pcs, king=king)
    out = tmp_path / "many.167k_vs_8k.compare.html"
    build_comparison_report(left, right, out, root=tmp_path, title_target="many")
    text = out.read_text(encoding="utf-8")
    assert '"pcaShowLegend": false' in text
    assert "showlegend:showLegend" in text
    assert "r:showLegend ? 16 : 24" in text


def test_run_no_html_does_not_render(monkeypatch, tmp_path: Path) -> None:
    import subprocess

    import grapeancestry.cli as cli

    results = tmp_path / "results"
    results.mkdir()
    (results / "foo.vcf.gz").write_bytes(b"")
    config = tmp_path / "config.yaml"
    config.write_text("{}\n")
    samples = tmp_path / "samples.yaml"
    samples.write_text("samples:\n  foo: {type: bam}\n")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "check_call", lambda *args, **kwargs: None)
    seen: dict = {}

    def fake_dispatch(*args, **kwargs):
        seen["args"] = args
        seen.update(kwargs)

    monkeypatch.setattr(cli, "_dispatch_panel_mode", fake_dispatch)
    result = CliRunner().invoke(
        main,
        ["run", "--config", str(config), "--samples", str(samples), "--sample", "foo", "--no-html", "--panel-mode", "both"],
    )
    assert result.exit_code == 0, result.output
    assert seen["panel_mode"] == "both"
    assert seen["render_html"] is False


def test_cli_help_lists_panel_mode() -> None:
    for command in ("analyze", "run", "analyze-batch"):
        result = CliRunner().invoke(main, [command, "--help"])
        assert result.exit_code == 0
        assert "--panel-mode" in result.output
        assert "167k" in result.output and "8k" in result.output and "both" in result.output


def _demo_nav(active: str) -> str:
    return build_top_nav_html(
        [
            {"kind": "167k", "href": "a.batch.report.html", "label_en": "GrapeAncestry (167K)", "label_zh": "GrapeAncestry（167K）"},
            {"kind": "8k", "href": "a.8k.batch.report.html", "label_en": "GrapeReseq (8K)", "label_zh": "GrapeReseq（8K）"},
            {"kind": "compare", "href": "a.167k_vs_8k.compare.html", "label_en": "167K vs 8K", "label_zh": "167K 与 8K 对照"},
        ],
        active,
    )


def test_dashboard_8k_nav_and_note_once(tmp_path: Path) -> None:
    nav = _demo_nav("8k")
    out = tmp_path / "sample.8k.sample-first-v2.report.html"
    write_dashboard_html(
        "S",
        "{}",
        out,
        tmp_path,
        write_sidecar=False,
        nav_html=nav,
        site_note_html=SITE_NOTE_HTML,
        panel_sites_count=8044,
    )
    text = out.read_text(encoding="utf-8")
    assert text.count('id="ga-report-nav"') == 1
    assert text.count('id="site-set-note"') == 1
    assert "PANEL_SITES = 8044;" in text
    assert "8,044" in text
    assert "projection onto the frozen" in text or "冻结 167K 模型" in text
    _write_dashboard("S2", {}, tmp_path / "via-panel.html", tmp_path, nav_html=nav)
    via = (tmp_path / "via-panel.html").read_text(encoding="utf-8")
    assert via.count('id="ga-report-nav"') == 1
    assert via.count('id="site-set-note"') == 1


def test_demo_entry_links_three_reports(tmp_path: Path) -> None:
    verdict = {
        "title_en": "Use the 167K report",
        "title_zh": "建议采用 167K 报告",
        "sentences_en": ["The 8K page is only a broad placement."],
        "sentences_zh": ["8K 只适合看群体大方向。"],
    }
    out = tmp_path / "ramos2019_np.reports.html"
    write_demo_entry_html(out, verdict=verdict, nav_html=_demo_nav("reports"))
    text = out.read_text(encoding="utf-8")
    assert "ramos2019_np.batch.report.html" in text
    assert "ramos2019_np.8k.batch.report.html" in text
    assert "ramos2019_np.167k_vs_8k.compare.html" in text
    assert "v1.1" in text
    assert "没有导航条" in text
    assert "建议采用 167K 报告" in text
    assert text.count('id="ga-report-nav"') == 1


def test_identity_thresholds_unchanged() -> None:
    text = (ROOT / "src" / "grapeancestry" / "identity" / "ibs.py").read_text(encoding="utf-8")
    assert "KING_Robust = (IBS2* - 2*IBS0) / (IBS1 + 2*IBS2*)" in text
    assert "Identical" in text and "Parent-Offspring" in text
