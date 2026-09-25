"""GrapeAncestry v1 UI: login → upload → live progress → finished report."""

from __future__ import annotations

import base64
import html
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from grapeancestry.release_io import customer_input_root, settings_root
from grapeancestry.webauth import (
    change_password,
    load_auth,
    update_settings,
    verify_password,
    write_auth,
)

st.set_page_config(page_title="GrapeAncestry v1", layout="wide")

SETTINGS = settings_root(ROOT)
INPUT_DIR = customer_input_root(ROOT)
REPORT_PORT = 8502
_SERVER_STARTED = False


def _lang() -> str:
    return str(st.session_state.get("language") or "en")


def t(en: str, zh: str) -> str:
    return zh if _lang() == "zh" else en


class _ReportHandler(SimpleHTTPRequestHandler):
    """Serve report HTML/assets only. Do not list data/ or the panel."""

    ALLOWED_PREFIXES = ("examples/", "output/", "results/", "assets/", "web/")

    def log_message(self, fmt: str, *args) -> None:
        return

    def list_directory(self, path: str):
        self.send_error(403, "Listing disabled")
        return None

    def translate_path(self, path: str) -> str:
        mapped = super().translate_path(path)
        root = Path(self.directory).resolve()
        target = Path(mapped).resolve()
        try:
            rel = target.relative_to(root).as_posix()
        except ValueError:
            return str(root / ".forbidden")
        if any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in self.ALLOWED_PREFIXES):
            return str(target)
        return str(root / ".forbidden")


def ensure_file_server() -> None:
    global _SERVER_STARTED
    if _SERVER_STARTED:
        return
    handler = partial(_ReportHandler, directory=str(ROOT))
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", REPORT_PORT), handler)
    except OSError:
        _SERVER_STARTED = True
        return
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    _SERVER_STARTED = True


def report_url(rel: str) -> str:
    return f"http://127.0.0.1:{REPORT_PORT}/{rel.lstrip('/')}"


_WATERFALL_COLS = (
    (
        "color-ages-bar-k2.jpg",
        "color-ages-pca3d.jpg",
        "color-ages-manh.jpg",
        "color-ages-q8.jpg",
        "color-ages-tree.jpg",
        "color-ages-bar-k5.jpg",
    ),
    (
        "color-ages-bar-k4.jpg",
        "color-ages-pca3d-dark.jpg",
        "color-ages-heat.jpg",
        "color-ages-q8-dark.jpg",
        "color-ages-lz.jpg",
        "color-ages-bar-k7.jpg",
    ),
    (
        "color-ages-bar-k6.jpg",
        "color-ages-pca13.jpg",
        "color-ages-f4.jpg",
        "color-ages-bar-k8-compact.jpg",
        "color-ages-sel-lz.jpg",
        "color-ages-f3out.jpg",
    ),
    (
        "color-ages-bar-k8.jpg",
        "color-ages-pca23.jpg",
        "color-ages-scatter.jpg",
        "color-ages-bar-k8-dark.jpg",
        "color-ages-manh-dark.jpg",
        "color-ages-tree-dark.jpg",
    ),
)


@st.cache_data
def _load_credits() -> dict:
    path = ROOT / "web" / "splash" / "credits.json"
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data
def _collage_data_uri() -> str:
    path = ROOT / "web" / "splash" / "shots" / "collage-falls.jpg"
    if not path.is_file():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _decorate_gate() -> None:
    """Collage is .stApp background, so it cannot cover the login widgets."""
    uri = _collage_data_uri()
    import streamlit.components.v1 as components

    components.html(
        """<script>
var d=window.parent.document;
var n=d.getElementById("ga-falls-root"); if(n) n.remove();
var s=d.getElementById("ga-falls-style"); if(s) s.remove();
</script>""",
        height=0,
    )
    st.markdown(
        f"""
<style>
  .stApp {{
    background-color: #12090d !important;
    background-image: none !important;
    isolation: isolate;
    overflow: hidden !important;
  }}
  .stApp::before {{
    content: "";
    position: absolute;
    left: 50%;
    top: 0;
    width: min(1100px, 100%);
    height: 260%;
    margin-left: calc(min(1100px, 100%) / -2);
    z-index: 0;
    pointer-events: none;
    background-image: url("{uri}");
    background-repeat: repeat-y;
    background-size: 100% auto;
    animation: ga-rise 48s linear infinite;
    will-change: transform;
  }}
  .stApp::after {{
    content: "";
    position: absolute;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background: linear-gradient(180deg, #12090de8 0%, #12090d99 20%, #12090d80 50%, #12090d99 80%, #12090de8 100%);
  }}
  .stApp > * {{
    position: relative;
    z-index: 1;
  }}
  @keyframes ga-rise {{
    from {{ transform: translate3d(0, 0, 0); }}
    to {{ transform: translate3d(0, -40%, 0); }}
  }}
  @media (prefers-reduced-motion: reduce) {{
    .stApp::before {{ animation: none; }}
  }}
  #ga-falls-root, #ga-falls-style, iframe[height="0"], [data-testid="stIFrame"] {{
    display: none !important;
  }}
  [data-testid="stToolbar"], .stAppDeployButton, [data-testid="stAppDeployButton"],
  [data-testid="stHeader"] {{ display: none !important; }}
  [data-testid="stAppViewContainer"], [data-testid="stMain"], .stMain {{
    background: transparent !important;
  }}
  [data-testid="stMainBlockContainer"], .stMainBlockContainer, .block-container {{
    max-width: 28rem !important;
    margin-left: auto !important;
    margin-right: auto !important;
    margin-top: 7vh !important;
    margin-bottom: 6vh !important;
    padding: 1.6rem 1.5rem 1.35rem !important;
    background: #1a0e12 !important;
    border: 1px solid #c4a57466 !important;
    border-radius: 6px !important;
    box-shadow: 0 28px 70px #000000c2 !important;
  }}
  .stForm {{ background: transparent !important; border: 0 !important; }}
  [data-testid="stAppViewContainer"] h1 {{
    font-family: Palatino, "Iowan Old Style", "Songti SC", Georgia, serif !important;
    letter-spacing: .04em;
    color: #f4efe6 !important;
    font-size: 1.55rem !important;
  }}
  [data-testid="stCaption"] {{ color: #d4b88a !important; }}
  .stTextInput input, .stNumberInput input {{
    background: #12090d !important;
    color: #f4efe6 !important;
    border: 1px solid #c4a57466 !important;
  }}
  .stSelectbox [data-baseweb="select"] > div {{
    background: #12090d !important;
    color: #f4efe6 !important;
  }}
  .ga-hero, .ga-credits {{
    font-family: Palatino, "Iowan Old Style", "Songti SC", Georgia, serif;
    color: #f4efe6;
    text-align: center;
  }}
  .ga-kicker {{ font-size: 0.68rem; letter-spacing: .28em; color: #c4a574; margin-bottom: .35rem; }}
  .ga-name {{ font-size: 1.85rem; font-weight: 600; letter-spacing: .04em; }}
  .ga-tag, .ga-tag-zh {{ margin: .45rem 0 0; line-height: 1.45; color: #f4efe6d6; font-size: 0.95rem; }}
  .ga-tag-zh {{ color: #c4a574; font-size: 0.9rem; }}
  .ga-rule {{ width: 3.2rem; height: 1px; background: #c4a574; margin: .85rem auto .2rem; }}
  .ga-credits {{ margin-top: 1.1rem; font-size: 0.72rem; line-height: 1.55; color: #f4efe6c4; text-align: left; }}
  .ga-credits strong {{ color: #f4efe6; }}
  .ga-credits a {{ color: #c4a574; }}
  .ga-affil {{ margin-top: .25rem; }}
  .ga-cite {{ margin-top: .45rem; font-style: italic; color: #c4a574c8; }}
</style>
""",
        unsafe_allow_html=True,
    )


def _gate_header() -> None:
    credits = _load_credits()
    st.markdown(
        f"""<div class="ga-hero">
  <div class="ga-kicker">v{html.escape(str(credits["version"]))} · 167K</div>
  <div class="ga-name">{html.escape(credits["product"])}</div>
  <p class="ga-tag">{html.escape(credits["tagline_en"])}</p>
  <p class="ga-tag-zh">{html.escape(credits["tagline_zh"])}</p>
  <div class="ga-rule"></div>
</div>""",
        unsafe_allow_html=True,
    )


def _gate_credits() -> None:
    credits = _load_credits()
    author = credits["author"]
    name = html.escape(f"{author['name_en']} · {author['name_zh']}")
    affils = "".join(f"<div class='ga-affil'>{html.escape(a)}</div>" for a in author["affiliations"])
    copy = html.escape(credits["copyright"])
    st.markdown(
        f"""<div class="ga-credits">
  <strong>{name}</strong>
  {affils}
  <div class="ga-cite">Affiliation as published in Dong et al. <em>Science</em> (2023). Panel:
    <a href="https://doi.org/10.1126/science.add8655">doi:10.1126/science.add8655</a></div>
  <div class="ga-cite">{copy}</div>
</div>""",
        unsafe_allow_html=True,
    )


def _list_input(suffixes: tuple[str, ...]) -> list[Path]:
    if not INPUT_DIR.is_dir():
        return []
    return [
        path
        for path in sorted(INPUT_DIR.iterdir())
        if path.is_file() and path.name.lower().endswith(suffixes)
    ]


def _input_choices(suffixes: tuple[str, ...], extra: list[Path] | None = None) -> list[Path]:
    paths = list(_list_input(suffixes))
    for path in extra or []:
        if path.is_file() and path not in paths:
            paths.append(path)
    return paths


def _label_input(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(INPUT_DIR.resolve())
        return str(rel)
    except ValueError:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return path.name


def _select_input(label: str, paths: list[Path], key: str) -> Path | None:
    if not paths:
        return None
    labels = ["—"] + [_label_input(p) for p in paths]
    pick = st.selectbox(label, options=labels, key=key)
    if pick == "—":
        return None
    return paths[labels.index(pick) - 1]


def _gate() -> bool:
    auth = load_auth(SETTINGS)
    if "authed" not in st.session_state:
        st.session_state.authed = False
    if "stage" not in st.session_state:
        st.session_state.stage = "upload"

    if not st.session_state.authed:
        _decorate_gate()
        _gate_header()

    if auth is None:
        st.title(t("1. First-time setup", "1. 首次设置"))
        st.caption(
            t(
                "Set a local access password. This only locks the browser UI on this machine, not Docker data.",
                "设置本地访问密码。只锁本机网页，锁不住 docker exec / 镜像里的数据。",
            )
        )
        with st.form("ga-setup", clear_on_submit=False):
            pw = st.text_input(t("Password", "密码"), type="password")
            pw2 = st.text_input(t("Confirm password", "确认密码"), type="password")
            language = st.selectbox("Language / 语言", options=["en", "zh"], index=0)
            threads = st.number_input(t("Default threads", "默认线程"), min_value=1, max_value=32, value=4)
            lab = st.text_input(t("Lab name (optional)", "实验室名（可选）"))
            submitted = st.form_submit_button(t("Create access and continue", "创建访问并继续"))
        _gate_credits()
        if submitted:
            if not pw or pw != pw2:
                st.error(t("Passwords do not match or are empty. Type the same password twice.", "密码为空或不一致。请把同一密码输入两遍。"))
            else:
                write_auth(SETTINGS, pw, language=language, threads=int(threads), lab_name=lab)
                st.session_state.authed = True
                st.session_state.language = language
                st.session_state.threads = int(threads)
                st.session_state.stage = "upload"
                st.rerun()
        return False

    if st.session_state.authed:
        st.session_state.language = auth.get("language") or st.session_state.get("language") or "en"
        st.session_state.threads = int(auth.get("threads") or 4)
        return True

    st.title(t("1. Log in", "1. 登录"))
    if auth.get("lab_name"):
        st.caption(str(auth["lab_name"]))
    st.caption(
        t(
            "Local UI lock only. After login: Analysis (FASTQ / BAM / VCF) or Demos (Ages + HUN89_query).",
            "只锁本机网页。登录后：分析（FASTQ / BAM / VCF）或演示（Ages + HUN89_query）。",
        )
    )
    with st.form("ga-login", clear_on_submit=False):
        pw = st.text_input(t("Password", "密码"), type="password")
        submitted = st.form_submit_button(t("Log in", "登录"))
    _gate_credits()
    if submitted:
        if verify_password(pw, auth):
            st.session_state.authed = True
            st.session_state.language = auth.get("language") or "en"
            st.session_state.threads = int(auth.get("threads") or 4)
            st.session_state.stage = "upload"
            st.rerun()
        else:
            st.error(t("Wrong password.", "密码错误。"))
    return False


def _page_settings() -> None:
    auth = load_auth(SETTINGS) or {}
    st.header(t("Settings", "设置"))
    language = st.selectbox(
        "Language / 语言",
        options=["en", "zh"],
        index=0 if _lang() == "en" else 1,
    )
    threads = st.number_input(
        t("Default threads", "默认线程"),
        min_value=1,
        max_value=32,
        value=int(auth.get("threads") or 4),
    )
    lab = st.text_input(t("Lab name", "实验室名"), value=str(auth.get("lab_name") or ""))
    if st.button(t("Save settings", "保存设置")):
        update_settings(SETTINGS, language=language, threads=int(threads), lab_name=lab)
        st.session_state.language = language
        st.session_state.threads = int(threads)
        st.success(t("Saved.", "已保存。"))
    st.subheader(t("Change password", "改密码"))
    new_pw = st.text_input(t("New password", "新密码"), type="password", key="npw")
    new_pw2 = st.text_input(t("Confirm new password", "确认新密码"), type="password", key="npw2")
    if st.button(t("Update password", "更新密码")):
        if not new_pw or new_pw != new_pw2:
            st.error(t("Passwords do not match or are empty.", "密码为空或不一致。"))
        else:
            change_password(SETTINGS, new_pw)
            st.success(t("Password updated.", "密码已更新。"))
    if st.button(t("Log out", "退出登录")):
        st.session_state.authed = False
        st.session_state.stage = "upload"
        st.rerun()


def _show_companion_json(parsed) -> None:
    from grapeancestry.cloud.analyze import analyze_parsed, reports_as_dicts

    reports = analyze_parsed(parsed, ROOT)
    for rep in reports:
        st.write(rep.sample)
        st.json(reports_as_dicts([rep])[0])
    st.download_button(
        "JSON",
        json.dumps(reports_as_dicts(reports), indent=2).encode(),
        file_name="chip_companion.json",
        key=f"cc-dl-{parsed.filename}-{parsed.samples[0] if parsed.samples else 'x'}",
    )


def _page_demos() -> None:
    from grapeancestry.cloud.analyze import demo_from_fingerprint
    from grapeancestry.cloud.sites import load_panel_sites
    from grapeancestry.cloud.vcf_py import parse_vcf_bytes

    ensure_file_server()
    st.header(t("Demos", "演示"))
    st.caption(
        t(
            "Finished V2 reports for Ages and HUN89_query. Quick VCF check is a JSON helper, not the full VS-1 report. New samples: Analysis.",
            "Ages 和 HUN89_query 的现成 V2 报告。快速 VCF 检查只出 JSON，不是完整 VS-1 报告。新样本请走「分析」。",
        )
    )
    packed = {"Ages": "Ages", "HUN89_query": "HUN89-capture"}
    for sample, folder in (("Ages", "ages"), ("HUN89_query", "hun89_query")):
        html = ROOT / "examples" / folder / f"{sample}.sample-first-v2.report.html"
        js = ROOT / "examples" / folder / f"{sample}.sample-first-v2.report.data.json"
        st.subheader(sample)
        if html.is_file():
            st.link_button(
                t(f"Open {sample} report", f"打开 {sample} 报告"),
                report_url(f"examples/{folder}/{html.name}"),
            )
            st.download_button(
                t("Download HTML", "下载 HTML"),
                data=html.read_bytes(),
                file_name=html.name,
                mime="text/html",
                key=f"dl-{sample}-html",
            )
        if js.is_file():
            st.download_button(
                t("Download JSON", "下载 JSON"),
                data=js.read_bytes(),
                file_name=js.name,
                mime="application/json",
                key=f"dl-{sample}-json",
            )
        if st.button(t("Quick VCF check", "快速 VCF 检查"), key=f"cc-{sample}"):
            parsed = demo_from_fingerprint(ROOT, packed[sample])
            if parsed is None:
                st.error(t("Demo pack missing.", "缺少 demo 打包。"))
            else:
                _show_companion_json(parsed)

    with st.expander(t("Quick check on a VCF in ./input", "对 ./input 里的 VCF 做快速检查")):
        vcfs = _input_choices(
            (".vcf.gz", ".vcf"),
            extra=[
                ROOT / "examples" / "ages" / "Ages.vcf.gz",
                ROOT / "examples" / "hun89_query" / "HUN89_query.vcf.gz",
            ],
        )
        vcf = _select_input(t("VCF", "VCF"), vcfs, "cc_vcf")
        if st.button(t("Analyze selected VCF", "分析所选 VCF"), disabled=vcf is None) and vcf is not None:
            panel = set(load_panel_sites(ROOT))
            parsed = parse_vcf_bytes(vcf.read_bytes(), filename=vcf.name, panel_sites=panel or None)
            _show_companion_json(parsed)


def _show_intake_reports(reports: list) -> None:
    for rep in reports:
        label = f"{rep.name} · {rep.kind} · {rep.size} B"
        text = " · ".join(rep.messages) or label
        if rep.ok:
            st.success(f"{label}: {text}")
        else:
            st.error(f"{label}: {text}")


def _pipeline_options_form(kind: str, fq_kind: str):
    import importlib

    import grapeancestry.web_run as web_run

    web_run = importlib.reload(web_run)
    ADMIX_MODES = web_run.ADMIX_MODES
    AR3_ADAPTER_SEL = web_run.AR3_ADAPTER_SEL
    AR3_POLYX = web_run.AR3_POLYX
    AR3_QUAL_TRIM = web_run.AR3_QUAL_TRIM
    FASTP_POLY_G = web_run.FASTP_POLY_G
    PCA_COLORS = web_run.PCA_COLORS
    PipelineOptions = web_run.PipelineOptions

    st.subheader(t("Step settings", "分步参数"))
    st.caption(
        t(
            "Only knobs the pipeline already has. Defaults match config/default.yaml and grapeancestry analyze/run.",
            "只暴露流水线里已有的参数。默认值与 config/default.yaml 以及 grapeancestry analyze/run 一致。",
        )
    )
    with st.expander(t("Identity / query", "身份 / query"), expanded=True):
        as_query = st.checkbox(
            t("Treat as query (recommended for new samples)", "按 query 分析（新样本建议勾选）"),
            value=True,
            key="opt_as_query",
        )
        force_query_vcf = st.checkbox(
            t("Replace existing query VCF (--force-query-vcf)", "覆盖已有 query VCF（--force-query-vcf）"),
            value=False,
            key="opt_force_query",
        )
        source_sample = ""
        if kind == "VCF":
            source_sample = st.text_input(
                t("Source sample id (optional, --source-sample)", "来源样本 ID（可选，--source-sample）"),
                key="opt_source_sample",
                help=t(
                    "BAM / mapDamage lineage on the VCF-only path. Empty = use Sample ID.",
                    "仅 VCF 路径上的 BAM / mapDamage 谱系。空则用样本 ID。",
                ),
            )
    with st.expander(t("Compute", "计算"), expanded=False):
        threads = st.number_input(
            t("Threads (-j / Snakemake / bcftools)", "线程（-j / Snakemake / bcftools）"),
            min_value=1,
            max_value=32,
            value=int(st.session_state.get("threads") or 4),
            key="opt_threads",
        )
        snakemake_force = False
        if kind != "VCF":
            snakemake_force = st.checkbox(
                t("Rerun all Snakemake rules (-F / --forceall)", "强制重跑全部规则（-F / --forceall）"),
                value=False,
                key="opt_forceall",
            )
        else:
            st.caption(
                t(
                    "VCF analyze does not start Snakemake; threads are unused on this path.",
                    "VCF 分析不跑 Snakemake，此路径不用线程。",
                )
            )
    fastp_min_length = 15
    fastp_qualified_quality = 15
    fastp_unqualified_percent = 40
    fastp_n_base_limit = 5
    fastp_poly_g = "auto"
    fastp_cut_tail = False
    fastp_cut_mean_quality = 20
    fastp_detect_adapter_pe = True
    adna_min_length = 25
    adna_adapter_selection = "auto"
    adna_adapter1 = ""
    adna_quality_trimming = "mott"
    adna_trim_min_quality = 2
    adna_trim_mott_rate = 0.05
    adna_min_overlap = 1
    adna_mismatch_rate = 0.1667
    adna_pre_trim_polyx = "auto"
    adna_min_mean_quality = 0
    bwa_mem_seed = 19
    bwa_mem_min_score = 30
    bwa_aln_l = 1024
    bwa_aln_n = 0.01
    bwa_aln_max_gap = 1
    min_mq = 0
    min_bq = 13
    max_depth = 250
    adjust_mq = 0
    min_dp = 0
    if kind == "FASTQ" and fq_kind in {"pe", "se"}:
        with st.expander(t("Trim · fastp", "修剪 · fastp"), expanded=True):
            st.caption("https://github.com/OpenGene/fastp")
            c1, c2 = st.columns(2)
            with c1:
                fastp_min_length = int(
                    st.number_input(
                        t("Min length (--length_required)", "最短读长（--length_required）"),
                        min_value=1,
                        max_value=100,
                        value=15,
                        key="opt_fastp_min_length",
                    )
                )
                fastp_qualified_quality = int(
                    st.number_input(
                        t("Qualified Q (--qualified_quality_phred)", "合格质量（--qualified_quality_phred）"),
                        min_value=0,
                        max_value=40,
                        value=15,
                        key="opt_fastp_qual",
                    )
                )
                fastp_unqualified_percent = int(
                    st.number_input(
                        t("Unqualified % (--unqualified_percent_limit)", "不合格碱基比例（--unqualified_percent_limit）"),
                        min_value=0,
                        max_value=100,
                        value=40,
                        key="opt_fastp_unqual",
                    )
                )
            with c2:
                fastp_n_base_limit = int(
                    st.number_input(
                        t("Max N bases (--n_base_limit)", "最多 N 碱基数（--n_base_limit）"),
                        min_value=0,
                        max_value=50,
                        value=5,
                        key="opt_fastp_nbase",
                    )
                )
                fastp_poly_g = st.selectbox(
                    t("polyG (--trim_poly_g)", "polyG（--trim_poly_g）"),
                    options=list(FASTP_POLY_G),
                    index=0,
                    key="opt_fastp_polyg",
                )
                fastp_cut_tail = st.checkbox(
                    t("3′ window trim (--cut_tail)", "3′ 滑窗修剪（--cut_tail）"),
                    value=False,
                    key="opt_fastp_cut_tail",
                )
                fastp_cut_mean_quality = int(
                    st.number_input(
                        t("Window mean Q (--cut_mean_quality)", "窗口均质（--cut_mean_quality）"),
                        min_value=1,
                        max_value=36,
                        value=20,
                        key="opt_fastp_cut_mean",
                    )
                )
            if fq_kind == "pe":
                fastp_detect_adapter_pe = st.checkbox(
                    t("Detect PE adapters (--detect_adapter_for_pe)", "检测双端接头（--detect_adapter_for_pe）"),
                    value=True,
                    key="opt_fastp_detect_pe",
                )
        with st.expander(t("Map · bwa mem", "比对 · bwa mem"), expanded=True):
            st.caption("http://bio-bwa.sourceforge.net/bwa.shtml")
            m1, m2 = st.columns(2)
            with m1:
                bwa_mem_seed = int(
                    st.number_input(
                        t("Seed length (-k)", "种子长度（-k）"),
                        min_value=11,
                        max_value=32,
                        value=19,
                        key="opt_bwa_mem_k",
                    )
                )
            with m2:
                bwa_mem_min_score = int(
                    st.number_input(
                        t("Min output score (-T)", "最低输出分（-T）"),
                        min_value=0,
                        max_value=100,
                        value=30,
                        key="opt_bwa_mem_t",
                    )
                )
    if kind == "FASTQ" and fq_kind == "adna":
        with st.expander(t("Trim · AdapterRemoval3", "修剪 · AdapterRemoval3"), expanded=True):
            st.caption("adapterremoval3 3.0.1 --help · https://adapterremoval.readthedocs.io/")
            adna_min_length = int(
                st.number_input(
                    t("Min length (--min-length)", "最短长度（--min-length）"),
                    min_value=15,
                    max_value=80,
                    value=25,
                    key="opt_adna_min_length",
                )
            )
            a1, a2 = st.columns(2)
            with a1:
                adna_adapter_selection = st.selectbox(
                    t("Adapter selection (--adapter-selection)", "接头选择（--adapter-selection）"),
                    options=list(AR3_ADAPTER_SEL),
                    index=0,
                    key="opt_adna_adapter_sel",
                )
                adna_adapter1 = st.text_input(
                    t("Adapter1 ACGTN (optional --adapter1)", "接头1 ACGTN（可选 --adapter1）"),
                    key="opt_adna_adapter1",
                )
                adna_quality_trimming = st.selectbox(
                    t("Quality trim (--quality-trimming)", "质量修剪（--quality-trimming）"),
                    options=list(AR3_QUAL_TRIM),
                    index=0,
                    key="opt_adna_qtrim",
                )
                adna_trim_min_quality = int(
                    st.number_input(
                        t("Trim min Q (--trim-min-quality)", "修剪最低质量（--trim-min-quality）"),
                        min_value=0,
                        max_value=40,
                        value=2,
                        key="opt_adna_trim_minq",
                    )
                )
            with a2:
                adna_trim_mott_rate = float(
                    st.number_input(
                        t("Mott rate (--trim-mott-rate)", "Mott 阈值（--trim-mott-rate）"),
                        min_value=0.0,
                        max_value=0.5,
                        value=0.05,
                        step=0.01,
                        format="%.3f",
                        key="opt_adna_mott",
                    )
                )
                adna_min_overlap = int(
                    st.number_input(
                        t("Min overlap (--min-overlap)", "最小重叠（--min-overlap）"),
                        min_value=1,
                        max_value=30,
                        value=1,
                        key="opt_adna_min_ov",
                    )
                )
                adna_mismatch_rate = float(
                    st.number_input(
                        t("Mismatch rate (--mismatch-rate)", "错配率（--mismatch-rate）"),
                        min_value=0.01,
                        max_value=0.5,
                        value=0.1667,
                        step=0.01,
                        format="%.4f",
                        key="opt_adna_mm",
                    )
                )
                adna_pre_trim_polyx = st.selectbox(
                    t("polyX (--pre-trim-polyx)", "polyX（--pre-trim-polyx）"),
                    options=list(AR3_POLYX),
                    index=0,
                    key="opt_adna_polyx",
                )
                adna_min_mean_quality = int(
                    st.number_input(
                        t("Min mean Q (0=off, --min-mean-quality)", "最低均质（0=关，--min-mean-quality）"),
                        min_value=0,
                        max_value=40,
                        value=0,
                        key="opt_adna_meanq",
                    )
                )
        with st.expander(t("Map · bwa aln", "比对 · bwa aln"), expanded=True):
            st.caption("http://bio-bwa.sourceforge.net/bwa.shtml")
            b1, b2, b3 = st.columns(3)
            with b1:
                bwa_aln_l = int(
                    st.number_input(
                        t("Seed (-l); 1024 = off", "种子（-l）；1024=关"),
                        min_value=32,
                        max_value=1024,
                        value=1024,
                        key="opt_bwa_aln_l",
                    )
                )
            with b2:
                bwa_aln_n = float(
                    st.number_input(
                        t("Max edit (-n)", "最大编辑（-n）"),
                        min_value=0.0,
                        max_value=0.10,
                        value=0.01,
                        step=0.01,
                        format="%.3f",
                        key="opt_bwa_aln_n",
                    )
                )
            with b3:
                bwa_aln_max_gap = int(
                    st.number_input(
                        t("Max gap opens (-o)", "最多 gap 打开（-o）"),
                        min_value=0,
                        max_value=10,
                        value=1,
                        key="opt_bwa_aln_o",
                    )
                )
    if kind in {"FASTQ", "BAM"}:
        with st.expander(t("Call · bcftools", "分型 · bcftools"), expanded=True):
            st.caption("http://www.htslib.org/doc/bcftools.html#mpileup")
            d1, d2 = st.columns(2)
            with d1:
                min_mq = int(
                    st.number_input(
                        t("Min mapQ (-q, also samtools view)", "最小比对质量（-q，比对后也用）"),
                        min_value=0,
                        max_value=60,
                        value=0,
                        key="opt_min_mq",
                    )
                )
                min_bq = int(
                    st.number_input(
                        t("Min baseQ (-Q)", "最小碱基质量（-Q）"),
                        min_value=0,
                        max_value=40,
                        value=13,
                        key="opt_min_bq",
                    )
                )
            with d2:
                max_depth = int(
                    st.number_input(
                        t("Max depth per file (-d)", "每文件最大深度（-d）"),
                        min_value=1,
                        max_value=10000,
                        value=250,
                        key="opt_max_depth",
                    )
                )
                adjust_mq = int(
                    st.number_input(
                        t("Adjust MQ (-C); 0=off, 50=Illumina", "校正 MQ（-C）；0=关，50=Illumina"),
                        min_value=0,
                        max_value=100,
                        value=0,
                        key="opt_adjust_mq",
                    )
                )
                min_dp = int(
                    st.number_input(
                        t("Drop FORMAT/DP below (0=off)", "丢掉 FORMAT/DP 低于（0=关）"),
                        min_value=0,
                        max_value=30,
                        value=0,
                        key="opt_min_dp",
                    )
                )
    with st.expander(t("Ancestry / report", "祖源 / 报告"), expanded=True):
        pca_color = st.selectbox(
            t("PCA colour column (--pca-color, 2449.info)", "PCA 着色列（--pca-color，2449.info）"),
            options=list(PCA_COLORS),
            index=0,
            key="opt_pca_color",
        )
        admix_mode = st.selectbox(
            t("ADMIXTURE mode (--admix-mode)", "ADMIXTURE 模式（--admix-mode）"),
            options=list(ADMIX_MODES),
            index=0,
            key="opt_admix_mode",
            format_func=lambda x: {
                "auto": t("auto (lookup in-panel; -P for new samples)", "auto（面板内查找；新样本用 -P）"),
                "lookup": t("lookup (in-panel Q only)", "lookup（只读面板 Q）"),
                "nnls": t("nnls (project on frozen P)", "nnls（投影到冻结 P）"),
                "official": t("official (admixture -P)", "official（admixture -P）"),
            }[x],
        )
        admix_all_k = st.checkbox(
            t("Project every K in 2–8 (--admix-all-k)", "投影 K=2–8（--admix-all-k）"),
            value=True,
            key="opt_admix_all_k",
        )
    if adna_adapter1 and any(ch not in "ACGTNacgtn" for ch in adna_adapter1):
        st.error(t("Adapter1 must be ACGTN only.", "接头1 只能是 ACGTN。"))
        adna_adapter1 = ""
    return PipelineOptions(
        as_query=as_query,
        threads=int(threads),
        force_query_vcf=force_query_vcf,
        snakemake_force=snakemake_force,
        pca_color=str(pca_color),
        admix_mode=str(admix_mode),
        admix_all_k=admix_all_k,
        source_sample=str(source_sample or ""),
        fastp_min_length=fastp_min_length,
        fastp_qualified_quality=fastp_qualified_quality,
        fastp_unqualified_percent=fastp_unqualified_percent,
        fastp_n_base_limit=fastp_n_base_limit,
        fastp_poly_g=str(fastp_poly_g),
        fastp_cut_tail=fastp_cut_tail,
        fastp_cut_mean_quality=fastp_cut_mean_quality,
        fastp_detect_adapter_pe=fastp_detect_adapter_pe,
        adna_min_length=adna_min_length,
        adna_adapter_selection=str(adna_adapter_selection),
        adna_adapter1=str(adna_adapter1 or ""),
        adna_quality_trimming=str(adna_quality_trimming),
        adna_trim_min_quality=adna_trim_min_quality,
        adna_trim_mott_rate=adna_trim_mott_rate,
        adna_min_overlap=adna_min_overlap,
        adna_mismatch_rate=adna_mismatch_rate,
        adna_pre_trim_polyx=str(adna_pre_trim_polyx),
        adna_min_mean_quality=adna_min_mean_quality,
        bwa_mem_seed=bwa_mem_seed,
        bwa_mem_min_score=bwa_mem_min_score,
        bwa_aln_l=bwa_aln_l,
        bwa_aln_n=bwa_aln_n,
        bwa_aln_max_gap=bwa_aln_max_gap,
        min_mq=min_mq,
        min_bq=min_bq,
        max_depth=max_depth,
        adjust_mq=adjust_mq,
        min_dp=min_dp,
    )


def _page_upload() -> None:
    import importlib

    import grapeancestry.input_intake as intake

    intake = importlib.reload(intake)
    ORLANDO_V5_AGES_RUN = intake.ORLANDO_V5_AGES_RUN
    ORLANDO_V5_AGES_STUDY = intake.ORLANDO_V5_AGES_STUDY
    ORLANDO_V5_AGES_URL = intake.ORLANDO_V5_AGES_URL
    copy_into_input = intake.copy_into_input
    fetch_url = intake.fetch_url
    inspect_input = intake.inspect_input
    write_bytes = intake.write_bytes

    st.title(t("2. Choose files", "2. 选择文件"))
    st.caption(
        t(
            "This machine / Docker only. Drag files here to write ./input, or copy a large FASTQ onto the host folder. Nothing is sent to a remote server.",
            "只在本机 / Docker。拖到这里会写入 ./input；大 FASTQ 也可直接拷到宿主机该文件夹。不会传到外网。",
        )
    )
    st.code(str(INPUT_DIR), language="text")
    dropped = st.file_uploader(
        t("Drag FASTQ / BAM / VCF into ./input", "把 FASTQ / BAM / VCF 拖进 ./input"),
        type=["fq", "fastq", "fq.gz", "fastq.gz", "bam", "vcf", "vcf.gz"],
        accept_multiple_files=True,
        key="intake_drop",
    )
    if dropped:
        sig = tuple((item.name, item.size) for item in dropped)
        if st.session_state.get("_drop_sig") != sig:
            reports = []
            try:
                for item in dropped:
                    dest = write_bytes(INPUT_DIR, item.name, item.getvalue())
                    reports.append(inspect_input(dest, root=ROOT))
            except (OSError, ValueError) as exc:
                st.error(str(exc))
            else:
                st.session_state._drop_sig = sig
                st.session_state.intake_reports = reports
                st.rerun()
    st.subheader(t("Download into ./input", "下载到 ./input"))
    st.caption(
        t(
            "Copy a packed demo or fetch an http(s) URL. Each file is checked after it lands. "
            f"Sample URL is the Orlando 2026 NC submitted BAM ({ORLANDO_V5_AGES_RUN} / {ORLANDO_V5_AGES_STUDY}; 12Xv2, not VS-1).",
            "复制打包演示，或用 http(s) 拉取。文件落地后会自动检查。"
            f"示例链接是 Orlando 2026 NC 提交的 BAM（{ORLANDO_V5_AGES_RUN} / {ORLANDO_V5_AGES_STUDY}；12Xv2，不是 VS-1）。",
        )
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("Get Ages.vcf.gz", "获取 Ages.vcf.gz")):
            try:
                dest = copy_into_input(ROOT / "examples" / "ages" / "Ages.vcf.gz", INPUT_DIR)
                st.session_state.intake_reports = [inspect_input(dest, root=ROOT)]
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(str(exc))
    with c2:
        if st.button(t("Get HUN89_query.vcf.gz", "获取 HUN89_query.vcf.gz")):
            try:
                dest = copy_into_input(
                    ROOT / "examples" / "hun89_query" / "HUN89_query.vcf.gz", INPUT_DIR
                )
                st.session_state.intake_reports = [inspect_input(dest, root=ROOT)]
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(str(exc))
    if "intake_url" not in st.session_state:
        st.session_state.intake_url = ORLANDO_V5_AGES_URL
    url = st.text_input(
        t("Download URL (http/https)", "下载地址（http/https）"),
        key="intake_url",
    )
    if st.button(t("Download and check", "下载并检查"), disabled=not str(url or "").strip()):
        try:
            dest = fetch_url(url, INPUT_DIR)
            st.session_state.intake_reports = [inspect_input(dest, root=ROOT)]
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(str(exc))
    if st.session_state.get("intake_reports"):
        _show_intake_reports(st.session_state.intake_reports)
    if st.button(t("Rescan ./input", "重新扫描 ./input")):
        st.rerun()
    kind = st.radio(
        t("Input type", "输入类型"),
        options=["FASTQ", "BAM", "VCF"],
        horizontal=True,
        key="kind",
    )
    sample = st.text_input(t("Sample ID", "样本 ID"), value=st.session_state.get("sample_id") or "QUERY")
    files: dict[str, str] = {}
    paired = False
    run_kind = "vcf"
    fq_kind = ""
    if kind == "FASTQ":
        fq_kind = st.selectbox(
            t("FASTQ library", "FASTQ 文库"),
            options=["pe", "se", "adna"],
            format_func=lambda x: {
                "pe": t("Modern paired-end", "现代双端"),
                "se": t("Modern single-end", "现代单端"),
                "adna": t("aDNA single-end", "古 DNA 单端"),
            }[x],
        )
        fq_paths = _input_choices((".fq.gz", ".fastq.gz", ".fq", ".fastq"))
        if not fq_paths:
            st.info(t("No FASTQ in ./input yet.", "./input 里还没有 FASTQ。"))
        r1 = _select_input(t("R1 / SE FASTQ", "R1 / 单端 FASTQ"), fq_paths, "pick_r1")
        if r1:
            files["r1"] = str(r1)
        if fq_kind == "pe":
            r2 = _select_input(t("R2 FASTQ", "R2 FASTQ"), fq_paths, "pick_r2")
            if r2:
                files["r2"] = str(r2)
        run_kind = fq_kind
    elif kind == "BAM":
        paired = st.checkbox(t("Paired-end BAM", "双端 BAM"), value=True)
        bam_paths = _input_choices((".bam",))
        if not bam_paths:
            st.info(t("No BAM in ./input yet. BAM must already be VS-1.", "./input 里还没有 BAM。BAM 必须已经是 VS-1。"))
        bam = _select_input(t("BAM", "BAM"), bam_paths, "pick_bam")
        if bam:
            files["bam"] = str(bam)
        run_kind = "bam"
    else:
        vcf_paths = _input_choices(
            (".vcf.gz", ".vcf"),
            extra=[
                ROOT / "examples" / "ages" / "Ages.vcf.gz",
                ROOT / "examples" / "hun89_query" / "HUN89_query.vcf.gz",
            ],
        )
        if not vcf_paths:
            st.info(t("No VCF in ./input yet.", "./input 里还没有 VCF。"))
        vcf = _select_input(t("VCF", "VCF"), vcf_paths, "pick_vcf")
        if vcf:
            files["vcf"] = str(vcf)
        run_kind = "vcf"

    opts = _pipeline_options_form(kind, fq_kind)
    opts.paired = paired

    if st.button(t("Start analysis", "开始分析"), type="primary"):
        if not sample.strip():
            st.error(t("Sample ID is required.", "需要样本 ID。"))
            return
        if run_kind == "pe" and ("r1" not in files or "r2" not in files):
            st.error(t("Need R1 and R2.", "需要 R1 和 R2。"))
            return
        if run_kind in {"se", "adna"} and "r1" not in files:
            st.error(t("Need a FASTQ.", "需要 FASTQ。"))
            return
        if run_kind == "bam" and "bam" not in files:
            st.error(t("Need a BAM.", "需要 BAM。"))
            return
        if run_kind == "vcf" and "vcf" not in files:
            st.error(t("Need a VCF.", "需要 VCF。"))
            return
        st.session_state.job = {
            "sample": sample.strip(),
            "kind": run_kind,
            "files": files,
            "paired": opts.paired,
            "as_query": opts.as_query,
            "threads": opts.threads,
            "options": opts.as_dict(),
        }
        st.session_state.sample_id = sample.strip()
        st.session_state.log_text = ""
        st.session_state.stage = "running"
        st.rerun()


def _page_progress() -> None:
    import importlib

    from grapeancestry.report.build_report import REPORT_V2_SUFFIX
    import grapeancestry.web_run as web_run

    web_run = importlib.reload(web_run)
    PipelineOptions = web_run.PipelineOptions
    iter_pipeline = web_run.iter_pipeline
    report_id_for = web_run.report_id_for

    job = st.session_state.get("job") or {}
    opts = PipelineOptions.from_dict(job.get("options"))
    opts.paired = bool(job.get("paired"))
    st.title(t("3. Analysis running", "3. 分析进行中"))
    st.caption(
        t(
            f"Sample {job.get('sample')} · {job.get('kind')} · {opts.admix_mode} · PCA {opts.pca_color}",
            f"样本 {job.get('sample')} · {job.get('kind')} · {opts.admix_mode} · PCA {opts.pca_color}",
        )
    )
    log_box = st.empty()
    status = st.empty()
    status.info(t("Running… live log below.", "正在运行，日志在下方更新。"))
    chunks: list[str] = []
    code = 1
    for line, rc in iter_pipeline(
        ROOT,
        str(job["sample"]),
        str(job["kind"]),
        dict(job["files"]),
        paired=opts.paired,
        as_query=opts.as_query,
        threads=opts.threads,
        options=opts,
    ):
        if line is not None:
            chunks.append(line)
            log_box.text_area(t("Log", "日志"), "".join(chunks)[-12000:], height=360)
        if rc is not None:
            code = rc
    st.session_state.log_text = "".join(chunks)
    if code != 0:
        status.error(t("Run failed. See the log. Fix the input and start a new analysis.", "失败，见日志。改输入后重新分析。"))
        if st.button(t("Back to file list", "回到选文件")):
            st.session_state.stage = "upload"
            st.rerun()
        return
    rid = report_id_for(str(job["sample"]), str(job["kind"]), bool(job.get("as_query")))
    html = ROOT / "results" / f"{rid}{REPORT_V2_SUFFIX}"
    if not html.is_file():
        status.error(t("Finished without a V2 HTML.", "结束但没有 V2 HTML。"))
        if st.button(t("Back to file list", "回到选文件")):
            st.session_state.stage = "upload"
            st.rerun()
        return
    st.session_state.done = {
        "report_id": rid,
        "html": str(html),
        "sidecar": str(html.with_name(html.name.replace(".html", ".data.json"))),
    }
    st.session_state.stage = "done"
    st.rerun()


def _page_done() -> None:
    ensure_file_server()
    done = st.session_state.get("done") or {}
    html = Path(done.get("html") or "")
    sidecar = Path(done.get("sidecar") or "")
    st.title(t("4. Report ready", "4. 报告已完成"))
    st.success(t("The V2 report is ready on this computer.", "V2 报告已在本机生成。"))
    if html.is_file():
        rel = html.relative_to(ROOT).as_posix()
        st.link_button(t("Open report in new tab", "在新标签打开报告"), report_url(rel))
        st.download_button(
            t("Download HTML", "下载 HTML"),
            data=html.read_bytes(),
            file_name=html.name,
            mime="text/html",
        )
    if sidecar.is_file():
        st.download_button(
            t("Download JSON", "下载 JSON"),
            data=sidecar.read_bytes(),
            file_name=sidecar.name,
            mime="application/json",
        )
    with st.expander(t("Log", "日志")):
        st.text(st.session_state.get("log_text") or "")
    if st.button(t("New analysis", "新分析")):
        st.session_state.stage = "upload"
        st.session_state.pop("job", None)
        st.session_state.pop("done", None)
        st.rerun()


ensure_file_server()
if not _gate():
    st.stop()

stage = st.session_state.get("stage") or "upload"
nav = st.sidebar.radio(
    t("Pages", "页面"),
    options=["Analysis", "Demos", "Settings"],
    format_func=lambda x: {
        "Analysis": t("Analysis", "分析"),
        "Demos": t("Demos", "演示"),
        "Settings": t("Settings", "设置"),
    }[x],
)
if stage == "running":
    nav = "Analysis"
if nav == "Analysis":
    st.sidebar.caption(
        t(
            "1 login · 2 choose files · 3 progress · 4 report",
            "1 登录 · 2 选文件 · 3 进度 · 4 报告",
        )
    )
    if stage != "running" and st.sidebar.button(t("New analysis", "新分析")):
        st.session_state.stage = "upload"
        st.rerun()
    if stage == "running":
        _page_progress()
    elif stage == "done":
        _page_done()
    else:
        _page_upload()
elif nav == "Demos":
    _page_demos()
else:
    _page_settings()
