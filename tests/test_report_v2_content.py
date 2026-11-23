"""Tests for sample-first V2 paths and stable V1 artifact stability."""

from __future__ import annotations

import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import re
import shutil
import subprocess
from collections.abc import Mapping
from datetime import datetime
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import grapeancestry.report.build_report as report_module
from grapeancestry.adna.project import SVDCacheResult
from grapeancestry.report.build_report import ReportBundle, v2_report_path
from grapeancestry.breeding.methods_doc import methods_html_section
from grapeancestry.report.interactive_dashboard import APP_JS, render_interactive_dashboard, write_dashboard_html
from grapeancestry.report.interactive_data import payload_to_json


ROOT = Path(__file__).resolve().parents[1]

STABLE_V1_REPORT_SHA256 = {
    "results/Ages.report.v1.html": "b10b59e3413f339d6269817ce9e1e17f49425701d34cccfb419d9f45822dab34",
    "results/Ages.report.v1.data.json": "d20511cc2e925a347ed568b6327c748fd8b115af8bd078e9e77f65c62506856c",
    "results/HUN89_query.report.v1.html": "75e811a5033bc68473792176efc1a608a434e01335873e95641fca3077c5fade",
    "results/HUN89_query.report.v1.data.json": "eb00107bd144c4f9ac87bfcf9fbd1f7f8e9ca526c6ecd8611602ac9d085af578",
}

PRESENTATION_PAYLOAD_KEYS = {"methods_html"}
VOLATILE_PROVENANCE_KEYS = {"generated_at_utc", "mtime_ns", "size"}
TECHNICAL_TOKEN_EXCEPTIONS = frozenset(
    {
        "PCA",
        "f3 / f4",
        "f3/f4",
        "ADMIXTURE",
        "ADMIXTURE K=2–8",
        "mapDamage2",
    }
)
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_EN_SPAN_RE = re.compile(
    r"""<(?P<tag>span|div)(?=[^>]*\bclass\s*=\s*["'][^"']*\ben\b)[^>]*>.*?</(?P=tag)>""",
    re.IGNORECASE | re.DOTALL,
)

AGES_V2_SEMANTIC_PAYLOAD_SHA256 = (
    "66b72fab9df5388c4ec9a79651986dbc24bc88849ab3f5a3b86e211bb58514ff"
)
HUN89_QUERY_V2_SEMANTIC_PAYLOAD_SHA256 = (
    "2626bffe2bb4e550ed2c41ae7b477825fa1f4e2ac06197e390fe1f76845d1a4c"
)


def semantic_payload_view(payload: object) -> object:
    """Return a recursive view without presentation or volatile provenance keys."""
    def view(value: object, *, path: tuple[object, ...]) -> object:
        if isinstance(value, Mapping):
            is_file_signature = (
                path
                and path[0] == "report_meta"
                and "path" in value
                and "available" in value
            )
            excluded_keys = PRESENTATION_PAYLOAD_KEYS | {"generated_at_utc"}
            if is_file_signature:
                excluded_keys |= VOLATILE_PROVENANCE_KEYS
            return {
                key: view(
                    child,
                    path=path + (key,),
                )
                for key, child in value.items()
                if key not in excluded_keys
            }
        if isinstance(value, list):
            return [
                view(child, path=path + (str(index),))
                for index, child in enumerate(value)
            ]
        return value

    return view(payload, path=())


def semantic_payload_digest(payload_or_path: object) -> str:
    """Hash a canonical JSON view that excludes only non-semantic payload keys."""
    if isinstance(payload_or_path, (str, Path)):
        payload = json.loads(Path(payload_or_path).read_text(encoding="utf-8"))
    else:
        payload = payload_or_path
    canonical = json.dumps(
        semantic_payload_view(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


_REPORT_META_IDENTIFIER_KEYS = (
    "schema_version",
    "report_id",
    "query_id",
    "source_sample_id",
    "library_type",
    "library_class",
    "library_type_sample_id",
)
_V2_REWRITE_SAMPLES = {
    "Ages": AGES_V2_SEMANTIC_PAYLOAD_SHA256,
    "HUN89_query": HUN89_QUERY_V2_SEMANTIC_PAYLOAD_SHA256,
}
_V2_CHECKED_IN_RELATIVES = (
    "results/Ages.sample-first-v2.report.html",
    "results/Ages.sample-first-v2.report.data.json",
    "results/HUN89_query.sample-first-v2.report.html",
    "results/HUN89_query.sample-first-v2.report.data.json",
)


def _field_path(path: tuple[object, ...]) -> str:
    return ".".join(str(part) for part in path)


def collect_identifier_numeric_list_fields(
    payload: object,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Collect report_meta identifiers/availability plus every numeric and list field."""
    view = semantic_payload_view(payload)
    identifiers: dict[str, object] = {}
    numerics: dict[str, object] = {}
    lists: dict[str, object] = {}

    def walk(value: object, path: tuple[object, ...]) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = path + (key,)
                if key in _REPORT_META_IDENTIFIER_KEYS or key in {
                    "query",
                    "path",
                    "available",
                }:
                    identifiers[_field_path(child_path)] = child
                walk(child, child_path)
            return
        if isinstance(value, list):
            lists[_field_path(path)] = value
            for index, child in enumerate(value):
                walk(child, path + (index,))
            return
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            numerics[_field_path(path)] = value

    walk(view, ())
    return identifiers, numerics, lists


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_without_methods_html(payload: Mapping) -> dict:
    return {key: value for key, value in payload.items() if key != "methods_html"}


def _embedded_dashboard_payload(html: str) -> dict:
    prefix = "var PAYLOAD = "
    suffix = ";\nboot(PAYLOAD);"
    start = html.index(prefix) + len(prefix)
    end = html.rindex(suffix)
    embedded = json.loads(html[start:end])
    assert isinstance(embedded, dict)
    return embedded


def assert_rewritten_v2_html_contracts(
    html: str, methods_html: str, library_class: str
) -> None:
    """Assert bilingual/static/runtime rewrite contracts on generated V2 HTML."""
    assert 'data-ga-theme-bootstrap' in html
    assert 'aria-label="Report language"' in html
    assert 'data-lang-choice="en"' in html
    assert 'data-lang-choice="zh"' in html
    assert 'html:not([data-lang="zh"]) .cn{display:none!important}' in html
    assert 'html[data-lang="zh"] .en{display:none!important}' in html
    assert 'class="en">Methods' in html
    assert 'class="cn">方法说明' in html
    assert "function pairLangBlocks" in html
    assert "function initLangController" in html
    assert "function setLang" in html
    assert "function resolveTheme" in html
    assert "function applyDamageSectionState" in html
    assert "function isModernLibrary" in html
    assert "localStorage.getItem('ga-lang')" in html
    assert re.search(r"<h2[^>]*>Reproduce", html) is None
    assert "Wall time on MBP" not in html
    assert "conda activate ga" not in html
    assert "Methods not used and why" not in html
    assert "未采用方法与理由" not in html
    assert "methods-breeding" in methods_html
    assert '<span class="en">Breeding methods &amp; data</span>' in methods_html
    assert '<span class="cn">育种方法与数据</span>' in methods_html
    embedded = _embedded_dashboard_payload(html)
    assert embedded["methods_html"] == methods_html
    if library_class == "modern":
        assert 'id="damage" data-library-class="modern" class="is-modern-library"' in html
        modern_note = _element_block(html, "damage-modern-note")
        assert "modern PE" in modern_note
        assert "Ginolhac" not in modern_note
    else:
        assert 'id="damage" data-library-class="ancient"' in html
        assert 'class="is-modern-library"' not in _element_block(html, "damage")
        assert "Ginolhac et al. 2011" in _element_block(html, "damage-guide")


def test_semantic_payload_view_is_path_aware_for_file_signatures() -> None:
    payload = {
        "plot": {
            "marker": {"size": [4, 8, 15]},
            "report_meta": {
                "record": {
                    "path": "semantic/nested.json",
                    "available": True,
                    "size": 222,
                    "mtime_ns": 333,
                }
            },
        },
        "outside_report_meta": {
            "path": "semantic/plot.json",
            "available": True,
            "size": 123,
            "mtime_ns": 456,
        },
        "report_meta": {
            "panel_cache": {
                "path": "results/cache/panel.npz",
                "available": True,
                "size": 789,
                "mtime_ns": 101112,
            },
            "shared_artifacts": {
                "selection": {
                    "manhattan": {
                        "path": "results/selection/manhattan.json",
                        "available": True,
                        "size": 131415,
                        "mtime_ns": 161718,
                    }
                }
            },
        },
        "methods_html": "<p>presentation only</p>",
        "generated_at_utc": "2026-09-17T00:00:00Z",
    }

    assert semantic_payload_view(payload) == {
        "plot": {
            "marker": {"size": [4, 8, 15]},
            "report_meta": {
                "record": {
                    "path": "semantic/nested.json",
                    "available": True,
                    "size": 222,
                    "mtime_ns": 333,
                }
            },
        },
        "outside_report_meta": {
            "path": "semantic/plot.json",
            "available": True,
            "size": 123,
            "mtime_ns": 456,
        },
        "report_meta": {
            "panel_cache": {
                "path": "results/cache/panel.npz",
                "available": True,
            },
            "shared_artifacts": {
                "selection": {
                    "manhattan": {
                        "path": "results/selection/manhattan.json",
                        "available": True,
                    }
                }
            },
        },
    }


def assert_stable_v1_report_checksums(root: Path = ROOT) -> None:
    """Assert stable V1 hashes, skipping only when artifacts are unavailable."""
    paths = {relative: root / relative for relative in STABLE_V1_REPORT_SHA256}
    present = [relative for relative, path in paths.items() if path.is_file()]
    if not present:
        pytest.skip("stable V1 report artifacts absent")

    for relative in present:
        expected = STABLE_V1_REPORT_SHA256[relative]
        actual = hashlib.sha256(paths[relative].read_bytes()).hexdigest()
        assert actual == expected, f"unexpected SHA-256 for {relative}: {actual}"


@pytest.mark.parametrize(("relative", "expected"), STABLE_V1_REPORT_SHA256.items())
def test_stable_v1_report_artifact_has_immutable_checksum(
    relative: str, expected: str
) -> None:
    path = ROOT / relative
    if not path.is_file():
        pytest.skip(f"stable V1 report artifact absent: {relative}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == expected, f"unexpected SHA-256 for {relative}: {actual}"


def test_v2_report_path_uses_sample_first_suffix() -> None:
    assert v2_report_path(ROOT / "results", "Ages") == (
        ROOT / "results" / "Ages.sample-first-v2.report.html"
    )
    assert v2_report_path(ROOT / "results", "HUN89_query") == (
        ROOT / "results" / "HUN89_query.sample-first-v2.report.html"
    )


def test_file_signature_is_workspace_relative_and_reports_absent_files(tmp_path: Path) -> None:
    signature = getattr(report_module, "file_signature", None)
    assert callable(signature)

    present = tmp_path / "results" / "cache" / "panel.npz"
    present.parent.mkdir(parents=True)
    present.write_bytes(b"panel")
    stat = present.stat()

    assert signature(tmp_path, present) == {
        "path": "results/cache/panel.npz",
        "available": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    assert signature(tmp_path, tmp_path / "results" / "missing.vcf.gz") == {
        "path": "results/missing.vcf.gz",
        "available": False,
    }


def test_report_meta_records_query_source_and_shared_artifact_signatures(
    tmp_path: Path,
) -> None:
    build_meta = getattr(report_module, "build_report_meta", None)
    assert callable(build_meta)

    paths = {
        "panel_cache": tmp_path / "results" / "cache" / "panel.npz",
        "query_vcf": tmp_path / "results" / "QUERY.vcf.gz",
        "source_bam": tmp_path / "results" / "bam" / "SOURCE.markdup.bam",
        "selection_manhattan": tmp_path / "results" / "selection" / "manhattan.json",
        "selection_locuszoom": tmp_path / "results" / "selection" / "locuszoom.json",
        "gwas_index": tmp_path / "results" / "gwas" / "index.tsv",
        "gwas_locuszoom": tmp_path / "results" / "gwas" / "locuszoom.json",
        "gs_index": tmp_path / "results" / "gs" / "index.tsv",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")

    meta = build_meta(
        tmp_path,
        query_id="QUERY",
        source_sample_id="SOURCE",
        panel_cache=paths["panel_cache"],
        query_vcf=paths["query_vcf"],
        source_bam=paths["source_bam"],
    )

    assert meta["schema_version"] == "sample-first-v2"
    assert meta["query_id"] == "QUERY"
    assert meta["source_sample_id"] == "SOURCE"
    assert meta["generated_at_utc"].endswith("Z")
    assert datetime.fromisoformat(
        meta["generated_at_utc"].replace("Z", "+00:00")
    ).tzinfo is not None
    assert meta["panel_cache"]["path"] == "results/cache/panel.npz"
    assert meta["query_vcf"]["path"] == "results/QUERY.vcf.gz"
    assert meta["source_bam"]["path"] == "results/bam/SOURCE.markdup.bam"
    assert meta["shared_artifacts"]["selection"]["manhattan"]["size"] == 1
    assert meta["shared_artifacts"]["selection"]["locuszoom"]["size"] == 1
    assert meta["shared_artifacts"]["gwas"]["index"]["size"] == 1
    assert meta["shared_artifacts"]["gwas"]["locuszoom"]["size"] == 1
    assert meta["shared_artifacts"]["gs"]["index"]["size"] == 1
    assert meta["library_type"] == ""
    assert meta["library_class"] == ""
    assert meta["library_type_sample_id"] == ""
    assert str(tmp_path) not in str(meta)


def test_resolve_sample_library_type_from_config_yaml() -> None:
    hun = report_module.resolve_sample_library_type(
        ROOT, source_sample_id="HUN89", query_id="HUN89_query"
    )
    ages = report_module.resolve_sample_library_type(
        ROOT, source_sample_id="Ages", query_id="Ages"
    )
    assert hun["library_type"] == "pe"
    assert hun["library_class"] == "modern"
    assert hun["library_type_sample_id"] == "HUN89"
    assert ages["library_type"] == "adna"
    assert ages["library_class"] == "ancient"
    assert ages["library_type_sample_id"] == "Ages"


def test_modern_library_bakes_hidden_damage_plots(tmp_path: Path) -> None:
    from grapeancestry.report.interactive_dashboard import (
        apply_damage_library_class,
        payload_library_class,
    )

    modern = json.dumps(
        {
            "query": "HUN89_query",
            "report_meta": {"library_type": "pe", "library_class": "modern"},
            "conclusions": ["Damage: 5′ C→T pos1=0.010."],
            "damage": {"ct5": [0.01], "ga3": [0.012]},
        }
    )
    ancient = json.dumps(
        {
            "query": "Ages",
            "report_meta": {"library_type": "adna", "library_class": "ancient"},
            "conclusions": ["Damage: 5′ C→T pos1=0.200."],
        }
    )
    assert payload_library_class(modern) == "modern"
    assert payload_library_class(ancient) == "ancient"
    assert 'class="is-modern-library"' in apply_damage_library_class(
        '<section id="damage">x</section>', modern
    )
    assert 'class="is-modern-library"' not in apply_damage_library_class(
        '<section id="damage">x</section>', ancient
    )

    html = write_dashboard_html(
        "HUN89_query",
        modern,
        tmp_path / "modern.html",
        ROOT,
        write_sidecar=False,
    ).read_text()
    assert 'id="damage" data-library-class="modern" class="is-modern-library"' in html
    assert 'id="damage-modern-note"' in html
    assert "function isModernLibrary" in html
    assert "if(applyDamageSectionState()) return;" in html
    assert "function applyDamageSectionState" in html
    assert 'class="en">Modern sample.' in html
    assert 'class="cn">现代样品。' in html
    modern_note = _element_block(html, "damage-modern-note")
    assert "modern PE" in modern_note
    assert "not applicable" in modern_note
    assert "现代 PE" in modern_note
    assert "不适用" in modern_note
    assert "Ginolhac" not in modern_note
    assert "Jónsson" not in modern_note and "Jonsson" not in modern_note
    assert "btr347" not in modern_note
    assert "btt193" not in modern_note
    assert "#damage.is-modern-library #damage-guide" in html
    guide = _element_block(html, "damage-guide")
    assert "hidden" in _element_block(html, "damage-modern-note") or (
        'id="damage-modern-note" hidden' in html
    )
    assert "Ginolhac et al. 2011" in guide
    assert "Jónsson et al. 2013" in guide

    ancient_payload = json.dumps(
        {
            "query": "Ages",
            "report_meta": {"library_type": "adna", "library_class": "ancient"},
            "damage": {
                "source": "mapDamage2",
                "version": "2.2.3",
                "ct5": [0.2],
                "ga3": [0.18],
                "length": [{"len": 40, "n": 12}],
            },
            "conclusions": ["Damage: 5′ C→T pos1=0.200."],
        }
    )
    assert payload_library_class(ancient_payload) == "ancient"
    ancient_html = write_dashboard_html(
        "Ages",
        ancient_payload,
        tmp_path / "ancient.html",
        ROOT,
        write_sidecar=False,
    ).read_text()
    assert 'id="damage" data-library-class="ancient"' in ancient_html
    assert 'class="is-modern-library"' not in _element_block(ancient_html, "damage")
    assert '"source": "mapDamage2"' in ancient_html
    assert "https://doi.org/10.1093/bioinformatics/btr347" in _element_block(
        ancient_html, "damage-guide"
    )
    assert "https://doi.org/10.1093/bioinformatics/btt193" in _element_block(
        ancient_html, "damage-guide"
    )


def test_modern_damage_copy_excludes_ancient_citations(tmp_path: Path) -> None:
    html = write_dashboard_html(
        "HUN89_query",
        json.dumps(
            {
                "query": "HUN89_query",
                "report_meta": {
                    "library_type": "pe",
                    "library_class": "modern",
                    "query_id": "HUN89_query",
                    "source_sample_id": "HUN89",
                },
                "conclusions": [
                    "Modern sample / modern PE library (config type: pe); "
                    "terminal C→T / G→A plots are not shown."
                ],
                "damage": {"source": "mapDamage2", "ct5": [0.01], "ga3": [0.012]},
            }
        ),
        tmp_path / "modern.html",
        ROOT,
        write_sidecar=False,
    ).read_text()
    modern_note = _element_block(html, "damage-modern-note")
    assert_nonempty_language_pair(modern_note, "Modern sample.", "现代样品。")
    assert_nonempty_language_pair(
        modern_note,
        "modern PE source library",
        "现代 PE 来源文库",
    )
    assert_nonempty_language_pair(
        modern_note,
        "ancient-DNA damage module is not applicable",
        "古 DNA 损伤模块不适用",
    )
    assert_nonempty_language_pair(
        modern_note,
        "no damage plot is displayed",
        "不显示损伤图",
    )
    for marker in (
        "Ginolhac",
        "Jónsson",
        "Jonsson",
        "btr347",
        "btt193",
        "mapDamage",
        "C→T",
        "G→A",
    ):
        assert marker not in modern_note

    observed = _run_report_node(
        r"""
function node(){
  return {
    innerHTML:'', textContent:'', hidden:true, style:{}, attrs:{},
    className:'', classList:{add:function(){},remove:function(){},toggle:function(){}},
    setAttribute:function(k,v){this.attrs[k]=String(v);},
    getAttribute:function(k){return this.attrs[k]||null;},
    removeAttribute:function(k){delete this.attrs[k];}
  };
}
function visible(html){
  var el=node();
  el.innerHTML=html;
  el.textContent=html;
  el.hidden=false;
  el.style.display='block';
  el.style.height='360px';
  el.style.minHeight='360px';
  return el;
}
var els={
  damage:node(),
  'damage-modern-note':node(),
  'damage-guide':visible('SENTINEL-GUIDE Ginolhac btr347'),
  'damage-note':visible('SENTINEL-NOTE'),
  'plot-damage':visible('SENTINEL-PLOT'),
  'plot-damage-len':visible('SENTINEL-PLOT-LEN'),
  'concl-list':node()
};
els.damage.setAttribute('data-library-class','modern');
document={
  getElementById:function(id){return els[id]||null;},
  querySelectorAll:function(){return [];}
};
window={_gaLangReady:true};
D={
  query:'HUN89_query',
  report_meta:{library_type:'pe',library_class:'modern',query_id:'HUN89_query',source_sample_id:'HUN89'},
  conclusions:['Modern sample / modern PE library (config type: pe); terminal C→T / G→A plots are not shown.'],
  damage:{source:'mapDamage2',version:'2.2.3',ct5:[0.01],ga3:[0.012]}
};
var before={
  guide:els['damage-guide'].innerHTML,
  guideHidden:!!els['damage-guide'].hidden,
  plot:els['plot-damage'].innerHTML,
  plotHidden:!!els['plot-damage'].hidden,
  plotLen:els['plot-damage-len'].innerHTML,
  plotLenHidden:!!els['plot-damage-len'].hidden,
  note:els['damage-note'].innerHTML
};
fillConclusions();
var hid=applyDamageSectionState();
console.log(JSON.stringify({
  before:before,
  hid:hid,
  after:{
    concl:els['concl-list'].innerHTML,
    guide:els['damage-guide'].innerHTML,
    guideHidden:!!els['damage-guide'].hidden,
    plot:els['plot-damage'].innerHTML,
    plotHidden:!!els['plot-damage'].hidden,
    plotLen:els['plot-damage-len'].innerHTML,
    plotLenHidden:!!els['plot-damage-len'].hidden,
    noteHidden:!!els['damage-note'].hidden,
    modernNoteHidden:!!els['damage-modern-note'].hidden
  },
  helper:typeof modernPeConclusionPair==='function'?modernPeConclusionPair():null
}));
"""
    )
    assert observed["before"]["guide"] == "SENTINEL-GUIDE Ginolhac btr347"
    assert observed["before"]["guideHidden"] is False
    assert observed["before"]["plot"] == "SENTINEL-PLOT"
    assert observed["before"]["plotHidden"] is False
    assert observed["before"]["plotLen"] == "SENTINEL-PLOT-LEN"
    assert observed["before"]["plotLenHidden"] is False
    assert observed["hid"] is True
    after = observed["after"]
    assert after["guideHidden"] is True
    assert after["plotHidden"] is True
    assert after["plotLenHidden"] is True
    assert after["noteHidden"] is True
    assert after["modernNoteHidden"] is False
    assert after["plot"] == ""
    assert after["plotLen"] == ""
    assert "SENTINEL-PLOT" not in after["plot"]
    assert "SENTINEL-GUIDE" not in (after["guide"] or "") or after["guideHidden"] is True
    assert_dynamic_pair(
        after["concl"],
        "Modern PE source library",
        "现代 PE 来源文库",
    )
    assert "Ginolhac" not in after["concl"]
    assert "Jónsson" not in after["concl"] and "Jonsson" not in after["concl"]
    assert "btr347" not in after["concl"] and "btt193" not in after["concl"]
    assert "mapDamage" not in after["concl"]
    assert observed["helper"] == {
        "en": (
            "Modern PE source library; the ancient-DNA damage module is "
            "not applicable, so no damage plot is displayed."
        ),
        "zh": "现代 PE 来源文库；古 DNA 损伤模块不适用，因此不显示损伤图。",
    }
    assert "function modernPeConclusionPair" in APP_JS
    assert APP_JS.count("function modernPeConclusionPair") == 1
    assert APP_JS.count("modernPeConclusionPair()") >= 2


def test_ancient_damage_copy_keeps_mapdamage_context(tmp_path: Path) -> None:
    html = write_dashboard_html(
        "Ages",
        json.dumps(
            {
                "query": "Ages",
                "report_meta": {
                    "library_type": "adna",
                    "library_class": "ancient",
                    "query_id": "Ages",
                    "source_sample_id": "Ages",
                },
                "damage": {
                    "source": "mapDamage2",
                    "version": "2.2.3",
                    "ct5": [0.2],
                    "ga3": [0.18],
                    "length": [{"len": 40, "n": 12}],
                },
            }
        ),
        tmp_path / "ancient.html",
        ROOT,
        write_sidecar=False,
    ).read_text()
    guide = _element_block(html, "damage-guide")
    assert "Ginolhac et al. 2011" in guide
    assert "https://doi.org/10.1093/bioinformatics/btr347" in guide
    assert "Jónsson et al. 2013" in guide
    assert "https://doi.org/10.1093/bioinformatics/btt193" in guide
    assert_nonempty_language_pair(guide, "How to read.", "怎么看：")
    assert_nonempty_language_pair(guide, "mapDamage2", "mapDamage2")
    assert_nonempty_language_pair(guide, "fragment-length", "片段长度")

    observed = _run_report_node(
        r"""
function node(){
  return {
    innerHTML:'', textContent:'', hidden:false, style:{display:''},
    id:'', clientWidth:500, clientHeight:500,
    classList:{add:function(){},toggle:function(){}},
    setAttribute:function(){}, removeAttribute:function(){}
  };
}
var layouts=[];
var els={
  damage:node(),
  'damage-modern-note':node(),
  'damage-guide':node(),
  'damage-note':node(),
  'plot-damage':Object.assign(node(),{id:'plot-damage'}),
  'plot-damage-len':Object.assign(node(),{id:'plot-damage-len'})
};
els['damage-modern-note'].hidden=true;
document={getElementById:function(id){return els[id]||null;},querySelectorAll:function(){return [];}};
window={};
Plotly={
  newPlot:function(el,data,layout){
    layouts.push({id:el.id,title:layout.title&&layout.title.text,x:layout.xaxis&&layout.xaxis.title,x2:layout.xaxis2&&layout.xaxis2.title,y:layout.yaxis&&layout.yaxis.title,hover:data.map(function(t){return t.hovertemplate;}),names:data.map(function(t){return t.name;})});
    return {then:function(fn){fn();}};
  },
  purge:function(){}
};
globalThis.Plotly=Plotly;
D={
  query:'Ages',
  report_meta:{library_type:'adna',library_class:'ancient',query_id:'Ages',source_sample_id:'Ages'},
  damage:{source:'mapDamage2',version:'2.2.3',ct5:[0.2],ga3:[0.18],length:[{len:40,n:12}]}
};
function snap(mode){
  langMode=mode;
  layouts.length=0;
  fillExtra();
  loadDamage();
  return {
    note:els['damage-note'].innerHTML||els['damage-note'].textContent,
    modernHidden:!!els['damage-modern-note'].hidden,
    guideHidden:!!els['damage-guide'].hidden,
    plots:layouts.slice()
  };
}
var withData={en:snap('en'),zh:snap('zh')};
D.damage={source:'mapDamage2',version:'2.2.3',ct5:[],ga3:[],length:[]};
els['plot-damage'].innerHTML='';
fillExtra(); loadDamage();
var emptyNote=els['damage-note'].innerHTML||els['damage-note'].textContent;
var emptyPlot=els['plot-damage'].innerHTML;
var failNode=node();
window.Plotly=undefined;
globalThis.Plotly=undefined;
plotlyUnavailable(failNode,'Damage plot');
console.log(JSON.stringify({
  withData:withData,
  emptyNote:emptyNote,
  emptyPlot:emptyPlot,
  fail:failNode.innerHTML
}));
"""
    )
    en_note = observed["withData"]["en"]["note"]
    zh_note = observed["withData"]["zh"]["note"]
    assert "mapDamage2" in en_note and "2.2.3" in en_note
    assert "mapDamage2" in zh_note and "2.2.3" in zh_note
    assert observed["withData"]["en"]["modernHidden"] is True
    assert observed["withData"]["en"]["guideHidden"] is False
    assert observed["withData"]["zh"]["guideHidden"] is False
    en_plots = {row["id"]: row for row in observed["withData"]["en"]["plots"]}
    zh_plots = {row["id"]: row for row in observed["withData"]["zh"]["plots"]}
    assert "Misincorporation (mapDamage)" in en_plots["plot-damage"]["title"]
    assert "Position from 5" in en_plots["plot-damage"]["x"]
    assert "Position from 3" in en_plots["plot-damage"]["x2"]
    assert "Frequency" in en_plots["plot-damage"]["y"]
    assert any("C→T" in name for name in en_plots["plot-damage"]["names"])
    assert any("5′" in (h or "") or "C→T" in (h or "") for h in en_plots["plot-damage"]["hover"])
    assert "Fragment length" in en_plots["plot-damage-len"]["title"]
    assert "Length" in en_plots["plot-damage-len"]["x"]
    assert "Reads" in en_plots["plot-damage-len"]["y"]
    assert "误掺入" in zh_plots["plot-damage"]["title"]
    assert "5′" in zh_plots["plot-damage"]["x"]
    assert "3′" in zh_plots["plot-damage"]["x2"]
    assert "频率" in zh_plots["plot-damage"]["y"]
    assert "片段长度" in zh_plots["plot-damage-len"]["title"]
    assert "长度" in zh_plots["plot-damage-len"]["x"]
    assert "读段" in zh_plots["plot-damage-len"]["y"]
    assert_error_language_pair(observed["emptyPlot"], "No damage profile", "没有损伤谱")
    assert_error_language_pair(observed["emptyNote"], "No damage profile", "没有损伤谱")
    assert "mapDamage2" in observed["emptyNote"]
    assert "2.2.3" in observed["emptyNote"]
    assert_error_language_pair(observed["fail"], "Plotly.js unavailable", "Plotly.js 不可用")


def test_modern_and_ancient_method_coverage_scopes_are_localized() -> None:
    observed = _run_report_node(
        r"""
var els={'method-coverage':{innerHTML:''},'report-meta':{innerHTML:''}};
document={getElementById:function(id){return els[id]||null;}};
function coverageFor(meta, extra){
  extra=extra||{};
  D={
    query:meta.query_id,
    report_meta:meta,
    method_coverage:{
      panel_genotype:{called:1,total:2,coverage:0.5},
      gs_predictions:[],
      gs:{available:false,unavailable_reason:'no per-sample GS prediction available'},
      damage:Object.assign({
        available:false,path:'results/'+meta.source_sample_id+'.damage.tsv',
        path_available:false,unavailable_reason:'no damage profile',
        source_sample_id:meta.source_sample_id
      }, extra.damage||{})
    }
  };
  els['method-coverage'].innerHTML='';
  els['report-meta'].innerHTML='';
  fillReportMeta();
  fillMethodCoverage();
  var coverage=els['method-coverage'].innerHTML;
  var damageReason='';
  coverage.split('<tr>').forEach(function(row){
    if(row.indexOf('Damage profile')>=0){
      var cells=row.split('</td>');
      damageReason=cells.length>3?cells[3]:row;
    }
  });
  return {
    coverage:coverage,
    meta:els['report-meta'].innerHTML,
    damageReason:damageReason,
    sourceLabel:typeof sourceDamageLabel==='function'?sourceDamageLabel():''
  };
}
var modern=coverageFor({
  query_id:'HUN89_query',source_sample_id:'HUN89',library_class:'modern',library_type:'pe'
});
var ancient=coverageFor({
  query_id:'Ages',source_sample_id:'Ages',library_class:'ancient',library_type:'adna'
},{damage:{available:true,path_available:true,unavailable_reason:''}});
console.log(JSON.stringify({modern:modern, ancient:ancient}));
"""
    )
    modern = observed["modern"]["coverage"]
    ancient = observed["ancient"]["coverage"]
    assert (
        'class="en">Damage profile</span><span class="cn">损伤谱</span></td><td>'
        '<span class="en">Source library</span><span class="cn">来源文库</span>'
        in modern
    )
    assert (
        'class="en">Damage profile</span><span class="cn">损伤谱</span></td><td>'
        '<span class="en">Query-derived</span><span class="cn">查询样本来源</span>'
        in ancient
    )
    assert_dynamic_pair(modern, "Source library", "来源文库")
    assert_dynamic_pair(ancient, "Query-derived", "查询样本来源")
    for blob in (modern, ancient, observed["modern"]["meta"], observed["ancient"]["meta"]):
        lowered = blob.lower()
        assert "panel training failed" not in lowered
        assert "training failed" not in lowered
        assert "训练失败" not in blob
        assert "panel 训练" not in blob
    assert "No per-query GS prediction available" in modern
    assert "没有可用的本查询 GS 预测" in modern
    assert "No per-query GS prediction available" in ancient
    assert "没有可用的本查询 GS 预测" in ancient
    modern_reason = observed["modern"]["damageReason"]
    ancient_reason = observed["ancient"]["damageReason"]
    assert "Source library" in modern_reason
    assert "来源文库" in modern_reason
    assert "HUN89" in modern_reason
    assert "Source library" not in ancient_reason
    assert "来源文库" not in ancient_reason
    assert "Query" in ancient_reason
    assert "查询样本" in ancient_reason
    assert "Ages" in ancient_reason
    assert_dynamic_pair(observed["modern"]["sourceLabel"], "Source library", "来源文库")
    assert "HUN89" in observed["modern"]["sourceLabel"]
    assert "HUN89_query" in observed["modern"]["sourceLabel"]
    assert_dynamic_pair(observed["ancient"]["sourceLabel"], "Query-derived", "查询样本来源")
    assert "Ages" in observed["ancient"]["sourceLabel"]


def test_build_bundle_loads_source_damage_without_explicit_damage_tsv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path
    cache = root / "results" / "cache" / "resolved.npz"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"cache")
    calls: list[tuple[str, Path | None]] = []
    writes: list[Path] = []
    source_damage = root / "results" / "SOURCE.damage.tsv"
    source_damage.write_bytes(b"source damage\n")

    def fake_write_damage(
        _ct5: list[float], path: Path, *, ga3: list[float] | None = None
    ) -> None:
        del ga3
        writes.append(Path(path))
        Path(path).write_bytes(b"rewritten by build_bundle\n")

    def fake_damage(root_arg: Path, sample: str, *, tsv: Path | None = None):
        del root_arg
        calls.append((sample, tsv))
        if sample == "SOURCE":
            return {"ct5": [0.1], "ga3": [0.2]}
        return None

    monkeypatch.setattr(
        "grapeancestry.adna.damage_lite.load_sample_damage", fake_damage
    )
    monkeypatch.setattr("grapeancestry.adna.damage_lite.write_damage_tsv", fake_write_damage)
    monkeypatch.setattr(
        "grapeancestry.core.dosage.resolve_cache", lambda _root: cache
    )
    monkeypatch.setattr(
        report_module,
        "load_cache",
        lambda _path: (
            np.array([[0]], dtype=np.int8),
            ["REF"],
            ["1:1"],
        ),
    )
    monkeypatch.setattr(
        report_module, "load_sample_dosage", lambda *_args: np.array([0], dtype=np.int8)
    )
    monkeypatch.setattr(report_module, "collect_ibs", lambda *_args: [])
    monkeypatch.setattr(report_module, "load_family_sites", lambda _path: [])
    monkeypatch.setattr(report_module, "load_svd_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        report_module,
        "run_smartpca_project",
        lambda *args, **kwargs: SVDCacheResult(
            ref_ids=["REF"],
            ref_coords=np.array([[0.0, 0.0, 0.0]]),
            query_ids=["REPORT"],
            query_coords=np.array([[0.0, 0.0, 0.0]]),
            evals=[],
            workdir=root,
            method="test",
            cache_name=cache.name,
            n_sites=1,
        ),
    )
    monkeypatch.setattr(report_module, "load_oiv_table", lambda _path: {})
    monkeypatch.setattr(report_module, "load_gene_func", lambda _root: {})
    monkeypatch.setattr(report_module, "trait_overlap", lambda *args, **kwargs: ([], 0))
    monkeypatch.setattr(
        report_module,
        "_load_precomputed_breeding",
        lambda _root, _sample: {
            "gwas_index": [],
            "gs_index": [],
            "gs_pred": [],
            "gwas_loci": [],
            "cross_top": [],
            "gwas_figs": {},
            "gwas_skip": "",
            "methods_html": "",
            "gwas_trait": "",
            "gs": {},
        },
    )
    monkeypatch.setattr(report_module, "greedy_coresnp", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "grapeancestry.popgen.selscan.load_scan_tables", lambda _path: {}
    )
    monkeypatch.setattr(
        "grapeancestry.popgen.selscan.load_named_windows", lambda _path: []
    )
    monkeypatch.setattr(
        "grapeancestry.popgen.selection_viz.load_selection_viz",
        lambda _root: {},
    )
    monkeypatch.setattr(
        "grapeancestry.popgen.selscan.scan_panel",
        lambda *args, **kwargs: {
            "het_dips": [],
            "het_window": None,
            "named": [],
            "by_grp": {},
            "science": [],
            "vs_summary": {},
        },
    )
    monkeypatch.setattr(
        "grapeancestry.popgen.fstats_report.fstats_for_query",
        lambda *args, **kwargs: {
            "f3": [],
            "f4": [],
            "f3_out": [],
            "query_called_sites": 0,
            "outgroup_n": 0,
            "fstat_pop": "Grp",
        },
    )
    monkeypatch.setattr(
        "grapeancestry.popgen.tree_nj.load_or_compute_panel_ibs_d",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("not needed")),
    )

    bundle = report_module.build_bundle(
        "REPORT",
        root,
        source_sample_id="SOURCE",
    )
    assert bundle.source_sample_id == "SOURCE"
    assert bundle.damage_profile == {"ct5": [0.1], "ga3": [0.2]}
    assert bundle.report_meta["panel_cache"]["path"] == "results/cache/resolved.npz"
    assert bundle.method_coverage["gs"]["available"] is False
    assert "no per-sample GS prediction" in bundle.method_coverage["gs"]["unavailable_reason"]
    assert ("SOURCE", root / "results" / "SOURCE.damage.tsv") in calls
    source_before = source_damage.stat()
    assert bundle.report_meta["source_damage_tsv"] == {
        "path": "results/SOURCE.damage.tsv",
        "available": True,
        "size": source_before.st_size,
        "mtime_ns": source_before.st_mtime_ns,
    }

    calls.clear()
    same_before_bytes = source_damage.read_bytes()
    same_before = source_damage.stat()
    same_bundle = report_module.build_bundle(
        "SOURCE",
        root,
        source_sample_id="SOURCE",
        damage_tsv=source_damage,
    )
    same_after = source_damage.stat()
    assert source_damage.read_bytes() == same_before_bytes
    assert same_after.st_mtime_ns == same_before.st_mtime_ns
    assert same_bundle.report_meta["source_damage_tsv"] == {
        "path": "results/SOURCE.damage.tsv",
        "available": True,
        "size": same_after.st_size,
        "mtime_ns": same_after.st_mtime_ns,
    }
    assert writes == []

    explicit = root / "custom.damage.tsv"
    explicit.write_text("damage")
    report_module.build_bundle(
        "REPORT",
        root,
        source_sample_id="SOURCE",
        damage_tsv=explicit,
    )
    assert ("REPORT", explicit) in calls


def test_precomputed_gwas_tsv_source_is_recorded(tmp_path: Path) -> None:
    gwas = tmp_path / "results" / "gwas"
    gwas.mkdir(parents=True)
    (gwas / "locuszoom.tsv").write_text(
        "trait\tslug\tchrom\tpos\tgene\tnlp\tn_snps\n"
        "T\tT\t1\t10\tG\t4.0\t2\n"
    )

    breeding = report_module._load_precomputed_breeding(tmp_path, "REPORT")

    assert breeding["gwas_loci_source"] == "results/gwas/locuszoom.tsv"
    assert breeding["gwas_loci"][0]["chrom"] == "1"


def _minimal_render_bundle() -> ReportBundle:
    return ReportBundle(
        sample="QUERY",
        qc={},
        ibs_hits=[],
        pca_sample=(0.0, 0.0),
        ref_pca=[],
        admix=None,
        admix_contrast=None,
        damage_freqs=None,
        trait_hits=[],
        fst=None,
        gea_r=None,
        purity_note="",
        conclusions=[],
    )


def test_sample_first_top_level_order_and_collapsed_panel_research(
    tmp_path: Path,
) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = html.split("<body>", 1)[1].split("<script>\n", 1)[0]
    top_level = [
        "sample-validity",
        "identity-placement",
        "population-placement",
        "sample-evidence",
        "panel-research",
        "methods",
        "dl",
    ]
    positions = [visible.index(f'id="{section_id}"') for section_id in top_level]
    assert positions == sorted(positions)
    assert '<details id="panel-research" open>' in visible
    assert "Panel research context" in visible
    assert "2449 panel 研究背景" in visible
    assert 'class="en">Panel research context' in visible
    assert 'class="cn">2449 panel 研究背景' in visible


def test_pca_pc2_window_and_square_canvas_contract(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    assert "PCA_PC2_RANGE=[-0.01,0.01]" in html
    assert "function withPcaPlotSize" in html
    assert "#plot-pca,#plot-pca3d{aspect-ratio:1/1" in html
    assert "PC2 is fixed at" in html
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
D={pca_points:[
  {iid:'a',pcs:[-0.20,-0.08,0.01]},
  {iid:'b',pcs:[0.30,0.09,-0.02]},
  {iid:'q',pcs:[0,0,0],query:true}
]};
var r1=pcaAxisRange(0), r2=pcaAxisRange(1), r3=pcaAxisRange(2);
var cube=pcaCubeRanges();
var el={id:'plot-pca',clientWidth:420};
console.log(JSON.stringify({
  pc2:r2,
  pc1span:r1[1]-r1[0],
  pc3span:r3[1]-r3[0],
  cube2:cube[1],
  equalized:Math.abs((r1[1]-r1[0])-(r2[1]-r2[0]))<1e-9,
  square:pcaSquareSize(el)
}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["pc2"] == pytest.approx([-0.01, 0.01])
    assert observed["cube2"] == pytest.approx([-0.01, 0.01])
    assert observed["pc1span"] > 0.4
    assert observed["equalized"] is False
    assert observed["square"]["width"] == observed["square"]["height"] == 420


def test_section_titles_use_larger_chapter_type(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    assert "section h2{font-size:18px" in html
    assert "#main-content > section > h2" in html
    assert "font-size:22px" in html
    assert "section h3{font-size:15px" in html


def test_sample_first_render_contracts_and_scope_labels(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = html.split("<script>\n", 1)[0]
    assert "Observed in this sample" in visible
    assert "本样品实际观测" in visible
    assert 'class="en">Observed in this sample' in visible
    assert 'class="cn">本样品实际观测' in visible
    assert visible.index('id="query-evidence"') < visible.index('id="gs-pred"')
    for label in (
        "Query-derived",
        "Query vs 2449 panel",
        "2449 panel only",
        "Reference only",
    ):
        assert label in visible
    assert "Query genotype evidence" in APP_JS
    assert "查询样本基因型证据" in APP_JS
    assert "function fillReportMeta" in APP_JS
    assert "function fillMethodCoverage" in APP_JS
    assert "Selection-window genotype" in APP_JS
    assert "Not the panel GWAS index below" in APP_JS
    assert "Panel GWAS-locus genotype" in APP_JS
    assert "function fillQueryEvidence" in APP_JS
    assert "panel_trait_catalog||D.traits" in APP_JS


def test_query_conclusion_sanitizer_drops_panel_only_claims() -> None:
    forbidden = (
        "Selection: 5 named windows on 167K.",
        "Trait-locus overlap: showing 4 of 10 panel hits.",
        "GS index: 8 trait-models; OIV 225=0.62.",
        "Pop context Fst (top-2 Grp / demo-scale WC on ≤800 sites): 0.04.",
    )
    for text in forbidden:
        assert report_module.sanitize_conclusion_text(text) == ""


def test_precomputed_binary_gwas_counts_and_gs_keys_are_lossless(
    tmp_path: Path,
) -> None:
    gwas = tmp_path / "results" / "gwas"
    gwas.mkdir(parents=True)
    (gwas / "index.tsv").write_text(
        "source\ttrait\tscale\tslug\n"
        "euvitis\tOIV 225_bin\tbinary\tOIV_225_bin\n"
    )
    summary = gwas / "euvitis" / "OIV_225_bin" / "summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text(json.dumps({"case_n": 10, "control_n": 90}))
    (tmp_path / "results" / "gs").mkdir(parents=True)
    (tmp_path / "results" / "gs" / "index.tsv").write_text(
        "source\ttrait\tbest_model\tcv_r\n"
        "euvitis\tOIV 225\ttopk_ridge\t0.62\n"
        "descep\tOIV 225\ttopk_ridge\t0.58\n"
    )

    breeding = report_module._load_precomputed_breeding(tmp_path, "QUERY")

    assert breeding["gwas_index"][0]["case_n"] == 10
    assert breeding["gwas_index"][0]["control_n"] == 90
    assert breeding["gs"] == {
        "euvitis::OIV 225": 0.62,
        "descep::OIV 225": 0.58,
    }
    assert "case_n" in APP_JS and "control_n" in APP_JS
    assert "imbalanced binary traits" in APP_JS


def test_differing_source_and_query_ids_render_source_damage_provenance(
    tmp_path: Path,
) -> None:
    bundle = replace(
        _minimal_render_bundle(),
        sample="HUN89_query",
        source_sample_id="HUN89",
        report_meta={
            "report_id": "HUN89_query.sample-first-v2.report.html",
            "query_id": "HUN89_query",
            "source_sample_id": "HUN89",
            "source_damage_tsv": {
                "path": "results/HUN89.damage.tsv",
                "available": True,
            },
            "panel_cache": {
                "path": "results/cache/panel.npz",
                "available": True,
            },
        },
        method_coverage={
            "damage": {
                "available": True,
                "source_sample_id": "HUN89",
                "path": "results/HUN89.damage.tsv",
                "unavailable_reason": "",
            }
        },
    )
    html = render_interactive_dashboard(bundle, tmp_path / "report.html", ROOT).read_text()
    assert '"source_sample_id": "HUN89"' in html
    assert '"query_id": "HUN89_query"' in html
    assert "Source library" in APP_JS
    assert "2449 panel only" in APP_JS
    assert "results/HUN89.damage.tsv" in html


def test_plotly_boot_guards_show_inline_unavailable_messages(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    html_path = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    )
    probe = r"""
var ids=['plot-pca','plot-pca3d','plot-bar','plot-tree','plot-damage','plot-damage-len'];
var els={};
ids.forEach(function(id){els[id]={innerHTML:'',style:{},clientWidth:500,clientHeight:500};});
document={getElementById:function(id){return els[id]||null;}};
D={
  pca_points:[{iid:'Q',pcs:[0,0,0],grp:'QUERY',query:true}],
  pca_n:3,
  admix_meta:{'8':{labels:['A'],colors:['#000']}},
  tree:{data:[],layout:{}},
  damage:{ct5:[0.1],ga3:[]}
};
var caught='';
try{loadPCA();loadPCA3d();loadBar(8);loadTree();loadDamage();}
catch(err){caught=String(err);}
console.log(JSON.stringify({
  caught:caught,
  pca:els['plot-pca'].innerHTML,
  pca3d:els['plot-pca3d'].innerHTML,
  bar:els['plot-bar'].innerHTML,
  tree:els['plot-tree'].innerHTML,
  damage:els['plot-damage'].innerHTML
}));
"""
    result = subprocess.run(
        [
            node,
            "-e",
            "new Function(process.argv[1]+process.argv[2])();",
            APP_JS,
            probe,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["caught"] == ""
    assert all(
        "Plotly.js unavailable" in observed[key]
        for key in ("pca", "pca3d", "bar", "tree", "damage")
    )


def test_task6_rendering_accessibility_and_conclusion_purity_contracts() -> None:
    fill_start = APP_JS.index("function fillConclusions")
    fill_end = APP_JS.index("\nfunction fillQuerySnapshot", fill_start)
    fill_fn = APP_JS[fill_start:fill_end]
    assert "(D.conclusions||[]).map(cleanConclusionPair)" in fill_fn
    assert "authorConclusionBits" not in fill_fn
    assert "addEventListener('toggle'" in APP_JS
    assert "requestAnimationFrame" in APP_JS[APP_JS.index("function refreshPanelResearchPlots"):APP_JS.index("function scrollToId")]
    for fn in ("fillReportMeta", "fillMethodCoverage", "fillQueryEvidence"):
        start = APP_JS.index("function "+fn)
        end = APP_JS.find("\nfunction ", start + 10)
        block = APP_JS[start:end if end >= 0 else None]
        assert "<caption>" in block
        assert "<thead>" in block
        assert 'scope="col"' in block
    assert "Panel context (2449 panel)" in APP_JS
    assert "keydown" in APP_JS and "Enter" in APP_JS and " " in APP_JS
    assert "Model score" in APP_JS
    assert "not probability or observed phenotype" in APP_JS
    assert "function evidenceAnnot" in APP_JS
    assert "function scaleHtml" in APP_JS
    assert "0/1 case–control" in APP_JS
    assert "Trait / gene / links" in APP_JS
    assert "doi.org/10.1126/science.add8655" in APP_JS
    assert "Binary and ordinal scores" in APP_JS
    assert "coverage" in APP_JS and "cv_r" in APP_JS and "flag" in APP_JS


def test_methods_html_section_excludes_reproduce_and_wall_time() -> None:
    html = methods_html_section(
        ROOT / "results" / "provenance",
        ROOT / "docs" / "REFERENCES.bib",
    )
    assert "function annotateMethodsReproduce" not in APP_JS
    assert "annotateMethodsReproduce(" not in APP_JS
    assert "methods-reproduce-note" not in APP_JS
    assert "Not needed to read this HTML" not in APP_JS
    assert re.search(r"<h2[^>]*>Reproduce", html) is None
    assert "Wall time on MBP" not in html
    assert "conda activate ga" not in html
    assert "methods-breeding" in html
    assert "local GS summary" in html
    assert "本地 GS 汇总" in html
    assert "Methods not used and why" not in html
    assert "未采用方法与理由" not in html


def test_sanitize_report_html_preserves_methods_source_spans() -> None:
    observed = _run_report_node(
        r"""
var labeled='<p class="en">from <span class="en">local GS summary</span><span class="cn">本地 GS 汇总</span> and <span class="en">GS training provenance</span><span class="cn">GS 训练溯源</span> and <span class="en">OIV 241 GWAS summary</span><span class="cn">OIV 241 GWAS 汇总</span></p>';
var raw='<code>results/gs/index.tsv</code> <code>results/provenance/gs_train.json</code> <code>results/gwas/euvitis/OIV_241_bin/summary.json</code> <code>results/cross/HUN89_mates.tsv</code>';
console.log(JSON.stringify({
  labeled: sanitizeReportHtml(labeled),
  raw: sanitizeReportHtml(raw)
}));
"""
    )
    assert observed["labeled"] == (
        '<p class="en">from <span class="en">local GS summary</span>'
        '<span class="cn">本地 GS 汇总</span> and '
        '<span class="en">GS training provenance</span>'
        '<span class="cn">GS 训练溯源</span> and '
        '<span class="en">OIV 241 GWAS summary</span>'
        '<span class="cn">OIV 241 GWAS 汇总</span></p>'
    )
    assert "local GS summary" in observed["raw"]
    assert "本地 GS 汇总" in observed["raw"]
    assert "GS training provenance" in observed["raw"]
    assert "GS 训练溯源" in observed["raw"]
    assert "OIV 241 GWAS summary" in observed["raw"]
    assert "OIV 241 GWAS 汇总" in observed["raw"]
    assert '<span class="en">the results tables</span><span class="cn">结果表</span>' in observed["raw"]
    assert "results/gs/index.tsv" not in observed["raw"]
    assert "the results tables" not in observed["labeled"]


def test_sample_evidence_joins_catalog_links_and_explains_scale() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
D={
  query_evidence:[{site:'2:5116947',trait:'OIV 225 colour',gene:'VvMybA1',query_gt:2,evidence:'curated_locus',
    panel_context:{source:'MAS_LOCI',annotation:'Dong 2023 Chr2:5116947'}}],
  panel_trait_catalog:[{site:'2:5116947',trait:'OIV_225',gene:'Vvsyl02G000314',alias:'VvMybA1',
    descriptor:'Berry: color of skin',product:'Transcription factor MYB1',uniprot:'A0A2R6S148',
    go:'GO:0005634',pfam:'PF00249'}],
  gwas_loci:[{slug:'OIV_225_bin',trait:'OIV 225_bin',descriptor:'Berry: color of skin',
    notations:'1=green yellow / 6=blue black',scale:'binary'}],
  gwas_index:[{trait:'OIV 225_bin',slug:'OIV_225_bin',n:382,case_n:173,control_n:209}]
};
var a=evidenceAnnot(D.query_evidence[0]);
var html=evidenceTraitHtml(D.query_evidence[0]);
var ctx=evidenceContextHtml(D.query_evidence[0]);
var note=gsTraitNote({trait:'OIV 225',slug:'OIV_225_bin',scale:'binary'});
console.log(JSON.stringify({
  uniprot:a.uniprot,
  hasUniprot:html.indexOf('uniprot.org/uniprotkb/A0A2R6S148')>=0,
  hasOiv:html.indexOf('eu-vitis.de')>=0,
  hasGo:html.indexOf('QuickGO')>=0,
  hasDong:ctx.indexOf('Dong 2023')>=0,
  binary:scaleHtml('binary').indexOf('0/1')>=0,
  ordinal:scaleHtml('ordinal').indexOf('OIV ordered grades')>=0,
  colourNote:note.indexOf('report policy')>=0 && note.indexOf('0.62')<0
}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed == {
        "uniprot": "A0A2R6S148",
        "hasUniprot": True,
        "hasOiv": True,
        "hasGo": True,
        "hasDong": True,
        "binary": True,
        "ordinal": True,
        "colourNote": True,
    }
    assert "Query genotype evidence" in APP_JS
    assert "查询样本基因型证据" in APP_JS
    assert "Panel annotation / model context" in APP_JS
    assert "面板注释 / 模型背景" in APP_JS


def test_query_evidence_and_gs_copy_is_scope_first_and_bilingual() -> None:
    evidence_start = APP_JS.index("function fillQueryEvidence")
    extra_start = APP_JS.index("\nfunction fillExtra", evidence_start)
    evidence_block = APP_JS[evidence_start:extra_start]
    assert "Query genotype evidence" in evidence_block
    assert "查询样本基因型证据" in evidence_block
    assert "Panel annotation / model context" in evidence_block
    assert "面板注释 / 模型背景" in evidence_block
    assert evidence_block.index("Query genotype evidence") < evidence_block.index(
        "Panel annotation / model context"
    )
    assert "Binary / ordinal scale" in evidence_block
    assert "二元 / 有序尺度" in evidence_block
    assert "Query-derived" in evidence_block

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var evidence={innerHTML:''}, gs={innerHTML:''};
document={getElementById:function(id){
  return id==='query-evidence'?evidence:(id==='gs-pred'?gs:null);
}};
D={
  query:'QUERY',
  query_evidence:[{
    site:'2:5116947', trait:'OIV 225 colour', gene:'VvMybA1', query_gt:2,
    evidence:'curated_locus',
    panel_context:{source:'MAS_LOCI', annotation:'Dong 2023 Chr2:5116947'}
  }],
  panel_trait_catalog:[],
  gwas_loci:[],
  gwas_index:[],
  gs_pred:[{
    trait:'OIV 225', slug:'OIV_225_bin', scale:'binary',
    pred:0.62, coverage:0.8, cv_r:0.62, flag:'ok'
  }],
  method_coverage:{gs:{available:true, unavailable_reason:''}}
};
fillQueryEvidence();
console.log(JSON.stringify({evidence:evidence.innerHTML,gs:gs.innerHTML}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert "Query genotype evidence" in observed["evidence"]
    assert "查询样本基因型证据" in observed["evidence"]
    assert "Query-derived" in observed["evidence"]
    assert "查询样本来源" in observed["evidence"]
    assert "Model score" in observed["gs"]
    assert "模型分数" in observed["gs"]


def test_selection_copy_distinguishes_overlay_and_panel_statistics() -> None:
    sites_start = APP_JS.index("function fillSelQuerySites")
    qc_meta_start = APP_JS.index("\nvar QC_META", sites_start)
    sites_block = APP_JS[sites_start:qc_meta_start]
    for text in (
        "Query sample genotypes",
        "查询样本基因型",
        "Panel map statistic",
        "面板统计量",
        "This run",
        "本次分析",
    ):
        assert text in sites_block

    for fn in (
        "drawSelManhattan",
        "drawSelHeat",
        "drawSelScatter",
        "drawLocusZoom",
        "drawSelLocusZoom",
    ):
        start = APP_JS.index("function " + fn)
        end = APP_JS.find("\nfunction ", start + 10)
        block = APP_JS[start:end if end >= 0 else None]
        assert "t(" in block or "bi(" in block
        assert any(chinese in block for chinese in ("查询", "面板", "图", "位点"))


def test_fill_sel_fstats_translation_helper_is_not_shadowed() -> None:
    observed = _run_report_node(
        r"""
function node(){
  return {
    innerHTML:'', value:'', options:[],
    querySelectorAll:function(){return [];},
    appendChild:function(child){this.options.push(child);},
    scrollIntoView:function(){}
  };
}
var table=node(), group=node();
document={getElementById:function(id){
  if(id==='sel-table') return table;
  if(id==='sel-manh-grp') return group;
  return null;
},createElement:function(){return {value:'',textContent:''};}};
D={
  selection_named:[], selection_by_grp:[], selection_loci:[],
  selection_s29_scatter:{}, selection_vs_summary:[],
  selection_manhattan:{
    fst_by_grp:{CG1:[0.1]}, sweeps:{}, sweep_thr:{}
  },
  selection_heatmap:{}, selection_fst_het_scatter:{},
  f3:[], f4:[], f3_out:[], outgroup_n:0
};
fillSelFstats();
console.log(JSON.stringify({options:group.options.map(function(o){return o.textContent;})}));
"""
    )
    assert observed == {
        "options": [
            "CG1 · simplified Fst (Grp vs rest)",
            "Fst among all Grps",
        ]
    }


def test_static_task5_reader_copy_uses_explicit_language_siblings(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = html.split("<script>\n", 1)[0]
    pairs = (
        (
            "sample-evidence",
            "This section reports query genotypes and per-query predictions.",
            "本节只报告查询样本的实际基因型和逐样本预测。",
        ),
        (
            "panel-research",
            "The following analyses describe the 2449 panel or published reference context.",
            "以下分析描述 2449 panel 或已发表参考背景。",
        ),
        ("sel", "Screening contrast is", "筛选对照是"),
        ("sel", "Default Grp = largest n.", "默认 Grp = n 最大的组。"),
        (
            "sel",
            "Our 167K sweep calls are shown here; literature intervals are checked separately.",
            "这里展示 167K sweep；文献区间另行核对。",
        ),
        (
            "sel",
            "Breeders score those three traits, so each window is checked for a signal in the 2,449-sample reference.",
            "育种记录里常有这三项，所以每个窗口都在 2,449 份参考材料里核对有没有分化信号。",
        ),
        (
            "sel",
            "Columns are the five windows; rows are 2449 panel Grps.",
            "横轴是五个窗口；纵轴是 2449 面板 Grp。",
        ),
        (
            "sel",
            "Grey is the shared deterministic stride-30 subsample; green stars are",
            "灰点是共用确定性 stride-30 子样本；绿星是",
        ),
        (
            "sel",
            "Panel regional context (among-Grps Fst).",
            "面板区域背景（全体 Grp 的 Fst）。",
        ),
        ("sel", "Reference-only S29 overlap check.", "仅作参考的 S29 重合核对。"),
        (
            "traits",
            "Design-time overlap of this 167K panel with GWAS/MAS trait loci.",
            "167K panel 与 GWAS/MAS 性状位点的设计期重叠。",
        ),
        (
            "traits",
            "Panel overlap with design-time GWAS/MAS loci",
            "面板与设计期 GWAS/MAS 位点的重合",
        ),
        ("breeding", "Panel GWAS/GS index.", "panel 的 GWAS/GS 索引。"),
        (
            "breeding",
            "GWAS / GS panel index and regional context.",
            "GWAS / GS 面板索引与区域背景。",
        ),
        (
            "breeding",
            "Official LocusZoom.js: drag to pan, scroll to zoom, click a SNP or gene.",
            "官方 LocusZoom.js：拖动平移、滚轮缩放、点击 SNP 或基因。",
        ),
    )
    for section_id, english, chinese in pairs:
        block = _element_block(visible, section_id)
        assert_nonempty_language_pair(block, english, chinese)
        assert '<div class="en">' in block
        assert '<div class="cn">' in block
    methods = _element_block(visible, "methods")
    assert_nonempty_language_pair(
        methods,
        "What was excluded, and how this report compares with the paper.",
        "这里说明排除了什么，以及和论文如何对照。",
    )
    selection = _element_block(visible, "sel")
    for repeated_exclusion in (
        "not XP-CLR/iHS/G12",
        "not a paper table",
        "not limited to the five named windows",
        "Not a second scan",
        "not the current Grp-vs-rest sweep contrast",
        "not one SNP",
    ):
        assert repeated_exclusion not in selection


def test_gwas_gs_and_cross_tables_have_localized_headers_and_empty_states() -> None:
    for text in (
        "Panel GWAS summary",
        "panel GWAS 汇总",
        "No GWAS index",
        "没有 GWAS 索引",
        "Panel GS model index",
        "面板 GS 模型索引",
        "No GS index",
        "没有 GS 索引",
        "Parent 1",
        "亲本 1",
        "Kinship",
        "亲缘",
        "No recommendation attached to this query report",
        "本查询报告未附杂交组合推荐",
    ):
        assert text in APP_JS

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
    var gwas={innerHTML:'',querySelectorAll:function(){return [];}};
    var gs={innerHTML:'',querySelectorAll:function(){return [];}};
    var cross={innerHTML:'',querySelectorAll:function(){return [];}};
document={getElementById:function(id){
  if(id==='gwas-index') return gwas;
  if(id==='gs-index') return gs;
  if(id==='cross-top') return cross;
  return null;
}};
D={
  query:'QUERY',
  report_meta:{query_id:'QUERY',source_sample_id:'QUERY'},
  gwas_index:[], gwas_loci:[], gs_index:[], cross_top:[], downloads:[]
};
fillExtra();
console.log(JSON.stringify({gwas:gwas.innerHTML,gs:gs.innerHTML,cross:cross.innerHTML}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert "没有 GWAS 索引" in observed["gwas"]
    assert "没有 GS 索引" in observed["gs"]
    assert "本查询报告未附杂交组合推荐" in observed["cross"]


def test_download_copy_is_query_only_and_bilingual() -> None:
    start = APP_JS.index("function allowQueryDownload")
    end = APP_JS.index("\nfunction identityLabel", start)
    block = APP_JS[start:end]
    assert ".filter(allowQueryDownload)" in block
    for text in (
        "Downloads are query-only",
        "下载仅限查询样本",
        "Missing query sidecars do not indicate analysis failure",
        "查询 sidecar 缺失不表示分析失败",
        "No query sidecars yet",
        "暂未生成查询样本 sidecar",
    ):
        assert text in block

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var downloads={innerHTML:''};
document={getElementById:function(id){return id==='downloads'?downloads:null;}};
D={
  query:'QUERY',
  report_meta:{query_id:'QUERY',source_sample_id:'SOURCE'},
  downloads:[
    {href:'QUERY.qc.tsv',label:'QC'},
    {href:'panel.dosage.tsv',label:'panel dosage'},
    {href:'QUERY.missing.tsv',label:'missing'}
  ]
};
QUERY='QUERY';
fillExtra();
console.log(downloads.innerHTML);
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "QUERY.qc.tsv" in result.stdout
    assert "panel.dosage.tsv" not in result.stdout
    assert "QUERY.missing.tsv" not in result.stdout


def test_download_labels_are_bilingual_and_unknown_labels_are_safe() -> None:
    observed = _run_report_node(
        r"""
var labels=[
  'QC TSV','IBS class counts','Clone / PO hits','Kinship top',
  'PCA (this sample)','Damage TSV','ADMIXTURE K=8 Q',
  '<img src=x onerror=1>'
];
console.log(JSON.stringify(labels.map(downloadLabelHtml)));
"""
    )
    assert "质控 TSV" in observed[0]
    assert "IBS 类别计数" in observed[1]
    assert "克隆 / 亲子命中" in observed[2]
    assert "亲缘近邻" in observed[3]
    assert "PCA（本样品）" in observed[4]
    assert "损伤 TSV" in observed[5]
    assert "ADMIXTURE K=8 Q（祖源成分）" in observed[6]
    assert "&lt;img src=x onerror=1&gt;" in observed[7]
    assert "<img src=x onerror=1>" not in observed[7]


def test_s29_doi_is_deduplicated_from_complete_static_and_dynamic_reference(
    tmp_path: Path,
) -> None:
    rendered = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    static_s29 = rendered.split('<details class="ref-only"', 1)[1].split(
        "</details>", 1
    )[0]
    static_en = "".join(
        block[0] for block in _class_element_blocks(static_s29, "en")
    )
    static_cn = "".join(
        block[0] for block in _class_element_blocks(static_s29, "cn")
    )
    doi = "doi.org/10.1126/science.add8655"
    assert static_en.count(doi) == 1
    assert static_cn.count(doi) == 1

    observed = _run_report_node(
        r"""
var sweep={innerHTML:'',querySelectorAll:function(){return [];}};
var s29={innerHTML:'',querySelectorAll:function(){return [];}};
document={getElementById:function(id){
  return id==='sel-sweep-table'?sweep:(id==='sel-s29-ref'?s29:null);
}};
D={
  selection_manhattan:{
    sweep_thr:{CG1:{n:2}},
    sweeps:{CG1:[
      {chrom:'1',pos:100,fst:0.2,het:0.1},
      {chrom:'1',pos:200,fst:0.3,het:0.1}
    ]}
  },
  selection_s29_scatter:{
    chrom:['1','1'],start:[90,190],end:[110,210],
    name:['S29_1_a','S29_1_b'],label:['1:90-110','1:190-210']
  },
  selection_loci:[], selection_vs_summary:[],
  panel_trait_catalog:[]
};
selManhGrp='CG1'; selManhFocus=null;
fillSelSweepTable();
fillSelScienceRef();
console.log(JSON.stringify({sweep:sweep.innerHTML,s29:s29.innerHTML}));
"""
    )
    assert observed["s29"].count(doi) == 0
    combined = static_en + observed["sweep"] + observed["s29"]
    assert combined.count(doi) == 1
    assert observed["sweep"].count("doi.org/10.1126/science.add8655") == 0
    assert "S29 interval overlap" in observed["sweep"]
    assert "Published intervals described above are summarized here." in observed["s29"]
    assert "上文所述的发表区间在此汇总。" in observed["s29"]


def test_selection_scatter_legend_is_localized_and_refreshable() -> None:
    observed = _run_report_node(
        r"""
var plots=[], plot={
  innerHTML:'', clientWidth:500,
  on:function(){}
};
document={getElementById:function(id){return id==='plot-sel-scatter'?plot:null;}};
Plotly={newPlot:function(el,data){plots.push(data);},purge:function(){}};
D={selection_fst_het_scatter:{
  het:[0.1],fst:[0.2],chrom:['1'],pos:[100],
  named_means:[{het:0.3,fst:0.4,label:'window-1',chrom:'1',pos:100,n:2}]
}};
langMode='en'; drawSelScatter();
langMode='zh'; drawSelScatter();
console.log(JSON.stringify({
  en:plots[0][1].name,
  zh:plots[1][1].name
}));
"""
    )
    assert observed == {
        "en": "window mean (= table)",
        "zh": "窗口均值（=表格）",
    }


def test_selection_locuszoom_layout_errors_are_localized_and_escaped() -> None:
    observed = _run_report_node(
        r"""
function box(){return {innerHTML:'',style:{},querySelectorAll:function(){return [];}};}
var plot=box(),meta=box(),detail=box(),gt=box(),gtplot=box();
document={getElementById:function(id){
  return {
    'plot-sel-lz':plot,'sel-lz-meta':meta,'sel-lz-detail':detail,
    'sel-gt-card':gt,'plot-sel-gt':gtplot
  }[id]||null;
}};
D={selection_loci:[{
  kind:'named',slug:'layout-error',chrom:'1',pos:100,
  window_start:90,window_end:110,
  snps:{pos:[100],site:['1:100'],ref:['A'],alt:['G'],
    fst:[0.2],nlp:[1],het:[0.1],het_window:[0.1],gene:['G']}
}]};
LocusZoom={
  Layouts:{get:function(){throw new Error('<svg onload=1>');}},
  DataSources:function(){return {add:function(){return this;}}},
  populate:function(){throw new Error('should not reach populate');}
};
selLzIdx=0; drawSelLocusZoom();
console.log(JSON.stringify(plot.innerHTML));
"""
    )
    assert "LocusZoom.js 加载失败" in observed
    assert "&lt;svg onload=1&gt;" in observed
    assert "<svg onload=1>" not in observed


def test_task5_payload_strings_are_escaped_before_inner_html() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
function box(){return {innerHTML:'',querySelectorAll:function(){return [];}};}
var sites=box(), meta=box(), detail=box(), gt=box(), gtplot=box(), gwas=box();
document={getElementById:function(id){
  return {
    'sel-query-sites':sites,
        'plot-sel-lz':box(),
    'sel-lz-meta':meta,
    'sel-lz-detail':detail,
    'sel-gt-card':gt,
    'plot-sel-gt':gtplot,
    'gwas-index':gwas
  }[id]||null;
}};
D={
  query:'QUERY',
  selection_loci:[{
    kind:'<img src=x onerror=1>',
    trait:'<svg onload=1>',
    slug:'<b>bad</b>',
    chrom:'1', pos:100, window_start:90, window_end:110, n_snps:1,
    snps:{pos:[100],site:['1:100'],ref:['A'],alt:['G'],fst:[0.2],nlp:[1],gene:['G']}
  }],
  selection_manhattan:{},
  gwas_index:[{
    source:'<img src=x onerror=1>', trait:'<svg onload=1>',
    scale:'binary', n:'<script>1</script>', n_bonf:'<b>2</b>'
  }],
  gwas_loci:[], gs_index:[], cross_top:[], downloads:[],
  panel_trait_catalog:[]
};
selLzIdx=0; selLzMetric='fst';
fillSelQuerySites();
drawSelLocusZoom();
fillExtra();
console.log(JSON.stringify({sites:sites.innerHTML,meta:meta.innerHTML,gwas:gwas.innerHTML}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    raw = "<img src=x onerror=1>"
    assert raw not in observed["sites"]
    assert raw not in observed["meta"]
    assert raw not in observed["gwas"]
    assert "&lt;img" in observed["meta"]
    assert "&lt;script&gt;" in observed["gwas"]


def test_selection_query_sites_preserve_safe_lz_why_markup() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var sites={innerHTML:'',querySelectorAll:function(){return [];}};
document={getElementById:function(id){return id==='sel-query-sites'?sites:null;}};
D={
  query:'QUERY',
  selection_loci:[{
    kind:'named', slug:'window-1', chrom:'1', pos:100,
    window_start:90, window_end:110,
    snps:{pos:[100],site:['1:100'],ref:['A'],alt:['G'],fst:[0.2],gene:['G']}
  }]
};
fillSelQuerySites();
console.log(sites.innerHTML);
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert '<span class="en">lead</span>' in result.stdout
    assert "&lt;span class=&quot;en&quot;&gt;" not in result.stdout


def test_sweep_action_labels_follow_active_language_and_refresh() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    refresh_start = APP_JS.index("function refreshLangContent")
    refresh_end = APP_JS.index("\nfunction ", refresh_start + 10)
    refresh_block = APP_JS[refresh_start:refresh_end]
    for call in ("fillExtra();", "fillSelFstats();"):
        assert call in refresh_block
    for redundant in (
        "fillSelQuerySites();",
        "fillFstatsCallout(D.f3_out||[], D.f3||[], D.f4||[]);",
        "drawLocusZoom();",
        "drawSelLocusZoom();",
        "drawSelManhattan();",
        "drawSelHeat();",
        "drawSelScatter();",
    ):
        assert redundant not in refresh_block

    probe = r"""
var table={innerHTML:'',querySelectorAll:function(){return [];}};
document={getElementById:function(id){return id==='sel-sweep-table'?table:null;}};
D={selection_manhattan:{
  sweep_thr:{CG1:{n:1}}, sweeps:{CG1:[{chrom:'1',pos:100,fst:0.2,het:0.1}]}
}};
selManhGrp='CG1'; selManhFocus=null;
langMode='en'; fillSelSweepTable(); var en=table.innerHTML;
langMode='zh'; fillSelSweepTable(); var zh=table.innerHTML;
console.log(JSON.stringify({en:en,zh:zh}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert 'aria-label="Pin 1:100 as a white star on the Manhattan plot"' in observed["en"]
    assert 'title="Pin 1:100 as a white star on the Manhattan plot"' in observed["en"]
    assert "将 1:100 钉在 Manhattan 图上显示为白星" in observed["zh"]
    assert 'title="将 1:100 钉在 Manhattan 图上显示为白星"' in observed["zh"]


def test_refresh_language_content_redraws_task5_views_once() -> None:
    observed = _run_report_node(
        r"""
function box(){
  return {
    innerHTML:'', value:'', options:[], textContent:'',
    querySelectorAll:function(){return [];},
    querySelector:function(){return null;},
    appendChild:function(child){this.options.push(child); return child;},
    addEventListener:function(){},
    setAttribute:function(){},
    getAttribute:function(){return null;}
  };
}
var els={};
var counts={extra:0,lz:0,manh:0,heat:0,scatter:0};
document={
  getElementById:function(id){ return els[id]||(els[id]=box()); },
  querySelectorAll:function(){return [];},
  createElement:function(){return {value:'',textContent:''};}
};
window={};
D={
  selection_named:[{name:'SDR_trait_locus',chrom:'2',start:1,end:2,n_sites:3,mean_het:'0.10',mean_fst:'0.02'}],
  selection_by_grp:[{grp:'CG1',n_samples:10,name:'SDR_trait_locus',n_sites:3,mean_het:'0.11',mean_fst_vs_rest:'0.04'}],
  selection_loci:[], selection_s29_scatter:{}, selection_vs_summary:[],
  selection_manhattan:{
    x:[1], chrom:['2'], pos:[100], fst:[0.2], het:[0.3],
    fst_by_grp:{CG1:[0.4]}, het_by_grp:{CG1:[0.5]},
    sweep_by_grp:{CG1:[0]}, sweep_thr:{CG1:{n:1,fst95:0.30,het05:0.12}},
    sweeps:{CG1:[{chrom:'2',pos:100,fst:0.4,het:0.12}]}
  },
  selection_heatmap:{grp:['CG1'],window:['SDR'],fst:[[0.04]],het:[[0.11]]},
  selection_fst_het_scatter:{},
  f3:[], f4:[], f3_out:[], outgroup_n:0
};
selManhGrp='CG1'; selManhMetric='fst'; selHeatMetric='fst';
var realLZ=drawSelLocusZoom, realManh=drawSelManhattan;
var realHeat=drawSelHeat, realScatter=drawSelScatter;
drawSelLocusZoom=function(){ counts.lz+=1; return realLZ.apply(this,arguments); };
drawSelManhattan=function(){ counts.manh+=1; return realManh.apply(this,arguments); };
drawSelHeat=function(){ counts.heat+=1; return realHeat.apply(this,arguments); };
drawSelScatter=function(){ counts.scatter+=1; return realScatter.apply(this,arguments); };
fillHeroStats=function(){}; fillAuthorIntake=function(){};
fillQuerySnapshot=function(){}; fillReportMeta=function(){};
fillMethodCoverage=function(){}; fillQueryEvidence=function(){};
fillQc=function(){}; fillConclusions=function(){};
fillCloneTable=function(){}; fillIbsKinship=function(){};
fillExtra=function(){counts.extra+=1;};
enhanceReportTables=function(){}; pairLangBlocks=function(){};
loadPCA=function(){}; loadPCA3d=function(){}; loadBar=function(){};
loadTree=function(){}; loadDamage=function(){};
langMode='zh';
refreshLangContent();
var grp=els['sel-manh-grp'];
console.log(JSON.stringify({
  extra:counts.extra, lz:counts.lz, manh:counts.manh, heat:counts.heat, scatter:counts.scatter,
  table:els['sel-table'].innerHTML,
  sweep:els['sel-sweep-table'].innerHTML,
  options:(grp.options||[]).map(function(o){return o.textContent;})
}));
"""
    )
    assert observed["extra"] == 1
    assert observed["lz"] == 1
    assert observed["manh"] == 1
    assert observed["heat"] == 1
    assert observed["scatter"] == 1
    assert "简化 Fst（Grp 对其余样品）" in observed["table"]
    assert "全体 Grp 的 Fst" in observed["table"]
    assert "在图上标出" in observed["sweep"]
    assert "sel-sweep-status" in observed["sweep"]
    assert any("简化 Fst" in opt for opt in observed["options"])


def test_fstat_table_escapes_malicious_nonnumeric_values() -> None:
    observed = _run_report_node(
        r"""
var row={a:'<img src=x onerror=1>',b:'B',
  value:'<svg onload=1>',se:'<script>1</script>',
  z:'<b>2</b>',n_sites:'<iframe>',n_blocks:'<math>'};
var html=fstatColTable(
  'f3', ['A','B','f3','SE','Z','n_sites','n_blocks'],
  [row], function(r){return [r.a,r.b,r.value,r.se,r.z,r.n_sites,r.n_blocks];}
);
console.log(JSON.stringify(html));
"""
    )
    assert "<img src=x onerror=1>" not in observed
    assert "<svg onload=1>" not in observed
    assert "<script>1</script>" not in observed
    assert "&lt;img" in observed
    assert "&lt;svg" in observed
    assert "&lt;script&gt;" in observed


def test_query_gt_card_successful_content_is_localized_in_chinese() -> None:
    observed = _run_report_node(
        r"""
var card={innerHTML:'',querySelectorAll:function(){return [];}};
document={getElementById:function(id){return id==='lz-gt-card'?card:null;}};
D={query:'QUERY'};
langMode='zh';
fillQueryGtCard('lz-gt-card', {
  query_gt_sample:'QUERY', chrom:'1', pos:100, lead_i:0,
  snps:{
    pos:[100,200], site:['1:100','1:200'], ref:['A','C'], alt:['G','T'],
    gene:['VvGene','VvOther'], mas:['',''], design:[0,0],
    gt:[1,-1]
  }
}, null);
console.log(JSON.stringify(card.innerHTML));
"""
    )
    assert "QUERY" in observed
    assert "1:100" in observed
    assert "VvGene" in observed
    assert "LocusZoom 是 2449 面板地图" in observed
    assert "本窗口芯片位点 2" in observed
    assert "重点位点（主位点 / MAS / 设计位点）" in observed
    assert "0/1 杂合" in observed
    assert "./. 缺失" in observed
    assert "LocusZoom is the 2449 map" not in observed
    assert "Chip sites in window" not in observed
    assert "Key sites (lead / MAS / design)" not in observed
    assert "0/1 het" not in observed
    assert "./. missing" not in observed


def test_selection_detail_labels_are_bilingual_in_chinese_success_state() -> None:
    observed = _run_report_node(
        r"""
var detail={innerHTML:''};
document={getElementById:function(id){return id==='sel-lz-detail'?detail:null;}};
D={query:'QUERY'};
langMode='zh';
var attached={
  chrom:'1',pos:100,query_gt_sample:'QUERY',
  snps:{pos:[100],site:['1:100'],ref:['A'],alt:['G'],
    fst:[0.2],het:[0.1],het_window:[0.2],gene:['VvGene'],
    region:['promoter'], gt:[1], r2:[0.85]}
};
fillSelLzSnp(attached,0);
var withGt=detail.innerHTML;
fillSelLzSnp({
  chrom:'1',pos:100,query_gt_sample:'QUERY',
  snps:{pos:[100],site:['1:100'],ref:['A'],alt:['G'],
    fst:[0.2],het:[0.1],het_window:[0.2],gene:['VvGene'],
    region:['promoter']}
},0);
console.log(JSON.stringify({withGt:withGt, missing:detail.innerHTML}));
"""
    )
    attached = observed["withGt"]
    missing = observed["missing"]
    assert "主位点" in attached
    assert "0/1 杂合" in attached
    assert "与主位点的 r²" in attached
    assert "0.850" in attached
    assert "VvGene" in attached
    assert "promoter" in attached
    assert "QUERY" in attached
    assert "1:100" in attached
    assert "基因" in attached
    assert "区域" in attached
    assert "0/1 het" not in attached
    assert "r² to lead" not in attached
    assert "not attached" not in attached
    assert "./. missing" not in attached
    assert "未附带" in missing
    assert "./. 缺失" in missing
    assert "基因" in missing
    assert "区域" in missing
    assert "主位点" in missing
    assert "not attached" not in missing


def test_fstats_success_tables_localize_titles_and_headers_in_chinese() -> None:
    observed = _run_report_node(
        r"""
var tables={innerHTML:''};
document={getElementById:function(id){
  return id==='fstats-tables'?tables:null;
},querySelectorAll:function(){return [];}};
D={
  selection_named:[], selection_by_grp:[], selection_loci:[],
  selection_s29_scatter:{}, selection_vs_summary:[],
  selection_manhattan:{}, selection_heatmap:{},
  selection_fst_het_scatter:{},
  f3_out:[{grp:'CG1',value:0.1,se:0.01,z:3,n_sites:12,n_blocks:4}],
  f3:[{a:'A',b:'B',value:0.2,se:0.02,z:2,n_sites:13,n_blocks:5}],
  f4:[{a:'A',b:'B',value:-0.1,se:0.03,z:-2,n_sites:14,n_blocks:6}],
  outgroup_n:1
};
langMode='zh';
fillSelFstats();
console.log(JSON.stringify(tables.innerHTML));
"""
    )
    assert "外群 f3" in observed
    assert "成对 f3" in observed
    assert "成对 f4" in observed
    assert "组别" in observed
    assert "SE（标准误）" in observed
    assert "n_sites（有效位点）" in observed
    assert "n_blocks（染色体块）" in observed
    assert "<h3>Outgroup-f3" not in observed
    assert "<h3>Pairwise f3" not in observed
    assert "<th>Grp</th>" not in observed
    assert "<th>SE</th>" not in observed
    assert "<th>n_sites</th>" not in observed


def test_query_evidence_dong_citation_is_one_near_table_and_rows_plain() -> None:
    observed = _run_report_node(
        r"""
var evidence={innerHTML:''}, gs={innerHTML:''};
document={getElementById:function(id){
  return id==='query-evidence'?evidence:(id==='gs-pred'?gs:null);
}};
D={
  query:'QUERY',
  query_evidence:[
    {site:'1:10',query_gt:1,evidence:'curated_locus',
      panel_context:{source:'MAS_LOCI',annotation:'Dong 2023 Table S29 interval A'}},
    {site:'1:20',query_gt:0,evidence:'curated_locus',
      panel_context:{source:'MAS_LOCI',annotation:'Dong 2023 Table S29 interval B'}}
  ],
  method_coverage:{}, panel_trait_catalog:[], gwas_loci:[],
  gwas_index:[], gs_pred:[]
};
fillQueryEvidence();
console.log(JSON.stringify({html:evidence.innerHTML,context:evidenceContextHtml(
  D.query_evidence[0])}));
"""
    )
    assert observed["html"].count("doi.org/10.1126/science.add8655") == 1
    assert "Dong et al. 2023" in observed["html"]
    assert "Dong 2023 Table S29 interval A" in observed["html"]
    assert "doi.org/10.1126/science.add8655" not in observed["context"]
    assert "<a " not in observed["context"]


def test_main_gwas_locuszoom_failure_does_not_abort_following_blocks() -> None:
    observed = _run_report_node(
        r"""
function box(){return {innerHTML:'',querySelectorAll:function(){return [];}};}
var plot=box(),gwas=box(),gs=box(),cross=box(),downloads=box();
document={getElementById:function(id){
  return {
    'plot-lz':plot,'gwas-index':gwas,'gs-index':gs,
    'cross-top':cross,'downloads':downloads
  }[id]||null;
}};
D={
  query:'QUERY',
  report_meta:{query_id:'QUERY',source_sample_id:'QUERY'},
  gwas_index:[{source:'euvitis',trait:'OIV 225',slug:'OIV_225_bin',
    scale:'binary',n:10,n_bonf:1}],
  gwas_loci:[{trait:'OIV 225',slug:'OIV_225_bin',chrom:'1',pos:100,
    window_start:90,window_end:110,n_snps:1,
    snps:{pos:[100],site:['1:100'],nlp:[2],ref:['A'],alt:['G'],
      beta:[0.1],se:[0.01],maf:[0.2],p:[0.01],q:[0.02],r2:[1],
      gene:['G'],region:['promoter'],bonf:[1]}}],
  gs_index:[{source:'euvitis',trait:'OIV 225',best_model:'ridge',cv_r:0.6,n:10}],
  cross_top:[{p1:'A',p2:'B',index:'0.5',kinship:'0.1'}],
  downloads:[{href:'QUERY.qc.tsv',label:'QC TSV'}],
  panel_trait_catalog:[],traits:[],gs_pred:[],cross_top_extra:[]
};
LocusZoom={Layouts:{get:function(){throw new Error('<img src=x onerror=1>');}},
  DataSources:function(){return {add:function(){return this;}}},
  populate:function(){throw new Error('populate should not run');}};
QUERY='QUERY';
fillExtra();
console.log(JSON.stringify({
  plot:plot.innerHTML,gwas:gwas.innerHTML,gs:gs.innerHTML,
  cross:cross.innerHTML,downloads:downloads.innerHTML
}));
"""
    )
    assert "LocusZoom.js 加载失败" in observed["plot"]
    assert "&lt;img" in observed["plot"]
    assert "Panel GS model index" in observed["gs"]
    assert "A" in observed["cross"] and "B" in observed["cross"]
    assert "QUERY.qc.tsv" in observed["downloads"]


def test_selection_sweep_threshold_is_stated_once_in_section(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "task5-rule.html", ROOT
    ).read_text()
    selection = _element_block(html.split("<script>\n", 1)[0], "sel")
    active_selection = selection.split('<details class="ref-only"', 1)[0]
    assert active_selection.count("top 5%") == 1
    assert active_selection.count("bottom 5%") == 1
    assert "Sweep = Fst ≥95th" not in active_selection


def test_selection_locuszoom_errors_are_localized_and_escape_details() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
function box(){return {innerHTML:'',style:{},querySelectorAll:function(){return [];} }; }
var plot=box(), meta=box(), detail=box(), gt=box(), gtplot=box();
document={getElementById:function(id){
  return {
    'plot-sel-lz':plot, 'sel-lz-meta':meta, 'sel-lz-detail':detail,
    'sel-gt-card':gt, 'plot-sel-gt':gtplot
  }[id]||null;
}};
D={selection_loci:[{kind:'named',slug:'no-data',chrom:'1',pos:100,snps:{pos:[]}}]};
selLzIdx=0; drawSelLocusZoom(); var empty=plot.innerHTML;
D.selection_loci=[{
  kind:'named',slug:'bad',chrom:'1',pos:100,window_start:90,window_end:110,
  snps:{pos:[100],site:['1:100'],ref:['A'],alt:['G'],fst:[0.2],nlp:[1],het:[0.1],
    het_window:[0.1],gene:['G']}
}];
LocusZoom={
  Layouts:{get:function(){return {panels:[],toolbar:{widgets:[]}};}},
  DataSources:function(){return {add:function(){return this;}}},
  populate:function(){throw new Error('<img src=x onerror=1>');}
};
drawSelLocusZoom();
console.log(JSON.stringify({empty:empty,error:plot.innerHTML}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert "该位点没有选择扫描 LocusZoom 数据" in observed["empty"]
    assert "<img src=x onerror=1>" not in observed["error"]
    assert "&lt;img" in observed["error"]
    assert "LocusZoom.js 加载失败" in observed["error"]


def test_source_scope_switches_between_source_library_and_query() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var meta={innerHTML:''}, coverage={innerHTML:''};
document={getElementById:function(id){
  return id==='report-meta'?meta:(id==='method-coverage'?coverage:null);
}};
D={
  query:'HUN89_query',
  report_meta:{
    query_id:'HUN89_query',
    source_sample_id:'HUN89',
    source_damage_tsv:{path:'results/HUN89.damage.tsv',available:true},
    panel_cache:{path:'results/cache/panel.npz',available:true}
  },
  method_coverage:{
    damage:{available:true,source_sample_id:'HUN89',path:'results/HUN89.damage.tsv',path_available:true},
    panel_genotype:{called:1,total:2,coverage:0.5},
    selection_locus_gt:{query_gt_called:0,query_gt_n:0,unavailable_reason:'no selection locus genotype coverage'},
    gwas_locus_gt:{query_gt_called:0,query_gt_n:0,unavailable_reason:'no GWAS locus genotype coverage'},
    fstats:{query_called_sites:0,unavailable_reason:'no fstats query sites'},
    gs_predictions:[],
    gs:{available:false,unavailable_reason:'no per-sample GS prediction available'}
  }
};
fillReportMeta(); fillMethodCoverage();
var differing={meta:meta.innerHTML, coverage:coverage.innerHTML};
D.query='HUN89';
D.report_meta.query_id='HUN89';
D.report_meta.source_sample_id='HUN89';
D.method_coverage.damage={available:true,source_sample_id:'HUN89',path:'results/HUN89.damage.tsv',path_available:true};
meta.innerHTML=''; coverage.innerHTML='';
fillReportMeta(); fillMethodCoverage();
console.log(JSON.stringify({differing:differing,equal:{meta:meta.innerHTML,coverage:coverage.innerHTML}}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert "Source library" in observed["differing"]["meta"]
    assert (
        'class="en">Damage profile</span><span class="cn">损伤谱</span></td><td>'
        '<span class="en">Source library</span><span class="cn">来源文库</span>'
        in observed["differing"]["coverage"]
    )
    assert (
        'class="en">Damage profile</span><span class="cn">损伤谱</span></td><td>'
        '<span class="en">Query-derived</span><span class="cn">查询样本来源</span>'
        in observed["equal"]["coverage"]
    )


def test_generic_table_enhancer_is_idempotent_and_keyboard_accessible(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var clicked=0, listeners=0, attrs={};
var th={getAttribute:function(){return null;},setAttribute:function(k,v){attrs[k]=v;}};
var row={
  getAttribute:function(k){return attrs[k]||null;},
  setAttribute:function(k,v){attrs[k]=v;},
  querySelectorAll:function(sel){return sel==='th'?[th]:[];},
  addEventListener:function(k,fn){listeners++; this.handler=fn;},
  click:function(){clicked++;}
};
var caption=null, tbody={tagName:'TBODY',appendChild:function(){}};
var table={
  getAttribute:function(k){return attrs[k]||null;},
  setAttribute:function(k,v){attrs[k]=v;},
  querySelector:function(sel){return sel==='caption'?caption:null;},
  querySelectorAll:function(sel){return sel==='tr'?[row]:[];},
  createCaption:function(){caption={className:'',textContent:''};return caption;},
  createTHead:function(){return {appendChild:function(){}};},
  tHead:null
};
var root={querySelectorAll:function(sel){return sel==='table'?[table]:(sel==='.clickrow'?[row]:[]);}};
enhanceReportTables(root); enhanceReportTables(root);
row.handler({key:'Enter',preventDefault:function(){}});
row.handler({key:' ',preventDefault:function(){}});
console.log(JSON.stringify({clicked:clicked,listeners:listeners,caption:!!caption,scope:attrs.scope||null}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "clicked": 2,
        "listeners": 1,
        "caption": True,
        "scope": "col",
    }
    assert ".sr-only" in render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    assert "enhanceReportTables(document)" in APP_JS


def test_report_meta_and_gs_tables_are_wrapped_once_without_replacing_tables() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
function makeNode(tag, id, html){
  var node={
    tagName:String(tag).toUpperCase(), id:id||'', innerHTML:html||'',
    className:'', children:[], parentElement:null, parentNode:null,
    attrs:{}, listeners:{}, caption:null,
    getAttribute:function(k){return this.attrs[k]||null;},
    setAttribute:function(k,v){this.attrs[k]=String(v);},
    querySelector:function(sel){return sel==='caption'?this.caption:null;},
    querySelectorAll:function(){return [];},
    createCaption:function(){
      this.caption=makeNode('caption');
      return this.caption;
    },
    appendChild:function(child){
      if(child.parentElement) child.parentElement.removeChild(child);
      this.children.push(child);
      child.parentElement=this;
      child.parentNode=this;
      return child;
    },
    insertBefore:function(child, ref){
      if(child.parentElement) child.parentElement.removeChild(child);
      var index=this.children.indexOf(ref);
      if(index<0) index=this.children.length;
      this.children.splice(index,0,child);
      child.parentElement=this;
      child.parentNode=this;
      return child;
    },
    removeChild:function(child){
      var index=this.children.indexOf(child);
      if(index>=0) this.children.splice(index,1);
      child.parentElement=null;
      child.parentNode=null;
      return child;
    },
    addEventListener:function(kind,fn){
      (this.listeners[kind]||(this.listeners[kind]=[])).push(fn);
    }
  };
  return node;
}
function tablesUnder(node){
  var found=[];
  (node.children||[]).forEach(function(child){
    if(child.tagName==='TABLE') found.push(child);
    found=found.concat(tablesUnder(child));
  });
  return found;
}
var reportMeta=makeNode('div','report-meta');
var gsPred=makeNode('div','gs-pred');
var reportTable=makeNode('table','report-table','<tr>report</tr>');
var gsTable=makeNode('table','gs-table','<tr>gs</tr>');
var listenerCalls=0;
reportTable.addEventListener('custom',function(){listenerCalls++;});
reportMeta.appendChild(reportTable);
gsPred.appendChild(gsTable);
var root=makeNode('main');
root.appendChild(reportMeta);
root.appendChild(gsPred);
root.querySelectorAll=function(sel){
  if(sel==='table') return tablesUnder(this);
  if(sel==='.clickrow') return [];
  return [];
};
document={createElement:function(tag){return makeNode(tag);}};
enhanceReportTables(root);
enhanceReportTables(root);
reportTable.listeners.custom[0]();
var reportWrapper=reportMeta.children[0];
var gsWrapper=gsPred.children[0];
console.log(JSON.stringify({
  reportClass:reportWrapper.className,
  gsClass:gsWrapper.className,
  reportChildren:reportMeta.children.length,
  gsChildren:gsPred.children.length,
  tableCount:tablesUnder(root).length,
  reportIdentity:reportWrapper.children[0]===reportTable,
  gsIdentity:gsWrapper.children[0]===gsTable,
  reportId:reportWrapper.children[0].id,
  gsId:gsWrapper.children[0].id,
  reportContent:reportWrapper.children[0].innerHTML,
  gsContent:gsWrapper.children[0].innerHTML,
  listenerCalls:listenerCalls,
  reportNested:reportWrapper.children[0].parentElement===reportWrapper,
  gsNested:gsWrapper.children[0].parentElement===gsWrapper
}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "reportClass": "table-scroll",
        "gsClass": "table-scroll",
        "reportChildren": 1,
        "gsChildren": 1,
        "tableCount": 2,
        "reportIdentity": True,
        "gsIdentity": True,
        "reportId": "report-table",
        "gsId": "gs-table",
        "reportContent": "<tr>report</tr>",
        "gsContent": "<tr>gs</tr>",
        "listenerCalls": 1,
        "reportNested": True,
        "gsNested": True,
    }


def test_author_context_rerender_reenhances_tables_without_duplicates() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var clicked=0, listeners=0, captionCount=0, attrs={};
var th={getAttribute:function(){return null;},setAttribute:function(k,v){attrs[k]=v;}};
var row={
  setAttribute:function(k,v){attrs[k]=v;},
  querySelectorAll:function(sel){return sel==='th'?[th]:[];},
  addEventListener:function(k,fn){listeners++; this.handler=fn;},
  click:function(){clicked++;}
};
var caption=null;
var table={
  querySelector:function(sel){return sel==='caption'?caption:null;},
  querySelectorAll:function(sel){return sel==='tr'?[row]:[];},
  createCaption:function(){captionCount++; caption={className:'',textContent:''}; return caption;},
  createTHead:function(){return {appendChild:function(){}};},
  setAttribute:function(){}
};
document={querySelectorAll:function(sel){return sel==='table'?[table]:(sel==='.clickrow'?[row]:[]);},
  getElementById:function(){return null;}};
window={};
loadAuthorState=function(){return {mode:'sample',sample:{},rows:[]};};
computeAuthorInference=function(){return {ids:[]};};
fillQueryMeta=function(){};
fillConclusions=function(){};
fillIbsKinship=function(){};
applyAuthorContext();
applyAuthorContext();
row.handler({key:'Enter',preventDefault:function(){}});
console.log(JSON.stringify({clicked:clicked,listeners:listeners,captions:captionCount}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "clicked": 1,
        "listeners": 1,
        "captions": 1,
    }


def _theme_css_blocks(html: str) -> tuple[str, str]:
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    light = re.search(r":root\{([^}]*)\}", style)
    dark = re.search(r':root\[data-theme="dark"\]\{([^}]*)\}', style)
    assert light and dark
    return light.group(1), dark.group(1)


def _css_hex(block: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}})", block)
    assert match, f"missing CSS token {name}"
    return match.group(1)


def _contrast_ratio(foreground: str, background: str) -> float:
    def channel(value: str) -> float:
        value = int(value, 16) / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    def luminance(color: str) -> float:
        return (
            0.2126 * channel(color[1:3])
            + 0.7152 * channel(color[3:5])
            + 0.0722 * channel(color[5:7])
        )

    lighter = max(luminance(foreground), luminance(background))
    darker = min(luminance(foreground), luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def test_theme_contracts_exist_in_rendered_report_and_app_js(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = html.split("<body>", 1)[1].split("<script>\n", 1)[0]

    light, dark = _theme_css_blocks(html)
    for name, value in {
        "--bg": "#f7f9fc",
        "--surface": "#ffffff",
        "--surface-2": "#eef2f7",
        "--text": "#172033",
        "--muted": "#526079",
        "--border": "#cbd5e1",
        "--plot-bg": "#ffffff",
        "--plot-grid": "#dbe3ed",
    }.items():
        assert f"{name}:{value}" in light
    for name, value in {
        "--bg": "#0b0f19",
        "--surface": "#131b2e",
        "--surface-2": "#0f172a",
        "--text": "#e2e8f0",
        "--muted": "#a8b3c7",
        "--border": "#2b3b59",
        "--plot-bg": "#131b2e",
        "--plot-grid": "#263654",
    }.items():
        assert f"{name}:{value}" in dark
    assert '@media (prefers-color-scheme: dark)' in html
    assert html.index("<script data-ga-theme-bootstrap>") < html.index(
        '<script src="../assets/plotly-2.32.0.min.js">'
    )

    for function_name in (
        "resolveTheme",
        "setTheme",
        "applyPlotTheme",
        "refreshThemedPlots",
    ):
        assert f"function {function_name}" in APP_JS
    assert "localStorage.getItem('ga-theme')" in APP_JS
    assert "localStorage.setItem('ga-theme'" in APP_JS
    assert "query-marker" in APP_JS
    assert 'aria-label="Report color theme"' in visible
    for mode in ("system", "light", "dark"):
        assert f'data-theme-choice="{mode}"' in visible
    assert visible.count('class="theme-choice"') == 3
    assert visible.count("aria-pressed=") >= 3
    assert 'html:not([data-lang="zh"]) .cn{display:none!important}' in html
    assert 'html[data-lang="zh"] .en{display:none!important}' in html
    assert 'aria-label="Report language"' in visible
    assert 'data-lang-choice="en"' in visible
    assert 'data-lang-choice="zh"' in visible
    assert visible.count('class="lang-choice"') == 2
    assert "localStorage.getItem('ga-lang')" in html
    assert "function initLangController" in APP_JS
    assert "function pairLangBlocks" in APP_JS
    assert "function setLang" in APP_JS


def test_theme_controller_handles_os_overrides_persistence_and_storage_denial() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var refreshes=0;
refreshThemedPlots=function(){refreshes++;};
function rootNode(){
  return {
    attrs:{},
    setAttribute:function(k,v){this.attrs[k]=String(v);},
    getAttribute:function(k){return this.attrs[k]||null;}
  };
}
var root=rootNode();
var buttons=['system','light','dark'].map(function(mode){
  return {mode:mode, attrs:{},
    getAttribute:function(k){return k==='data-theme-choice'?this.mode:this.attrs[k]||null;},
    setAttribute:function(k,v){this.attrs[k]=String(v);}};
});
document={
  documentElement:root,
  querySelectorAll:function(sel){return sel==='.theme-choice'?buttons:[];}
};
var osDark=true, mediaHandler=null;
window={
  matchMedia:function(){
    return {
      matches:osDark,
      addEventListener:function(kind,fn){if(kind==='change') mediaHandler=fn;},
      addListener:function(fn){mediaHandler=fn;}
    };
  },
  getComputedStyle:function(){return {getPropertyValue:function(){return '';}};}
};
var store={saved:null,
  getItem:function(key){return key==='ga-theme'?this.saved:null;},
  setItem:function(key,value){if(key==='ga-theme') this.saved=String(value);}
};
globalThis.localStorage=store;
initThemeController();
var observed={
  systemInitial:root.getAttribute('data-theme'),
  explicitLight:setTheme('light',true),
  explicitLightAttr:root.getAttribute('data-theme'),
  explicitDark:setTheme('dark',true),
  explicitDarkAttr:root.getAttribute('data-theme'),
  saved:store.saved
};
setTheme('system',false);
osDark=false;
mediaHandler({matches:false});
observed.systemLight=root.getAttribute('data-theme');
osDark=true;
mediaHandler({matches:true});
observed.systemDark=root.getAttribute('data-theme');
var deniedRoot=rootNode();
document.documentElement=deniedRoot;
globalThis.localStorage={
  getItem:function(){throw new Error('denied');},
  setItem:function(){throw new Error('denied');}
};
var caught='';
try{
  observed.deniedRead=readStoredTheme();
  setTheme('dark',true);
  observed.deniedTheme=deniedRoot.getAttribute('data-theme');
}catch(err){caught=String(err);}
observed.caught=caught;
observed.pressed=buttons.map(function(b){return b.attrs['aria-pressed']||null;});
var original={
  paper_bgcolor:'#original', plot_bgcolor:'#original',
  font:{color:'#original',size:9},
  xaxis:{gridcolor:'#original',zerolinecolor:'#original'},
  scene:{bgcolor:'#original',xaxis:{gridcolor:'#original'}}
};
var before=JSON.stringify(original);
var themed=applyPlotTheme(original);
observed.layout={
  unchanged:JSON.stringify(original)===before,
  paper:themed.paper_bgcolor,
  font:themed.font.color,
  grid:themed.xaxis.gridcolor,
  scene:themed.scene.bgcolor
};
observed.refreshes=refreshes;
console.log(JSON.stringify(observed));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed == {
        "systemInitial": "dark",
        "explicitLight": "light",
        "explicitLightAttr": "light",
        "explicitDark": "dark",
        "explicitDarkAttr": "dark",
        "saved": "dark",
        "systemLight": "light",
        "systemDark": "dark",
        "deniedRead": "system",
        "deniedTheme": "dark",
        "caught": "",
        "pressed": ["false", "false", "true"],
        "layout": {
            "unchanged": True,
            "paper": "#131b2e",
            "font": "#e2e8f0",
            "grid": "#263654",
            "scene": "#131b2e",
        },
        "refreshes": 6,
    }


def test_language_controller_persists_and_pairs_cn_blocks() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
function el(tag, cls, text){
  return {
    tagName:tag, className:cls||'', childNodes:[], children:[],
    firstChild:null, parentNode:null, attrs:{},
    setAttribute:function(k,v){this.attrs[k]=String(v);},
    getAttribute:function(k){return this.attrs[k]||null;},
    querySelector:function(sel){
      var all=this.querySelectorAll(sel);
      return all[0]||null;
    },
    querySelectorAll:function(sel){
      var out=[];
      function walk(node){
        var c=' '+String(node.className||'')+' ';
        if((sel==='.cn'||(sel&&sel.indexOf('.cn')>=0)) && c.indexOf(' cn ')>=0) out.push(node);
        else if((sel==='.en'||(sel&&sel.indexOf('.en')>=0)) && c.indexOf(' en ')>=0) out.push(node);
        (node.children||[]).forEach(walk);
      }
      walk(this);
      return out;
    },
    appendChild:function(n){
      n.parentNode=this;
      this.childNodes.push(n);
      if(n.tagName) this.children.push(n);
      this.firstChild=this.childNodes[0];
      return n;
    },
    insertBefore:function(n, ref){
      n.parentNode=this;
      var i=this.childNodes.indexOf(ref);
      this.childNodes.splice(i<0?this.childNodes.length:i,0,n);
      if(n.tagName){
        var j=this.children.indexOf(ref);
        this.children.splice(j<0?this.children.length:j,0,n);
      }
      this.firstChild=this.childNodes[0];
      return n;
    }
  };
}
var enText={nodeType:3, textContent:'How to read. English.'};
var cn=el('DIV','cn','怎么看');
cn.nodeType=1;
var guide=el('DIV','sec-guide');
guide.appendChild(enText);
guide.appendChild(cn);
var root=el('HTML','');
root.nodeType=1;
var buttons=[{choice:'en',attrs:{},getAttribute:function(k){return k==='data-lang-choice'?this.choice:this.attrs[k]||null;},setAttribute:function(k,v){this.attrs[k]=String(v);}},
             {choice:'zh',attrs:{},getAttribute:function(k){return k==='data-lang-choice'?this.choice:this.attrs[k]||null;},setAttribute:function(k,v){this.attrs[k]=String(v);}}];
document={
  documentElement:root,
  querySelectorAll:function(sel){
    if(sel==='.lang-choice') return buttons;
    if(sel==='.cn') return [cn];
    return [];
  },
  createElement:function(tag){return el(tag.toUpperCase(),'');}
};
window={};
var store={saved:null,
  getItem:function(key){return key==='ga-lang'?this.saved:null;},
  setItem:function(key,value){if(key==='ga-lang') this.saved=String(value);}
};
globalThis.localStorage=store;
initLangController();
pairLangBlocks(guide);
var afterInit={lang:root.getAttribute('data-lang'), htmlLang:root.getAttribute('lang'), paired:guide.getAttribute('data-lang-paired'), enClass:guide.children[0]&&guide.children[0].className};
setLang('zh',true);
var afterZh={lang:root.getAttribute('data-lang'), htmlLang:root.getAttribute('lang'), saved:store.saved, pressed:[buttons[0].attrs['aria-pressed'],buttons[1].attrs['aria-pressed']]};
setLang('en',true);
console.log(JSON.stringify({afterInit:afterInit, afterZh:afterZh, afterEn:{lang:root.getAttribute('data-lang'), saved:store.saved}}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["afterInit"]["lang"] == "en"
    assert observed["afterInit"]["htmlLang"] == "en"
    assert observed["afterInit"]["paired"] == "1"
    assert observed["afterInit"]["enClass"] == "en"
    assert observed["afterZh"]["lang"] == "zh"
    assert observed["afterZh"]["htmlLang"] == "zh-CN"
    assert observed["afterZh"]["saved"] == "zh"
    assert observed["afterZh"]["pressed"] == ["false", "true"]
    assert observed["afterEn"]["lang"] == "en"
    assert observed["afterEn"]["saved"] == "en"


def test_theme_text_and_accent_controls_meet_wcag_contrast(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    light, dark = _theme_css_blocks(html)
    for block in (light, dark):
        assert _contrast_ratio(_css_hex(block, "--text"), _css_hex(block, "--bg")) >= 4.5
        assert _contrast_ratio(_css_hex(block, "--muted"), _css_hex(block, "--bg")) >= 4.5
        assert (
            _contrast_ratio(_css_hex(block, "--on-accent"), _css_hex(block, "--accent"))
            >= 3.0
        )
        assert (
            _contrast_ratio(
                _css_hex(block, "--query-marker"), _css_hex(block, "--plot-bg")
            )
            >= 3.0
        )
        assert (
            _contrast_ratio(
                _css_hex(block, "--query-marker-outline"), _css_hex(block, "--plot-bg")
            )
            >= 3.0
        )


def test_apply_plot_theme_sets_all_axis_theme_colors_without_mutation() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var root={attrs:{},setAttribute:function(k,v){this.attrs[k]=String(v);}};
document={documentElement:root,querySelectorAll:function(){return [];}};
window={
  matchMedia:function(){return {matches:true};},
  getComputedStyle:function(){return {getPropertyValue:function(){return '';}};}
};
var layout={
  paper_bgcolor:'#old-paper',
  plot_bgcolor:'#old-plot',
  font:{color:'#old-font',size:12},
  xaxis:{color:'#old-x',gridcolor:'#old-x-grid',zerolinecolor:'#old-x-zero',range:[0,1]},
  xaxis2:{color:'#old-x2',gridcolor:'#old-x2-grid',zerolinecolor:'#old-x2-zero',anchor:'y'},
  yaxis:{color:'#old-y',gridcolor:'#old-y-grid',zerolinecolor:'#old-y-zero',title:'Y'},
  yaxis2:{color:'#old-y2',gridcolor:'#old-y2-grid',zerolinecolor:'#old-y2-zero',overlaying:'y'},
  custom:{keep:true}
};
var before=JSON.stringify(layout);
var themed=applyPlotTheme(layout);
console.log(JSON.stringify({
  unchanged:JSON.stringify(layout)===before,
  axes:['xaxis','xaxis2','yaxis','yaxis2'].map(function(k){
    return [themed[k].color,themed[k].gridcolor,themed[k].zerolinecolor,themed[k].anchor||null];
  }),
  preserved:[themed.xaxis.range,themed.custom.keep,themed.yaxis.title]
}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "unchanged": True,
        "axes": [
            ["#e2e8f0", "#263654", "#263654", None],
            ["#e2e8f0", "#263654", "#263654", "y"],
            ["#e2e8f0", "#263654", "#263654", None],
            ["#e2e8f0", "#263654", "#263654", None],
        ],
        "preserved": [[0, 1], True, "Y"],
    }


def test_theme_chrome_uses_semantic_tokens_and_motion_contracts(
    tmp_path: Path,
) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    for selector in (
        ".sidebar a:hover",
        "#top-bar",
        "#pinned-sample",
        ".author-src",
        ".author-chip:hover",
        "#fstats-callout",
        ".gt-card",
        ".gt-card.warn",
        ".tag-green",
        ".tag-red",
        ".qc-pill.primary",
    ):
        start = style.index(selector)
        end = style.index("}", start)
        block = style[start:end]
        assert "rgba(" not in block, selector
    assert "--accent-soft" in style
    assert "--warning-soft" in style
    assert "--shadow" in style
    for selector in (
        ".js-plotly-plot .plotly .modebar",
        ".js-plotly-plot .plotly .hovertext",
        "#plot-lz .lz-toolbar",
        "#plot-lz .lz-tooltip",
        "#plot-lz .lz-data_layer-tooltip",
        "#plot-lz svg.lz-locuszoom .lz-legend-background",
        "#plot-lz .lz-data_layer-tooltip button",
        "#plot-lz .lz-tooltip-close-button",
        "#plot-lz .lz-data_layer-tooltip table",
        "#plot-lz .lz-data_layer-tooltip th",
        "#plot-lz .lz-data_layer-tooltip td",
        "#plot-lz .lz-toolbar-menu",
        "#plot-lz .lz-toolbar-menu-content",
        "#plot-lz .lz-toolbar-menu .lz-toolbar-button",
        "#plot-lz .lz-toolbar-menu a",
        "#plot-lz .lz-toolbar-menu a:focus-visible",
        ".theme-transition .main",
    ):
        assert selector in style
    assert ".sidebar,.sidebar-toggle,.main,#top-bar,.theme-control,.theme-choice" in style
    assert "animation:none!important" in style
    assert "function motionBehavior" in APP_JS
    assert "behavior:motionBehavior()" in APP_JS
    assert "scrollIntoView({behavior:'smooth'" not in APP_JS


def test_motion_behavior_follows_reduced_motion_preference() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var reduced=false;
window={matchMedia:function(){return {matches:reduced};}};
console.log(JSON.stringify({
  normal:motionBehavior(),
  reduced:(reduced=true,motionBehavior())
}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"normal": "smooth", "reduced": "auto"}


def test_theme_refresh_relayouts_existing_plots_without_rebuilding_state() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var calls=[], root={setAttribute:function(){}};
var details=[{id:'panel-research',open:true}];
var plot={
  layout:{paper_bgcolor:'#old',plot_bgcolor:'#old',xaxis:{},yaxis:{}},
  _fullLayout:{xaxis:{},yaxis:{}},
  data:[{name:'QUERY',marker:{color:'#old',line:{color:'#old'}}}]
};
document={
  documentElement:root,
  querySelectorAll:function(){return details;},
  getElementById:function(id){
    return id==='plot-lz'||id==='plot-sel-lz'?null:plot;
  }
};
var Plotly={
  relayout:function(){calls.push('relayout');},
  restyle:function(){calls.push('restyle');},
  newPlot:function(){calls.push('newPlot');},
  purge:function(){calls.push('purge');}
};
window={
  Plotly:Plotly,
  matchMedia:function(){return {matches:false};},
  getComputedStyle:function(){return {getPropertyValue:function(){return '';}};}
};
D={query:'QUERY',gwas_loci:[],selection_loci:[]};
QUERY='QUERY'; currentK='7'; selectedIID='SAMPLE';
selManhGrp='CG1'; selManhMetric='het'; selHeatMetric='fst';
selManhFocus={chrom:'2',pos:123}; lzIdx=2; selLzIdx=3;
loadPCA=function(){calls.push('loadPCA');};
resetPlot=function(){calls.push('resetPlot');};
refreshThemedPlots();
console.log(JSON.stringify({
  relayout:calls.indexOf('relayout')>=0,
  restyle:calls.indexOf('restyle')>=0,
  rebuilt:calls.some(function(x){return x==='newPlot'||x==='loadPCA'||x==='resetPlot';}),
  state:[currentK,selectedIID,selManhGrp,selManhMetric,selHeatMetric,
    JSON.stringify(selManhFocus),lzIdx,selLzIdx],
  details:details[0].open
}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "relayout": True,
        "restyle": True,
        "rebuilt": False,
        "state": [
            "7",
            "SAMPLE",
            "CG1",
            "het",
            "fst",
            '{"chrom":"2","pos":123}',
            2,
            3,
        ],
        "details": True,
    }


def test_partial_plotly_api_shows_inline_unavailable_without_throwing() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var target={innerHTML:'',_fullLayout:null};
document={
  documentElement:{setAttribute:function(){}},
  querySelectorAll:function(){return [];},
  getElementById:function(){return target;}
};
window={
  Plotly:{relayout:null,restyle:null,purge:null},
  matchMedia:function(){return {matches:false};},
  getComputedStyle:function(){return {getPropertyValue:function(){return '';}};}
};
D={query:'Q',gwas_loci:[],selection_loci:[]};
var caught='';
try{loadPCA();refreshThemedPlots();}catch(err){caught=String(err);}
console.log(JSON.stringify({caught:caught,message:target.innerHTML}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["caught"] == ""
    assert "Plotly.js unavailable" in observed["message"]


def test_panel_navigation_refreshes_once_when_opening_or_revisiting() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    probe = r"""
var refreshCalls=0, toggleHandlers=[];
var panel={
  id:'panel-research', tagName:'DETAILS', _open:false, parentElement:null,
  get open(){return this._open;},
  set open(value){
    var changed=this._open!==!!value;
    this._open=!!value;
    if(changed && this._open) toggleHandlers.forEach(function(fn){fn();});
  },
  addEventListener:function(kind,fn){
    if(kind==='toggle') toggleHandlers.push(fn);
  }
};
var target={
  id:'panel-target', parentElement:panel,
  scrollIntoView:function(){}
};
var link={classList:{remove:function(){},add:function(){}}};
document={
  getElementById:function(id){
    return id==='panel-target'?target:(id==='panel-research'?panel:null);
  },
  querySelectorAll:function(sel){return sel==='.sidebar a'?[link]:[];},
  querySelector:function(){return link;}
};
window={matchMedia:function(){return {matches:false};}};
motionBehavior=function(){return 'auto';};
refreshPanelResearchPlots=function(){refreshCalls++;};
bindPanelResearchToggle();
scrollToId('panel-target');
var afterOpening=refreshCalls;
scrollToId('panel-target');
var afterRevisit=refreshCalls-afterOpening;
console.log(JSON.stringify({
  toggleListeners:toggleHandlers.length,
  afterOpening:afterOpening,
  afterRevisit:afterRevisit,
  total:refreshCalls
}));
"""
    result = subprocess.run(
        [node, "-e", "new Function(process.argv[1]+process.argv[2])();", APP_JS, probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "toggleListeners": 1,
        "afterOpening": 1,
        "afterRevisit": 1,
        "total": 2,
    }


def test_v2_sidecar_semantic_digest_is_recorded_for_ages() -> None:
    path = ROOT / "results" / "Ages.sample-first-v2.report.data.json"
    assert semantic_payload_digest(path) == AGES_V2_SEMANTIC_PAYLOAD_SHA256


def test_v2_sidecar_semantic_digest_is_recorded_for_hun89_query() -> None:
    path = ROOT / "results" / "HUN89_query.sample-first-v2.report.data.json"
    assert semantic_payload_digest(path) == HUN89_QUERY_V2_SEMANTIC_PAYLOAD_SHA256


def test_v2_rewrite_preserves_semantic_sidecar_digests_and_v1_checksums(
    tmp_path: Path,
) -> None:
    v1_before = {
        relative: _file_sha256(ROOT / relative)
        for relative in STABLE_V1_REPORT_SHA256
    }
    assert set(v1_before) == set(STABLE_V1_REPORT_SHA256)
    for relative, actual in v1_before.items():
        assert (ROOT / relative).is_file(), f"missing V1 artifact {relative}"
        assert actual == STABLE_V1_REPORT_SHA256[relative], (
            f"unexpected SHA-256 for {relative}: {actual}"
        )

    checked_in_before = {
        relative: _file_sha256(ROOT / relative) for relative in _V2_CHECKED_IN_RELATIVES
    }

    methods_html = methods_html_section(
        ROOT / "results" / "provenance",
        ROOT / "docs" / "REFERENCES.bib",
    )
    assert re.search(r"<h2[^>]*>Reproduce", methods_html) is None
    assert "Wall time on MBP" not in methods_html
    assert "Methods not used and why" not in methods_html

    for sample, expected_digest in _V2_REWRITE_SAMPLES.items():
        sidecar = ROOT / "results" / f"{sample}.sample-first-v2.report.data.json"
        before = json.loads(sidecar.read_text(encoding="utf-8"))
        assert semantic_payload_digest(sidecar) == expected_digest
        assert semantic_payload_digest(before) == expected_digest

        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        payload["methods_html"] = methods_html
        data_json = payload_to_json(payload)
        dest = tmp_path / sample / f"{sample}.sample-first-v2.report.html"
        dest.parent.mkdir(parents=True)
        write_dashboard_html(
            sample,
            data_json,
            dest,
            ROOT,
            write_sidecar=True,
            merged_vcf_note=str(payload.get("merged_note") or ""),
        )

        after_sidecar = dest.with_suffix(".data.json")
        after = json.loads(after_sidecar.read_text(encoding="utf-8"))
        assert after["methods_html"] == methods_html
        assert semantic_payload_digest(after_sidecar) == expected_digest
        assert semantic_payload_digest(after) == expected_digest
        assert semantic_payload_view(before) == semantic_payload_view(after)
        assert _payload_without_methods_html(before) == _payload_without_methods_html(
            after
        )

        before_ids, before_nums, before_lists = collect_identifier_numeric_list_fields(
            before
        )
        after_ids, after_nums, after_lists = collect_identifier_numeric_list_fields(
            after
        )
        assert before_ids == after_ids
        assert before_nums == after_nums
        assert before_lists == after_lists

        html = dest.read_text(encoding="utf-8")
        library_class = str((after.get("report_meta") or {}).get("library_class") or "")
        assert_rewritten_v2_html_contracts(html, after["methods_html"], library_class)

    for relative, digest in checked_in_before.items():
        assert _file_sha256(ROOT / relative) == digest, (
            f"checked-in artifact mutated during temp rewrite: {relative}"
        )
    for relative, expected in STABLE_V1_REPORT_SHA256.items():
        actual = _file_sha256(ROOT / relative)
        assert actual == expected, f"unexpected SHA-256 for {relative}: {actual}"
        assert actual == v1_before[relative]


def test_v2_visible_copy_inventory_has_all_report_sections(
    tmp_path: Path,
) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = html.split("<body>", 1)[1].split("<script>\n", 1)[0]

    for section_id in (
        "sample-validity",
        "identity-placement",
        "population-placement",
        "sample-evidence",
        "panel-research",
        "methods",
        "dl",
    ):
        assert f'id="{section_id}"' in visible

    for function_name in (
        "fillReportMeta",
        "fillMethodCoverage",
        "fillQuerySnapshot",
        "fillQc",
        "fillConclusions",
        "fillQueryEvidence",
        "fillExtra",
        "fillCloneTable",
        "fillIbsKinship",
        "fillSelFstats",
        "fillSelQuerySites",
        "fillFstatsCallout",
        "drawLocusZoom",
        "drawSelLocusZoom",
        "drawSelManhattan",
        "drawSelHeat",
        "drawSelScatter",
        "loadDamage",
    ):
        assert f"function {function_name}" in APP_JS


_ADJACENT_LANGUAGE_PAIR_RE = re.compile(
    r"""
    <(?P<en_tag>[A-Za-z][\w:-]*)
    (?P<en_attrs>[^>]*\bclass\s*=\s*["'][^"']*\ben\b[^"']*["'][^>]*)>
    (?P<en_body>.*?)
    </(?P=en_tag)\s*>
    \s*
    <(?P<cn_tag>[A-Za-z][\w:-]*)
    (?P<cn_attrs>[^>]*\bclass\s*=\s*["'][^"']*\bcn\b[^"']*["'][^>]*)>
    (?P<cn_body>.*?)
    </(?P=cn_tag)\s*>
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)
_CLASS_ATTRIBUTE_RE = re.compile(
    r"""\bclass\s*=\s*(?P<quote>["'])(?P<value>.*?)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)


def _class_tokens(attributes: str) -> set[str]:
    tokens: set[str] = set()
    for match in _CLASS_ATTRIBUTE_RE.finditer(attributes):
        tokens.update(match.group("value").split())
    return tokens


def _normalized_html_text(fragment: str) -> str:
    text = _HTML_TAG_RE.sub(" ", fragment)
    return " ".join(unescape(text).split())


def _has_adjacent_language_pair(
    content: str, english: str, chinese: str
) -> bool:
    expected_en = _normalized_html_text(english)
    expected_cn = _normalized_html_text(chinese)
    content_without_comments = _HTML_COMMENT_RE.sub("", content)
    for match in _ADJACENT_LANGUAGE_PAIR_RE.finditer(content_without_comments):
        if "en" not in _class_tokens(match.group("en_attrs")):
            continue
        if "cn" not in _class_tokens(match.group("cn_attrs")):
            continue
        en_text = _normalized_html_text(match.group("en_body"))
        cn_text = _normalized_html_text(match.group("cn_body"))
        if expected_en and expected_en in en_text and expected_cn and expected_cn in cn_text:
            return True
    return False


def _element_block(markup: str, element_id: str) -> str:
    """Return a complete ID-selected element, including nested descendants."""

    class ElementCollector(HTMLParser):
        _VOID_ELEMENTS = {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }

        def __init__(self, target_id: str) -> None:
            super().__init__(convert_charrefs=False)
            self.target_id = target_id
            self.target_tag: str | None = None
            self.stack: list[str] = []
            self.parts: list[str] = []
            self.done = False

        def _raw_starttag(self) -> str:
            return self.get_starttag_text() or ""

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if self.done:
                return
            raw = self._raw_starttag()
            if self.target_tag is None:
                if dict(attrs).get("id") != self.target_id:
                    return
                self.target_tag = tag.lower()
                self.stack.append(self.target_tag)
                self.parts.append(raw)
                return
            self.parts.append(raw)
            normalized_tag = tag.lower()
            if normalized_tag not in self._VOID_ELEMENTS:
                self.stack.append(normalized_tag)

        def handle_startendtag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if self.done:
                return
            raw = self._raw_starttag()
            if self.target_tag is None:
                if dict(attrs).get("id") == self.target_id:
                    self.target_tag = tag.lower()
                    self.parts.append(raw)
                    self.done = True
                return
            self.parts.append(raw)

        def handle_endtag(self, tag: str) -> None:
            if self.target_tag is None or self.done:
                return
            normalized_tag = tag.lower()
            self.parts.append(f"</{normalized_tag}>")
            if normalized_tag not in self.stack:
                return
            while self.stack:
                if self.stack.pop() == normalized_tag:
                    break
            if not self.stack:
                self.done = True

        def handle_data(self, data: str) -> None:
            if self.target_tag is not None and not self.done:
                self.parts.append(data)

        def handle_entityref(self, name: str) -> None:
            if self.target_tag is not None and not self.done:
                self.parts.append(f"&{name};")

        def handle_charref(self, name: str) -> None:
            if self.target_tag is not None and not self.done:
                self.parts.append(f"&#{name};")

        def handle_comment(self, data: str) -> None:
            if self.target_tag is not None and not self.done:
                self.parts.append(f"<!--{data}-->")

        def handle_decl(self, decl: str) -> None:
            if self.target_tag is not None and not self.done:
                self.parts.append(f"<!{decl}>")

        def handle_pi(self, data: str) -> None:
            if self.target_tag is not None and not self.done:
                self.parts.append(f"<?{data}>")

        def unknown_decl(self, data: str) -> None:
            if self.target_tag is not None and not self.done:
                self.parts.append(f"<![{data}]>")

    collector = ElementCollector(element_id)
    collector.feed(markup)
    collector.close()
    assert collector.target_tag is not None, f"missing element block: {element_id}"
    assert collector.done, f"unterminated element block: {element_id}"
    return "".join(collector.parts)


def _class_element_blocks(
    markup: str, class_name: str
) -> list[tuple[str, str]]:
    """Return class-selected HTML blocks and their direct text nodes."""

    class ClassCollector(HTMLParser):
        _VOID_ELEMENTS = {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }

        def __init__(self, target_class: str) -> None:
            super().__init__(convert_charrefs=False)
            self.target_class = target_class
            self.stack: list[dict[str, object]] = []
            self.targets: list[dict[str, object]] = []
            self.blocks: list[tuple[str, str]] = []

        def _append(self, value: str) -> None:
            for target in self.targets:
                target["parts"].append(value)  # type: ignore[union-attr]

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            raw = self.get_starttag_text() or ""
            self._append(raw)
            classes = set((dict(attrs).get("class") or "").split())
            target: dict[str, object] = {
                "tag": tag.lower(),
                "parts": [raw],
                "direct": [],
                "is_target": self.target_class in classes,
            }
            if target["is_target"]:
                self.targets.append(target)
            if tag.lower() not in self._VOID_ELEMENTS:
                self.stack.append(target)

        def handle_startendtag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            raw = self.get_starttag_text() or ""
            self._append(raw)
            classes = set((dict(attrs).get("class") or "").split())
            if self.target_class in classes:
                self.blocks.append((raw, ""))

        def handle_endtag(self, tag: str) -> None:
            raw = f"</{tag.lower()}>"
            self._append(raw)
            if not self.stack:
                return
            frame = self.stack.pop()
            if frame["is_target"]:
                assert self.targets and self.targets[-1] is frame
                self.targets.pop()
                self.blocks.append(
                    ("".join(frame["parts"]), "".join(frame["direct"]))
                )

        def handle_data(self, data: str) -> None:
            self._append(data)
            if self.stack and self.stack[-1]["is_target"]:
                self.stack[-1]["direct"].append(data)  # type: ignore[union-attr]

        def handle_entityref(self, name: str) -> None:
            self._append(f"&{name};")

        def handle_charref(self, name: str) -> None:
            self._append(f"&#{name};")

    collector = ClassCollector(class_name)
    collector.feed(markup)
    collector.close()
    return collector.blocks


def _nearby_has_distinct_chinese(html: str, token: str, radius: int = 480) -> bool:
    """Require Han text near an identical technical token, not the token itself."""
    if not token:
        return False
    for match in re.finditer(re.escape(token), html):
        start = max(0, match.start() - radius)
        end = min(len(html), match.end() + radius)
        remainder = html[start:end].replace(token, "")
        if _HAN_RE.search(remainder):
            return True
    return False


def _zh_visible_copy(html: str) -> str:
    """Approximate Chinese-visible text by dropping adjacent English spans."""
    return _normalized_html_text(_EN_SPAN_RE.sub("", html))


def assert_technical_token_has_nearby_chinese(html: str, token: str) -> None:
    """Identical technical tokens are not bilingual proof by themselves."""
    assert token in TECHNICAL_TOKEN_EXCEPTIONS, (
        f"{token!r} is not on the technical-token exception list"
    )
    assert token in html, f"missing technical token {token!r}"
    assert _nearby_has_distinct_chinese(html, token), (
        f"technical token {token!r} lacks distinct nearby Chinese"
    )


def assert_nonempty_language_pair(
    html: str, english: str, chinese: str
) -> None:
    """Require adjacent, nonempty EN/CN content in one localized block."""
    assert english.strip(), "English copy must be non-empty"
    assert chinese.strip(), "Chinese copy must be non-empty"
    en_norm = _normalized_html_text(english)
    zh_norm = _normalized_html_text(chinese)
    if en_norm == zh_norm:
        assert_technical_token_has_nearby_chinese(html, en_norm)
        return
    assert _has_adjacent_language_pair(
        html, english, chinese
    ), f"missing adjacent EN/CN pair: {english!r} / {chinese!r}"


def assert_dynamic_pair(content: str, english: str, chinese: str) -> None:
    """Require both language forms in JavaScript-generated report copy."""
    assert_nonempty_language_pair(content, english, chinese)


def assert_error_language_pair(
    content: str, english_marker: str, chinese_marker: str
) -> None:
    """Require semantic EN/CN markers in one adjacent error block."""
    assert _has_adjacent_language_pair(
        content, english_marker, chinese_marker
    ), (
        "missing adjacent bilingual error markers: "
        f"{english_marker!r} / {chinese_marker!r}"
    )


def _run_report_node(probe: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    result = subprocess.run(
        [
            node,
            "-e",
            "new Function(process.argv[1]+process.argv[2])();",
            APP_JS,
            probe,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_runtime_validity_tables_have_bilingual_labels_and_scopes() -> None:
    observed = _run_report_node(
        r"""
function node(){
  return {innerHTML:'',querySelectorAll:function(){return [];}};
}
var els={
  'report-meta':node(),
  'method-coverage':node(),
  'query-q8':node(),
  'qc-highlights':node(),
  'qc-table':node()
};
document={getElementById:function(id){return els[id]||null;}};
D={
  query:'Q',
  report_meta:{
    report_id:'R',
    query_id:'Q',
    source_sample_id:'SRC',
    generated_at_utc:'2026-09-17T00:00:00Z',
    panel_cache:{path:'panel.npz',available:true},
    query_vcf:{path:'Q.vcf.gz',available:true},
    source_bam:{path:'SRC.bam',available:true},
    source_damage_tsv:{path:'SRC.damage.tsv',available:true},
    shared_artifacts:{selection:{manhattan:{available:true}}}
  },
  method_coverage:{
    panel_genotype:{called:4,total:5,coverage:0.8},
    selection_locus_gt:{query_gt_called:2,query_gt_n:3},
    gwas_locus_gt:{query_gt_called:1,query_gt_n:2},
    fstats:{query_called_sites:4},
    gs_predictions:[],
    damage:{source_sample_id:'SRC',path:'SRC.damage.tsv',available:true},
    gs:{available:false,unavailable_reason:'No per-query GS prediction available.'}
  },
  query_q8:[{label:'CG1',value:0.6,color:'#123456'}],
  qc:{n_called:12,n_variant:2,mean_depth:1.2}
};
QUERY='Q'; langMode='en';
fillReportMeta();
fillMethodCoverage();
fillQuerySnapshot();
fillQc();
console.log(JSON.stringify({
  meta:els['report-meta'].innerHTML,
  coverage:els['method-coverage'].innerHTML,
  snapshot:els['query-q8'].innerHTML,
  qc:els['qc-table'].innerHTML
}));
"""
    )

    for english, chinese in (
        ("Identifier", "标识"),
        ("Query-derived", "查询样本来源"),
        ("Source library", "来源文库"),
        ("2449 panel only", "仅 2449 面板"),
    ):
        assert_dynamic_pair(observed["meta"], english, chinese)
    for english, chinese in (
        ("Method", "方法"),
        ("Scope", "范围"),
        ("Query vs 2449 panel", "查询样本 vs 2449 面板"),
        ("Exact count / coverage", "实际数量 / 覆盖度"),
        ("Reason / caveat", "原因 / 注意"),
    ):
        assert_dynamic_pair(observed["coverage"], english, chinese)
    assert_dynamic_pair(observed["snapshot"], "Ancestry", "祖源成分")
    for english, chinese in (
        ("Metric", "指标"),
        ("Value", "数值"),
        ("Called genotypes", "已分型基因型"),
    ):
        assert_dynamic_pair(observed["qc"], english, chinese)


def test_identity_tables_and_empty_states_have_bilingual_copy() -> None:
    observed = _run_report_node(
        r"""
function node(){
  return {innerHTML:'',querySelectorAll:function(){return [];}};
}
var els={
  'clone-table':node(),
  'ibs-summary':node(),
  'ibs-table':node(),
  'kinship-table':node(),
  'fstats-callout':node()
};
document={getElementById:function(id){return els[id]||null;}};
window={_authorMatchIds:[]};
D={query:'Q',report_meta:{query_id:'Q',source_sample_id:'Q'},ibs_summary:{Identical:0,'Parent-Offspring':0,'Full Sib':0,Unrelated:0},outgroup_n:0};
fillCloneTable();
fillIbsKinship();
fillFstatsCallout([],[],[]);
console.log(JSON.stringify({
  clone:els['clone-table'].innerHTML,
  summary:els['ibs-summary'].innerHTML,
  ibs:els['ibs-table'].innerHTML,
  kinship:els['kinship-table'].innerHTML,
  fstats:els['fstats-callout'].innerHTML
}));
"""
    )

    assert_dynamic_pair(observed["clone"], "Class", "关系类别")
    assert_dynamic_pair(
        observed["clone"], "No Identical/PO hits", "没有 Identical/PO 命中"
    )
    for english, chinese in (
        ("Identical", "完全相同"),
        ("Parent-Offspring", "亲子"),
        ("Full Sib", "全同胞"),
        ("Unrelated", "无关"),
    ):
        assert_dynamic_pair(observed["summary"], english, chinese)
    assert_dynamic_pair(observed["ibs"], "Rel", "关系")
    assert_dynamic_pair(observed["ibs"], "No IBS matches", "没有 IBS 近邻")
    assert_dynamic_pair(observed["kinship"], "Rank", "排名")
    assert_dynamic_pair(
        observed["kinship"], "No kinship matches", "没有亲缘近邻"
    )
    assert_dynamic_pair(observed["fstats"], "No f3/f4", "没有 f3/f4")
    assert_dynamic_pair(
        observed["fstats"],
        "No designated OUT was available",
        "没有可用的指定 OUT",
    )


def test_population_plot_copy_separates_scope_and_method() -> None:
    observed = _run_report_node(
        r"""
function plotNode(){
  return {innerHTML:'',style:{},clientWidth:500,clientHeight:500,on:function(){}};
}
var treeEl=plotNode(), treeLayouts=[];
document={
  documentElement:null,
  getElementById:function(id){return id==='plot-tree'?treeEl:null;}
};
window={
  Plotly:{
    newPlot:function(el,data,layout){treeLayouts.push(layout);return {then:function(fn){fn();}};},
    purge:function(){}
  }
};
globalThis.Plotly=window.Plotly;
globalThis.requestAnimationFrame=function(fn){fn();};
D={
  query:'Q',
  pca_method:'GCTA64 GRM-PCA (panel167k_nogwas)',
  pca_n:3,
  pca_evals:[0.4,0.2,0.1],
  pca_points:[
    {iid:'R1',pcs:[1,2,3],grp:'CG1'},
    {iid:'Q',pcs:[4,5,6],grp:'QUERY',query:true}
  ],
  grp_colors:{CG1:'#123456'},
  srows:[
    {iid:'R1',idx:0,grp:'CG1',qvals:{'8':[0.2,0.8]}},
    {iid:'Q',idx:1,grp:'QUERY',query:true,qvals:{'8':[0.7,0.3]}}
  ],
  admix_query_in_panel:false,
  admix_meta:{'8':{labels:['A','B'],colors:['#123456','#654321']}},
  tree:{data:[],layout:{xaxis:{range:[-1,1]},yaxis:{range:[-1,1]}}}
};
SROWS=D.srows; QUERY='Q'; selectedIID=null; treeShape='circular';
function snapshot(mode){
  langMode=mode;
  var p=buildPca2dFig(0,1);
  var a=buildAdmixFig(8);
  loadTree();
  var pt=p.data[p.data.length-1];
  return {
    pcaTitle:p.layout.title,
    pcaX:p.layout.xaxis.title,
    pcaNames:p.data.map(function(x){return x.name;}),
    pcaHover:pt.hovertemplate,
    admixTitle:a.layout.title,
    admixY:a.layout.yaxis.title,
    admixHover:a.data[a.data.length-1].hovertemplate,
    treeTitle:treeLayouts[treeLayouts.length-1].title
  };
}
console.log(JSON.stringify({en:snapshot('en'),zh:snapshot('zh')}));
"""
    )

    assert "GCTA64 PCA" in observed["en"]["pcaTitle"]
    assert "Frozen panel PCA" in observed["en"]["pcaTitle"]
    assert "Query sample" in observed["en"]["pcaTitle"]
    assert "PC1" in observed["en"]["pcaX"]
    assert any("Query / Q" in name for name in observed["en"]["pcaNames"])
    assert "query sample" in observed["en"]["pcaHover"]
    assert "Frozen 2449-panel ADMIXTURE" in observed["en"]["admixTitle"]
    assert "query projection" in observed["en"]["admixTitle"]
    assert "Ancestry proportion" in observed["en"]["admixY"]
    assert "query projection" in observed["en"]["admixHover"]
    assert "Frozen 2449-panel NJ tree" in observed["en"]["treeTitle"]

    assert "冻结面板 PCA" in observed["zh"]["pcaTitle"]
    assert "查询样本" in observed["zh"]["pcaTitle"]
    assert "主成分1" in observed["zh"]["pcaX"]
    assert any("查询样本 / Q" in name for name in observed["zh"]["pcaNames"])
    assert "查询样本" in observed["zh"]["pcaHover"]
    assert "冻结 2449 面板 ADMIXTURE" in observed["zh"]["admixTitle"]
    assert "查询样本投影" in observed["zh"]["admixTitle"]
    assert "祖源比例" in observed["zh"]["admixY"]
    assert "查询样本投影" in observed["zh"]["admixHover"]
    assert "冻结 2449 面板 NJ 树" in observed["zh"]["treeTitle"]


def test_runtime_plot_failures_have_bilingual_messages() -> None:
    observed = _run_report_node(
        r"""
function node(){
  return {innerHTML:'',style:{},clientWidth:500,clientHeight:500,on:null};
}
var els={
  unavailable:node(),
  'plot-pca':node(),
  'plot-pca3d':node(),
  'plot-bar':node(),
  'plot-tree':node(),
  'plot-lz':node()
};
document={getElementById:function(id){return els[id]||null;}};
window={};
D={query:'Q',pca_points:[],pca_n:0,admix_meta:{},tree:null,gwas_loci:[]};
QUERY='Q';
plotlyUnavailable(els.unavailable,'PCA plot');
window.Plotly={newPlot:function(){},purge:function(){}};
globalThis.Plotly=window.Plotly;
loadPCA();
loadPCA3d();
loadBar(8);
loadTree();
drawLocusZoom();
console.log(JSON.stringify({
  unavailable:els.unavailable.innerHTML,
  pca:els['plot-pca'].innerHTML,
  pca3d:els['plot-pca3d'].innerHTML,
  bar:els['plot-bar'].innerHTML,
  tree:els['plot-tree'].innerHTML,
  locus:els['plot-lz'].innerHTML
}));
"""
    )

    assert_error_language_pair(
        observed["unavailable"],
        "Plotly.js unavailable",
        "Plotly.js 不可用",
    )
    assert_error_language_pair(observed["pca"], "No PCA", "没有 PCA")
    assert_error_language_pair(
        observed["pca3d"],
        "Need ≥3 PCs for 3D",
        "3D 需要至少 3 个主成分",
    )
    assert_error_language_pair(
        observed["bar"], "No ADMIXTURE K=8", "没有 ADMIXTURE K=8"
    )
    assert_error_language_pair(observed["tree"], "No NJ tree", "没有 NJ 树")
    assert_error_language_pair(
        observed["locus"],
        "No LocusZoom data",
        "没有该位点的 LocusZoom 数据",
    )


def test_runtime_reason_unknown_values_keep_bilingual_source_context() -> None:
    observed = _run_report_node(
        r"""
console.log(JSON.stringify({
  reason:runtimeReason('upstream <reason> & status')
}));
"""
    )
    assert_dynamic_pair(
        observed["reason"],
        "Source reason",
        "来源原因",
    )
    assert "upstream &lt;reason&gt; &amp; status" in observed["reason"]


def test_unavailable_message_localizes_known_gs_reason_and_escapes_unknown() -> None:
    observed = _run_report_node(
        r"""
console.log(JSON.stringify({
  knownSample:unavailableMessage('no per-sample GS prediction available'),
  knownQuery:unavailableMessage('No per-query GS prediction available.'),
  unknown:unavailableMessage('<img src=x onerror=1> & <svg onload=1>')
}));
"""
    )
    for key in ("knownSample", "knownQuery"):
        html = observed[key]
        zh = _zh_visible_copy(html)
        assert "不可用" in zh
        assert "没有可用的本查询 GS 预测" in zh
        assert "no per-sample gs prediction available" not in zh.lower()
        assert "no per-query gs prediction available" not in zh.lower()
        assert_dynamic_pair(html, "Unavailable", "不可用")
        assert_dynamic_pair(
            html,
            "No per-query GS prediction available.",
            "没有可用的本查询 GS 预测。",
        )
        assert "Unavailable" in html
        assert "No per-query GS prediction available" in html

    unknown = observed["unknown"]
    zh_unknown = _zh_visible_copy(unknown)
    assert "不可用" in zh_unknown
    assert "来源原因" in zh_unknown
    assert "<img" not in unknown
    assert "<svg" not in unknown
    assert "&lt;img src=x onerror=1&gt;" in unknown
    assert "&lt;svg onload=1&gt;" in unknown
    assert "&amp;" in unknown
    assert_dynamic_pair(unknown, "Unavailable", "不可用")
    assert_dynamic_pair(unknown, "Source reason", "来源原因")


def test_locuszoom_populate_failures_escape_bilingual_exception() -> None:
    observed = _run_report_node(
        r"""
var target={
  innerHTML:'',
  style:{},
  clientWidth:500,
  clientHeight:500,
  querySelectorAll:function(){return [];}
};
document={getElementById:function(id){return id==='plot-lz'?target:null;}};
D={
  gwas_loci:[{
    chrom:'1',
    pos:5,
    window_start:1,
    window_end:10,
    lead_i:0,
    snps:{
      pos:[5], nlp:[3], ref:['A'], alt:['G'], site:['1:5'],
      gene:[''], region:[''], beta:[0], se:[0], maf:[0.2],
      mas:[''], gt:['0/1'], r2:[1]
    },
    genes:[]
  }]
};
lzIdx=0;
fillLzMeta=function(){};
fillLzDetail=function(){};
fillLzBonf=function(){};
fillQueryGtCard=function(){};
drawQueryGtStrip=function(){};
LocusZoom={
  Layouts:{get:function(){
    return {panels:[],toolbar:{widgets:[]}};
  }},
  DataSources:function(){
    this.add=function(){return this;};
  },
  populate:function(){
    throw new Error('bad <populate> & failure');
  }
};
drawLocusZoom();
console.log(JSON.stringify({html:target.innerHTML}));
"""
    )
    assert_error_language_pair(
        observed["html"],
        "LocusZoom.js failed",
        "LocusZoom.js 加载失败",
    )
    assert "bad &lt;populate&gt; &amp; failure" in observed["html"]


def test_fstat_bar_empty_rows_have_bilingual_no_data() -> None:
    observed = _run_report_node(
        r"""
var target={
  innerHTML:'',
  style:{},
  clientWidth:500,
  clientHeight:500
};
document={getElementById:function(id){return id==='plot-f3'?target:null;}};
window={Plotly:{newPlot:function(){},purge:function(){}}};
drawFstatBars('plot-f3',[], 'f3', function(){return '';}, false);
console.log(JSON.stringify({html:target.innerHTML}));
"""
    )
    assert_error_language_pair(
        observed["html"],
        "No f3 rows",
        "没有 f3 数据行",
    )


def test_pair_lang_blocks_enforces_whitelist_and_pairs_siblings() -> None:
    observed = _run_report_node(
        r"""
function el(tag, cls, text){
  return {
    tagName:String(tag||'').toUpperCase(),
    className:cls||'',
    textContent:text||'',
    nodeType:1,
    childNodes:[],
    children:[],
    parentNode:null,
    previousSibling:null,
    nextSibling:null,
    attrs:{},
    setAttribute:function(k,v){this.attrs[k]=String(v);},
    getAttribute:function(k){return this.attrs[k]||null;},
    appendChild:function(node){
      if(node.parentNode&&node.parentNode.removeChild) node.parentNode.removeChild(node);
      var last=this.childNodes[this.childNodes.length-1]||null;
      if(last) last.nextSibling=node;
      node.previousSibling=last;
      node.nextSibling=null;
      node.parentNode=this;
      this.childNodes.push(node);
      if(node.nodeType===1) this.children.push(node);
      return node;
    },
    insertBefore:function(node,ref){
      if(node.parentNode&&node.parentNode.removeChild) node.parentNode.removeChild(node);
      var index=this.childNodes.indexOf(ref);
      if(index<0) index=this.childNodes.length;
      var before=index>0?this.childNodes[index-1]:null;
      var after=this.childNodes[index]||null;
      node.parentNode=this;
      node.previousSibling=before;
      node.nextSibling=after;
      if(before) before.nextSibling=node;
      if(after) after.previousSibling=node;
      this.childNodes.splice(index,0,node);
      if(node.nodeType===1){
        var childIndex=this.children.indexOf(ref);
        if(childIndex<0) childIndex=this.children.length;
        this.children.splice(childIndex,0,node);
      }
      return node;
    },
    removeChild:function(node){
      var index=this.childNodes.indexOf(node);
      if(index<0) return node;
      var before=index>0?this.childNodes[index-1]:null;
      var after=this.childNodes[index+1]||null;
      if(before) before.nextSibling=after;
      if(after) after.previousSibling=before;
      this.childNodes.splice(index,1);
      var childIndex=this.children.indexOf(node);
      if(childIndex>=0) this.children.splice(childIndex,1);
      node.parentNode=null;
      node.previousSibling=null;
      node.nextSibling=null;
      return node;
    },
    querySelectorAll:function(sel){
      var out=[];
      var wanted=sel==='.cn'?' cn ':sel==='.en'?' en ':'';
      function walk(node){
        var cls=' '+String(node.className||'')+' ';
        if(wanted&&cls.indexOf(wanted)>=0) out.push(node);
        (node.children||[]).forEach(walk);
      }
      walk(this);
      return out;
    }
  };
}
function text(value){
  return {nodeType:3,textContent:value,parentNode:null,previousSibling:null,nextSibling:null};
}
function pair(parent, en1, cn1, en2, cn2){
  parent.appendChild(text(en1));
  parent.appendChild(el('span','cn',cn1));
  parent.appendChild(text(en2));
  parent.appendChild(el('span','cn',cn2));
}
var root=el('main','');
var generic=el('div','generic');
var guide=el('div','sec-guide');
var info=el('div','info-box');
var cell=el('td','');
pair(generic,'generic EN 1','generic CN 1','generic EN 2','generic CN 2');
pair(guide,'guide EN 1','guide CN 1','guide EN 2','guide CN 2');
pair(info,'info EN 1','info CN 1','info EN 2','info CN 2');
pair(cell,'cell EN 1','cell CN 1','cell EN 2','cell CN 2');
root.appendChild(generic);
root.appendChild(guide);
root.appendChild(info);
root.appendChild(cell);
document={
  createElement:function(tag){return el(tag,'');}
};
pairLangBlocks(root);
console.log(JSON.stringify({
  genericEn:generic.querySelectorAll('.en').length,
  genericCn:generic.querySelectorAll('.cn').length,
  guideEn:guide.querySelectorAll('.en').length,
  guideCn:guide.querySelectorAll('.cn').length,
  infoEn:info.querySelectorAll('.en').length,
  infoCn:info.querySelectorAll('.cn').length,
  cellEn:cell.querySelectorAll('.en').length,
  cellCn:cell.querySelectorAll('.cn').length
}));
"""
    )
    assert observed == {
        "genericEn": 0,
        "genericCn": 2,
        "guideEn": 2,
        "guideCn": 2,
        "infoEn": 2,
        "infoCn": 2,
        "cellEn": 2,
        "cellCn": 2,
    }


def test_rendered_static_copy_has_nonempty_en_cn_pairs(tmp_path: Path) -> None:
    rendered = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    nav = _element_block(rendered, "report-sidebar")

    for english, chinese in (
        ("Interactive", "交互报告"),
        ("Sample validity", "样本有效性"),
        ("Identity & placement", "身份与定位"),
        ("Population placement", "群体定位"),
        ("Sample evidence", "样本证据"),
        ("Methods", "方法"),
        ("Downloads", "下载"),
    ):
        assert_nonempty_language_pair(nav, english, chinese)

    section_blocks = {
        section_id: _element_block(rendered, section_id)
        for section_id in (
            "sample-validity",
            "identity-placement",
            "population-placement",
            "sample-evidence",
            "panel-research",
            "sel",
            "clone",
            "methods",
            "dl",
        )
    }
    for parent_id, nested_id in (
        ("sample-validity", "damage"),
        ("identity-placement", "ibs"),
        ("population-placement", "tree"),
        ("sample-evidence", "gs-pred"),
        ("panel-research", "sel"),
    ):
        assert f'id="{nested_id}"' in section_blocks[parent_id]

    for section_id, english, chinese in (
        ("sample-validity", "Query-derived", "查询样本来源"),
        ("identity-placement", "Query vs 2449 panel", "查询样本 vs 2449 面板"),
        ("population-placement", "Query vs 2449 panel", "查询样本 vs 2449 面板"),
        ("sample-evidence", "Query-derived", "查询样本来源"),
        ("panel-research", "Panel research context", "2449 panel 研究背景"),
        ("sel", "2449 panel only", "仅 2449 面板"),
        ("methods", "Methods", "方法说明"),
        ("dl", "Downloads", "下载"),
    ):
        assert_nonempty_language_pair(
            section_blocks[section_id], english, chinese
        )

    for section_id in (
        "sample-validity",
        "identity-placement",
        "population-placement",
        "sample-evidence",
        "panel-research",
        "methods",
    ):
        assert_nonempty_language_pair(
            section_blocks[section_id], "How to read.", "怎么看："
        )
    for section_id in ("clone", "dl"):
        assert_nonempty_language_pair(
            section_blocks[section_id], "How to use.", "怎么用："
        )


def test_static_navigation_and_controls_have_en_cn_copy(tmp_path: Path) -> None:
    rendered = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = rendered.split("<body>", 1)[1].split("<script>\n", 1)[0]

    for english, chinese in (
        ("Go", "前往"),
        ("Find", "查找"),
        ("ADMIXTURE K:", "ADMIXTURE K："),
        (
            "Black ★/◆ = query · yellow ◆ = pinned sample",
            "黑色★/◆=查询样本 · 黄色◆=已钉住样本",
        ),
        ("Lang", "语言"),
        ("Theme", "主题"),
        ("View:", "视图："),
        ("Full", "完整"),
        ("Compact", "紧凑"),
        ("Layout:", "布局："),
        ("Circular", "圆形"),
        ("Rectangular", "矩形"),
        ("2D axes:", "二维坐标轴："),
        ("Y", "纵轴"),
        ("Grp", "组别"),
        ("Number in cell", "单元格数值"),
        ("Window", "窗口"),
        ("Locus", "位点"),
        ("K=8 composition", "K=8 组成"),
        ("Metadata", "元数据"),
        ("4K class counts", "4K 类别计数"),
        ("Clone + PO list", "克隆与亲子列表"),
        ("IBS top", "IBS 近邻"),
        ("Kinship top", "亲缘"),
        ("PCA", "PCA"),
        ("ADMIXTURE K=2–8", "ADMIXTURE K=2–8"),
        ("ADMIXTURE bar (K tabs)", "ADMIXTURE 柱图（K 标签）"),
        ("NJ Tree", "NJ 树"),
        ("f3 / f4", "f3 / f4"),
        ("Advanced exploratory allele sharing", "探索性等位基因共享"),
        ("Exploratory f3  f3(Q; A, B)", "探索性 f3：f3(Q; A, B)"),
        ("Genome-wide (2449 panel)", "全基因组（2449 面板）"),
        ("Sweep sites (this Grp)", "Sweep 位点（该 Grp）"),
        ("5 named loci × Grp", "5 个命名位点 × Grp"),
        ("Fst vs het", "Fst 与杂合度"),
        ("Trait loci", "性状位点"),
        ("LocusZoom (panel GWAS)", "LocusZoom（面板 GWAS）"),
        ("GS accuracy", "GS 准确度"),
        ("Top crosses", "推荐杂交组合"),
        ("Methods", "方法说明"),
        ("Downloads", "下载"),
    ):
        assert_nonempty_language_pair(visible, english, chinese)

    assert_nonempty_language_pair(
        _element_block(rendered, "dl"), "How to use.", "怎么用："
    )
    assert_nonempty_language_pair(
        visible, "GrapeAncestry interactive report", "GrapeAncestry 交互报告"
    )


def test_static_scope_badges_use_canonical_terms(tmp_path: Path) -> None:
    rendered = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()

    for section_id, english, chinese in (
        ("sample-validity", "Query-derived", "查询样本来源"),
        (
            "identity-placement",
            "Query vs 2449 panel",
            "查询样本 vs 2449 面板",
        ),
        (
            "population-placement",
            "Query vs 2449 panel",
            "查询样本 vs 2449 面板",
        ),
        ("sample-evidence", "Query-derived", "查询样本来源"),
        ("sel", "2449 panel only", "仅 2449 面板"),
        ("traits", "2449 panel only", "仅 2449 面板"),
        ("breeding", "2449 panel only", "仅 2449 面板"),
    ):
        assert_nonempty_language_pair(
            _element_block(rendered, section_id), english, chinese
        )

    reference = _element_block(rendered, "panel-research")
    assert_nonempty_language_pair(reference, "Reference only", "仅作核对")

    scope_blocks = _class_element_blocks(rendered, "scope-label")
    assert scope_blocks
    for block, direct_text in scope_blocks:
        assert not direct_text.strip(), (
            "scope labels must not contain direct raw text: "
            f"{direct_text!r}"
        )
        pairs = list(_ADJACENT_LANGUAGE_PAIR_RE.finditer(block))
        assert any(
            _normalized_html_text(match.group("en_body"))
            and _normalized_html_text(match.group("cn_body"))
            for match in pairs
        ), f"scope label lacks a nonempty adjacent EN/CN pair: {block!r}"


def test_static_controls_have_localized_aria_names(tmp_path: Path) -> None:
    rendered = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = rendered.split("<body>", 1)[1].split("<script>\n", 1)[0]

    assert 'aria-label="Close report navigation"' in visible
    assert 'placeholder="ID / variety / origin / VIVC"' in visible
    assert "function refreshStaticControlLabels" in APP_JS

    observed = _run_report_node(
        r"""
function node(attrs){
  return {
    attrs:attrs||{},
    classList:{contains:function(){return false;}},
    getAttribute:function(key){return this.attrs[key]||null;},
    setAttribute:function(key,value){this.attrs[key]=String(value);}
  };
}
function names(el){
  return {
    aria:el.attrs['aria-label']||null,
    title:el.attrs.title||null
  };
}
function snapshot(el){
  return JSON.parse(JSON.stringify(el.attrs));
}
var root=node();
var sidebar=node();
sidebar.id='report-sidebar';
var els={
  'sidebar-toggle':node({'aria-expanded':'true'}),
  'sample-slider':node(),
  'sample-search':node(),
  'admix-full-btn':node(),
  'admix-compact-btn':node(),
  'tree-circ-btn':node(),
  'tree-rect-btn':node()
};
var goButton=node(), findButton=node(), clearButton=node();
var kButtons=[2,3,4,5,6,7,8].map(function(k){
  return node({'data-k':String(k)});
});
var langControl=node(), themeControl=node();
var langButtons=['en','zh'].map(function(choice){
  return node({'data-lang-choice':choice});
});
var themeButtons=['system','light','dark'].map(function(choice){
  return node({'data-theme-choice':choice});
});
document={
  documentElement:root,
  getElementById:function(id){
    if(id==='report-sidebar') return sidebar;
    return els[id]||null;
  },
  querySelectorAll:function(selector){
    if(selector==='.browser-go') return [goButton];
    if(selector==='.sample-search-button') return [findButton];
    if(selector==='.clear-highlight') return [clearButton];
    if(selector==='.lang-control') return [langControl];
    if(selector==='.theme-control') return [themeControl];
    if(selector==='.lang-choice') return langButtons;
    if(selector==='.theme-choice') return themeButtons;
    if(selector==='.kbtn') return kButtons;
    if(selector==='.pca-axis-btn') return [];
    if(selector.indexOf('data-i18n-en')>=0) return [];
    return [];
  }
};
window={_gaLangReady:false};
langMode='en';
refreshStaticControlLabels();
setSidebarAccessibility(sidebar,els['sidebar-toggle'],false);
var enOpen=names(els['sidebar-toggle']);
setSidebarAccessibility(sidebar,els['sidebar-toggle'],true);
var enClosed=names(els['sidebar-toggle']);
var en={
  slider:snapshot(els['sample-slider']),
  search:snapshot(els['sample-search']),
  go:names(goButton),
  find:names(findButton),
  clear:names(clearButton),
  k:kButtons.map(names),
  lang:langButtons.map(names),
  theme:themeButtons.map(names),
  full:names(els['admix-full-btn']),
  compact:names(els['admix-compact-btn']),
  tree:[names(els['tree-circ-btn']),names(els['tree-rect-btn'])],
  sidebarOpen:enOpen,
  sidebarClosed:enClosed
};
setLang('zh',false);
setSidebarAccessibility(sidebar,els['sidebar-toggle'],false);
var zhOpen=names(els['sidebar-toggle']);
setSidebarAccessibility(sidebar,els['sidebar-toggle'],true);
var zhClosed=names(els['sidebar-toggle']);
var zh={
  slider:snapshot(els['sample-slider']),
  search:snapshot(els['sample-search']),
  go:names(goButton),
  find:names(findButton),
  clear:names(clearButton),
  k:kButtons.map(names),
  lang:langButtons.map(names),
  theme:themeButtons.map(names),
  full:names(els['admix-full-btn']),
  compact:names(els['admix-compact-btn']),
  tree:[names(els['tree-circ-btn']),names(els['tree-rect-btn'])],
  sidebarOpen:zhOpen,
  sidebarClosed:zhClosed
};
console.log(JSON.stringify({en:en,zh:zh}));
"""
    )

    assert observed["en"]["slider"] == {
        "aria-label": "Sample browser position",
        "title": "Browse panel samples",
    }
    assert observed["en"]["search"] == {
        "aria-label": "Search sample",
        "title": "Search by ID, variety, origin, or VIVC",
        "placeholder": "ID / variety / origin / VIVC",
    }
    assert observed["en"]["go"] == {
        "aria": "Go to selected sample",
        "title": "Go to selected sample",
    }
    assert observed["en"]["find"] == {
        "aria": "Find sample",
        "title": "Find sample",
    }
    assert observed["en"]["clear"] == {
        "aria": "Clear pinned sample",
        "title": "Clear pinned sample",
    }
    assert observed["en"]["k"] == [
        {"aria": f"Show ADMIXTURE K={k}", "title": f"Show ADMIXTURE K={k}"}
        for k in range(2, 9)
    ]
    assert observed["en"]["lang"] == [
        {"aria": "Use English", "title": "Use English"},
        {"aria": "Use Chinese", "title": "Use Chinese"},
    ]
    assert observed["en"]["theme"] == [
        {"aria": "Use system theme", "title": "Use system theme"},
        {"aria": "Use light theme", "title": "Use light theme"},
        {"aria": "Use dark theme", "title": "Use dark theme"},
    ]
    assert observed["en"]["full"] == {
        "aria": "Show full panel",
        "title": "Show full panel",
    }
    assert observed["en"]["compact"] == {
        "aria": "Show compact panel",
        "title": "Show compact panel",
    }
    assert observed["en"]["tree"] == [
        {"aria": "Show circular tree", "title": "Show circular tree"},
        {"aria": "Show rectangular tree", "title": "Show rectangular tree"},
    ]
    assert observed["en"]["sidebarOpen"] == {
        "aria": "Close report navigation",
        "title": "Hide",
    }
    assert observed["en"]["sidebarClosed"] == {
        "aria": "Open report navigation",
        "title": "Show",
    }

    assert observed["zh"]["slider"] == {
        "aria-label": "样本浏览位置",
        "title": "浏览面板样本",
    }
    assert observed["zh"]["search"] == {
        "aria-label": "搜索样本",
        "title": "按 ID、品种、产地或 VIVC 搜索",
        "placeholder": "ID / 品种 / 产地 / VIVC",
    }
    assert observed["zh"]["go"] == {
        "aria": "跳转到选中样本",
        "title": "跳转到选中样本",
    }
    assert observed["zh"]["find"] == {
        "aria": "查找样本",
        "title": "查找样本",
    }
    assert observed["zh"]["clear"] == {
        "aria": "清除已钉住样本",
        "title": "清除已钉住样本",
    }
    assert observed["zh"]["k"] == [
        {"aria": f"查看 ADMIXTURE K={k}", "title": f"查看 ADMIXTURE K={k}"}
        for k in range(2, 9)
    ]
    assert observed["zh"]["lang"] == [
        {"aria": "使用英文", "title": "使用英文"},
        {"aria": "使用中文", "title": "使用中文"},
    ]
    assert observed["zh"]["theme"] == [
        {"aria": "使用系统主题", "title": "使用系统主题"},
        {"aria": "使用浅色主题", "title": "使用浅色主题"},
        {"aria": "使用深色主题", "title": "使用深色主题"},
    ]
    assert observed["zh"]["full"] == {
        "aria": "显示完整面板",
        "title": "显示完整面板",
    }
    assert observed["zh"]["compact"] == {
        "aria": "显示紧凑面板",
        "title": "显示紧凑面板",
    }
    assert observed["zh"]["tree"] == [
        {"aria": "显示圆形树", "title": "显示圆形树"},
        {"aria": "显示矩形树", "title": "显示矩形树"},
    ]
    assert observed["zh"]["sidebarOpen"] == {
        "aria": "关闭报告导航",
        "title": "隐藏",
    }
    assert observed["zh"]["sidebarClosed"] == {
        "aria": "打开报告导航",
        "title": "显示",
    }
def test_dynamic_report_copy_has_localized_scope_and_status_pairs() -> None:
    observed = _run_report_node(
        r"""
var els={
  'report-meta':{innerHTML:''},
  'method-coverage':{innerHTML:''},
  'query-evidence':{innerHTML:''},
  'gs-pred':{innerHTML:''}
};
document={getElementById:function(id){return els[id]||null;}};
window={_authorMatchIds:[]};
D={
  query:'QUERY',
  report_meta:{
    report_id:'QUERY.sample-first-v2.report.html',
    query_id:'QUERY',
    source_sample_id:'SOURCE',
    generated_at_utc:'2026-09-17T00:00:00Z',
    panel_cache:{path:'results/cache/panel.npz',available:false},
    query_vcf:{path:'results/QUERY.vcf.gz',available:true,size:42},
    source_bam:{path:'results/bam/SOURCE.markdup.bam',available:true,size:7},
    source_damage_tsv:{path:'results/SOURCE.damage.tsv',available:false},
    shared_artifacts:{
      selection:{
        manhattan:{path:'results/selection/manhattan.json',available:true,size:1},
        locuszoom:{path:'results/selection/locuszoom.json',available:false}
      },
      gwas:{
        index:{path:'results/gwas/index.tsv',available:true,size:2},
        locuszoom:{path:'results/gwas/locuszoom.json',available:false}
      },
      gs:{index:{path:'results/gs/index.tsv',available:true,size:3}}
    }
  },
  method_coverage:{
    panel_genotype:{called:1,total:2,coverage:0.5},
    selection_locus_gt:{
      query_gt_called:0,query_gt_n:0,
      unavailable_reason:'no selection-window calls'
    },
    gwas_locus_gt:{
      query_gt_called:0,query_gt_n:0,
      unavailable_reason:'no GWAS-locus calls'
    },
    fstats:{query_called_sites:0,unavailable_reason:'no fstats query sites'},
    gs_predictions:[],
    damage:{
      available:false,source_sample_id:'SOURCE',
      path:'results/SOURCE.damage.tsv',path_available:false,
      unavailable_reason:'no damage profile'
    },
    gs:{available:false,unavailable_reason:'No per-query GS prediction available.'}
  },
  query_evidence:[{
    site:'2:5116947',
    trait:'OIV 225 colour',
    gene:'VvMybA1',
    query_gt:1,
    call_status:'called',
    evidence:'curated_locus',
    panel_context:{
      source:'MAS_LOCI',
      annotation:'Dong 2023 Chr2:5116947'
    }
  }],
  panel_trait_catalog:[],
  gwas_loci:[],
  gs_pred:[]
};
fillReportMeta();
fillMethodCoverage();
fillQueryEvidence();
var evidenceRows=els['query-evidence'].innerHTML.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/g)||[];
var evidenceRow=evidenceRows.filter(function(row){
  return row.indexOf('2:5116947')>=0;
})[0]||'';
console.log(JSON.stringify({
  meta:els['report-meta'].innerHTML,
  coverage:els['method-coverage'].innerHTML,
  evidence:els['query-evidence'].innerHTML+els['gs-pred'].innerHTML,
  evidenceRow:evidenceRow
}));
"""
    )

    assert "QUERY" in observed["meta"]
    assert "SOURCE" in observed["meta"]
    assert_dynamic_pair(observed["meta"], "Source library", "来源文库")
    assert_dynamic_pair(observed["meta"], "Query-derived", "查询样本来源")
    assert_dynamic_pair(observed["meta"], "2449 panel only", "仅 2449 面板")
    assert_dynamic_pair(observed["meta"], "available", "可用")
    assert_dynamic_pair(observed["meta"], "not available", "不可用")
    assert_dynamic_pair(
        observed["coverage"], "Query vs 2449 panel", "查询样本 vs 2449 面板"
    )
    assert_dynamic_pair(observed["coverage"], "Query-derived", "查询样本来源")
    assert_dynamic_pair(observed["evidence"], "Unavailable", "不可用")
    assert "2:5116947" in observed["evidenceRow"]
    assert_dynamic_pair(observed["evidenceRow"], "called", "已分型")
    assert_dynamic_pair(
        observed["evidenceRow"], "Query-derived", "查询样本来源"
    )


def test_language_toggle_preserves_bilingual_dynamic_content() -> None:
    observed = _run_report_node(
        r"""
function button(choice){
  return {
    attrs:{},
    getAttribute:function(key){
      return key==='data-lang-choice'?choice:(this.attrs[key]||null);
    },
    setAttribute:function(key,value){this.attrs[key]=String(value);}
  };
}
var coverage={innerHTML:''};
var root={
  attrs:{},
  setAttribute:function(key,value){this.attrs[key]=String(value);},
  getAttribute:function(key){return this.attrs[key]||null;}
};
var buttons=[button('en'),button('zh')];
document={
  documentElement:root,
  querySelectorAll:function(sel){
    return sel==='.lang-choice'?buttons:[];
  },
  getElementById:function(id){
    return id==='method-coverage'?coverage:null;
  }
};
window={_gaLangReady:true};
var store={
  saved:null,
  getItem:function(){return null;},
  setItem:function(key,value){
    if(key==='ga-lang') this.saved=String(value);
  }
};
globalThis.localStorage=store;
D={query:'QUERY',report_meta:{query_id:'QUERY',source_sample_id:'QUERY'},method_coverage:{}};
var rerenders=0;
var realRefresh=refreshLangContent;
refreshLangContent=function(){
  rerenders+=1;
  coverage.innerHTML='';
  realRefresh();
};
initLangController();
fillMethodCoverage();
coverage.innerHTML+='<span class="en">STALE COPY</span><span class="cn">旧 DOM</span>';
var before=coverage.innerHTML;
setLang('zh',true);
console.log(JSON.stringify({
  before:before,
  after:coverage.innerHTML,
  staleAfter:coverage.innerHTML.indexOf('STALE COPY')>=0,
  rerenders:rerenders,
  lang:root.getAttribute('data-lang'),
  htmlLang:root.getAttribute('lang'),
  saved:store.saved
}));
"""
    )

    assert "Query-derived" in observed["before"]
    assert observed["staleAfter"] is False
    assert observed["rerenders"] == 1
    assert observed["lang"] == "zh"
    assert observed["htmlLang"] == "zh-CN"
    assert observed["saved"] == "zh"
    assert_dynamic_pair(observed["after"], "Query-derived", "查询样本来源")


def test_empty_and_error_messages_have_en_cn_forms() -> None:
    observed = _run_report_node(
        r"""
function plotNode(){
  return {
    innerHTML:'',
    style:{},
    clientWidth:500,
    clientHeight:500,
    classList:{toggle:function(){}}
  };
}
var els={
  render:plotNode(),
  'plot-pca':plotNode(),
  'plot-tree':plotNode(),
  'plot-damage':plotNode(),
  'query-evidence':plotNode(),
  'gs-pred':plotNode()
};
document={
  getElementById:function(id){return els[id]||null;},
  querySelectorAll:function(){return [];}
};
window={};
D={
  query:'QUERY',
  method_coverage:{
    selection_locus_gt:{unavailable_reason:'no selection-window calls'},
    gwas_locus_gt:{unavailable_reason:'no GWAS-locus calls'},
    gs:{unavailable_reason:'No per-query GS prediction available.'}
  },
  query_evidence:[],
  gs_pred:[]
};
QUERY='QUERY';
plotlyUnavailable(els.render,'PCA plot');
window.Plotly={newPlot:function(){},purge:function(){}};
loadPCA();
loadTree();
loadDamage();
fillQueryEvidence();
console.log(JSON.stringify({
  rendering:els.render.innerHTML,
  pca:els['plot-pca'].innerHTML,
  tree:els['plot-tree'].innerHTML,
  damage:els['plot-damage'].innerHTML,
  queryEvidence:els['query-evidence'].innerHTML,
  gsPred:els['gs-pred'].innerHTML
}));
"""
    )

    assert_error_language_pair(
        observed["rendering"], "Plotly.js unavailable", "Plotly.js 不可用"
    )
    assert_error_language_pair(observed["pca"], "No PCA", "没有 PCA")
    assert_error_language_pair(observed["tree"], "No NJ tree", "没有 NJ 树")
    assert_error_language_pair(
        observed["damage"], "No damage profile", "没有损伤谱"
    )
    assert_error_language_pair(
        observed["queryEvidence"], "Unavailable", "不可用"
    )
    assert_error_language_pair(
        observed["gsPred"], "Unavailable", "不可用"
    )


def _purity_branch_probe() -> dict:
    return _run_report_node(
        r"""
function pairOf(raw){
  var p=formatPurityDisplay(raw);
  return {en:p.en, zh:p.zh, raw:raw};
}
var raws={
  insufficient:'Purity: insufficient calls.',
  warn:'Purity WARNING: excess het=0.400 (panel mean 0.200, z=4.0) — possible mixture.',
  warnDepth:'Purity WARNING: excess het=0.400 (panel mean 0.200, z=4.0) — possible mixture. Low mean depth (2.1×) can under-call heterozygotes — not necessarily genetic purity.',
  lowDepth:'Purity note: low het=0.034 (panel mean 0.260). Low mean depth (0.6×) can under-call heterozygotes — not necessarily genetic purity.',
  withinDepth:'Purity OK: het=0.123 within panel range (mean 0.200 ± 0.050). Low mean depth (2.1×) can under-call heterozygotes — not necessarily genetic purity.'
};
var concl={innerHTML:''}, note={innerHTML:'', textContent:''};
document={getElementById:function(id){
  if(id==='concl-list') return concl;
  if(id==='purity-note') return note;
  return null;
}};
D={purity:raws.withinDepth, conclusions:[raws.insufficient, raws.warn, raws.lowDepth, raws.withinDepth]};
fillConclusions();
fillExtra();
var out={
  raw:D.purity,
  note:String(note.innerHTML||note.textContent||''),
  concl:concl.innerHTML,
  cleaned:cleanConclusion(raws.withinDepth),
  pair:typeof cleanConclusionPair==='function'?cleanConclusionPair(raws.warn):null
};
Object.keys(raws).forEach(function(k){ out[k]=pairOf(raws[k]); });
console.log(JSON.stringify(out));
"""
    )


def test_purity_copy_is_heterozygosity_screen_not_purity_call() -> None:
    assert "function formatPurityDisplay" in APP_JS
    observed = _purity_branch_probe()
    assert observed["raw"].startswith("Purity OK:")
    assert observed["pair"] and observed["pair"]["zh"]
    assert "span class=\"cn\"" in observed["concl"]
    assert "杂合度筛查" in observed["concl"]
    assert_dynamic_pair(observed["note"], "Heterozygosity screen", "杂合度筛查")
    assert_dynamic_pair(observed["concl"], "Heterozygosity screen", "杂合度筛查")

    insuff = observed["insufficient"]
    assert "insufficient" in insuff["en"].lower()
    assert "分型不足" in insuff["zh"]
    assert "under-call" not in insuff["en"].lower()
    assert "低估" not in insuff["zh"]

    warn = observed["warn"]
    assert "0.400" in warn["en"] and "0.200" in warn["en"] and "4.0" in warn["en"]
    assert "above" in warn["en"]
    assert "高于" in warn["zh"]
    assert "mixture" in warn["en"].lower() or "sample-level" in warn["en"].lower()
    assert "混合" in warn["zh"] or "样品层面" in warn["zh"]
    assert "under-call" not in warn["en"].lower()
    assert "低估" not in warn["zh"]
    assert "Low mean depth" not in warn["en"]

    warn_d = observed["warnDepth"]
    assert "mixture" in warn_d["en"].lower() or "sample-level" in warn_d["en"].lower()
    assert "2.1" in warn_d["en"] and "2.1" in warn_d["zh"]
    assert "under-call" in warn_d["en"].lower()
    assert "低估" in warn_d["zh"]

    low = observed["lowDepth"]
    assert "0.034" in low["en"] and "0.260" in low["en"]
    assert "below" in low["en"]
    assert "低于" in low["zh"]
    assert "0.6" in low["en"] and "0.6" in low["zh"]
    assert "under-call" in low["en"].lower()
    assert "低估" in low["zh"]

    within = observed["withinDepth"]
    assert "0.123" in within["en"] and "0.200" in within["en"] and "0.050" in within["en"]
    assert "within" in within["en"]
    assert "分布内" in within["zh"] or "之内" in within["zh"]
    assert "2.1" in within["en"]
    assert "under-call" in within["en"].lower()
    assert "低估" in within["zh"]

    for key in ("insufficient", "warn", "warnDepth", "lowDepth", "withinDepth"):
        text_en = observed[key]["en"]
        text_zh = observed[key]["zh"]
        assert text_en.startswith("Heterozygosity screen")
        assert text_zh.startswith("杂合度筛查")
        assert "purity estimate" in text_en.lower()
        assert "纯度估计" in text_zh
        assert "Purity OK" not in text_en
        assert "purity call" not in text_en.lower()
        assert " 相对" not in text_zh
        assert "杂合度筛查：" not in text_zh or "杂合度筛查，" in text_zh


def test_selection_labels_use_simplified_fst_and_distinguish_metrics(
    tmp_path: Path,
) -> None:
    html = APP_JS
    assert "simplified Fst (Grp vs rest)" in html
    assert "简化 Fst（Grp 对其余样品）" in html
    assert "Fst among all Grps" in html
    assert "全体 Grp 的 Fst" in html
    assert "windowed heterozygosity" in html
    assert "窗口杂合度" in html
    assert "mean_fst_vs_rest" in html
    visible = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text().split("<script>\n", 1)[0]
    sel = _element_block(visible, "sel")
    assert "simplified Fst (Grp vs rest)" in sel
    assert "简化 Fst（Grp 对其余样品）" in sel
    assert "Fst among all Grps" in sel
    assert "全体 Grp 的 Fst" in sel
    assert "windowed heterozygosity" in sel
    assert "窗口杂合度" in sel
    assert "het inside this Grp" not in sel
    assert "het ≤5th" not in sel
    assert "het ≤5%" not in sel
    assert "Weir" not in sel
    observed = _run_report_node(
        r"""
function node(){
  return {
    innerHTML:'', value:'', options:[], data:null, on:function(){},
    querySelectorAll:function(){return [];},
    appendChild:function(child){this.options.push(child);},
    scrollIntoView:function(){}
  };
}
var table=node(), group=node(), manh=node(), heat=node(), sweep=node();
document={
  getElementById:function(id){
    if(id==='sel-table') return table;
    if(id==='sel-manh-grp') return group;
    if(id==='plot-sel-manh') return manh;
    if(id==='plot-sel-heat') return heat;
    if(id==='sel-sweep-table') return sweep;
    return null;
  },
  createElement:function(){return {value:'',textContent:''};}
};
window={Plotly:{newPlot:function(el,data,layout){el._layout=layout; el._data=data;}, purge:function(){}}};
globalThis.Plotly=window.Plotly;
D={
  selection_named:[{name:'SDR_trait_locus',chrom:'2',start:1,end:2,n_sites:3,mean_het:'0.10',mean_fst:'0.02'}],
  selection_by_grp:[{grp:'CG1',n_samples:10,name:'SDR_trait_locus',n_sites:3,mean_het:'0.11',mean_fst_vs_rest:'0.04'}],
  selection_loci:[], selection_s29_scatter:{}, selection_vs_summary:[],
  selection_manhattan:{
    x:[1], chrom:['2'], pos:[100], fst:[0.2], het:[0.3],
    fst_by_grp:{CG1:[0.4]}, het_by_grp:{CG1:[0.5]},
    sweep_by_grp:{CG1:[0]}, sweep_thr:{CG1:{n:1,fst95:0.30,het05:0.12}},
    sweeps:{CG1:[{chrom:'2',pos:100,fst:0.4,het:0.12}]}
  },
  selection_heatmap:{
    grp:['CG1'], window:['SDR_trait_locus'], window_lab:['SDR'],
    chrom:['2'], start:[1], end:[2], n_sites:[3],
    fst:[[0.04]], het:[[0.11]]
  },
  selection_fst_het_scatter:{},
  f3:[], f4:[], f3_out:[], outgroup_n:0
};
selManhGrp='CG1'; selManhMetric='fst'; selHeatMetric='fst';
fillSelFstats();
fillSelSweepTable();
drawSelManhattan();
drawSelHeat();
var sweepHtml=sweep.innerHTML;
selManhGrp='overall';
drawSelManhattan();
console.log(JSON.stringify({
  table:table.innerHTML,
  sweep:sweepHtml,
  options:group.options.map(function(o){return o.textContent;}),
  grpY: (function(){
    selManhGrp='CG1'; drawSelManhattan();
    return (document.getElementById('plot-sel-manh')._layout||{}).yaxis||{};
  })().title,
  grpTitle:(function(){
    selManhGrp='CG1'; drawSelManhattan();
    return (document.getElementById('plot-sel-manh')._layout||{}).title||{};
  })(),
  overallY:(function(){
    selManhGrp='overall'; drawSelManhattan();
    return (document.getElementById('plot-sel-manh')._layout||{}).yaxis||{};
  })().title,
  heatTitle:(document.getElementById('plot-sel-heat')._layout||{}).title
}));
"""
    )
    assert "simplified Fst (Grp vs rest)" in observed["table"]
    assert "简化 Fst（Grp 对其余样品）" in observed["table"]
    assert "Fst among all Grps" in observed["table"]
    assert "全体 Grp 的 Fst" in observed["table"]
    assert "0.04" in observed["table"] and "0.02" in observed["table"]
    assert any("simplified Fst" in opt for opt in observed["options"])
    assert any("Fst among all Grps" in opt for opt in observed["options"])
    grp_y = observed["grpY"]
    overall_y = observed["overallY"]
    grp_y_text = grp_y if isinstance(grp_y, str) else (grp_y or {}).get("text", grp_y)
    overall_y_text = (
        overall_y
        if isinstance(overall_y, str)
        else (overall_y or {}).get("text", overall_y)
    )
    assert "simplified Fst" in str(grp_y_text)
    assert "Fst among all Grps" in str(overall_y_text)
    assert "Weir" not in observed["table"]
    grp_title = observed["grpTitle"]
    grp_title_text = (
        grp_title
        if isinstance(grp_title, str)
        else (grp_title or {}).get("text", grp_title)
    )
    assert "windowed heterozygosity" in str(grp_title_text)
    assert "het ≤5th" not in str(grp_title_text)
    assert "0.30" in observed["sweep"] and "0.12" in observed["sweep"]
    assert "windowed heterozygosity" in observed["sweep"]
    assert "窗口杂合度" in observed["sweep"]
    assert "het in " not in observed["sweep"]
    assert "组内 het" not in observed["sweep"]


def test_gs_copy_marks_oiv225_as_report_policy() -> None:
    assert "rankable under this report policy" in APP_JS
    assert "报告策略" in APP_JS
    assert "panel CV r" in APP_JS
    assert "panel 交叉验证 r" in APP_JS
    assert '<th scope="col">CV r</th>' not in APP_JS
    assert "CV r 偏低" not in APP_JS
    assert "Still not an observed phenotype" not in APP_JS
    assert "仍然不是观测表型" not in APP_JS
    observed = _run_report_node(
        r"""
var evidence={innerHTML:''}, gs={innerHTML:''}, index={innerHTML:''};
document={getElementById:function(id){
  if(id==='query-evidence') return evidence;
  if(id==='gs-pred') return gs;
  if(id==='gs-index') return index;
  return null;
}};
D={
  query:'QUERY',
  query_evidence:[],
  panel_trait_catalog:[],
  gwas_loci:[],
  gwas_index:[{trait:'OIV 225',slug:'OIV_225_bin',n:382,case_n:173,control_n:209}],
  gs_pred:[{
    trait:'OIV 225', slug:'OIV_225_bin', scale:'binary',
    pred:0.62, coverage:0.8, cv_r:0.6246234136298449, flag:'ok'
  }],
  gs_index:[{source:'panel',trait:'OIV 225',best_model:'rrBLUP',cv_r:'0.625',n:382}],
  method_coverage:{gs:{available:true, unavailable_reason:''}}
};
fillQueryEvidence();
fillExtra();
console.log(JSON.stringify({
  note:gsTraitNote({trait:'OIV 225',slug:'OIV_225_bin',scale:'binary',cv_r:0.6246234136298449}),
  noteNoCv:gsTraitNote({trait:'OIV 225',slug:'OIV_225_bin',scale:'binary'}),
  gs:gs.innerHTML,
  index:index.innerHTML,
  ok:gsFlagHtml('ok'),
  low:gsFlagHtml('low_cv_r')
}));
"""
    )
    assert "rankable under this report policy" in observed["note"]
    assert "报告策略" in observed["note"]
    assert "0.625" in observed["note"]
    assert "≈ 0.62" not in observed["note"]
    assert "≈ 0.62" not in observed["gs"]
    assert "0.625" in observed["gs"]
    assert "0.62" not in observed["noteNoCv"]
    assert "≈ 0.62" not in observed["noteNoCv"]
    assert "decision-grade" not in observed["note"].lower()
    assert "universal" not in observed["note"].lower()
    assert "model score" in observed["gs"].lower()
    assert "phenotype validation" in observed["gs"] or "表型验证" in observed["gs"]
    assert "row-specific" in observed["gs"].lower() or "本行" in observed["gs"] or "row" in observed["gs"].lower()
    assert "panel CV r" in observed["index"]
    assert "panel 交叉验证 r" in observed["index"]
    assert ">CV r<" not in observed["index"]
    assert "panel CV r" in observed["ok"].lower() or "panel 交叉验证 r" in observed["ok"]
    assert "Still not an observed phenotype" not in observed["ok"]
    assert "仍然不是观测表型" not in observed["ok"]
    assert "panel cv r" in observed["low"].lower()
    assert "panel 交叉验证 r" in observed["low"]
    assert "CV r 偏低" not in observed["low"]
    assert_dynamic_pair(observed["note"], "report policy", "报告策略")
    assert_dynamic_pair(observed["index"], "panel CV r", "panel 交叉验证 r")


def test_oiv241_copy_uses_no_locus_overlap_language(tmp_path: Path) -> None:
    observed = _run_report_node(
        r"""
D={gwas_index:[], gwas_loci:[]};
console.log(JSON.stringify({
  note:gsTraitNote({trait:'OIV 241',slug:'OIV_241_bin',scale:'binary'})
}));
"""
    )
    visible = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text().split("<script>\n", 1)[0]
    named = _element_block(visible, "named-window-why")
    assert "No OIV 241 locus overlap found in the panel GWAS" in observed["note"]
    assert "panel GWAS 未发现 OIV 241 位点重合" in observed["note"]
    assert "No OIV 241 locus overlap found in the panel GWAS" in named
    assert "panel GWAS 未发现 OIV 241 位点重合" in named
    for text in (observed["note"], named):
        lowered = text.lower()
        assert "agl11" not in lowered
        assert "seedless" not in lowered
        assert "无核" not in text
        assert "recovered" not in lowered
        assert "找回" not in text


def test_pca_copy_separates_gcta_axes_from_lsq_projection(tmp_path: Path) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = html.split("<script>\n", 1)[0]
    pca = _element_block(visible, "pca")
    assert "GCTA64 GRM-PCA" in pca
    assert "least-squares projected" in pca or "least-squares" in pca
    assert "最小二乘" in pca
    assert "doi.org/10.1016/j.ajhg.2010.11.011" in pca
    assert "doi.org/10.1371/journal.pgen.0020190" in pca
    assert "smartPCA" not in pca
    assert "lsqproject" not in pca
    observed = _run_report_node(
        r"""
var raw='smartPCA lsqproject (cached evec)';
D={pca_method:raw};
langMode='en';
var enSmart=pcaMethodLabel(raw);
var enLsq=pcaMethodLabel('lsqproject onto frozen axes');
langMode='zh';
var zhSmart=pcaMethodLabel(raw);
var zhLsq=pcaMethodLabel('lsqproject onto frozen axes');
langMode='en';
console.log(JSON.stringify({
  raw:D.pca_method,
  gcta:pcaMethodLabel('GCTA64 GRM-PCA (panel167k_nogwas)'),
  empty:pcaMethodLabel(''),
  enSmart:enSmart,
  enLsq:enLsq,
  zhSmart:zhSmart,
  zhLsq:zhLsq
}));
"""
    )
    assert observed["raw"] == "smartPCA lsqproject (cached evec)"
    assert "GCTA64" in observed["gcta"]
    assert "smartPCA" not in observed["gcta"]
    assert "least-squares" not in observed["gcta"].lower()
    assert observed["empty"] == "—"
    for label in (observed["enSmart"], observed["enLsq"]):
        assert "least-squares projection" in label
        assert "smartPCA" not in label
        assert "lsqproject" not in label
    for label in (observed["zhSmart"], observed["zhLsq"]):
        assert "最小二乘投影" in label
        assert "smartPCA" not in label
        assert "lsqproject" not in label


def test_sdr_copy_separates_h1_h5_literature_from_panel_annotation(
    tmp_path: Path,
) -> None:
    html = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    visible = html.split("<script>\n", 1)[0]
    named = _element_block(visible, "named-window-why")
    assert "H1–H5" in named or "H1-H5" in named
    assert "Dong" in named
    assert "literature" in named.lower() or "文献" in named
    assert "panel annotation" in named.lower() or "面板注释" in named
    observed = _run_report_node(
        r"""
var traits={innerHTML:''};
document={getElementById:function(id){return id==='trait-table'?traits:null;}};
D={
  panel_trait_catalog:[
    {
      site:'2:14277567', trait:'OIV 151 flower sex', gene:'SDR',
      note:'from_gwas_set_annotated; Panel SDR tag; Science sex = haplotype (H1/H2), not this SNP alone'
    },
    {
      site:'1:15057634', trait:'OIV 225', gene:'Vvsyl01G001227',
      note:'from_gwas_set_annotated'
    }
  ]
};
fillExtra();
console.log(JSON.stringify({
  note:gsTraitNote({trait:'OIV 151',slug:'OIV_151_bin',scale:'binary'}),
  traits:traits.innerHTML
}));
"""
    )
    assert "Dong" in observed["note"]
    assert "H1" in observed["note"] and "H5" in observed["note"]
    assert "literature" in observed["note"].lower() or "文献" in observed["note"]
    assert "panel annotation" in observed["note"].lower() or "面板注释" in observed["note"]
    sdr_cell = observed["traits"]
    assert "panel annotation" in sdr_cell.lower() or "面板注释" in sdr_cell
    assert "from_gwas_set_annotated; Panel SDR tag; Science sex = haplotype (H1/H2)" not in sdr_cell
    assert "Science sex = haplotype" not in sdr_cell
    assert "H1–H5" in sdr_cell or "H1-H5" in sdr_cell or "H1–H5" in observed["note"]
    assert "来源元数据" in sdr_cell
    assert "from_gwas_set_annotated" in sdr_cell


def _sidecar_payload(sample: str) -> dict:
    path = ROOT / "results" / f"{sample}.sample-first-v2.report.data.json"
    return json.loads(path.read_text())


def test_hun89_and_ages_conclusions_are_bilingual_in_zh(tmp_path: Path) -> None:
    ages = _sidecar_payload("Ages")
    hun = _sidecar_payload("HUN89_query")
    observed = _run_report_node(
        "var ages="
        + json.dumps(
            {
                "purity": ages["purity"],
                "conclusions": ages["conclusions"],
                "report_meta": {"library_class": ages["report_meta"]["library_class"]},
            },
            ensure_ascii=False,
        )
        + ";\nvar hun="
        + json.dumps(
            {
                "purity": hun["purity"],
                "conclusions": hun["conclusions"],
                "report_meta": {"library_class": hun["report_meta"]["library_class"]},
            },
            ensure_ascii=False,
        )
        + r""";
function render(payload){
  var concl={innerHTML:''};
  document={getElementById:function(id){return id==='concl-list'?concl:null;}};
  D=payload;
  fillConclusions();
  return concl.innerHTML;
}
console.log(JSON.stringify({ages:render(ages), hun:render(hun)}));
"""
    )
    ages_html = render_interactive_dashboard(
        replace(
            _minimal_render_bundle(),
            sample="Ages",
            purity_note=ages["purity"],
            conclusions=list(ages["conclusions"]),
            report_meta={"library_class": "ancient", "query_id": "Ages"},
        ),
        tmp_path / "ages.html",
        ROOT,
    ).read_text()
    hun_html = render_interactive_dashboard(
        replace(
            _minimal_render_bundle(),
            sample="HUN89_query",
            purity_note=hun["purity"],
            conclusions=list(hun["conclusions"]),
            report_meta={"library_class": "modern", "query_id": "HUN89_query"},
        ),
        tmp_path / "hun.html",
        ROOT,
    ).read_text()
    assert '"library_class": "ancient"' in ages_html
    assert '"library_class": "modern"' in hun_html
    for label, html, payload in (
        ("Ages", observed["ages"], ages),
        ("HUN89_query", observed["hun"], hun),
    ):
        assert html.count("<li>") >= 8, label
        assert 'class="en"' in html and 'class="cn"' in html
        assert "杂合度筛查" in html
        assert "参考面板" in html or "面板" in html
        for token in ("0.034", "0.260", "GM17", "K7/CG5") if label == "Ages" else (
            "0.301",
            "HUN89",
            "K5/CG4",
            "0.6246234136298449",
        ):
            assert token in html
        assert "Purity OK" not in html
        assert "Purity note" not in html
        raw_join = " ".join(payload["conclusions"])
        if "Damage:" in raw_join and payload["report_meta"]["library_class"] != "modern":
            assert "损伤" in html or "C→T" in html
        if payload["report_meta"]["library_class"] == "modern":
            assert "现代" in html
            assert not re.search(r"<li>[^<]*class=\"en\">Damage", html)
        assert_dynamic_pair(html, "Heterozygosity screen", "杂合度筛查")


_QUERY_META_STALE_EN = (
    "Field",
    "Value",
    "Sample",
    "Mode",
    "Variety",
    "Origin",
    "Date / period",
    "Material",
    "Contact / lab",
    "Notes",
    "Country",
    "Use",
    "Taxon",
    "Contributor",
    "Wild",
    "Flower sex",
    "Skin colour",
    "Muscat",
    "PO partners",
    "Clone of",
    "Dominant K=8",
    "PCA method",
    "In panel",
    "labelled",
    "from author origin",
    "Panel matches from author record",
    "No 2449 label matches",
)


def _assert_no_stale_english(html: str) -> None:
    visible = _zh_visible_copy(html)
    for label in _QUERY_META_STALE_EN:
        assert label not in visible, f"stale English label still visible: {label!r}"


def test_query_meta_sample_and_population_tables_are_bilingual_in_zh() -> None:
    observed = _run_report_node(
        r"""
function box(){
  return {
    innerHTML:'',
    querySelectorAll:function(){return [];},
    addEventListener:function(){}
  };
}
var meta=box();
var store={};
window={};
document={getElementById:function(id){return id==='query-meta'?meta:null;}};
localStorage={
  getItem:function(k){return store[k]||null;},
  setItem:function(k,v){store[k]=String(v);}
};
QUERY='HUN89_query';
SROWS=[
  {iid:'HUN89',acc:'SZEKSZARDI',origin:'HUNGARY',geo:'EUR',con:'HUN',grp:'CG4',qvals:{'8_dom':'CG4'}},
  {iid:'HUN01',acc:'FURMINT',origin:'HUNGARY',geo:'EUR',con:'HUN',grp:'CG4',qvals:{'8_dom':'CG4'}}
];
D={
  query:'HUN89_query',
  pca_method:'GCTA64',
  query_meta:{
    name:'SZEKSZARDI', origin:'HUNGARY', geo:'', con:'',
    vivc:'12144', uti:'WINE', taxon:'Vitis vinifera',
    contributor:'PANEL', wild:'no', sex:'H', color:'B',
    muscat:'no', po:'PO1', clone_of:'CL1', grp:'CG4',
    q8_dom:'CG4', pc1:0.111, pc2:0.222, pc3:0.333,
    pca_method:'GCTA64', acc_local:'local-acc'
  }
};
store['ga-author:HUN89_query']=JSON.stringify({
  mode:'sample',
  sample:{
    iid:'HUN89_query', name:'Furmint', origin:'HUNGARY',
    date:'2020', material:'leaf', contact:'Lab A', notes:'keep-note'
  },
  rows:[]
});
langMode='zh';
fillQueryMeta();
var sample=meta.innerHTML;
store['ga-author:HUN89_query']=JSON.stringify({
  mode:'population',
  sample:{iid:'HUN89_query',name:'Furmint',origin:'HUNGARY',date:'2020',material:'leaf',contact:'Lab A',notes:'keep-note'},
  rows:[
    {iid:'HUN89',name:'Furmint',origin:'Tokaj',date:'2020',notes:'keep-row'},
    {iid:'OUT1',name:'OutX',origin:'France',date:'',notes:''}
  ]
});
fillQueryMeta();
console.log(JSON.stringify({sample:sample, population:meta.innerHTML}));
"""
    )
    sample = observed["sample"]
    population = observed["population"]
    assert_dynamic_pair(sample, "Query metadata", "查询元数据")
    assert_dynamic_pair(sample, "Field", "字段")
    assert_dynamic_pair(sample, "Value", "值")
    for english, chinese in (
        ("Sample", "样品"),
        ("Variety", "品种"),
        ("Origin", "来源"),
        ("Date / period", "年代"),
        ("Material", "材料"),
        ("Contact / lab", "联系人 / 实验室"),
        ("Notes", "备注"),
        ("Country", "国家"),
        ("Use", "用途"),
        ("Taxon", "分类单元"),
        ("Contributor", "提供者"),
        ("Wild", "野生"),
        ("Flower sex", "花性"),
        ("Skin colour", "果皮颜色"),
        ("Muscat", "麝香"),
        ("PO partners", "亲子配对"),
        ("Clone of", "无性系来源"),
        ("Grp", "组别"),
        ("Dominant K=8", "主导 K=8"),
        ("PCA method", "PCA 方法"),
    ):
        assert_dynamic_pair(sample, english, chinese)
    assert "HUN89_query" in sample
    assert "SZEKSZARDI" in sample
    assert "keep-note" in sample
    assert "local-acc" in sample
    assert "12144" in sample
    assert "来自作者来源" in sample
    assert "作者记录匹配的面板样品" in sample
    assert "HUN89" in sample
    _assert_no_stale_english(sample)
    assert "from author origin" not in _zh_visible_copy(sample)

    assert_dynamic_pair(population, "Mode", "模式")
    assert_dynamic_pair(population, "Population", "群体")
    assert_dynamic_pair(population, "ID", "编号")
    assert_dynamic_pair(population, "Variety", "品种")
    assert_dynamic_pair(population, "In panel", "在面板中")
    assert "已标注" in population
    assert "是" in population
    assert "否" in population
    assert "Furmint" in population
    assert "Tokaj" in population
    assert "2020" in population
    assert 'data-iid="HUN89"' in population
    assert "下方 ADMIXTURE / PCA 针对" in population
    assert "HUN89_query" in population
    _assert_no_stale_english(population)
    assert "labelled" not in _zh_visible_copy(population)
    assert "In panel" not in _zh_visible_copy(population)


def test_author_intake_population_labels_refresh_in_zh() -> None:
    observed = _run_report_node(
        r"""
function box(){
  return {
    innerHTML:'',
    nodes:[],
    querySelectorAll:function(sel){
      if(sel==='.author-mode button' || sel==='input,textarea' || sel==='.author-del') return this.nodes;
      return [];
    },
    querySelector:function(){return null;},
    addEventListener:function(){}
  };
}
var intake=box();
var meta=box();
var store={};
var root={attrs:{},setAttribute:function(k,v){this.attrs[k]=String(v);},getAttribute:function(k){return this.attrs[k]||null;}};
document={
  documentElement:root,
  getElementById:function(id){
    if(id==='author-intake') return intake;
    if(id==='query-meta') return meta;
    return null;
  },
  querySelectorAll:function(){return [];}
};
window={_gaLangReady:true};
localStorage={
  getItem:function(k){return store[k]||null;},
  setItem:function(k,v){store[k]=String(v);}
};
QUERY='HUN89_query';
SROWS=[{iid:'HUN89',acc:'SZEKSZARDI',origin:'HUNGARY',geo:'EUR',con:'HUN',grp:'CG4'}];
D={query:'HUN89_query',query_meta:{name:'SZEKSZARDI',origin:'HUNGARY'},pca_method:'GCTA64'};
store['ga-author:HUN89_query']=JSON.stringify({
  mode:'population',
  sample:{iid:'HUN89_query',name:'Furmint',origin:'HUNGARY',date:'2020',material:'leaf',contact:'Lab A',notes:'keep-note'},
  rows:[{iid:'HUN89',name:'Furmint',origin:'Tokaj',date:'2020',notes:'keep-row'}]
});
fillConclusions=function(){}; fillIbsKinship=function(){};
fillHeroStats=function(){}; fillQuerySnapshot=function(){ fillQueryMeta(); };
fillReportMeta=function(){}; fillMethodCoverage=function(){};
fillQueryEvidence=function(){}; fillQc=function(){}; fillCloneTable=function(){};
fillExtra=function(){}; fillSelFstats=function(){}; enhanceReportTables=function(){};
pairLangBlocks=function(){}; loadPCA=function(){}; loadPCA3d=function(){};
loadBar=function(){}; loadTree=function(){}; loadDamage=function(){};
langMode='en';
fillAuthorIntake();
var before=intake.innerHTML;
setLang('zh',false);
console.log(JSON.stringify({
  before:before,
  intake:intake.innerHTML,
  meta:meta.innerHTML,
  lang:root.getAttribute('data-lang')
}));
"""
    )
    assert observed["lang"] == "zh"
    assert "Furmint" in observed["intake"]
    assert "keep-row" in observed["intake"]
    assert "HUN89" in observed["intake"]
    assert "样本编号" in observed["intake"]
    assert "品种或编号" in observed["intake"]
    assert "来源或遗址" in observed["intake"]
    assert "年代" in observed["intake"]
    assert "备注" in observed["intake"]
    assert 'title="移除"' in observed["intake"] or "aria-label=\"移除\"" in observed["intake"]
    assert "Sample ID" not in _zh_visible_copy(observed["intake"])
    assert "Variety / accession" not in _zh_visible_copy(observed["intake"])
    assert "Remove" not in _zh_visible_copy(observed["intake"])
    assert "Furmint" in observed["meta"]
    assert "Tokaj" in observed["meta"]
    assert "2020" in observed["meta"]
    assert_dynamic_pair(observed["meta"], "In panel", "在面板中")
    _assert_no_stale_english(observed["meta"])


def test_shipped_v2_artifacts_lock_modern_ancient_gs_methods_and_downloads() -> None:
    hun_sidecar = ROOT / "results" / "HUN89_query.sample-first-v2.report.data.json"
    ages_sidecar = ROOT / "results" / "Ages.sample-first-v2.report.data.json"
    hun_html_path = ROOT / "results" / "HUN89_query.sample-first-v2.report.html"
    ages_html_path = ROOT / "results" / "Ages.sample-first-v2.report.html"
    hun = json.loads(hun_sidecar.read_text(encoding="utf-8"))
    ages = json.loads(ages_sidecar.read_text(encoding="utf-8"))
    hun_html = hun_html_path.read_text(encoding="utf-8")
    ages_html = ages_html_path.read_text(encoding="utf-8")

    assert hun["query"] == "HUN89_query"
    assert hun["report_meta"]["query_id"] == "HUN89_query"
    assert hun["report_meta"]["source_sample_id"] == "HUN89"
    assert hun["report_meta"]["library_class"] == "modern"
    assert hun["report_meta"]["library_type"] == "pe"
    assert (hun.get("method_coverage") or {}).get("gs", {}).get("available") is True
    assert len(hun.get("gs_pred") or []) == 8

    assert ages["query"] == "Ages"
    assert ages["report_meta"]["query_id"] == "Ages"
    assert ages["report_meta"]["source_sample_id"] == "Ages"
    assert ages["report_meta"]["library_class"] == "ancient"
    assert ages["report_meta"]["library_type"] == "adna"
    assert (ages.get("method_coverage") or {}).get("gs", {}).get("available") is False
    assert len(ages.get("gs_pred") or []) == 0
    reason = str((ages.get("method_coverage") or {}).get("gs", {}).get("unavailable_reason") or "")
    assert re.search(r"no per-(query|sample) GS prediction available", reason, re.I)

    hun_embedded = _embedded_dashboard_payload(hun_html)
    ages_embedded = _embedded_dashboard_payload(ages_html)
    assert hun_embedded == hun
    assert ages_embedded == ages
    assert hun_embedded["methods_html"] == hun["methods_html"]
    assert ages_embedded["methods_html"] == ages["methods_html"]

    hun_damage = _element_block(hun_html, "damage")
    ages_damage = _element_block(ages_html, "damage")
    assert 'data-library-class="modern"' in hun_damage
    assert 'class="is-modern-library"' in hun_damage
    assert 'data-library-class="ancient"' in ages_damage
    assert "is-modern-library" not in ages_damage
    ages_guide = _element_block(ages_html, "damage-guide")
    ages_methods = _element_block(ages_html, "methods")
    ages_context = ages_guide + ages_methods + str(ages.get("methods_html") or "")
    assert "doi.org/10.1093/bioinformatics/btr347" in ages_context
    assert "doi.org/10.1093/bioinformatics/btt193" in ages_context

    for methods in (
        hun["methods_html"],
        ages["methods_html"],
        hun_html,
        ages_html,
    ):
        assert re.search(r"<h2[^>]*>Reproduce", methods) is None
        assert "Wall time on MBP" not in methods
        assert "Methods not used and why" not in methods
        assert "未采用方法与理由" not in methods

    for sample, payload in (("HUN89_query", hun), ("Ages", ages)):
        hrefs = [str(item.get("href") or "") for item in payload.get("downloads") or []]
        assert hrefs
        for href in hrefs:
            assert href.startswith(sample + ".")
            assert "/" not in href
            assert ".." not in href
            assert not re.search(r"panel|2449|dosage|nogwas|reference", href, re.I)

    for token in ("PCA", "f3 / f4", "ADMIXTURE"):
        assert_technical_token_has_nearby_chinese(hun_html, token)
        assert_technical_token_has_nearby_chinese(ages_html, token)

    rendered = _run_report_node(
        "var hun="
        + json.dumps(
            {
                "query": hun["query"],
                "report_meta": hun["report_meta"],
                "gs_pred": hun["gs_pred"],
                "method_coverage": {"gs": (hun.get("method_coverage") or {}).get("gs") or {}},
                "downloads": hun["downloads"],
                "query_evidence": [],
                "panel_trait_catalog": [],
                "gwas_loci": [],
                "gwas_index": [],
                "gs_index": [],
                "cross_top": [],
            },
            ensure_ascii=False,
        )
        + ";\nvar ages="
        + json.dumps(
            {
                "query": ages["query"],
                "report_meta": ages["report_meta"],
                "gs_pred": ages["gs_pred"],
                "method_coverage": {"gs": (ages.get("method_coverage") or {}).get("gs") or {}},
                "downloads": ages["downloads"],
                "query_evidence": [],
                "panel_trait_catalog": [],
                "gwas_loci": [],
                "gwas_index": [],
                "gs_index": [],
                "cross_top": [],
            },
            ensure_ascii=False,
        )
        + r""";
function box(){return {innerHTML:'',querySelectorAll:function(){return [];}};}
function render(payload){
  var gs=box(), downloads=box(), evidence=box();
  document={getElementById:function(id){
    return id==='gs-pred'?gs:(id==='downloads'?downloads:(id==='query-evidence'?evidence:null));
  }};
  D=payload; QUERY=payload.query;
  fillQueryEvidence();
  fillExtra();
  return {gs:gs.innerHTML, downloads:downloads.innerHTML};
}
console.log(JSON.stringify({hun:render(hun), ages:render(ages)}));
"""
    )
    assert rendered["hun"]["gs"].count("<tr>") >= 9
    assert "OIV 225" in rendered["hun"]["gs"]
    ages_gs_zh = _zh_visible_copy(rendered["ages"]["gs"])
    assert "不可用" in ages_gs_zh
    assert "没有可用的本查询 GS 预测" in ages_gs_zh
    assert "no per-sample gs prediction available" not in ages_gs_zh.lower()
    assert "no per-query gs prediction available" not in ages_gs_zh.lower()
    assert "HUN89_query.qc.tsv" in rendered["hun"]["downloads"]
    assert "Ages.qc.tsv" in rendered["ages"]["downloads"]
    assert "panel.dosage" not in rendered["hun"]["downloads"]
    assert "panel.dosage" not in rendered["ages"]["downloads"]


def test_sweep_action_click_and_keyboard_persist_after_zh_refresh() -> None:
    observed = _run_report_node(
        r"""
function parseButtons(html){
  var out=[], re=/<button\b([^>]*)>/g, m;
  while((m=re.exec(html||''))){
    var attrs={};
    m[1].replace(/([^\s=]+)="([^"]*)"/g,function(_,k,v){attrs[k]=v;});
    out.push({
      attrs:attrs, listeners:{}, className:'',
      getAttribute:function(k){return this.attrs[k]||null;},
      setAttribute:function(k,v){this.attrs[k]=String(v);},
      addEventListener:function(kind,fn){
        (this.listeners[kind]||(this.listeners[kind]=[])).push(fn);
      },
      focus:function(){ focused=this; },
      click:function(){
        (this.listeners.click||[]).forEach(function(fn){fn({type:'click'});});
      }
    });
  }
  return out;
}
var focused=null, buttons=[], manhDraws=0;
var table={
  _html:'',
  get innerHTML(){return this._html;},
  set innerHTML(v){ this._html=v; buttons=parseButtons(v); },
  querySelectorAll:function(sel){
    return sel.indexOf('button')>=0?buttons:[];
  }
};
document={getElementById:function(id){
  return id==='sel-sweep-table'?table:(id==='plot-sel-manh'?{scrollIntoView:function(){}}:null);
}};
D={selection_manhattan:{
  sweep_thr:{CG1:{n:1,fst95:0.3,het05:0.1}},
  sweeps:{CG1:[{chrom:'2',pos:100,fst:0.4,het:0.12}]}
}};
selManhGrp='CG1'; selManhFocus=null; langMode='en';
var realManh=drawSelManhattan;
drawSelManhattan=function(){ manhDraws+=1; fillSelSweepTable(); };
fillSelSweepTable();
var first=buttons[0];
first.focus();
first.click();
var afterClick=table.innerHTML;
var space={key:' ',defaultPrevented:false,preventDefault:function(){this.defaultPrevented=true;}};
fillSelSweepTable();
buttons[0].listeners.keydown[0](space);
var afterKey=table.innerHTML;
langMode='en';
window={_gaLangReady:true};
fillHeroStats=function(){}; fillAuthorIntake=function(){};
fillQuerySnapshot=function(){}; fillReportMeta=function(){};
fillMethodCoverage=function(){}; fillQueryEvidence=function(){};
fillQc=function(){}; fillConclusions=function(){};
fillCloneTable=function(){}; fillIbsKinship=function(){};
fillExtra=function(){}; enhanceReportTables=function(){}; pairLangBlocks=function(){};
loadPCA=function(){}; loadPCA3d=function(){}; loadBar=function(){};
loadTree=function(){}; loadDamage=function(){};
fillSelFstats=function(){ fillSelSweepTable(); };
setLang('zh',false);
console.log(JSON.stringify({
  afterClick:afterClick,
  afterKey:afterKey,
  afterZh:table.innerHTML,
  focus:selManhFocus,
  focused:!!focused,
  manhDraws:manhDraws,
  spacePrevented:space.defaultPrevented
}));
"""
    )
    assert observed["focus"] == {"chrom": "2", "pos": 100}
    assert observed["focused"] is True
    assert observed["spacePrevented"] is True
    for blob in (observed["afterClick"], observed["afterKey"], observed["afterZh"]):
        assert 'id="sel-sweep-status"' in blob
        assert 'aria-pressed="true"' in blob
        assert "is-sweep-focus" in blob
    assert "Pinned on the Manhattan" in observed["afterClick"]
    assert "在图上标出" in observed["afterZh"]
    assert "已钉在上方 Manhattan" in observed["afterZh"]
    assert "Show on plot" not in _zh_visible_copy(observed["afterZh"])


def test_table_scroll_regions_and_stat_q_title_refresh_with_language() -> None:
    observed = _run_report_node(
        r"""
function makeNode(tag, cls){
  var node={
    tagName:String(tag).toUpperCase(), className:cls||'',
    children:[], parentElement:null, attrs:{},
    getAttribute:function(k){return this.attrs[k]||null;},
    setAttribute:function(k,v){this.attrs[k]=String(v); if(k==='class') this.className=String(v);},
    querySelector:function(){return null;},
    querySelectorAll:function(){return [];},
    appendChild:function(child){
      this.children.push(child); child.parentElement=this; return child;
    }
  };
  return node;
}
var wrapper=makeNode('div','table-scroll');
var table=makeNode('table');
wrapper.appendChild(table);
var root=makeNode('main');
root.appendChild(wrapper);
root.querySelectorAll=function(sel){
  if(sel==='table') return [table];
  if(sel==='.table-scroll') return [wrapper];
  if(sel==='.clickrow') return [];
  return [];
};
var qEl={
  textContent:'', title:'', attrs:{},
  scrollWidth:240, clientWidth:160,
  setAttribute:function(k,v){this.attrs[k]=String(v); if(k==='title') this.title=String(v);},
  getAttribute:function(k){return this.attrs[k]||null;},
  removeAttribute:function(k){delete this.attrs[k]; if(k==='title') this.title='';}
};
document={
  getElementById:function(id){return id==='stat-q'?qEl:null;},
  querySelectorAll:function(){return [];},
  createElement:function(tag){return makeNode(tag);}
};
QUERY='HUN89_query'; D={query:'HUN89_query',qc:{},query_meta:{}};
langMode='en';
enhanceReportTables(root);
fillHeroStats();
var en={
  role:wrapper.getAttribute('role'),
  tabindex:wrapper.getAttribute('tabindex'),
  aria:wrapper.getAttribute('aria-label'),
  title:wrapper.getAttribute('title'),
  qTitle:qEl.title,
  children:wrapper.children.length
};
langMode='zh';
enhanceReportTables(root);
fillHeroStats();
console.log(JSON.stringify({
  en:en,
  zh:{
    role:wrapper.getAttribute('role'),
    tabindex:wrapper.getAttribute('tabindex'),
    aria:wrapper.getAttribute('aria-label'),
    title:wrapper.getAttribute('title'),
    qTitle:qEl.title,
    children:wrapper.children.length
  }
}));
"""
    )
    assert observed["en"]["role"] == "region"
    assert observed["en"]["tabindex"] == "0"
    assert observed["en"]["aria"] == "Scrollable results table"
    assert observed["en"]["title"] == "Scroll horizontally to view all columns"
    assert observed["en"]["qTitle"] == "HUN89_query"
    assert observed["zh"]["role"] == "region"
    assert observed["zh"]["tabindex"] == "0"
    assert observed["zh"]["aria"] == "可横向滚动的结果表"
    assert observed["zh"]["title"] == "横向滚动可查看全部列"
    assert observed["zh"]["qTitle"] == "HUN89_query"
    assert observed["en"]["children"] == 1
    assert observed["zh"]["children"] == 1


def test_sample_who_localizes_clone_and_escapes_hover_html() -> None:
    observed = _run_report_node(
        r"""
QUERY='QUERY';
SROWS=[{
  iid:'CLONE1',
  acc:'<img src=x onerror=1>',
  acc_local:'<b>local</b>',
  origin:'Tokaj',
  con:'HUN',
  geo:'EUR',
  uti:'<iframe>',
  grp:'CG4',
  taxon:'<script>1</script>',
  vivc:'12144',
  clone_of:'PARENT1'
},{
  iid:'QUERY',
  acc:'SafeAcc',
  origin:'HUNGARY'
}];
loadAuthorState=function(){
  return {mode:'sample', sample:{
    name:'<svg onload=1>', origin:'Site-A', date:'2020'
  }, rows:[]};
};
function run(lang){
  langMode=lang;
  return {
    cloneQuery:sampleWho('CLONE1','query'),
    clonePinned:sampleWho('CLONE1','pinned'),
    cloneUnknown:sampleWho('CLONE1','<img src=z>'),
    queryHover:sampleWho('QUERY','query'),
    pinnedHover:sampleWho('QUERY','pinned')
  };
}
console.log(JSON.stringify({en:run('en'), zh:run('zh')}));
"""
    )

    def assert_safe_payload(html: str) -> None:
        for raw in (
            "<img",
            "<b>",
            "<iframe",
            "<script",
            "<svg",
        ):
            assert raw not in html
        assert "&lt;img" in html
        assert "&amp;lt;" not in html
        assert "&lt;b&gt;local&lt;/b&gt;" in html or "&lt;b&gt;" in html
        assert "CLONE1" in html
        assert "Tokaj" in html
        assert "HUN" in html
        assert "EUR" in html
        assert "CG4" in html
        assert "12144" in html
        assert "PARENT1" in html
        assert "<br>" in html

    en_clone = observed["en"]["cloneQuery"]
    zh_clone = observed["zh"]["cloneQuery"]
    assert_safe_payload(en_clone)
    assert_safe_payload(zh_clone)
    assert "Clone of: PARENT1" in en_clone
    assert "克隆对应：PARENT1" in zh_clone
    assert "clone of" not in zh_clone.lower()
    assert "克隆对应" not in en_clone
    assert "Query sample" in en_clone
    assert "查询样本" in zh_clone
    assert "Query sample" not in zh_clone
    assert "查询样本" not in en_clone
    assert "Pinned sample" in observed["en"]["clonePinned"]
    assert "已钉住样本" in observed["zh"]["clonePinned"]
    assert "Pinned sample" not in observed["zh"]["clonePinned"]
    assert "已钉住样本" not in observed["en"]["clonePinned"]
    assert "&lt;img src=z&gt;" in observed["en"]["cloneUnknown"]
    assert "&lt;img src=z&gt;" in observed["zh"]["cloneUnknown"]

    en_query = observed["en"]["queryHover"]
    zh_query = observed["zh"]["queryHover"]
    assert "QUERY" in en_query and "QUERY" in zh_query
    assert "Site-A" in en_query and "2020" in en_query
    assert "&lt;svg onload=1&gt;" in en_query
    assert "&lt;svg onload=1&gt;" in zh_query
    assert "<svg" not in en_query and "<svg" not in zh_query
    assert "Query sample" in en_query
    assert "查询样本" in zh_query
    assert "Pinned sample" in observed["en"]["pinnedHover"]
    assert "已钉住样本" in observed["zh"]["pinnedHover"]
    assert "<br>" in en_query and "<br>" in zh_query


def test_pinned_summary_localizes_clone_and_escapes_detail() -> None:
    refresh_start = APP_JS.index("function refreshLangContent")
    refresh_end = APP_JS.index("\nfunction ", refresh_start + 10)
    refresh_block = APP_JS[refresh_start:refresh_end]
    assert "renderPinnedSummary(selectedIID)" in refresh_block
    assert "highlightSample(" not in refresh_block

    observed = _run_report_node(
        r"""
function pinNode(kind){
  var node={_t:'', _h:'', writes:[], style:{display:'none'}};
  Object.defineProperty(node,'textContent',{
    get:function(){return this._t;},
    set:function(v){ this._t=String(v); this.writes.push(kind+':text'); }
  });
  Object.defineProperty(node,'innerHTML',{
    get:function(){return this._h;},
    set:function(v){ this._h=String(v); this.writes.push(kind+':html'); }
  });
  return node;
}
var pinIid=pinNode('iid'), pinAcc=pinNode('acc'), pinDet=pinNode('det');
var pinBar={style:{display:'none'}};
document={getElementById:function(id){
  return {
    'pin-iid':pinIid,'pin-acc':pinAcc,'pin-detail':pinDet,'pinned-sample':pinBar
  }[id]||null;
}};
SROWS=[{
  iid:'CLONE1', acc:'<img src=x onerror=1>', acc_local:'Furmint',
  origin:'Tokaj', geo:'EUR', uti:'WINE', vivc:'12144',
  clone_of:'PARENT1', grp:'<svg onload=1>', grp_info:'',
  qvals:{'8':[0.91,0.02,0.02,0.01,0.01,0.01,0.01,0.01],'8_dom':'<script>1</script>'},
  pc1:0.111, pc2:0.222, pc3:0.333, idx:3
}];
currentK='8'; selectedIID='CLONE1';
langMode='en';
renderPinnedSummary('CLONE1');
var en={iid:pinIid.textContent, acc:pinAcc.textContent, det:pinDet.innerHTML, writes:pinAcc.writes.concat(pinDet.writes), display:pinBar.style.display};
langMode='zh';
renderPinnedSummary('CLONE1');
console.log(JSON.stringify({
  en:en,
  zh:{iid:pinIid.textContent, acc:pinAcc.textContent, det:pinDet.innerHTML, display:pinBar.style.display}
}));
"""
    )
    assert observed["en"]["iid"] == "CLONE1"
    assert observed["zh"]["iid"] == "CLONE1"
    assert observed["en"]["display"] == "block"
    assert observed["zh"]["display"] == "block"
    assert "acc:text" in observed["en"]["writes"]
    assert "acc:html" not in observed["en"]["writes"]
    assert "det:html" in observed["en"]["writes"]
    assert "Clone of: PARENT1" in observed["en"]["acc"]
    assert "克隆对应：PARENT1" in observed["zh"]["acc"]
    assert "clone of" not in observed["zh"]["acc"].lower()
    assert "克隆对应" not in observed["en"]["acc"]
    assert "Furmint" in observed["en"]["acc"] and "Tokaj" in observed["en"]["acc"]
    assert "12144" in observed["en"]["acc"]
    assert "<img src=x onerror=1>" in observed["en"]["acc"]
    assert "CORE" in observed["en"]["det"]
    assert "核心" in observed["zh"]["det"]
    assert "CORE" not in observed["zh"]["det"]
    assert "ADMIXED" not in observed["en"]["det"]
    assert "混合" not in observed["en"]["det"]
    assert "Grp=" in observed["en"]["det"] and "Grp=" in observed["zh"]["det"]
    assert "Q8=" in observed["en"]["det"] and "0.91" in observed["en"]["det"]
    assert "PC1=0.111" in observed["en"]["det"] and "PC3=0.333" in observed["zh"]["det"]
    assert "<svg" not in observed["en"]["det"]
    assert "<script" not in observed["en"]["det"]
    assert "&lt;svg onload=1&gt;" in observed["en"]["det"]
    assert "&lt;script&gt;1&lt;/script&gt;" in observed["en"]["det"]
    assert "&lt;svg onload=1&gt;" in observed["zh"]["det"]


def test_language_refresh_updates_pin_bar_once_without_rehighlight() -> None:
    observed = _run_report_node(
        r"""
function pinNode(){
  var node={_t:'', _h:'', style:{}};
  Object.defineProperty(node,'textContent',{get:function(){return this._t;}, set:function(v){this._t=String(v);}});
  Object.defineProperty(node,'innerHTML',{get:function(){return this._h;}, set:function(v){this._h=String(v);}});
  return node;
}
var pinIid=pinNode(), pinAcc=pinNode(), pinDet=pinNode();
var pinBar={style:{display:'none'}};
var slider={_v:'0'};
Object.defineProperty(slider,'value',{
  get:function(){return this._v;},
  set:function(v){ this._v=String(v); sliderWrites+=1; }
});
var sliderWrites=0, browserCalls=0, highlightCalls=0, pinRenders=0;
var loads={pca:0,pca3d:0,bar:0,tree:0,damage:0,sel:0};
document={
  getElementById:function(id){
    return {
      'pin-iid':pinIid,'pin-acc':pinAcc,'pin-detail':pinDet,
      'pinned-sample':pinBar,'sample-slider':slider
    }[id]||null;
  },
  querySelectorAll:function(){return [];}
};
window={_gaLangReady:true};
D={query:'CLONE1'};
SROWS=[{
  iid:'CLONE1', acc:'Furmint', origin:'Tokaj', clone_of:'PARENT1',
  grp:'CG4', qvals:{'8':[0.20,0.10,0.10,0.10,0.10,0.10,0.15,0.15],'8_dom':'CG4'},
  pc1:0.111, pc2:0.222, idx:3
}];
currentK='8'; langMode='en';
updateBrowser=function(){ browserCalls+=1; };
refreshPca3dHighlight=function(){};
relayoutPlot=function(){};
highlightSample('CLONE1');
var afterHighlight={
  selected:selectedIID, slider:slider.value, sliderWrites:sliderWrites,
  browserCalls:browserCalls, acc:pinAcc.textContent, det:pinDet.innerHTML,
  display:pinBar.style.display
};
var realHL=highlightSample;
highlightSample=function(id){ highlightCalls+=1; return realHL.apply(this,arguments); };
var realPin=renderPinnedSummary;
renderPinnedSummary=function(id){ pinRenders+=1; return realPin.apply(this,arguments); };
fillHeroStats=function(){}; fillAuthorIntake=function(){};
fillQuerySnapshot=function(){}; fillReportMeta=function(){};
fillMethodCoverage=function(){}; fillQueryEvidence=function(){};
fillQc=function(){}; fillConclusions=function(){};
fillCloneTable=function(){}; fillIbsKinship=function(){};
fillExtra=function(){}; enhanceReportTables=function(){}; pairLangBlocks=function(){};
fillSelFstats=function(){ loads.sel+=1; };
loadPCA=function(){ loads.pca+=1; };
loadPCA3d=function(){ loads.pca3d+=1; };
loadBar=function(){ loads.bar+=1; };
loadTree=function(){ loads.tree+=1; };
loadDamage=function(){ loads.damage+=1; };
setLang('zh', false);
console.log(JSON.stringify({
  afterHighlight:afterHighlight,
  afterZh:{
    selected:selectedIID, slider:slider.value, acc:pinAcc.textContent,
    det:pinDet.innerHTML, iid:pinIid.textContent, display:pinBar.style.display
  },
  highlightCalls:highlightCalls, pinRenders:pinRenders,
  sliderWrites:sliderWrites, browserCalls:browserCalls, loads:loads
}));
"""
    )
    assert observed["afterHighlight"]["selected"] == "CLONE1"
    assert observed["afterHighlight"]["slider"] == "3"
    assert observed["afterHighlight"]["display"] == "block"
    assert "Clone of: PARENT1" in observed["afterHighlight"]["acc"]
    assert "ADMIXED" in observed["afterHighlight"]["det"]
    assert observed["afterZh"]["selected"] == "CLONE1"
    assert observed["afterZh"]["slider"] == "3"
    assert observed["afterZh"]["iid"] == "CLONE1"
    assert observed["afterZh"]["display"] == "block"
    assert "克隆对应：PARENT1" in observed["afterZh"]["acc"]
    assert "clone of" not in observed["afterZh"]["acc"].lower()
    assert "混合" in observed["afterZh"]["det"]
    assert "ADMIXED" not in observed["afterZh"]["det"]
    assert "CORE" not in observed["afterZh"]["det"]
    assert "Furmint" in observed["afterZh"]["acc"]
    assert "CG4" in observed["afterZh"]["det"]
    assert "0.111" in observed["afterZh"]["det"]
    assert observed["highlightCalls"] == 0
    assert observed["pinRenders"] == 1
    assert observed["sliderWrites"] == 1
    assert observed["browserCalls"] == 1
    assert observed["loads"] == {
        "pca": 1, "pca3d": 1, "bar": 1, "tree": 1, "damage": 1, "sel": 1
    }


_RUNTIME_EMPTY_INFO_BOX_IDS = frozenset(
    {"k8-paint-note", "sel-lz-detail", "lz-detail"}
)


def _info_box_id(block: str) -> str:
    match = re.search(r'\bid="([^"]+)"', block)
    return match.group(1) if match else ""


def test_static_info_boxes_are_paired_without_english_placeholders(
    tmp_path: Path,
) -> None:
    rendered = render_interactive_dashboard(
        _minimal_render_bundle(), tmp_path / "report.html", ROOT
    ).read_text()
    chrome = rendered.split("<body>", 1)[1].split("<script>\n", 1)[0]
    boxes = _class_element_blocks(chrome, "info-box")
    assert boxes
    unpaired = []
    placeholder = []
    for html, _direct in boxes:
        box_id = _info_box_id(html)
        if box_id in _RUNTIME_EMPTY_INFO_BOX_IDS:
            continue
        zh = _zh_visible_copy(html)
        if not zh.strip():
            continue
        if not re.search(r'\bclass\s*=\s*["\'][^"\']*\ben\b', html) or not re.search(
            r'\bclass\s*=\s*["\'][^"\']*\bcn\b', html
        ):
            unpaired.append((box_id or zh[:80], zh[:160]))
        if "见英文" in zh or "见上方英文" in zh:
            placeholder.append((box_id or zh[:80], zh[:160]))
        assert _HAN_RE.search(zh), f"info-box lacks visible Chinese: {zh[:160]}"
    assert not unpaired, f"unpaired English info-boxes: {unpaired}"
    assert not placeholder, f"CN placeholders pointing at hidden English: {placeholder}"
    traits = _element_block(chrome, "traits")
    traits_zh = _zh_visible_copy(traits)
    assert "SwissProt" in traits_zh
    assert "http://www.eu-vitis.de/docs/descriptors/oivdesc/" in traits_zh
    assert "https://www.oiv.int/node/2830" in traits_zh
    assert "doi.org/10.1038/s41592-021-01101-x" in traits_zh
    breeding = _element_block(chrome, "breeding")
    breeding_zh = _zh_visible_copy(breeding)
    assert "LocusZoom.js 0.14.0" in breeding_zh
    assert "doi.org/10.1093/bioinformatics/btab186" in breeding_zh
    assert "doi.org/10.1038/ng.548" in breeding_zh
    assert "summary.json" in breeding_zh
    source = Path(
        "src/grapeancestry/report/interactive_dashboard.py"
    ).read_text(encoding="utf-8")
    assert "见英文" not in source
    assert "见上方英文" not in source


def test_admix_method_notes_localize_known_payload_and_escape_unknown() -> None:
    refresh_start = APP_JS.index("function refreshLangContent")
    refresh_end = APP_JS.index("\nfunction ", refresh_start + 10)
    refresh_block = APP_JS[refresh_start:refresh_end]
    assert "fillAdmixMethodNotes(" in refresh_block
    assert "function fillAdmixMethodNotes" in APP_JS
    ages = _sidecar_payload("Ages")
    hun = _sidecar_payload("HUN89_query")
    observed = _run_report_node(
        "var agesMethods="
        + json.dumps(ages.get("admix_methods") or "", ensure_ascii=False)
        + ";\nvar hunFamily="
        + json.dumps(hun.get("admix_strip_family") or hun.get("admix_run_family") or "", ensure_ascii=False)
        + r""";
function box(){return {innerHTML:'',textContent:''};}
function render(payload){
  var methods=box(), prov=box();
  document={getElementById:function(id){
    return id==='admix-methods'?methods:(id==='admix-provenance'?prov:null);
  }};
  D=payload;
  fillAdmixMethodNotes();
  return {methods:methods.innerHTML, prov:prov.innerHTML};
}
var known=render({
  admix_methods:agesMethods,
  admix_strip_family:hunFamily,
  admix_run_family:hunFamily,
  admix_provenance:{}
});
langMode='zh';
var knownZh=render({
  admix_methods:agesMethods,
  admix_strip_family:'panel167k_nogwas',
  admix_run_family:'panel167k_nogwas',
  admix_provenance:{}
});
langMode='en';
var doi=render({
  admix_methods:agesMethods,
  admix_provenance:{article:{doi:'10.1126/science.add8655'}}
});
langMode='zh';
var missing=render({admix_methods:'', admix_provenance:{}});
var bad=render({
  admix_methods:'<img src=x onerror=1> raw English leftover',
  admix_provenance:{article:{doi:'<svg onload=1>'}}
});
console.log(JSON.stringify({
  known:known, knownZh:knownZh, doi:doi, missing:missing, bad:bad
}));
"""
    )
    known_en = observed["known"]["methods"]
    known_zh = _zh_visible_copy(observed["knownZh"]["methods"])
    assert "13,950" in known_en and "153,483" in known_en
    assert "Alexander" in known_en
    assert "doi.org/10.1101/gr.094052.109" in known_en
    assert "13,950" in known_zh and "153,483" in known_zh
    assert "聚类亲和度" in known_zh or "无监督" in known_zh
    assert "ADMIXTURE K=2–8 is one unsupervised series" not in known_zh
    assert "<img" not in known_zh
    prov_zh = _zh_visible_copy(observed["knownZh"]["prov"])
    assert "167k" in prov_zh
    assert "doi:10.1126/science.add8655" in prov_zh
    assert "Source DOI unavailable" not in prov_zh
    missing_zh = _zh_visible_copy(observed["missing"]["prov"])
    assert "来源 DOI 不可用" in missing_zh
    assert "Source DOI unavailable" not in missing_zh
    doi_html = observed["doi"]["prov"]
    assert "10.1126/science.add8655" in doi_html
    bad_methods = observed["bad"]["methods"]
    bad_prov = observed["bad"]["prov"]
    assert "<img" not in bad_methods
    assert "&lt;img src=x onerror=1&gt;" in bad_methods
    assert "<svg" not in bad_prov
    assert "&lt;svg onload=1&gt;" in bad_prov


def test_fstat_success_plots_use_active_language_titles_and_hover() -> None:
    observed = _run_report_node(
        r"""
var plots={};
function plotNode(id){
  return {id:id, innerHTML:'', style:{}, clientWidth:500, clientHeight:400};
}
var els={
  'plot-f3-out':plotNode('plot-f3-out'),
  'plot-f4':plotNode('plot-f4'),
  'plot-f3':plotNode('plot-f3'),
  'fstats-tables':{innerHTML:''},
  'fstats-callout':{innerHTML:''}
};
document={
  getElementById:function(id){return els[id]||null;},
  querySelectorAll:function(){return [];}
};
var Plotly={
  newPlot:function(el, data, layout){
    plots[el.id]={
      title:layout&&layout.title,
      hover:data&&data[0]&&data[0].hovertemplate,
      x:data&&data[0]&&data[0].x,
      y:data&&data[0]&&data[0].y
    };
  },
  purge:function(){}
};
window={Plotly:Plotly};
globalThis.Plotly=Plotly;
drawSelLocusZoom=function(){};
drawSelManhattan=function(){};
drawSelHeat=function(){};
drawSelScatter=function(){};
fillSelQuerySites=function(){};
D={
  selection_named:[], selection_by_grp:[], selection_loci:[],
  selection_s29_scatter:{}, selection_vs_summary:[],
  selection_manhattan:{}, selection_heatmap:{},
  selection_fst_het_scatter:{},
  f3_out:[{grp:'CG1',value:0.11,se:0.01,z:4.2,n_sites:12,n_blocks:4}],
  f3:[{a:'A',b:'B',value:0.22,se:0.02,z:2.1,n_sites:13,n_blocks:5}],
  f4:[{a:'A',b:'B',value:-0.13,se:0.03,z:-2.2,n_sites:14,n_blocks:6}],
  outgroup_n:2
};
langMode='en';
fillSelFstats();
var en={f3out:plots['plot-f3-out'], f4:plots['plot-f4'], f3:plots['plot-f3']};
plots={};
langMode='zh';
fillSelFstats();
console.log(JSON.stringify({
  en:en,
  zh:{f3out:plots['plot-f3-out'], f4:plots['plot-f4'], f3:plots['plot-f3']}
}));
"""
    )
    en = observed["en"]["f3out"]
    zh = observed["zh"]["f3out"]
    assert "Outgroup-f3" in en["title"]
    assert "query" in en["title"]
    assert "higher = more shared drift" in en["title"]
    assert "外群" in zh["title"]
    assert "query" in zh["title"]
    assert "共享漂变" in zh["title"]
    assert "higher = more shared drift" not in zh["title"]
    assert "SE=" in en["hover"] and "n_sites=" in en["hover"] and "n_blocks=" in en["hover"]
    assert "Z=" in zh["hover"]
    assert "n_sites" in zh["hover"] and "n_blocks" in zh["hover"]
    assert "SE（标准误）" in zh["hover"]
    assert observed["en"]["f4"]["x"] == observed["zh"]["f4"]["x"]
    assert observed["en"]["f4"]["y"] == observed["zh"]["f4"]["y"]
    assert "成对" in observed["zh"]["f4"]["title"] or "f4" in observed["zh"]["f4"]["title"]
    assert "Pairwise" not in observed["zh"]["f4"]["title"] or "f4" in observed["zh"]["f4"]["title"]


def test_language_refresh_redraws_fstat_plots_once() -> None:
    refresh_start = APP_JS.index("function refreshLangContent")
    refresh_end = APP_JS.index("\nfunction ", refresh_start + 10)
    assert "fillSelFstats();" in APP_JS[refresh_start:refresh_end]
    observed = _run_report_node(
        r"""
var n=0;
function plotNode(id){return {id:id, innerHTML:'', style:{}, clientWidth:400, clientHeight:300};}
var els={
  'plot-f3-out':plotNode('plot-f3-out'),
  'plot-f4':plotNode('plot-f4'),
  'plot-f3':plotNode('plot-f3'),
  'fstats-tables':{innerHTML:''},
  'fstats-callout':{innerHTML:''}
};
document={
  getElementById:function(id){return els[id]||{innerHTML:'',textContent:'',querySelectorAll:function(){return [];},options:[],appendChild:function(){}};},
  querySelectorAll:function(){return [];},
  createElement:function(){return {value:'',textContent:''};}
};
var Plotly={newPlot:function(){ n+=1; }, purge:function(){}};
window={_gaLangReady:true, Plotly:Plotly};
globalThis.Plotly=Plotly;
drawSelLocusZoom=function(){};
drawSelManhattan=function(){};
drawSelHeat=function(){};
drawSelScatter=function(){};
fillSelQuerySites=function(){};
fillHeroStats=function(){}; fillAuthorIntake=function(){};
fillQuerySnapshot=function(){}; fillReportMeta=function(){};
fillMethodCoverage=function(){}; fillQueryEvidence=function(){};
fillQc=function(){}; fillConclusions=function(){};
fillCloneTable=function(){}; fillIbsKinship=function(){};
fillExtra=function(){}; enhanceReportTables=function(){}; pairLangBlocks=function(){};
loadPCA=function(){}; loadPCA3d=function(){}; loadBar=function(){};
loadTree=function(){}; loadDamage=function(){};
fillAdmixMethodNotes=function(){};
D={
  query:'Q',
  selection_named:[], selection_by_grp:[], selection_loci:[],
  selection_s29_scatter:{}, selection_vs_summary:[],
  selection_manhattan:{}, selection_heatmap:{},
  selection_fst_het_scatter:{},
  f3_out:[{grp:'CG1',value:0.1,se:0.01,z:3,n_sites:10,n_blocks:3}],
  f3:[{a:'A',b:'B',value:0.2,se:0.02,z:2,n_sites:11,n_blocks:4}],
  f4:[{a:'A',b:'B',value:-0.1,se:0.03,z:-2,n_sites:12,n_blocks:5}],
  outgroup_n:1
};
langMode='en';
fillSelFstats();
var afterDraw=n;
n=0;
setLang('zh', false);
console.log(JSON.stringify({afterDraw:afterDraw, refresh:n}));
"""
    )
    assert observed["afterDraw"] == 3
    assert observed["refresh"] == 3


def test_shipped_identity_conclusions_localize_relation_words_in_zh() -> None:
    ages = _sidecar_payload("Ages")
    hun = _sidecar_payload("HUN89_query")
    observed = _run_report_node(
        "var ages="
        + json.dumps(
            {
                "purity": ages["purity"],
                "conclusions": ages["conclusions"],
                "report_meta": {"library_class": ages["report_meta"]["library_class"]},
            },
            ensure_ascii=False,
        )
        + ";\nvar hun="
        + json.dumps(
            {
                "purity": hun["purity"],
                "conclusions": hun["conclusions"],
                "report_meta": {"library_class": hun["report_meta"]["library_class"]},
            },
            ensure_ascii=False,
        )
        + r""";
function render(payload){
  var concl={innerHTML:''};
  document={getElementById:function(id){return id==='concl-list'?concl:null;}};
  D=payload;
  fillConclusions();
  return concl.innerHTML;
}
console.log(JSON.stringify({ages:render(ages), hun:render(hun)}));
"""
    )
    ages_zh = _zh_visible_copy(observed["ages"])
    hun_zh = _zh_visible_copy(observed["hun"])
    assert "身份（4K）" in ages_zh and "身份（4K）" in hun_zh
    assert "最近非自身" in ages_zh and "最近非自身" in hun_zh
    assert "克隆筛查" in ages_zh and "克隆筛查" in hun_zh
    assert "无关" in ages_zh
    assert "GM17" in ages_zh
    assert "R1=0.042" in ages_zh and "KING=-0.137" in ages_zh
    assert "完全相同=0" in ages_zh
    assert "亲子=0" in ages_zh
    assert "HUN89" in hun_zh
    assert "KING=0.500" in hun_zh
    assert "完全相同" in hun_zh
    assert "亲子=1" in hun_zh
    for zh in (ages_zh, hun_zh):
        assert "Unrelated" not in zh
        assert "clone-screen" not in zh
        assert "nearest non-self" not in zh
        assert "Identical=" not in zh
        assert "PO=" not in zh
        assert "Parent-Offspring" not in zh


def test_gwas_and_selection_lz_detail_localize_lead_and_bonferroni() -> None:
    observed = _run_report_node(
        r"""
var lz={innerHTML:''}, meta={innerHTML:''};
document={getElementById:function(id){
  return id==='lz-detail'?lz:(id==='sel-lz-meta'?meta:null);
}};
D={query:'QUERY'};
langMode='zh';
fillLzDetail({
  chrom:'2', pos:100, n:10,
  snps:{
    pos:[100], site:['2:100'], ref:['A'], alt:['G'],
    nlp:[8.1], p:[1e-8], q:[1e-6], beta:[0.1], se:[0.01],
    maf:[0.2], n:[10], r2:[0.9], bonf:[1],
    gene:['VvGene'], region:['promoter'], dist:[12], strand:['+']
  }
}, 'snp', 0);
var rec={
  kind:'named', slug:'OIV225', chrom:'2', pos:100,
  window_start:90, window_end:110, n_snps:3,
  snps:{pos:[100], site:['2:100']}
};
selLzMetric='fst';
var realDet=document.getElementById;
document={getElementById:function(id){
  if(id==='sel-lz-meta') return meta;
  if(id==='plot-sel-lz') return {innerHTML:'', style:{}};
  if(id==='sel-lz-detail') return {innerHTML:''};
  if(id==='sel-gt-card') return {innerHTML:''};
  if(id==='plot-sel-gt') return {innerHTML:''};
  return null;
}};
fillQueryGtCard=function(){};
drawQueryGtStrip=function(){};
fillSelLzSnp=function(){};
locusZoomCan=function(){return false;};
D={query:'QUERY', selection_loci:[rec]};
selLzIdx=0; selLzFocusPos=null;
drawSelLocusZoom();
console.log(JSON.stringify({detail:lz.innerHTML, meta:meta.innerHTML}));
"""
    )
    detail_zh = _zh_visible_copy(observed["detail"])
    meta_zh = _zh_visible_copy(observed["meta"])
    assert "主位点" in detail_zh
    assert "是" in detail_zh
    assert " · lead" not in observed["detail"]
    assert ">yes<" not in observed["detail"] and "yes" not in detail_zh.split("Bonferroni")[-1][:8]
    assert "2:100" in detail_zh
    assert "0.900" in detail_zh or "0.9" in detail_zh
    assert "主位点" in meta_zh
    assert " · lead " not in observed["meta"]
    assert "2:100" in meta_zh
    assert "r²" in meta_zh or "r²" in observed["meta"]


def test_missing_genotype_card_zh_keeps_scope_and_escaped_vcf_path() -> None:
    observed = _run_report_node(
        r"""
var card={innerHTML:''};
document={getElementById:function(id){return id==='lz-gt-card'?card:null;}};
D={query:'QUERY<script>'};
langMode='zh';
fillQueryGtCard('lz-gt-card', {query_gt_sample:'HUN89<script>', snps:{}});
console.log(JSON.stringify({html:card.innerHTML}));
"""
    )
    html = observed["html"]
    zh = _zh_visible_copy(html)
    assert "本样品分型不在这份 HTML 里" in zh
    assert "Fst" in zh
    assert "log10" in zh
    assert "r²" in zh
    assert "2449" in zh
    assert "HUN89" in zh
    assert "results/" in zh and ".vcf.gz" in zh
    assert "<code>" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Rebuild" not in zh
    assert "not calls for" not in zh


def test_app_js_and_dashboard_javascript_parse() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the dashboard JS contract")
    check = subprocess.run(
        [node, "--check"],
        input=APP_JS,
        text=True,
        capture_output=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr
    boot = subprocess.run(
        [node, "-e", "new Function(process.argv[1]);", APP_JS],
        check=False,
        capture_output=True,
        text=True,
    )
    assert boot.returncode == 0, boot.stderr
