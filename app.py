"""GrapeAncestry v1.2.0 UI: login, choose files, watch the run, open the report."""

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

st.set_page_config(page_title="GrapeAncestry v1.2.0", layout="wide")

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


_PANEL_MODES = ("167k", "8k", "both")
_REPORT_LABELS = {
    "167k": ("GrapeAncestry report (167K)", "GrapeAncestry 报告（167K）"),
    "8k": ("GrapeReseq report (8K)", "GrapeReseq 报告（8K）"),
    "compare": ("167K vs 8K comparison", "167K 与 8K 比较"),
}


def _panel_choice() -> str:
    """Read the home-screen site-set checkboxes. Empty string means neither is selected."""
    use_167 = bool(st.session_state.get("ga_panel_167k", True))
    use_8k = bool(st.session_state.get("ga_panel_8k", False))
    if use_167 and use_8k:
        return "both"
    if use_167:
        return "167k"
    if use_8k:
        return "8k"
    return ""


def _with_panel_mode(options: dict, panel_mode: str) -> dict:
    merged = dict(options)
    merged["panel_mode"] = panel_mode if panel_mode in _PANEL_MODES else "167k"
    return merged


def _fallback_report_artifacts(root: Path, *, is_batch: bool, target: str, panel_mode: str) -> list[dict]:
    """Filenames from the v1.2 interface contract. Used until web_run.find_report_artifacts exists."""
    mode = panel_mode if panel_mode in _PANEL_MODES else "167k"
    if is_batch:
        specs = [
            ("167k", f"{target}.batch.report.html", f"{target}.batch.report.data.json"),
            ("8k", f"{target}.8k.batch.report.html", f"{target}.8k.batch.report.data.json"),
            ("compare", f"{target}.167k_vs_8k.compare.html", None),
        ]
    else:
        specs = [
            ("167k", f"{target}.sample-first-v2.report.html", f"{target}.sample-first-v2.report.data.json"),
            ("8k", f"{target}.8k.sample-first-v2.report.html", f"{target}.8k.sample-first-v2.report.data.json"),
            ("compare", f"{target}.167k_vs_8k.compare.html", None),
        ]
    if mode == "167k":
        specs = [item for item in specs if item[0] == "167k"]
    elif mode == "8k":
        specs = [item for item in specs if item[0] == "8k"]
    found: list[dict] = []
    roots = [root / "results", root / "output" / "results"]
    for kind, html_name, sidecar_name in specs:
        html_path = next((base / html_name for base in roots if (base / html_name).is_file()), None)
        if html_path is None:
            continue
        sidecar_path = None
        if sidecar_name:
            sidecar_path = next((base / sidecar_name for base in roots if (base / sidecar_name).is_file()), None)
        label_en, label_zh = _REPORT_LABELS[kind]
        found.append(
            {
                "kind": kind,
                "label_en": label_en,
                "label_zh": label_zh,
                "html": str(html_path),
                "sidecar": str(sidecar_path) if sidecar_path else None,
            }
        )
    return found


def _resolve_reports(root: Path, *, is_batch: bool, target: str, panel_mode: str) -> list[dict]:
    found: list[dict] | None = None
    try:
        from grapeancestry.web_run import find_report_artifacts
    except ImportError:
        find_report_artifacts = None  # type: ignore[assignment]
    if find_report_artifacts is not None:
        try:
            found = list(
                find_report_artifacts(root, is_batch=is_batch, target=target, panel_mode=panel_mode or "167k")
            )
        except TypeError:
            found = None
    if not found:
        found = _fallback_report_artifacts(root, is_batch=is_batch, target=target, panel_mode=panel_mode)
    reports: list[dict] = []
    for item in found or []:
        if not isinstance(item, dict):
            continue
        html_path = item.get("html")
        if not html_path:
            continue
        kind = str(item.get("kind") or "")
        label_en, label_zh = _REPORT_LABELS.get(kind, ("Report", "报告"))
        sidecar = item.get("sidecar")
        reports.append(
            {
                "kind": kind,
                "label_en": str(item.get("label_en") or label_en),
                "label_zh": str(item.get("label_zh") or label_zh),
                "html": str(html_path),
                "sidecar": str(sidecar) if sidecar else None,
            }
        )
    return reports


def _done_payload(target: str, *, is_batch: bool, panel_mode: str) -> dict:
    reports = _resolve_reports(ROOT, is_batch=is_batch, target=target, panel_mode=panel_mode)
    primary = reports[0] if reports else {}
    return {
        "report_id": target,
        "batch": is_batch,
        "panel_mode": panel_mode,
        "reports": reports,
        "html": primary.get("html") or "",
        "sidecar": primary.get("sidecar") or "",
    }


def _reports_from_done(done: dict) -> list[dict]:
    reports = list(done.get("reports") or [])
    if reports:
        return reports
    html = done.get("html")
    if not html:
        return []
    return [
        {
            "kind": "167k",
            "label_en": "Report",
            "label_zh": "报告",
            "html": str(html),
            "sidecar": done.get("sidecar") or None,
        }
    ]


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
  <div class="ga-kicker">v{html.escape(str(credits["version"]))}</div>
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
                "Choose a password for this page. It only locks the browser on this computer. It does not encrypt the files inside the container.",
                "给这个页面设一个密码。它只锁本机浏览器，不会加密容器里的文件。",
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
                st.error(t("The two passwords do not match, or one of them is empty.", "两次密码不一致，或有一处为空。"))
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
            "This password only locks the local page. After login you can start an analysis (FASTQ, BAM, or VCF) or open the Ages and HUN89 demos.",
            "这个密码只锁本机页面。登录后可以开始分析（FASTQ、BAM 或 VCF），也可以打开 Ages 和 HUN89 演示。",
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
            st.error(t("The two passwords do not match, or one of them is empty.", "两次密码不一致，或有一处为空。"))
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
            "Reviewed reports for Ages and HUN89_query. The quick VCF check only writes JSON. For a full VS-1 report, use Analysis.",
            "这里是 Ages 和 HUN89_query 的成稿报告。快速检查只写出 JSON。完整的 VS-1 报告请到「分析」。",
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
                st.error(t("This install does not include the demo package.", "当前安装里没有演示数据包。"))
            else:
                _show_companion_json(parsed)

    with st.expander(t("Quick check of a VCF in the input folder", "快速检查输入文件夹里的 VCF")):
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

    st.subheader(t("Run settings", "运行参数"))
    st.caption(
        t(
            "These are settings the pipeline already accepts. Defaults match config/default.yaml.",
            "这里只列出流水线已经支持的参数。默认值与 config/default.yaml 一致。",
        )
    )
    with st.expander(t("Sample role", "样本角色"), expanded=True):
        as_query = st.checkbox(
            t("Treat this sample as a new query (recommended)", "把这个样本当作新的查询样本（建议勾选）"),
            value=True,
            key="opt_as_query",
        )
        force_query_vcf = st.checkbox(
            t("Overwrite an existing query VCF", "覆盖已有的查询 VCF"),
            value=False,
            key="opt_force_query",
        )
        source_sample = ""
        if kind == "VCF":
            source_sample = st.text_input(
                t("Source sample ID (optional)", "来源样本 ID（可选）"),
                key="opt_source_sample",
                help=t(
                    "Used only for a VCF, to attach the BAM and mapDamage record. Leave blank to use the Sample ID.",
                    "只在输入是 VCF 时使用，用来关联 BAM 和 mapDamage 记录。留空则用样本 ID。",
                ),
            )
    with st.expander(t("Compute", "计算"), expanded=False):
        threads = st.number_input(
            t("Threads (Snakemake and bcftools)", "线程数（Snakemake 和 bcftools）"),
            min_value=1,
            max_value=32,
            value=int(st.session_state.get("threads") or 4),
            key="opt_threads",
        )
        snakemake_force = False
        if kind != "VCF":
            snakemake_force = st.checkbox(
                t("Rerun every Snakemake step", "重跑全部 Snakemake 步骤"),
                value=False,
                key="opt_forceall",
            )
        else:
            st.caption(
                t(
                    "A VCF does not start Snakemake, so the thread count is unused here.",
                    "VCF 分析不启动 Snakemake，线程数在这里不起作用。",
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
        with st.expander(t("Read trimming (fastp)", "读段修剪（fastp）"), expanded=True):
            st.caption("https://github.com/OpenGene/fastp")
            c1, c2 = st.columns(2)
            with c1:
                fastp_min_length = int(
                    st.number_input(
                        t("Minimum read length", "最短读长"),
                        min_value=1,
                        max_value=100,
                        value=15,
                        key="opt_fastp_min_length",
                    )
                )
                fastp_qualified_quality = int(
                    st.number_input(
                        t("Qualified base quality (Phred)", "合格碱基质量（Phred）"),
                        min_value=0,
                        max_value=40,
                        value=15,
                        key="opt_fastp_qual",
                    )
                )
                fastp_unqualified_percent = int(
                    st.number_input(
                        t("Maximum fraction of low-quality bases (%)", "低质量碱基比例上限（%）"),
                        min_value=0,
                        max_value=100,
                        value=40,
                        key="opt_fastp_unqual",
                    )
                )
            with c2:
                fastp_n_base_limit = int(
                    st.number_input(
                        t("Maximum N bases", "最多 N 碱基数"),
                        min_value=0,
                        max_value=50,
                        value=5,
                        key="opt_fastp_nbase",
                    )
                )
                fastp_poly_g = st.selectbox(
                    t("polyG trim", "polyG 修剪"),
                    options=list(FASTP_POLY_G),
                    index=0,
                    key="opt_fastp_polyg",
                )
                fastp_cut_tail = st.checkbox(
                    t("Trim the 3′ end by sliding window", "按滑窗修剪 3′ 端"),
                    value=False,
                    key="opt_fastp_cut_tail",
                )
                fastp_cut_mean_quality = int(
                    st.number_input(
                        t("Window mean quality", "窗口平均质量"),
                        min_value=1,
                        max_value=36,
                        value=20,
                        key="opt_fastp_cut_mean",
                    )
                )
            if fq_kind == "pe":
                fastp_detect_adapter_pe = st.checkbox(
                    t("Detect paired-end adapters", "检测双端接头"),
                    value=True,
                    key="opt_fastp_detect_pe",
                )
        with st.expander(t("Alignment (bwa mem)", "比对（bwa mem）"), expanded=True):
            st.caption("http://bio-bwa.sourceforge.net/bwa.shtml")
            m1, m2 = st.columns(2)
            with m1:
                bwa_mem_seed = int(
                    st.number_input(
                        t("Seed length", "种子长度"),
                        min_value=11,
                        max_value=32,
                        value=19,
                        key="opt_bwa_mem_k",
                    )
                )
            with m2:
                bwa_mem_min_score = int(
                    st.number_input(
                        t("Minimum alignment score", "最低比对分数"),
                        min_value=0,
                        max_value=100,
                        value=30,
                        key="opt_bwa_mem_t",
                    )
                )
    if kind == "FASTQ" and fq_kind == "adna":
        with st.expander(t("Read trimming (AdapterRemoval3)", "读段修剪（AdapterRemoval3）"), expanded=True):
            st.caption("adapterremoval3 3.0.1 --help · https://adapterremoval.readthedocs.io/")
            adna_min_length = int(
                st.number_input(
                    t("Minimum read length", "最短读长"),
                    min_value=15,
                    max_value=80,
                    value=25,
                    key="opt_adna_min_length",
                )
            )
            a1, a2 = st.columns(2)
            with a1:
                adna_adapter_selection = st.selectbox(
                    t("Adapter set", "接头集合"),
                    options=list(AR3_ADAPTER_SEL),
                    index=0,
                    key="opt_adna_adapter_sel",
                )
                adna_adapter1 = st.text_input(
                    t("Adapter 1 sequence (A/C/G/T/N, optional)", "接头 1 序列（A/C/G/T/N，可选）"),
                    key="opt_adna_adapter1",
                )
                adna_quality_trimming = st.selectbox(
                    t("Quality trimming", "质量修剪"),
                    options=list(AR3_QUAL_TRIM),
                    index=0,
                    key="opt_adna_qtrim",
                )
                adna_trim_min_quality = int(
                    st.number_input(
                        t("Minimum quality to keep", "保留的最低质量"),
                        min_value=0,
                        max_value=40,
                        value=2,
                        key="opt_adna_trim_minq",
                    )
                )
            with a2:
                adna_trim_mott_rate = float(
                    st.number_input(
                        t("Mott trimming threshold", "Mott 修剪阈值"),
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
                        t("Minimum overlap (bp)", "最短重叠（bp）"),
                        min_value=1,
                        max_value=30,
                        value=1,
                        key="opt_adna_min_ov",
                    )
                )
                adna_mismatch_rate = float(
                    st.number_input(
                        t("Mismatch rate", "错配率"),
                        min_value=0.01,
                        max_value=0.5,
                        value=0.1667,
                        step=0.01,
                        format="%.4f",
                        key="opt_adna_mm",
                    )
                )
                adna_pre_trim_polyx = st.selectbox(
                    t("polyX trim", "polyX 修剪"),
                    options=list(AR3_POLYX),
                    index=0,
                    key="opt_adna_polyx",
                )
                adna_min_mean_quality = int(
                    st.number_input(
                        t("Minimum mean quality (0 turns this off)", "最低平均质量（0 表示关闭）"),
                        min_value=0,
                        max_value=40,
                        value=0,
                        key="opt_adna_meanq",
                    )
                )
        with st.expander(t("Alignment (bwa aln)", "比对（bwa aln）"), expanded=True):
            st.caption("http://bio-bwa.sourceforge.net/bwa.shtml")
            b1, b2, b3 = st.columns(3)
            with b1:
                bwa_aln_l = int(
                    st.number_input(
                        t("Seed length (1024 turns seeding off)", "种子长度（1024 表示关闭）"),
                        min_value=32,
                        max_value=1024,
                        value=1024,
                        key="opt_bwa_aln_l",
                    )
                )
            with b2:
                bwa_aln_n = float(
                    st.number_input(
                        t("Maximum edit distance", "最大编辑距离"),
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
                        t("Maximum gap opens", "最多允许的缺口数"),
                        min_value=0,
                        max_value=10,
                        value=1,
                        key="opt_bwa_aln_o",
                    )
                )
    if kind in {"FASTQ", "BAM"}:
        with st.expander(t("Variant calling (bcftools)", "变异检出（bcftools）"), expanded=True):
            st.caption("http://www.htslib.org/doc/bcftools.html#mpileup")
            d1, d2 = st.columns(2)
            with d1:
                min_mq = int(
                    st.number_input(
                        t("Minimum mapping quality", "最低比对质量"),
                        min_value=0,
                        max_value=60,
                        value=0,
                        key="opt_min_mq",
                    )
                )
                min_bq = int(
                    st.number_input(
                        t("Minimum base quality", "最低碱基质量"),
                        min_value=0,
                        max_value=40,
                        value=13,
                        key="opt_min_bq",
                    )
                )
            with d2:
                max_depth = int(
                    st.number_input(
                        t("Maximum depth per file", "每个文件的最大深度"),
                        min_value=1,
                        max_value=10000,
                        value=250,
                        key="opt_max_depth",
                    )
                )
                adjust_mq = int(
                    st.number_input(
                        t("Mapping-quality adjustment (0 off, 50 for Illumina)", "比对质量校正（0 关闭，Illumina 常用 50）"),
                        min_value=0,
                        max_value=100,
                        value=0,
                        key="opt_adjust_mq",
                    )
                )
                min_dp = int(
                    st.number_input(
                        t("Drop genotypes with FORMAT/DP below (0 turns this off)", "丢掉 FORMAT/DP 低于该值的基因型（0 表示关闭）"),
                        min_value=0,
                        max_value=30,
                        value=0,
                        key="opt_min_dp",
                    )
                )
    with st.expander(t("Ancestry plots", "祖源图"), expanded=True):
        pca_color = st.selectbox(
            t("PCA colour (column in the 2449 table)", "PCA 着色（2449 表中的列）"),
            options=list(PCA_COLORS),
            index=0,
            key="opt_pca_color",
        )
        admix_mode = st.selectbox(
            t("ADMIXTURE mode", "ADMIXTURE 模式"),
            options=list(ADMIX_MODES),
            index=0,
            key="opt_admix_mode",
            format_func=lambda x: {
                "auto": t("Automatic: look up panel samples, project new ones", "自动：面板内样本直接读取，新样本做投影"),
                "lookup": t("Panel lookup only", "只读取面板里已有的 Q"),
                "nnls": t("Project onto the frozen allele frequencies (NNLS)", "用 NNLS 投影到冻结的等位基因频率"),
                "official": t("Project with ADMIXTURE -P", "用 ADMIXTURE -P 投影"),
            }[x],
        )
        admix_all_k = st.checkbox(
            t("Project every K from 2 to 8", "对 K=2 到 8 都做投影"),
            value=True,
            key="opt_admix_all_k",
        )
    if adna_adapter1 and any(ch not in "ACGTNacgtn" for ch in adna_adapter1):
        st.error(t("Adapter 1 can contain only A, C, G, T, and N.", "接头 1 只能包含 A、C、G、T 和 N。"))
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
            "Files stay on this computer, inside the Docker app. Drop them below to copy into the input folder, or place a large FASTQ directly in that folder. Nothing is sent to a remote server.",
            "文件只留在这台电脑的 Docker 应用里。拖到下面会复制进输入文件夹；很大的 FASTQ 也可以直接放进该文件夹。不会上传到远程服务器。",
        )
    )
    st.code(str(INPUT_DIR), language="text")
    dropped = st.file_uploader(
        t("Drop FASTQ, BAM, or VCF files", "拖入 FASTQ、BAM 或 VCF"),
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
    st.subheader(t("Bring a file into the input folder", "把文件放进输入文件夹"))
    st.caption(
        t(
            "Copy a bundled demo, or download from an http or https link. Each file is checked after it arrives. "
            f"The sample link is the BAM submitted with Orlando 2026, Nature Communications ({ORLANDO_V5_AGES_RUN}, {ORLANDO_V5_AGES_STUDY}). That BAM was aligned to 12Xv2, not VS-1.",
            "可以复制内置演示，也可以从 http 或 https 链接下载。文件到达后会自动检查。"
            f"示例链接是 Orlando 2026《Nature Communications》提交的 BAM（{ORLANDO_V5_AGES_RUN}，{ORLANDO_V5_AGES_STUDY}）。它比对的是 12Xv2，不是 VS-1。",
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
        t("Download link (http or https)", "下载链接（http 或 https）"),
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
    if st.button(t("Refresh the input folder", "重新读取输入文件夹")):
        st.rerun()
    mode = st.radio(
        t("Analysis mode", "分析模式"),
        options=["one", "several"],
        format_func=lambda item: {
            "one": t("One sample", "一个样本"),
            "several": t("Several samples", "多个样本"),
        }[item],
        horizontal=True,
        key="analysis_mode",
    )
    st.markdown(f"**{t('Site set', '位点集')}**")
    panel_left, panel_right = st.columns(2)
    with panel_left:
        use_167 = st.checkbox("GrapeAncestry (167K)", value=True, key="ga_panel_167k")
        st.caption(t("167,433-site capture panel.", "167,433 个位点的捕获芯片。"))
    with panel_right:
        use_8k = st.checkbox("GrapeReseq (8K)", value=False, key="ga_panel_8k")
        st.caption(
            t(
                "8,044 sites: the overlap of GrapeReseq 10K and the 167K panel.",
                "8,044 个位点，即 GrapeReseq 10K 与 167K 面板的交集。",
            )
        )
    if use_167 and use_8k:
        panel_mode = "both"
        st.info(
            "Both HTML reports will be written, plus a 167K-vs-8K comparison with a conclusion.\n\n"
            "将生成两份 HTML 报告，以及一份带结论的 167K 与 8K 比较报告。"
        )
    elif use_167:
        panel_mode = "167k"
    elif use_8k:
        panel_mode = "8k"
    else:
        panel_mode = ""
        st.warning(
            "Select at least one site set before starting.\n\n"
            "请至少勾选一种位点集，才能开始分析。"
        )
    st.session_state.panel_mode = panel_mode
    if mode == "several":
        _render_several_samples()
        return
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
            st.info(t("The input folder has no FASTQ yet.", "输入文件夹里还没有 FASTQ。"))
        r1 = _select_input(t("R1, or the single-end FASTQ", "R1，或单端 FASTQ"), fq_paths, "pick_r1")
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
            st.info(t("The input folder has no BAM yet. A BAM must already be aligned to VS-1.", "输入文件夹里还没有 BAM。BAM 必须已经比对到 VS-1。"))
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
            st.info(t("The input folder has no VCF yet.", "输入文件夹里还没有 VCF。"))
        vcf = _select_input(t("VCF", "VCF"), vcf_paths, "pick_vcf")
        if vcf:
            files["vcf"] = str(vcf)
        run_kind = "vcf"

    opts = _pipeline_options_form(kind, fq_kind)
    opts.paired = paired

    if st.button(t("Start analysis", "开始分析"), type="primary", disabled=not panel_mode):
        if not panel_mode:
            st.warning(
                "Select at least one site set before starting.\n\n请至少勾选一种位点集，才能开始分析。"
            )
            return
        if not sample.strip():
            st.error(t("Enter a sample ID.", "请填写样本 ID。"))
            return
        if run_kind == "pe" and ("r1" not in files or "r2" not in files):
            st.error(t("Choose both R1 and R2.", "请同时选择 R1 和 R2。"))
            return
        if run_kind in {"se", "adna"} and "r1" not in files:
            st.error(t("Choose a FASTQ file.", "请选择一个 FASTQ 文件。"))
            return
        if run_kind == "bam" and "bam" not in files:
            st.error(t("Choose a BAM file.", "请选择一个 BAM 文件。"))
            return
        if run_kind == "vcf" and "vcf" not in files:
            st.error(t("Choose a VCF file.", "请选择一个 VCF 文件。"))
            return
        st.session_state.job = {
            "sample": sample.strip(),
            "kind": run_kind,
            "files": files,
            "paired": opts.paired,
            "as_query": opts.as_query,
            "threads": opts.threads,
            "options": _with_panel_mode(opts.as_dict(), panel_mode),
        }
        st.session_state.sample_id = sample.strip()
        st.session_state.log_text = ""
        st.session_state.stage = "running"
        st.rerun()


def _default_batch_kind(filename: str) -> str:
    from grapeancestry.input_intake import guess_kind

    kind = guess_kind(filename)
    if kind == "bam":
        return "bam"
    if kind == "vcf":
        return "vcf"
    stem = Path(filename).name.lower()
    if stem.endswith("_1.fq.gz") or stem.endswith("_2.fq.gz") or "_1.fq" in stem or "_2.fq" in stem:
        return "fastq-pe"
    if "_1." in stem or "_2." in stem:
        return "fastq-pe"
    return "fastq-se"


def _render_several_samples() -> None:
    from grapeancestry.input_intake import inspect_input
    from grapeancestry.web_run import BATCH_KINDS, default_sample_id

    st.subheader(t("Several samples", "多个样本"))
    st.caption(
        t(
            "Each file in the input folder is one row. Paired FASTQ needs an R2 file. A BAM must already be aligned to VS-1.",
            "输入文件夹里每个文件占一行。双端 FASTQ 需要指定 R2。BAM 必须已经比对到 VS-1。",
        )
    )
    paths = sorted(path for path in INPUT_DIR.iterdir() if path.is_file()) if INPUT_DIR.is_dir() else []
    if not paths:
        st.info(t("The input folder is empty.", "输入文件夹是空的。"))
        return
    names = [path.name for path in paths]
    rows = [
        {
            "include": True,
            "sample_id": default_sample_id(path.name),
            "kind": _default_batch_kind(path.name),
            "file": path.name,
            "r2": "",
        }
        for path in paths
    ]
    edited = st.data_editor(
        rows,
        column_config={
            "include": st.column_config.CheckboxColumn(t("Include", "纳入")),
            "sample_id": st.column_config.TextColumn(t("Sample ID", "样本 ID")),
            "kind": st.column_config.SelectboxColumn(t("Kind", "类型"), options=list(BATCH_KINDS)),
            "file": st.column_config.TextColumn(t("File", "文件"), disabled=True),
            "r2": st.column_config.SelectboxColumn(t("R2 file", "R2 文件"), options=[""] + names),
        },
        hide_index=True,
        key="batch_editor",
        num_rows="fixed",
    )
    batch_name = st.text_input(t("Batch name", "批次名称"), value="batch", key="batch_name")
    panel_mode = str(st.session_state.get("panel_mode") or "")
    if not st.button(t("Start batch", "开始批次"), type="primary", disabled=not panel_mode):
        return
    if panel_mode not in _PANEL_MODES:
        st.warning(
            "Select at least one site set before starting.\n\n请至少勾选一种位点集，才能开始分析。"
        )
        return
    chosen = []
    if hasattr(edited, "to_dict"):
        records = edited.to_dict("records")
    else:
        records = list(edited)
    for row in records:
        if not row.get("include"):
            continue
        chosen.append(row)
    if len(chosen) < 2:
        st.error(t("Include at least two samples.", "请至少纳入两个样本。"))
        return
    ids = [str(row.get("sample_id") or "").strip() for row in chosen]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        st.error(t("Each sample ID must be filled in, and no two samples can share an ID.", "每个样本 ID 都要填写，而且不能重复。"))
        return
    job_rows = []
    for row, sample in zip(chosen, ids):
        kind = str(row.get("kind") or "")
        filename = str(row.get("file") or "")
        path = INPUT_DIR / filename
        if kind == "fastq-pe" and not str(row.get("r2") or "").strip():
            st.error(t(f"{sample} needs an R2 file.", f"{sample} 还需要指定 R2 文件。"))
            return
        if kind == "bam":
            report = inspect_input(path, root=ROOT)
            if not report.ok:
                st.error("; ".join(report.messages) or t("This BAM is not aligned to VS-1.", "这个 BAM 没有比对到 VS-1。"))
                return
        files: dict[str, str] = {}
        if kind in {"fastq-pe", "fastq-se", "adna"}:
            files["r1"] = str(path)
            if kind == "fastq-pe":
                files["r2"] = str(INPUT_DIR / str(row.get("r2")))
        elif kind == "bam":
            files["bam"] = str(path)
        elif kind == "vcf":
            files["vcf"] = str(path)
        else:
            st.error(t(f"The file type for {sample} is not recognised.", f"无法识别 {sample} 的文件类型。"))
            return
        job_rows.append({"sample": sample, "kind": kind, "files": files, "paired": kind == "bam"})
    name = str(batch_name or "").strip() or "batch"
    st.session_state.job = {
        "batch": True,
        "name": name,
        "rows": job_rows,
        "options": {"panel_mode": panel_mode},
    }
    st.session_state.log_text = ""
    st.session_state.stage = "running"
    st.rerun()


def _page_progress() -> None:
    import importlib

    import grapeancestry.web_run as web_run

    web_run = importlib.reload(web_run)
    PipelineOptions = web_run.PipelineOptions
    iter_pipeline = web_run.iter_pipeline
    report_id_for = web_run.report_id_for

    job = st.session_state.get("job") or {}
    if job.get("batch"):
        _page_progress_batch(job)
        return
    raw_options = dict(job.get("options") or {})
    panel_mode = str(raw_options.get("panel_mode") or "167k")
    opts = PipelineOptions.from_dict(raw_options)
    opts.paired = bool(job.get("paired"))
    st.title(t("3. Analysis running", "3. 分析进行中"))
    st.caption(
        t(
            f"Sample {job.get('sample')} · {job.get('kind')} · site set {panel_mode} · ADMIXTURE {opts.admix_mode} · PCA colour {opts.pca_color}",
            f"样本 {job.get('sample')} · {job.get('kind')} · 位点集 {panel_mode} · ADMIXTURE {opts.admix_mode} · PCA 着色 {opts.pca_color}",
        )
    )
    log_box = st.empty()
    status = st.empty()
    status.info(t("Running. The log updates below.", "正在运行，日志在下面更新。"))
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
        status.error(
            t(
                "The run failed. Read the log, correct the input, and start again.",
                "分析没有跑完。请看日志，改好输入后再开始。",
            )
        )
        if st.button(t("Back to file selection", "返回选择文件")):
            st.session_state.stage = "upload"
            st.rerun()
        return
    rid = report_id_for(str(job["sample"]), str(job["kind"]), bool(job.get("as_query")))
    st.session_state.done = _done_payload(rid, is_batch=False, panel_mode=panel_mode)
    if not (st.session_state.done.get("reports") or []):
        status.error(t("The run finished, but no report HTML was written.", "分析结束了，但没有写出报告。"))
        if st.button(t("Back to file selection", "返回选择文件")):
            st.session_state.stage = "upload"
            st.rerun()
        return
    st.session_state.stage = "done"
    st.rerun()


def _page_progress_batch(job: dict) -> None:
    import importlib

    import grapeancestry.web_run as web_run

    web_run = importlib.reload(web_run)
    iter_batch_pipeline = web_run.iter_batch_pipeline
    PipelineOptions = web_run.PipelineOptions

    rows = list(job.get("rows") or [])
    name = str(job.get("name") or "batch")
    raw_options = dict(job.get("options") or {})
    panel_mode = str(raw_options.get("panel_mode") or "167k")
    opts = PipelineOptions.from_dict(raw_options)
    st.title(t("3. Analysis running", "3. 分析进行中"))
    status = st.empty()
    status.info(t(f"Batch {name} · 0/{len(rows)}", f"批次 {name} · 0/{len(rows)}"))
    log_box = st.empty()
    chunks: list[str] = []
    code = 1
    for line, rc in iter_batch_pipeline(ROOT, rows, name, options=opts):
        if line is not None:
            chunks.append(line)
            if line.startswith("[batch] "):
                status.info(line.strip())
            log_box.text_area(t("Log", "日志"), "".join(chunks)[-12000:], height=360)
        if rc is not None:
            code = rc
    st.session_state.log_text = "".join(chunks)
    if code != 0:
        status.error(
            t(
                "The run failed. Read the log, correct the input, and start again.",
                "分析没有跑完。请看日志，改好输入后再开始。",
            )
        )
        if st.button(t("Back to file selection", "返回选择文件")):
            st.session_state.stage = "upload"
            st.rerun()
        return
    st.session_state.done = _done_payload(name, is_batch=True, panel_mode=panel_mode)
    if not (st.session_state.done.get("reports") or []):
        status.error(t("The run finished, but no batch report was written.", "分析结束了，但没有写出批次报告。"))
        if st.button(t("Back to file selection", "返回选择文件")):
            st.session_state.stage = "upload"
            st.rerun()
        return
    st.session_state.stage = "done"
    st.rerun()


def _render_report_card(index: int, report: dict) -> None:
    label = t(str(report.get("label_en") or "Report"), str(report.get("label_zh") or "报告"))
    html_path = Path(str(report.get("html") or ""))
    sidecar_raw = report.get("sidecar")
    sidecar = Path(str(sidecar_raw)) if sidecar_raw else None
    st.markdown(f"**{label}**")
    if html_path.is_file():
        try:
            rel = html_path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            rel = html_path.as_posix().lstrip("/")
        open_col, html_col = st.columns(2)
        with open_col:
            st.link_button(t("Open in a new tab", "在新标签页打开"), report_url(rel))
        with html_col:
            st.download_button(
                t("Download HTML", "下载 HTML"),
                data=html_path.read_bytes(),
                file_name=html_path.name,
                mime="text/html",
                key=f"done-html-{index}-{html_path.name}",
            )
    else:
        st.caption(t("This report file is not on disk yet.", "这份报告还没有写到磁盘上。"))
    if sidecar is not None and sidecar.is_file():
        st.download_button(
            t("Download JSON", "下载 JSON"),
            data=sidecar.read_bytes(),
            file_name=sidecar.name,
            mime="application/json",
            key=f"done-json-{index}-{sidecar.name}",
        )


def _page_done() -> None:
    ensure_file_server()
    done = st.session_state.get("done") or {}
    reports = _reports_from_done(done)
    st.title(t("4. Report ready", "4. 报告已完成"))
    if len(reports) > 1:
        st.success(
            t(
                "The reports are on this computer. Open each one, or download the HTML.",
                "报告已经写在这台电脑上。可以逐份打开，也可以下载 HTML。",
            )
        )
    else:
        st.success(t("The report is on this computer.", "报告已经写在这台电脑上。"))
    if not reports:
        st.warning(t("No report file was found.", "没有找到报告文件。"))
    for index, report in enumerate(reports):
        _render_report_card(index, report)
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
            "Sign in, choose files, watch the run, then open the report.",
            "先登录，再选文件，看运行进度，最后打开报告。",
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
