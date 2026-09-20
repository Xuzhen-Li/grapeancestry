"""Render bilingual METHODS_breeding.md + HTML section from provenance JSON."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from pathlib import Path

from grapeancestry.breeding.provenance import collect_ref_keys

SECTION_TITLES = [
    "Data sources & provenance",
    "Phenotype processing",
    "Genotype data",
    "GWAS",
    "Genomic prediction",
    "Cross recommendation",
    "Software & versions",
    "Methods not used and why",
    "Caveats",
    "References",
]

SECTION_TITLES_CN = [
    "数据来源与溯源",
    "表型处理",
    "基因型数据",
    "全基因组关联",
    "基因组预测",
    "杂交组合推荐",
    "软件与版本",
    "未采用方法与理由",
    "局限与声明",
    "参考文献",
]


def _clean_tex(s: str) -> str:
    s = re.sub(r"\\textit\{([^}]*)\}", r"*\1*", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("--", "–")
    return re.sub(r"\s+", " ", s).strip()


def _bib_braced(body: str, start: int) -> tuple[str, int]:
    depth = 0
    j = start
    while j < len(body):
        if body[j] == "{":
            depth += 1
        elif body[j] == "}":
            depth -= 1
            if depth == 0:
                return body[start + 1 : j], j + 1
        j += 1
    return body[start + 1 :], len(body)


def parse_bib_keys(bib_text: str) -> dict[str, dict[str, str]]:
    """BibTeX key extractor; braces in titles are matched, not truncated."""
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"@\w+\{([^,]+),([\s\S]*?)\n\}", bib_text):
        key = m.group(1).strip()
        body = m.group(2)
        fields: dict[str, str] = {}
        i = 0
        while i < len(body):
            fm = re.search(r"(\w+)\s*=\s*", body[i:])
            if not fm:
                break
            name = fm.group(1).lower()
            i = i + fm.end()
            while i < len(body) and body[i].isspace():
                i += 1
            if i >= len(body):
                break
            if body[i] == "{":
                val, i = _bib_braced(body, i)
            elif body[i] == '"':
                j = body.find('"', i + 1)
                val = body[i + 1 : j] if j > i else ""
                i = j + 1 if j > i else i + 1
            else:
                j = body.find(",", i)
                val = body[i:j] if j > i else body[i:]
                i = j if j > i else len(body)
            fields[name] = _clean_tex(val)
        out[key] = fields
    return out


def load_all_provenance(prov_dir: Path) -> list[dict]:
    recs = []
    if not prov_dir.exists():
        return recs
    for p in sorted(prov_dir.glob("*.json")):
        recs.append(json.loads(p.read_text(encoding="utf-8")))
    return recs


def _rec_by_step(recs: list[dict], step: str) -> dict | None:
    for r in recs:
        if r.get("step") == step:
            return r
    return None


def _latest(recs: list[dict]) -> dict:
    if not recs:
        return {}
    return max(recs, key=lambda r: str(r.get("timestamp") or ""))


def _rel(path: object) -> str:
    s = str(path or "").replace("\\", "/")
    marker = "grapeancestry_suite/"
    if marker in s:
        return s.split(marker, 1)[1]
    return s


def _fmt(v: object, nd: int = 3) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, float):
        if v != v:
            return "—"
        if abs(v) < 1e-3 and v != 0:
            return f"{v:.2e}"
        return f"{v:.{nd}f}"
    return str(v)


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [c.replace("|", "/") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _root_from_recs(recs: list[dict]) -> Path | None:
    for r in recs:
        for block in (r.get("outputs") or []) + (r.get("inputs") or []):
            p = str(block.get("path") or "")
            if "grapeancestry_suite/" in p.replace("\\", "/"):
                base = p.replace("\\", "/").split("grapeancestry_suite/", 1)[0]
                return Path(base) / "grapeancestry_suite"
    here = Path(__file__).resolve().parents[3]
    if (here / "docs").exists():
        return here
    return None


BACKGROUND_ONLY_REF_KEYS = frozenset(
    {
        "brault2022",
        "flutre2022",
        "fodor2014",
        "hazel1943",
        "laucou2018",
        "migicovsky2017",
        "akdemir2016",
        "habier2011",
        "ma2018",
        "wang2023",
    }
)


def _inactive_ref_keys(*, with_bayes: bool) -> set[str]:
    keys = set(BACKGROUND_ONLY_REF_KEYS)
    if with_bayes:
        keys.discard("habier2011")
    return keys


def _gs_row(rows: list[dict[str, str]], trait: str) -> dict[str, str] | None:
    for row in rows:
        if (row.get("trait") or "") == trait:
            return row
    return None


def _fmt_cv(value: object, nd: int = 4) -> str:
    try:
        return f"{float(value):.{nd}f}"
    except (TypeError, ValueError):
        return ""


def _oiv241_case_control(root: Path | None) -> tuple[str, str]:
    if root:
        path = root / "results" / "gwas" / "euvitis" / "OIV_241_bin" / "summary.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            case_n = data.get("case_n")
            control_n = data.get("control_n")
            if case_n is not None and control_n is not None:
                return str(case_n), str(control_n)
    return "", ""


def _keep_visible_caveat(item: str, inactive: set[str], *, with_bayes: bool) -> bool:
    low = item.lower()
    if any(key.lower() in low for key in inactive):
        return False
    tokens = [
        "background only",
        "deepgs",
        "dnngp",
        "ma 2018",
        "wang 2023",
        "akdemir",
    ]
    if not with_bayes:
        tokens.append("bayesc")
    return not any(token in low for token in tokens)


# Interpretation-only caveats shown in the embedded report (EN → concise CN).
CAVEAT_CN = {
    "Progeny variance ignores LD (no genetic map).": (
        "子代方差忽略连锁不平衡（无遗传图谱）。"
    ),
    "167K panel includes 13,950 design-time GWAS sites; in-panel association only.": (
        "167K 面板含 13,950 个设计期 GWAS 位点；仅面板内关联。"
    ),
    (
        "Binary 0/1 traits use the same LMM as Kang 2010 WTCCC "
        "(doi:10.1038/ng.548 Online Methods: linear model on binary phenotypes). "
        "P-values can be unreliable when cases are highly imbalanced."
    ): (
        "二元 0/1 性状使用与 Kang 2010 WTCCC 相同的线性混合模型"
        "（doi:10.1038/ng.548）。病例高度不平衡时 P 值可能不可靠。"
    ),
    "eu-vitis and des-cep values are not merged (2022-05-23 file note).": (
        "eu-vitis 与 des-cep 数值不合并（2022-05-23 文件说明）。"
    ),
    "0 coded as missing; multi-value ordinal mean / nominal consensus.": (
        "将 0 记为缺失；多值有序取均值、名义取共识。"
    ),
}

DOC_ONLY_CAVEAT_TOKENS = (
    "41mb",
    "grin/npgs",
    "all-matched workbook",
    "2256 rows including blanks",
    "plan §0",
    "traits_n_ge_50_total is after parse",
)

# Bounded table-cell map (ETL notes, cross labels, software status). Not an i18n framework.
CELL_PHRASE_CN = {
    "eu-vitis Excel used-range rows (header excluded)": "eu-vitis Excel 使用区行数（不含表头）",
    "des-cep Excel used-range rows, including blanks": "des-cep Excel 使用区行数（含空行）",
    "eu-vitis nonempty pandas rows": "eu-vitis 非空 pandas 行",
    "des-cep nonempty pandas rows": "des-cep 非空 pandas 行",
    "des-cep unique Library IDs": "des-cep 唯一 Library ID",
    "eu-vitis IDs in 2449 panel": "eu-vitis 落在 2449 面板中的 ID",
    "des-cep IDs in 2449 panel": "des-cep 落在 2449 面板中的 ID",
    "union of panel IDs with phenotype": "有表型的面板 ID 并集",
    "non-empty OIV cells": "非空 OIV 单元格",
    "`0` coded as missing": "`0` 记为缺失",
    "pipe-separated multi-value cells": "竖线分隔多值单元格",
    "out-of-scale / nominal disagreement": "越界 / 名义不一致",
    "des-cep replicate groups aggregated": "des-cep 重复组合并",
    "(source, trait) with n≥50 after parse": "解析后 n≥50 的（来源, 性状）",
    "parent": "亲本",
    "target": "目标",
    "candidates": "候选",
    "pairs scored": "已评分组合",
    "removed kinship": "亲缘剔除",
    "removed sex": "性别剔除",
    "removed clone": "无性系剔除",
    "reported": "已报告",
    "output": "输出",
    "not installed": "未安装",
}

_UNUSED_METHODS_SECTION = re.compile(
    r"(?ms)^## 8\. Methods not used and why /[^\n]*\n.*?(?=^## |\Z)"
)


def _is_doc_only_caveat(item: str) -> bool:
    low = item.lower()
    return any(token in low for token in DOC_ONLY_CAVEAT_TOKENS)


def _keep_embed_caveat(item: str) -> bool:
    if item in CAVEAT_CN:
        return True
    return not _is_doc_only_caveat(item)


def _emit_caveat_items(caveats: list[str], *, embed: bool) -> list[str]:
    if not caveats:
        return ["- (none)"]
    lines: list[str] = []
    for item in caveats:
        if not embed:
            lines.append(f"- {item}")
            continue
        zh = CAVEAT_CN.get(item)
        if zh:
            lines.append(f"- **EN**: {item}")
            lines.append(f"- **CN**: {zh}")
        else:
            lines.append(f"- **EN**: Source-recorded caveat: {item}")
            lines.append(f"- **CN**: 溯源记录：{item}")
    return lines


def render_methods_markdown(
    recs: list[dict],
    bib: dict[str, dict[str, str]],
    *,
    extra_caveats: list[str] | None = None,
    root: Path | None = None,
    embed: bool = False,
) -> str:
    etl = _rec_by_step(recs, "phenotype_etl") or {}
    gwas = _rec_by_step(recs, "gwas") or {}
    gs = _rec_by_step(recs, "gs_train") or {}
    cross = _rec_by_step(recs, "cross_recommend") or {}
    counts = etl.get("counts") or {}
    cr_c = cross.get("counts") or {}
    gs_p = gs.get("parameters") or {}
    vers = _latest(recs)

    root = root or _root_from_recs(recs)
    gwas_rows = _read_tsv((root / "results" / "gwas" / "index.tsv") if root else Path())
    gs_rows = _read_tsv((root / "results" / "gs" / "index.tsv") if root else Path())
    if not gs_rows:
        gs_rows = [
            {
                "source": r.get("source", ""),
                "trait": r.get("trait", ""),
                "best_model": r.get("best_model", ""),
                "cv_r": str(r.get("cv_r", "")),
                "n": str(r.get("n", "")),
            }
            for r in (gs.get("counts") or {}).get("per_trait") or []
        ]

    pending: list[str] = list(extra_caveats or [])
    for r in recs:
        pending.extend(r.get("caveats") or [])
    for k, fields in bib.items():
        note = fields.get("note", "")
        if "[待确认]" in note:
            pending.append(f"bib:{k}: {note}")
    # de-duplicate, keep order
    with_bayes = bool(gs_p.get("with_bayes"))
    inactive = _inactive_ref_keys(with_bayes=with_bayes)
    seen: set[str] = set()
    caveats: list[str] = []
    for item in pending:
        if item not in seen and _keep_visible_caveat(
            item, inactive, with_bayes=with_bayes
        ):
            seen.add(item)
            caveats.append(item)
    if embed:
        caveats = [item for item in caveats if _keep_embed_caveat(item)]

    used_keys = set(collect_ref_keys(recs))
    if with_bayes:
        used_keys.add("habier2011")
    used_keys = sorted(used_keys)
    oiv225 = _gs_row(gs_rows, "OIV 225")
    oiv151 = _gs_row(gs_rows, "OIV 151")
    oiv241 = _gs_row(gs_rows, "OIV 241")
    cv225 = _fmt_cv(oiv225.get("cv_r") if oiv225 else None, 4)
    cv225_3 = _fmt_cv(oiv225.get("cv_r") if oiv225 else None, 3)
    cv151 = _fmt_cv(oiv151.get("cv_r") if oiv151 else None, 2)
    cv241 = _fmt_cv(oiv241.get("cv_r") if oiv241 else None, 4)
    case_n, control_n = _oiv241_case_control(root)
    best225 = (oiv225 or {}).get("best_model") or "—"
    lines: list[str] = []

    lines.append(
        "# Methods: phenotype, GWAS, genomic selection, cross recommendation / "
        "方法：表型、GWAS、基因组选择、杂交推荐"
    )
    lines.append("")
    if not embed:
        lines.append(
            "**EN**: Bilingual methods for GrapeAncestry Suite breeding modules. "
            "Counts are copied from `results/provenance/*.json` and `results/*/index.tsv`."
        )
        lines.append("")
        lines.append(
            "**CN**: GrapeAncestry Suite 育种模块方法说明。"
            "计数来自 `results/provenance/*.json` 与 `results/*/index.tsv`。"
        )
        lines.append("")

    lines.append("## Key results / 主要结果")
    lines.append("")
    if embed:
        lines.append(
            "**EN**: Rank berry colour (**OIV 225** binary) as currently "
            f"rankable under this report policy (panel CV *r* = {cv225 or '—'} ≈ "
            f"{cv225_3 or '—'}, {best225}). **Flower sex (OIV 151 binary)** GWAS hits "
            f"the SDR region, but panel CV *r* ≈ {cv151 or '—'} is too low to rank "
            "parents. **OIV 241 binary**: no OIV 241 locus overlap found in the panel "
            "GWAS; "
            f"panel CV *r* = {cv241 or '—'} remains exploratory because of the "
            f"{case_n or '—'}/{control_n or '—'} imbalance, so it is not suitable for "
            "ranking parents. One limitation: the HUN89 mate list ranks under an "
            "LD-ignoring progeny-variance approximation, not a predicted field outcome."
        )
        lines.append("")
        lines.append(
            "**CN**：按本报告策略对浆果皮色（**OIV 225** 二元）排序"
            f"（panel CV *r*={cv225 or '—'}≈{cv225_3 or '—'}，{best225}）。"
            f"**花性（OIV 151）** GWAS 打到 SDR，但 panel CV *r*≈{cv151 or '—'}，"
            "不能用来排亲本。**OIV 241 二元**：panel GWAS 未发现 OIV 241 位点重合；"
            f"因 {case_n or '—'}/{control_n or '—'} 不平衡，panel CV *r*={cv241 or '—'} "
            "仍为探索性，不适合排亲本。一项限制：HUN89 杂交表是忽略 LD 的子代方差近似排序，"
            "不是田间预测。"
        )
    else:
        lines.append(
            "**EN**: On this 167K in-panel set, **berry colour (OIV 225 binary)** is currently "
            f"rankable under this report policy (panel CV *r* = {cv225 or '—'} ≈ {cv225_3 or '—'}, "
            f"{best225}). **Flower sex (OIV 151 binary)** GWAS hits the SDR region, but panel CV "
            f"*r* ≈ {cv151 or '—'} is too low to rank parents. **OIV 241 binary**: no OIV 241 locus "
            "overlap found in the panel GWAS; "
            f"panel CV *r* = {cv241 or '—'} remains exploratory because of the "
            f"{case_n or '—'}/{control_n or '—'} imbalance, so it is not suitable for ranking "
            "parents. The HUN89 mate list is a ranking under an LD-ignoring "
            "progeny-variance approximation, not a predicted field outcome."
        )
        lines.append("")
        lines.append(
            "**CN**：本面板内，**浆果皮色（OIV 225 二元）** 在本报告策略下目前可排序"
            f"（panel CV *r*={cv225 or '—'}≈{cv225_3 or '—'}）。**花性（OIV 151）** GWAS 打到 SDR，"
            f"但 panel CV *r*≈{cv151 or '—'}，不能用来排亲本。**OIV 241 二元**：panel GWAS 未发现 "
            "OIV 241 位点重合；"
            f"因 {case_n or '—'}/{control_n or '—'} 不平衡，panel CV *r*={cv241 or '—'} 仍为探索性，"
            "不适合排亲本。HUN89 杂交表是忽略 LD 的子代方差近似排序，不是田间预测。"
        )
    lines.append("")
    lines.append("## GS decision scope / GS 决策范围")
    lines.append("")
    if embed:
        lines.append(
            "**EN**: Rank OIV 225 colour as currently rankable under this report policy "
            f"from `results/gs/index.tsv` (`trait`, `n`, `best_model`, `cv_r`) and "
            f"`results/provenance/gs_train.json` (`counts.per_trait`); "
            f"panel CV *r* = {cv225 or '—'} ≈ {cv225_3 or '—'}. No OIV 241 locus overlap "
            "found in the panel GWAS. The recorded imbalance in "
            "`results/gwas/euvitis/OIV_241_bin/summary.json` "
            f"(`case_n={case_n or '—'}`, `control_n={control_n or '—'}`) leaves "
            f"`cv_r={cv241 or '—'}` exploratory and not suitable for ranking parents "
            "or claiming seedlessness. One limitation: binary-trait P-values follow the "
            "EMMAX caveat ([Kang et al.](https://doi.org/10.1038/ng.548)); no GS score "
            "here is an observed phenotype."
        )
        lines.append("")
        lines.append(
            "**CN**：按本报告策略从 `results/gs/index.tsv` 的 "
            "`trait`、`n`、`best_model`、`cv_r` 与 `results/provenance/gs_train.json` 的 "
            "`counts.per_trait` 对 OIV 225 皮色排序；"
            f"panel CV *r*={cv225 or '—'}≈{cv225_3 or '—'}。panel GWAS 未发现 OIV 241 位点重合。"
            "`results/gwas/euvitis/OIV_241_bin/summary.json` 记录 "
            f"`case_n={case_n or '—'}`、`control_n={control_n or '—'}`，因此 "
            f"`cv_r={cv241 or '—'}` 仍为探索性，不适合排亲本，也不能据此声称无核。"
            "一项限制：二元性状 P 值遵循 EMMAX 说明（[Kang 等](https://doi.org/10.1038/ng.548)）；"
            "此处 GS 分数不是观测表型。"
        )
    else:
        lines.append(
            "**EN**: OIV 225 colour GS is currently rankable under this report policy "
            f"(`cv_r={cv225 or '—'}`, approximately {cv225_3 or '—'}). This statement is copied "
            "from local summary fields: `results/gs/index.tsv` (`trait`, `n`, `best_model`, `cv_r`) "
            "and `results/provenance/gs_train.json` (`counts.per_trait`). No OIV 241 locus overlap "
            "found in the panel GWAS. The OIV 241 imbalance is recorded in "
            "`results/gwas/euvitis/OIV_241_bin/summary.json` "
            f"(`case_n={case_n or '—'}`, `control_n={control_n or '—'}`), so its "
            f"`cv_r={cv241 or '—'}` remains exploratory and is not suitable for ranking parents "
            "or claiming seedlessness. Binary-trait interpretation follows the EMMAX caveat "
            "([Kang et al.](https://doi.org/10.1038/ng.548)); no GS score here is an observed "
            "phenotype."
        )
        lines.append("")
        lines.append(
            "**CN**：本报告策略下的可排序结论来自本地 summary 字段：`results/gs/index.tsv` 的 "
            "`trait`、`n`、`best_model`、`cv_r`，以及 `results/provenance/gs_train.json` 的 "
            "`counts.per_trait`。panel GWAS 未发现 OIV 241 位点重合。OIV 241 的类别不平衡记录在 "
            "`results/gwas/euvitis/OIV_241_bin/summary.json` 的 "
            f"`case_n={case_n or '—'}`、`control_n={control_n or '—'}`，因此 "
            f"`cv_r={cv241 or '—'}` 仍仅供探索，不适合排亲本，也不能据此声称无核。"
            "二元性状解释遵循 EMMAX 限制（[Kang 等](https://doi.org/10.1038/ng.548)）；"
            "这里的 GS 分数不是观测表型。"
        )
    lines.append("")
    if embed:
        lines.append(
            "**EN**: Counts are copied from provenance JSON and local index tables."
        )
        lines.append("")
        lines.append("**CN**: 计数来自溯源 JSON 与本地索引表。")
        lines.append("")

    # 1
    lines.append(f"## 1. {SECTION_TITLES[0]} / {SECTION_TITLES_CN[0]}")
    lines.append("")
    if embed:
        lines.append(
            "**EN**: Use the 2022-05-23 eu-vitis.de and OIV *des cépages du monde* "
            "2009 package; Library ID matches the 2449 panel IDs exactly. Sources: "
            "[eu-vitis](http://www.eu-vitis.de/); "
            "[OIV 2009 2nd edition](https://www.oiv.int/node/2830)."
        )
        lines.append("")
        lines.append(
            "**CN**: 使用 2022-05-23 eu-vitis.de 与 OIV 2009 表型包；"
            "Library ID 与 2449 面板 ID 精确匹配。"
            "来源：[eu-vitis](http://www.eu-vitis.de/)；"
            "[OIV 2009 第 2 版](https://www.oiv.int/node/2830)。"
        )
    else:
        lines.append(
            "**EN**: Phenotypes are from the 2022-05-23 eu-vitis.de and OIV *des cépages du monde* "
            "2009 package. Library ID matches the 2449 panel IDs exactly. GRIN/NPGS tables and the "
            "41 MB all-matched workbook are unused (no Library-ID map; ST1 is the deduplicated subset). "
            "Sources: [eu-vitis](http://www.eu-vitis.de/); "
            "[OIV 2009 2nd edition](https://www.oiv.int/node/2830)."
        )
        lines.append("")
        lines.append(
            "**CN**: 表型来自 2022-05-23 数据包（eu-vitis.de 与 OIV 2009 世界品种描述）。"
            "Library ID 与面板 ID 精确匹配。GRIN/NPGS 与「所有能对应样品」大表本轮不用。"
        )
    lines.append("")

    # 2
    lines.append(f"## 2. {SECTION_TITLES[1]} / {SECTION_TITLES_CN[1]}")
    lines.append("")
    etl_keys = [
        ("xlsx_max_row_euvitis", "eu-vitis Excel used-range rows (header excluded)"),
        ("xlsx_max_row_descep", "des-cep Excel used-range rows, including blanks"),
        ("xlsx_rows_euvitis", "eu-vitis nonempty pandas rows"),
        ("xlsx_rows_descep", "des-cep nonempty pandas rows"),
        ("uniq_libid_descep", "des-cep unique Library IDs"),
        ("ids_in_panel_euvitis", "eu-vitis IDs in 2449 panel"),
        ("ids_in_panel_descep", "des-cep IDs in 2449 panel"),
        ("ids_in_panel_union", "union of panel IDs with phenotype"),
        ("cells_total", "non-empty OIV cells"),
        ("cells_zero_dropped", "`0` coded as missing"),
        ("cells_multivalue", "pipe-separated multi-value cells"),
        ("cells_out_of_scale_dropped", "out-of-scale / nominal disagreement"),
        ("replicates_aggregated", "des-cep replicate groups aggregated"),
        ("traits_n_ge_50_total", "(source, trait) with n≥50 after parse"),
    ]
    lines.extend(
        _md_table(
            ["Node", "Count", "Note"],
            [[f"`{k}`", str(counts.get(k, "NA")), note] for k, note in etl_keys],
        )
    )
    lines.append("")
    if embed:
        lines.append(
            "**EN**: Code `0` as missing; take ordinal means and nominal consensus for "
            "multi-value cells. One limitation: eu-vitis and des-cep are **not** merged "
            "(2022-05-23 file note)."
        )
        lines.append("")
        lines.append(
            "**CN**: 将 `0` 记为缺失；多值有序取均值、名义取共识。"
            "一项限制：eu-vitis 与 des-cep **不**合并（2022-05-23 文件说明）。"
        )
    else:
        lines.append(
            "**EN**: `0` = missing (OIV scales do not include 0). Multi-value `a|b`: ordinal mean, "
            "nominal consensus else NA. Out-of-scale dropped. des-cep replicates: ordinal median, "
            "nominal mode (tie → NA). eu-vitis and des-cep are **not** merged "
            "(2022-05-23 file note). des-cep Excel used range is 2256 rows including blanks; "
            "nonempty rows = 312 unique Library IDs (no ST1 replicates). "
            "`traits_n_ge_50_total` is after parse; raw non-zero n≥50 was 168."
        )
        lines.append("")
        lines.append(
            "**CN**: `0` 视为缺失；`a|b` 有序取均值、名义一致才保留；越界剔除；"
            "des-cep 重复行有序取中位数、名义取众数；两来源不合并。"
            "des-cep Excel 使用区 2256 行含空行；非空行=唯一 Library ID。"
            "n≥50 为解析后计数（原始非零为 168）。"
        )
    lines.append("")

    # 3
    lines.append(f"## 3. {SECTION_TITLES[2]} / {SECTION_TITLES_CN[2]}")
    lines.append("")
    lines.append(
        "**EN**: The analysis matrix is 2449 × 167,433 dosages (0/1/2, −1 missing). "
        "Default site filter on the phenotype subset: MAF ≥ 0.05, missing ≤ 0.2. "
        "The 167K panel includes 13,950 design-time GWAS sites; results are "
        "**in-panel association**, not a random-genome scan."
    )
    lines.append("")
    lines.append(
        "**CN**: 剂量矩阵 2449×167,433。默认 MAF≥0.05、缺失≤0.2。"
        "面板含 13,950 个设计期 GWAS 位点，结果只解释为面板内关联。"
    )
    lines.append("")

    # 4
    lines.append(f"## 4. {SECTION_TITLES[3]} / {SECTION_TITLES_CN[3]}")
    lines.append("")
    lines.append(
        "**EN**: Mixed model $y = C\\alpha + u + e$, $u \\sim N(0, \\sigma_g^2 K)$, "
        "$e \\sim N(0, \\sigma_e^2 I)$. $K$ = VanRaden (2008) GRM. Variance components by "
        "EMMA $\\delta = \\sigma_e^2/\\sigma_g^2$ (Kang 2008), then P3D/EMMAX one-time "
        "$\\delta$ for all SNPs (Kang 2010; Zhang 2010). $C$ = intercept + 3 PCs of $K$. "
        "Tests: $t$ on weighted residuals; $\\lambda_{GC}$ (Devlin & Roeder 1999); "
        "Bonferroni $0.05/m$; BH-FDR (Benjamini & Hochberg 1995); clump ±200 kb. "
        "Binary traits use the same LMM as Kang 2010 on WTCCC case–control phenotypes "
        "(doi:10.1038/ng.548)."
    )
    lines.append("")
    lines.append(
        "**CN**: EMMAX/P3D 混合模型；VanRaden GRM；δ 只估一次；协变量为截距+3 个 PC；"
        "Bonferroni 与 BH-FDR；±200 kb clump。二元性状按 Kang 2010 对 0/1 做线性混合模型。"
    )
    lines.append("")
    if gwas_rows:
        lines.append(
            "**EN**: Curated GWAS table (source: `results/gwas/index.tsv`; "
            "`trait_locus_overlap` cells copied exactly):"
        )
        lines.append("")
        lines.append(
            "**CN**: 整理后的 GWAS 表（来源：`results/gwas/index.tsv`；"
            "`trait_locus_overlap` 单元格原样复制）："
        )
        lines.append("")
        gwas_tbl = []
        for r in gwas_rows:
            overlap = r.get("trait_locus_overlap") or ""
            gwas_tbl.append(
                [
                    r.get("trait", ""),
                    r.get("n", ""),
                    _fmt(float(r["lambda"]), 3) if r.get("lambda") else "—",
                    r.get("n_bonf", ""),
                    f"{r.get('top_chrom', '')}:{r.get('top_pos', '')}",
                    r.get("top_gene", "") or "—",
                    overlap if overlap else "—",
                ]
            )
        lines.extend(
            _md_table(
                [
                    "trait",
                    "n",
                    "λ_GC",
                    "n Bonferroni",
                    "lead",
                    "gene",
                    "trait_locus_overlap (exact source cell)",
                ],
                gwas_tbl,
            )
        )
        lines.append("")
        lines.append(
            "**EN**: Positive controls: OIV 225_bin overlaps `OIV_225`; OIV 151_bin overlaps "
            "`sdr`; no OIV 241 locus overlap found in the panel GWAS."
        )
        lines.append("")
        lines.append(
            "**CN**: 阳性对照：OIV 225_bin 与 `OIV_225` 重合；OIV 151_bin 与 `sdr` 重合；"
            "panel GWAS 未发现 OIV 241 位点重合。"
        )
        lines.append("")

    # 5
    lines.append(f"## 5. {SECTION_TITLES[4]} / {SECTION_TITLES_CN[4]}")
    lines.append("")
    gs_models = (
        "**EN**: Models: GBLUP-REML (VanRaden 2008; Habier 2007); rrBLUP dual "
        "(Meuwissen 2001; Endelman 2011); RKHS Gaussian kernel averaging "
        "(Gianola 2008; de los Campos 2010; Pérez 2014); Elastic Net FISTA "
        "(Zou & Hastie 2005; Beck & Teboulle 2009; Ogutu 2012); top-k ridge"
    )
    if with_bayes:
        gs_models += "; BayesCπ (Habier 2011; ≤20k markers)"
    gs_models += (
        ". Shared k-fold CV. Recorded run: "
        f"k={gs_p.get('k_folds', '—')}, repeats={gs_p.get('repeats', '—')}, "
        f"max_sites={gs_p.get('max_sites', '—')}."
    )
    lines.append(gs_models)
    lines.append("")
    cn_gs = "**CN**: 上述模型同一折划分；最优模型按平均 Pearson *r*。"
    if with_bayes:
        cn_gs += "含 BayesCπ（Habier 2011）。"
    lines.append(cn_gs)
    lines.append("")
    if gs_rows:
        lines.append("**EN**: Curated GS (`results/gs/index.tsv`):")
        lines.append("")
        lines.append("**CN**: 整理后的 GS（`results/gs/index.tsv`）：")
        lines.append("")
        gs_tbl = []
        for r in gs_rows:
            cv = r.get("cv_r") or ""
            try:
                cv_s = _fmt(float(cv), 3)
            except (TypeError, ValueError):
                cv_s = str(cv)
            gs_tbl.append(
                [
                    r.get("trait", ""),
                    r.get("scale", ""),
                    r.get("n", ""),
                    r.get("best_model", ""),
                    cv_s,
                ]
            )
        lines.extend(
            _md_table(["trait", "scale", "n", "best model", "panel CV r"], gs_tbl)
        )
        lines.append("")
        lines.append("**EN**: OIV 452 / 455 skipped (n = 0 after parse).")
        lines.append("")
        lines.append("**CN**: OIV 452 / 455 已跳过（解析后 n = 0）。")
        lines.append("")

    # 6
    lines.append(f"## 6. {SECTION_TITLES[5]} / {SECTION_TITLES_CN[5]}")
    lines.append("")
    lines.append(
        "**EN**: Usefulness criterion $\\mathrm{UC} = \\mu_{\\mathrm{progeny}} + i\\,\\sigma_{\\mathrm{progeny}}$ "
        "with $i=1.755$ (10% truncation; Zhong & Jannink 2007; Lehermeier 2017). "
        "$\\sigma^2$ ignores LD (independent-loci approximation). "
        "Kinship filter KING-robust > 0.0884 / ≥ 0.354 (Manichaikul 2010). "
        "Both-female pairs dropped."
    )
    lines.append("")
    lines.append("**CN**: 有用性准则 + 无连锁的后代方差近似 + KING 亲缘过滤 + 雌×雌剔除。")
    lines.append("")
    if cr_c:
        lines.extend(
            _md_table(
                ["Item", "Value"],
                [
                    ["parent", str(cr_c.get("parent", "—"))],
                    ["target", str((cross.get("parameters") or {}).get("target", "—"))],
                    ["candidates", str(cr_c.get("n_candidates", "—"))],
                    ["pairs scored", str(cr_c.get("n_pairs_total", "—"))],
                    ["removed kinship", str(cr_c.get("n_removed_kinship", "—"))],
                    ["removed sex", str(cr_c.get("n_removed_sex", "—"))],
                    ["removed clone", str(cr_c.get("n_removed_clone", "—"))],
                    ["reported", str(cr_c.get("n_reported", "—"))],
                    ["output", _rel(cr_c.get("out_tsv", "results/cross/HUN89_mates.tsv"))],
                ],
            )
        )
        lines.append("")

    # 7
    lines.append(f"## 7. {SECTION_TITLES[6]} / {SECTION_TITLES_CN[6]}")
    lines.append("")
    lines.extend(
        _md_table(
            ["Software", "Version"],
            [
                ["Python", str(vers.get("python") or "—")],
                ["NumPy", str(vers.get("numpy") or "—")],
                ["SciPy", str(vers.get("scipy") or "—")],
                ["PyTorch", str(vers.get("torch") or "not installed")],
                ["git", str(vers.get("git_sha") or "—")[:12]],
            ],
        )
    )
    lines.append("")

    if not embed:
        # 8 (documentation only)
        lines.append(f"## 8. {SECTION_TITLES[7]} / {SECTION_TITLES_CN[7]}")
        lines.append("")
        lines.append(
            "**EN**: Random forests / GBM not used (sklearn binary incompatible here). "
            "Multi-trait GBLUP and ordinal threshold models not implemented. "
            "No genetic map, so no LD-aware progeny variance. Genomic mating optimiser not implemented."
        )
        lines.append("")
        lines.append(
            "**CN**: 未用 RF/GBM、多性状 GBLUP、有序阈值模型；无图谱故无 LD 后代方差；"
            "未做 genomic mating 优化。"
        )
        lines.append("")

    # 9
    lines.append(f"## 9. {SECTION_TITLES[8]} / {SECTION_TITLES_CN[8]}")
    lines.append("")
    lines.extend(_emit_caveat_items(caveats, embed=embed))
    lines.append("")

    # 10
    lines.append(f"## 10. {SECTION_TITLES[9]} / {SECTION_TITLES_CN[9]}")
    lines.append("")
    for k in used_keys:
        f = bib.get(k, {})
        doi = f.get("doi", "")
        url = f.get("url", "")
        title = f.get("title", "") or k
        link = f"https://doi.org/{doi}" if doi else url
        if link:
            lines.append(f"- `{k}` {title}. <{link}>")
        else:
            lines.append(f"- `{k}` {title}")
    lines.append("")

    if not embed:
        lines.append("## Reproduce")
        lines.append("")
        lines.append(
            "These commands rebuild the 2449 **panel** phenotype table, GWAS, GS models, "
            "this methods appendix, and a sample report. They are a lab recipe, not required "
            "to read an already-written HTML report. `HUN89` here is the example source sample "
            "in this file. Wall time is a local MacBook Pro note, not a paper result."
        )
        lines.append("")
        lines.append("```bash")
        lines.append("conda activate ga")
        lines.append("cd grapeancestry_suite")
        lines.append("python scripts/build_phenotype.py")
        lines.append(
            'grapeancestry gwas --pheno data/phenotype.tsv --trait "OIV 225" --source euvitis --binary'
        )
        lines.append("grapeancestry gwas --pheno data/phenotype.tsv --curated")
        lines.append("grapeancestry gs-train --pheno data/phenotype.tsv --curated")
        lines.append("grapeancestry gs-predict --sample HUN89 --min-cv-r 0.2")
        lines.append(
            'grapeancestry cross-recommend --target "OIV 225=1,OIV 241=1" --parent HUN89'
        )
        lines.append("python -m grapeancestry.breeding.methods_doc")
        lines.append("grapeancestry analyze --sample HUN89")
        lines.append("```")
        lines.append("")
        lines.append(
            "Wall time on MBP: ETL <2 min; one GWAS trait ~1–2 min; curated GWAS ~20 min; "
            "curated GS (6 models, 3-fold, 3000 sites) ~30 s; analyze ~3 min."
        )
        lines.append("")
    return "\n".join(lines)


TABLE_HEADER_CN = {
    "Node": "节点",
    "Count": "计数",
    "Note": "说明",
    "trait": "性状",
    "n Bonferroni": "Bonferroni 数",
    "lead": "主位点",
    "gene": "基因",
    "trait_locus_overlap (exact source cell)": "位点重合（源单元格）",
    "scale": "量表",
    "best model": "最优模型",
    "panel CV r": "面板交叉验证 r",
    "Item": "项目",
    "Value": "值",
    "Software": "软件",
    "Version": "版本",
}

EVIDENCE_SOURCE_LABELS = (
    ("results/gs/index.tsv", "local GS summary", "本地 GS 汇总"),
    ("results/provenance/gs_train.json", "GS training provenance", "GS 训练溯源"),
    (
        "results/gwas/euvitis/OIV_241_bin/summary.json",
        "OIV 241 GWAS summary",
        "OIV 241 GWAS 汇总",
    ),
)

_HEADING_BI = re.compile(
    r"^(?P<prefix>(?:\d+\.\s+)?)(?P<en>.+?)\s+/\s+(?P<zh>.+)$"
)
_LANG_PARA = re.compile(r"^\*\*(EN|CN)\*\*[：:]\s*(?P<body>.*)$", re.S)


def _bilingual_phrase(en: str, zh: str) -> str:
    return f'<span class="en">{en}</span><span class="cn">{zh}</span>'


def _heading_html(title: str, level: int) -> str:
    match = _HEADING_BI.match(title)
    if match:
        prefix = html.escape(match.group("prefix") or "")
        inner = (
            f'{prefix}<span class="en">{_inline_md(match.group("en"))}</span>'
            f'<span class="cn">{_inline_md(match.group("zh"))}</span>'
        )
    else:
        inner = _inline_md(title)
    return f"<h{level}>{inner}</h{level}>"


def _th_html(header: str) -> str:
    cell = _inline_md(header)
    zh = TABLE_HEADER_CN.get(header)
    if not zh or zh == header:
        return f"<th>{cell}</th>"
    return (
        f'<th><span class="en">{cell}</span>'
        f'<span class="cn">{_inline_md(zh)}</span></th>'
    )


def localize_shared_cell(text: str) -> str:
    """Bounded EN/CN map for ETL notes, cross labels, and software status."""
    zh = CELL_PHRASE_CN.get(text)
    if zh is None:
        return _inline_md(text)
    return _bilingual_phrase(_inline_md(text), _inline_md(zh))


def _td_html(cell: str) -> str:
    return f"<td>{localize_shared_cell(cell)}</td>"


def _li_html(text: str) -> str:
    match = _LANG_PARA.match(text)
    if match:
        cls = "en" if match.group(1) == "EN" else "cn"
        return f'<li class="{cls}">{_inline_md(match.group("body"))}</li>'
    return f"<li>{_inline_md(text)}</li>"


def _paragraph_html(text: str) -> str:
    match = _LANG_PARA.match(text)
    if match:
        cls = "en" if match.group(1) == "EN" else "cn"
        return f'<p class="{cls}">{_inline_md(match.group("body"))}</p>'
    return f"<p>{_inline_md(text)}</p>"


def _inline_md(text: str) -> str:
    text = html.escape(text)

    def _code(m: re.Match[str]) -> str:
        return f"<code>{m.group(1)}</code>"

    text = re.sub(r"`([^`]+)`", _code, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"\$([^$]+)\$", r"<span class='math'>\1</span>", text)
    text = re.sub(r"&lt;(https?://[^&]+)&gt;", r'<a href="\1">\1</a>', text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def markdown_to_html(md: str) -> str:
    """Small subset: headings, tables, lists, fenced code, paragraphs."""
    chunks: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            fence = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                fence.append(html.escape(lines[i]))
                i += 1
            i += 1
            chunks.append("<pre><code>" + "\n".join(fence) + "</code></pre>")
            continue
        if line.startswith("| ") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            header = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            thead = "".join(_th_html(h) for h in header)
            body = []
            for row in rows:
                tds = "".join(_td_html(c) for c in row)
                body.append(f"<tr>{tds}</tr>")
            chunks.append(
                f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(body)}</tbody></table>"
            )
            continue
        if line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            title = line[hashes:].strip()
            chunks.append(_heading_html(title, min(hashes, 4)))
            i += 1
            continue
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(_li_html(lines[i][2:]))
                i += 1
            chunks.append("<ul>" + "".join(items) + "</ul>")
            continue
        if not line.strip():
            i += 1
            continue
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "-", "`")):
            para.append(lines[i])
            i += 1
        chunks.append(_paragraph_html(" ".join(para)))
    return "\n".join(chunks)


def sanitize_methods_html(html: str) -> str:
    """Hide internal paths while keeping bilingual evidence-source labels."""
    html = str(html or "")
    for path, en, zh in EVIDENCE_SOURCE_LABELS:
        label = _bilingual_phrase(en, zh)
        escaped = re.escape(path)
        html = re.sub(rf"<code>{escaped}</code>", label, html)
        html = re.sub(rf">{escaped}<", f">{label}<", html)
        html = re.sub(rf"`{escaped}`", label, html)
    generic = (
        (r"<code>[^<]*2449\.info[^<]*</code>", "the 2449 panel IDs", "2449 面板 ID"),
        (r"<code>[^<]*panel_dosage[^<]*</code>", "the dosage matrix", "剂量矩阵"),
        (
            r"<code>[^<]*gwas_exclude[^<]*</code>",
            "the GWAS/trait-locus exclude list",
            "GWAS/性状位点排除表",
        ),
        (r"<code>results/[^<]+</code>", "the results tables", "结果表"),
        (r"<code>data/panel/[^<]+</code>", "the panel metadata", "面板元数据"),
        (r">results/[^<]+<", "the results tables", "结果表"),
        (r">data/panel/[^<]+<", "the panel metadata", "面板元数据"),
        (r"`results/[^`]+`", "the results tables", "结果表"),
        (r"`data/panel/[^`]+`", "the panel metadata", "面板元数据"),
        (r"`[^`]*\.(?:tsv|info|npz|xlsx|json)[^`]*`", "the source table", "源表"),
    )
    for pattern, en, zh in generic:
        label = _bilingual_phrase(en, zh)
        if pattern.startswith(">"):
            html = re.sub(pattern, f">{label}<", html)
        else:
            html = re.sub(pattern, label, html)
    return html


def methods_html_section(
    provenance_dir: Path,
    bib_path: Path | None = None,
    *,
    include_reproduce: bool = False,
) -> str:
    recs = load_all_provenance(provenance_dir)
    bib = (
        parse_bib_keys(bib_path.read_text(encoding="utf-8"))
        if bib_path and bib_path.exists()
        else {}
    )
    root = provenance_dir.parent.parent if provenance_dir.name == "provenance" else None
    md = render_methods_markdown(recs, bib, root=root, embed=not include_reproduce)
    if not include_reproduce:
        md = _UNUSED_METHODS_SECTION.sub("", md)
        md = md.split("\n## Reproduce\n", 1)[0].rstrip() + "\n"
    inner = sanitize_methods_html(markdown_to_html(md))
    return (
        '<div class="methods-breeding">'
        '<h3><span class="en">Breeding methods &amp; data</span>'
        '<span class="cn">育种方法与数据</span></h3>'
        f"{inner}</div>"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=None)
    args = p.parse_args(argv)
    root = args.root or Path(__file__).resolve().parents[3]
    prov = root / "results" / "provenance"
    bib_path = root / "docs" / "REFERENCES.bib"
    recs = load_all_provenance(prov)
    bib = parse_bib_keys(bib_path.read_text(encoding="utf-8")) if bib_path.exists() else {}
    md = render_methods_markdown(recs, bib, root=root)
    dest = root / "docs" / "METHODS_breeding.md"
    dest.write_text(md, encoding="utf-8")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
