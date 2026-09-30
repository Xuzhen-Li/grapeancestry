"""Dashboard-style HTML report (form inspired by grouping_663/dashboard).

Sidebar nav + pinned sample bar + sectioned panels — static (no Plotly CDN).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grapeancestry.report.build_report import ReportBundle


def _fmt(x: float, nd: int = 2) -> str:
    if x != x:
        return "NA"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    return f"{x:.{nd}f}"


def _img(b64: str | None) -> str:
    if not b64:
        return "<p class='muted'>Not available.</p>"
    return f'<img src="data:image/png;base64,{b64}" style="max-width:100%;height:auto;"/>'


def render_dashboard(bundle: "ReportBundle", out_html: Path, images: dict) -> Path:
    qc_rows = "".join(
        f"<tr><td>{k}</td><td>{_fmt(v, 4) if isinstance(v, float) and abs(v) < 10 else _fmt(v)}</td></tr>"
        for k, v in bundle.qc.items()
    )
    ibs_rows = "".join(
        f"<tr><td>{i}</td><td>{r.get('ref','')}</td><td>{r.get('relationship','')}</td>"
        f"<td>{r.get('R1','')}</td><td>{r.get('KING_Robust','')}</td>"
        f"<td>{r.get('IBS2*_pct','')}</td></tr>"
        for i, r in enumerate(bundle.ibs_relationships[:12], 1)
    )
    sum_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in bundle.ibs_summary.items()
    ) or "<tr><td colspan=2>—</td></tr>"
    clone_rows = "".join(
        f"<tr><td>{r.get('relationship','')}</td><td>{r.get('ref','')}</td>"
        f"<td>{r.get('R1','')}</td><td>{r.get('KING_Robust','')}</td>"
        f"<td>{r.get('IBS2*_pct','')}</td></tr>"
        for r in bundle.clone_hits[:40]
    ) or "<tr><td colspan=5>No Identical / PO hits vs panel.</td></tr>"
    sel_rows = "".join(
        f"<tr><td>{o.get('site','')}</td><td>{_fmt(float(o.get('het', float('nan'))), 4)}</td>"
        f"<td>{o.get('gene','')}</td><td>{o.get('dist','')}</td>"
        f"<td>{o.get('region','')}</td></tr>"
        for o in bundle.selection_outliers[:20]
    ) or "<tr><td colspan=5>—</td></tr>"
    named_rows = "".join(
        f"<tr><td>{r.get('name','')}</td><td>{r.get('chrom','')}:{r.get('start','')}-{r.get('end','')}</td>"
        f"<td>{r.get('n_sites','')}</td><td>{r.get('mean_het','')}</td>"
        f"<td>{r.get('mean_fst','')}</td></tr>"
        for r in (getattr(bundle, "selection_named", None) or [])
    ) or "<tr><td colspan=5>—</td></tr>"
    by_grp_rows = "".join(
        f"<tr><td>{r.get('grp','')}</td><td>{r.get('n_samples','')}</td><td>{r.get('name','')}</td>"
        f"<td>{r.get('n_sites','')}</td><td>{r.get('mean_het','')}</td>"
        f"<td>{r.get('mean_fst_vs_rest', r.get('mean_fst',''))}</td></tr>"
        for r in (getattr(bundle, "selection_by_grp", None) or [])
    ) or "<tr><td colspan=6>—</td></tr>"
    f3_rows = "".join(
        f"<tr><td>{r.get('label','')}</td><td>{_fmt(float(r.get('value', float('nan'))), 5)}</td></tr>"
        for r in bundle.f3_rows[:15]
    ) or "<tr><td colspan=2>—</td></tr>"
    f4_rows = "".join(
        f"<tr><td>{r.get('label','')}</td><td>{_fmt(float(r.get('value', float('nan'))), 5)}</td></tr>"
        for r in bundle.f4_rows[:15]
    ) or "<tr><td colspan=2>—</td></tr>"
    trait_rows = "".join(
        f"<tr><td>{t['site']}</td><td>{t['trait']}</td><td>{t.get('descriptor','')}</td>"
        f"<td>{t.get('gene','')}</td><td>{t.get('dist','')}</td>"
        f"<td>{t.get('region','')}</td><td>{t['note']}</td></tr>"
        for t in bundle.trait_hits[:20]
    ) or "<tr><td colspan=7>—</td></tr>"
    kin_rows = "".join(
        f"<tr><td>{r.get('rank', i)}</td><td>{r.get('ref_id', '')}</td>"
        f"<td>{r.get('relationship', '')}</td>"
        f"<td>{r.get('KING_Robust', r.get('kinship', ''))}</td></tr>"
        for i, r in enumerate(bundle.kinship_top, 1)
    ) or "<tr><td colspan=4>—</td></tr>"
    conc = "".join(f"<li>{c}</li>" for c in bundle.conclusions)
    gs = bundle.gs
    from grapeancestry.report.build_report import pca_method_label

    n_id = int(bundle.ibs_summary.get("Identical", 0))
    n_po = int(bundle.ibs_summary.get("Parent-Offspring", 0))
    pin_detail = (
        f"PC1={bundle.pca_sample[0]:.3f} PC2={bundle.pca_sample[1]:.3f} · "
        f"{pca_method_label(bundle.pca_method)} · "
        f"clone-screen Identical={n_id} PO={n_po}"
    )

    # ADMIXTURE table
    admix_tbl = "<p class='muted'>ADMIXTURE unavailable.</p>"
    ac = bundle.admix_contrast
    if ac and (ac.q_by_k or ac.projected_by_k or ac.panel_mean_by_k):
        rows = []
        ks = sorted(set(ac.q_by_k) | set(ac.projected_by_k) | set(ac.panel_mean_by_k))

        def fmt(d: dict) -> str:
            if not d:
                return "—"
            return " ".join(f"{d[c]:.2f}" for c in sorted(d, key=lambda x: int(x[1:])))

        for k in ks:
            rows.append(
                f"<tr><td>K={k}</td><td><code>{fmt(ac.q_by_k.get(k, {}))}</code></td>"
                f"<td><code>{fmt(ac.projected_by_k.get(k, {}))}</code></td>"
                f"<td><code>{fmt(ac.grp_mean_by_k.get(k, {}))}</code></td>"
                f"<td><code>{fmt(ac.panel_mean_by_k.get(k, {}))}</code></td></tr>"
            )
        admix_tbl = (
            f"<p>K=2–8 Q for this sample vs panel means.</p>"
            f"<table><tr><th>K</th><th>lookup</th><th>projected</th><th>Grp mean</th><th>panel</th></tr>"
            f"{''.join(rows)}</table>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GrapeAncestry — {bundle.sample}</title>
<style>
:root {{
  --bg:#f7f5f1; --surface:#fff; --text:#1a1a1a; --muted:#666;
  --accent:#2f5d3a; --border:#ddd; --amber:#b45309;
  --sidebar:200px;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Georgia, "Songti SC", serif; color:var(--text); background:var(--bg); }}
nav.sidebar {{
  position:fixed; left:0; top:0; bottom:0; width:var(--sidebar);
  background:#1e2a22; color:#e8efe9; overflow-y:auto; padding:14px 0; z-index:50;
}}
nav.sidebar .brand {{ padding:0 14px 10px; font-weight:700; font-size:13px; color:#9fd0a8; }}
nav.sidebar .sub {{ padding:0 14px 8px; font-size:10px; color:#8a9; }}
nav.sidebar h2 {{ margin:14px 14px 4px; font-size:10px; text-transform:uppercase; letter-spacing:.06em; color:#7a9080; }}
nav.sidebar a {{
  display:block; padding:6px 14px; color:#d5e0d8; text-decoration:none; font-size:12px;
}}
nav.sidebar a:hover, nav.sidebar a.active {{ background:#2a3b30; color:#fff; }}
.main {{ margin-left:var(--sidebar); }}
#top-bar {{
  position:sticky; top:0; z-index:40; background:var(--surface);
  border-bottom:1px solid var(--border); box-shadow:0 1px 6px rgba(0,0,0,.06);
}}
#pinned {{
  padding:8px 18px; background:#fff8eb; border-bottom:1px solid #f0d9a8; font-size:12px;
}}
#pinned strong {{ color:var(--amber); }}
section {{ padding:18px 22px 8px; max-width:980px; }}
section h2 {{ color:var(--accent); border-bottom:2px solid var(--accent); padding-bottom:4px; font-size:1.25rem; }}
.info-box {{
  background:#eef5ef; border-left:4px solid var(--accent); padding:10px 12px;
  font-size:.9rem; color:#333; margin:.6rem 0 1rem;
}}
.card {{ background:var(--surface); border:1px solid var(--border); padding:12px 14px; margin:10px 0; }}
table {{ border-collapse:collapse; width:100%; margin:.5rem 0 1rem; font-size:.88rem; }}
th,td {{ border:1px solid #ccc; padding:.35rem .5rem; text-align:left; }}
th {{ background:#e8f0ea; }}
.muted {{ color:var(--muted); font-size:.88rem; }}
img {{ border:1px solid #e0e0e0; background:#fff; }}
.star {{ background:#eef5ef; padding:.8rem 1rem; border-left:4px solid var(--accent); }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
@media (max-width:900px) {{
  nav.sidebar {{ width:56px; }}
  nav.sidebar .brand, nav.sidebar .sub, nav.sidebar h2, nav.sidebar a {{ font-size:0; padding:8px; }}
  .main {{ margin-left:56px; }}
  .grid2 {{ grid-template-columns:1fr; }}
}}
</style>
<script>
function go(id) {{
  document.querySelectorAll('nav.sidebar a').forEach(a => a.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({{behavior:'smooth', block:'start'}});
  const link = document.querySelector('nav.sidebar a[data-id="'+id+'"]');
  if (link) link.classList.add('active');
  return false;
}}
</script>
</head><body>
<nav class="sidebar">
  <div class="brand">GrapeAncestry</div>
  <div class="sub">167K capture · sample report<br/>layout ≈ Italy grouping dashboard</div>
  <h2>Overview</h2>
  <a href="#summary" data-id="summary" class="active" onclick="return go('summary')">Conclusions</a>
  <h2>Capture</h2>
  <a href="#qc" data-id="qc" onclick="return go('qc')">QC / depth / call rate</a>
  <a href="#damage" data-id="damage" onclick="return go('damage')">Damage</a>
  <h2>Identity</h2>
  <a href="#clone" data-id="clone" onclick="return go('clone')">Clone + PO list</a>
  <a href="#ibs" data-id="ibs" onclick="return go('ibs')">4K IBS / KING</a>
  <h2>Ancestry</h2>
  <a href="#pca" data-id="pca" onclick="return go('pca')">PCA + ADMIXTURE</a>
  <a href="#tree" data-id="tree" onclick="return go('tree')">NJ Tree</a>
  <h2>Affinity / Selection / Breeding</h2>
  <a href="#fstats" data-id="fstats" onclick="return go('fstats')">f3 / f4</a>
  <a href="#sel" data-id="sel" onclick="return go('sel')">Selection (named windows + Fst)</a>
  <h2>Breeding</h2>
  <a href="#gwas" data-id="gwas" onclick="return go('gwas')">GWAS / GS</a>
  <h2>Pop</h2>
  <a href="#pop" data-id="pop" onclick="return go('pop')">Fst / CoreSNP</a>
</nav>

<div class="main">
<div id="top-bar">
  <div id="pinned">🔍 <strong>{bundle.sample}</strong>
    <span class="muted" style="margin-left:8px">{pin_detail}</span>
  </div>
</div>

<section id="summary">
  <h2>Conclusions</h2>
  <div class="star"><ul>{conc}</ul></div>
  <p class="muted">{bundle.merged_vcf_note}</p>
</section>

<section id="qc">
  <h2>Capture QC</h2>
  <div class="info-box"><strong>Method</strong>: samtools bedcov on 167,433 panel sites + bcftools GT/DP.
  Covered = sites with depth≥1/5/10×. Calling rate = non-missing GT / VCF sites (and vs full panel).</div>
  <div class="card">{_img(images.get("qc"))}
  <table><tr><th>Metric</th><th>Value</th></tr>{qc_rows}</table></div>
</section>

<section id="damage">
  <h2>Damage</h2>
  <div class="card">{_img(images.get("damage"))}
  <p class="muted">mapDamage / damage_lite 5′ C→T. aDNA elevated at ends; modern usually flat.</p></div>
</section>

<section id="clone">
  <h2>Clone + PO list</h2>
  <div class="info-box"><strong>Italy clone screen</strong> (<code>CLONE_CONTEXT.md</code> / <code>clone_4k_summary</code>):
  Identical + Parent-Offspring only. Identical: R1≥1.2 + IBS2*%≥0.99 + KING≥0.3426.
  PO: 0.5&lt;R1&lt;1.2 + 0.21≤KING&lt;0.3426 + R0≤0.096. File: <code>*.ibs_clone_hits.tsv</code>.</div>
  <div class="card">
  <table><tr><th>Class</th><th>Ref</th><th>R1</th><th>KING</th><th>IBS2*%</th></tr>{clone_rows}</table>
  <h3>Class counts</h3>
  <table><tr><th>Class</th><th>Count</th></tr>{sum_rows}</table>
  </div>
</section>

<section id="ibs">
  <h2>4K IBS / KING</h2>
  <div class="card">{_img(images.get("ibs"))}
  <table><tr><th>#</th><th>Ref</th><th>Rel</th><th>R1</th><th>KING</th><th>IBS2*%</th></tr>{ibs_rows}</table>
  <h3>Kinship top</h3>
  <table><tr><th>#</th><th>Ref</th><th>Rel</th><th>KING</th></tr>{kin_rows}</table>
  <p class="muted">{bundle.purity_note}</p></div>
</section>

<section id="pca">
  <h2>PCA + ADMIXTURE</h2>
  <div class="info-box"><strong>PCA</strong>: {pca_method_label(bundle.pca_method)} (color={bundle.pca_color}).
  <strong>ADMIXTURE</strong>: K=2–8 use the declared component order.
  Names follow Dong et al. 2023 Fig. 1D.</div>
  <div class="card">{_img(images.get("pca"))}{_img(images.get("admix"))}{_img(images.get("admix_str"))}
  {admix_tbl}</div>
</section>

<section id="tree">
  <h2>NJ Tree</h2>
  <div class="info-box"><strong>Form</strong>: Italy dashboard NJ section (IBS → tree; query tip ★).
  Here: dosage IBS (1 − genotype identity) on <strong>all 2449 + query</strong> → Neighbor-Joining
  (Saitou &amp; Nei 1987 doi:10.1093/oxfordjournals.molbev.a040454). No Grp subsample.
  Branch length ≈ 1 − genotype-match fraction. Tips colored by Grp.</div>
  <div class="card">{_img(images.get("tree"))}</div>
</section>

<section id="fstats">
  <h2>f3 / f4</h2>
  <div class="info-box"><strong>Method</strong>: Patterson f3/f4 on allele dosages vs GEO means (OUT as outgroup when present).
  Not ADMIXTURE / Dong Grp. Demo-scale on the available dosage cache — interpret directionally.
  qpGraph is not fitted (needs a population history graph, not a single query).</div>
  <div class="grid2">
    <div class="card">{_img(images.get("f3"))}
    <table><tr><th>f3</th><th>value</th></tr>{f3_rows}</table></div>
    <div class="card"><table><tr><th>f4</th><th>value</th></tr>{f4_rows}</table></div>
  </div>
</section>

<section id="sel">
  <h2>Selection (unphased)</h2>
  <div class="info-box"><strong>Scan</strong>: our MAS/GWAS named windows
  plus per-site Fst by Grp and ±50 kb windowed het on the 167K dosages.
  Screening = Fst(Grp vs rest), not one among-all-Grps statistic.
  Sweep = Fst vs rest ≥95th and within-Grp windowed het ≤5th.
  OUT skipped. Not XP-CLR/iHS/G12. Science tables are overlap checks only.
  Interactive HTML uses LocusZoom.js
  (Y = Fst / windowed het) plus Manhattan / Grp heatmap / Fst-vs-het scatter.</div>
  <div class="card">
  <table><tr><th>Window</th><th>Interval</th><th>n sites</th><th>mean het</th><th>mean Fst</th></tr>{named_rows}</table>
  <h3>By Grp</h3>
  <table><tr><th>Grp</th><th>n</th><th>Window</th><th>n sites</th><th>mean het</th><th>Fst vs rest</th></tr>{by_grp_rows}</table>
  {_img(images.get("selection"))}
  <table><tr><th>Site</th><th>het</th><th>Gene</th><th>Dist</th><th>Region</th></tr>{sel_rows}</table></div>
</section>

<section id="gwas">
  <h2>GWAS / GS ({bundle.gwas_trait})</h2>
  <div class="card">
  <table><tr><th>Site</th><th>Trait</th><th>Descriptor</th><th>Gene</th><th>Dist</th><th>Region</th><th>Note</th></tr>{trait_rows}</table>
  <p>GS CV: rrBLUP r={_fmt(gs.get('rrblup_r', float('nan')), 3)};
  GBLUP r={_fmt(gs.get('gblup_r', float('nan')), 3)};
  MLP r={_fmt(gs.get('mlp_r', float('nan')), 3)};
  CNN r={_fmt(gs.get('cnn_r', float('nan')), 3)}</p>
  </div>
</section>

<section id="pop">
  <h2>Population context</h2>
  <div class="card">
  <p>Weir–Cockerham Fst (top-2 Grp demo): <strong>{_fmt(bundle.fst, 4) if bundle.fst is not None else 'NA'}</strong></p>
  <p>GEA Spearman r: <strong>{_fmt(bundle.gea_r, 4) if bundle.gea_r is not None else 'NA'}</strong></p>
  <p>CoreSNP (demo): <code>{', '.join(bundle.coresnp[:12]) or 'NA'}</code></p>
  </div>
</section>

<p class="muted" style="padding:8px 22px 24px">GrapeAncestry Suite · sidebar form ≈ Italy <code>grouping_663</code> dashboard · see docs/BUILD.md</p>
</div>
</body></html>"""
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html)
    return out_html
