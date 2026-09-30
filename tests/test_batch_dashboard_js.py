"""Batch-mode dashboard JS: switcher, PCA stars, ADMIXTURE ticks, graph edges."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from grapeancestry.report import interactive_dashboard
from grapeancestry.report.interactive_dashboard import APP_JS


def _run_node(probe: str) -> dict:
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


_DOC = r"""
function makeEl(){
  return {
    innerHTML:'', textContent:'', value:'', hidden:false, style:{},
    className:'', attrs:{},
    classList:{
      add:function(){}, remove:function(){}, toggle:function(){}, contains:function(){return false;}
    },
    setAttribute:function(k,v){this.attrs[k]=v;},
    getAttribute:function(k){return this.attrs[k]||null;},
    removeAttribute:function(k){delete this.attrs[k];},
    addEventListener:function(kind, fn){
      (this._listeners||(this._listeners={}))[kind]=fn;
    },
    appendChild:function(){},
    querySelectorAll:function(){return [];},
    querySelector:function(){return null;}
  };
}
var window={_authorMatchIds:[]};
var els={};
document={
  getElementById:function(id){return els[id]||(els[id]=makeEl());},
  querySelectorAll:function(){return [];},
  querySelector:function(){return null;},
  createElement:function(){return makeEl();},
  addEventListener:function(){},
  documentElement:{setAttribute:function(){}, getAttribute:function(){return 'en';}, style:{}}
};
"""


def test_batch_switcher_pca_admixture_and_graph() -> None:
    observed = _run_node(
        _DOC
        + r"""
D={
  batch:true,
  query:'A',
  queries:[
    {id:'A', library_type:'adna', calling_rate:11, nearest_id:'840', nearest_class:'Parent-Offspring', nearest_king:'0.2895'},
    {id:'B', library_type:'adna', calling_rate:22, nearest_id:'26', nearest_class:'Full Sib', nearest_king:'0.1899'},
    {id:'C', library_type:'adna', calling_rate:33, nearest_id:'GM17', nearest_class:'Unrelated', nearest_king:'-0.2'}
  ],
  per_query:{
    A:{qc:{calling_rate_panel_pct:11}, conclusions:['from A'], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null},
    B:{qc:{calling_rate_panel_pct:22}, conclusions:['from B'], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null},
    C:{qc:{calling_rate_panel_pct:33}, conclusions:['from C'], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null}
  },
  pca_points:[
    {iid:'P', grp:'CG1', pcs:[0,0,0]},
    {iid:'A', grp:'QUERY', pcs:[1,1,1], query:true},
    {iid:'B', grp:'QUERY', pcs:[2,2,2], query:true},
    {iid:'C', grp:'QUERY', pcs:[3,3,3], query:true}
  ],
  pca_method:'',
  pca_evals:[],
  grp_colors:{CG1:'#cccccc'},
  admix_meta:{'2':{labels:['K1','K2'], colors:['#111111','#222222']}},
  admix_group_order:['CG1'],
  admix_query_in_panel:false,
  graph:{
    nodes:[
      {id:'A', kind:'query'}, {id:'B', kind:'query'}, {id:'C', kind:'query'},
      {id:'840', kind:'panel', label:'840 · SAVAGNIN BLANC'},
      {id:'26', kind:'panel', label:'26 · PINOT NOIR'}
    ],
    edges:[
      {source:'A', target:'840', class:'Parent-Offspring', king:0.2895, r1:0.82},
      {source:'B', target:'26', class:'Full Sib', king:0.1899, r1:0.4}
    ]
  }
};
SROWS=[
    {iid:'P', idx:0, grp:'CG1', qvals:{'2':[0.2,0.8]}},
    {iid:'26', idx:4, grp:'CG6', acc:'PINOT NOIR'},
    {iid:'840', idx:5, grp:'CG6', acc:'SAVAGNIN BLANC'},
  {iid:'A', idx:1, grp:'QUERY', qvals:{'2':[0.9,0.1]}, query:true},
  {iid:'B', idx:2, grp:'QUERY', qvals:{'2':[0.4,0.6]}, query:true},
  {iid:'C', idx:3, grp:'QUERY', qvals:{'2':[0.3,0.7]}, query:true}
];
QUERY='A';
batchUserAct=true;
var pca=buildPca2dFig(0,1);
var stars=pca.data.filter(function(tr){return tr.marker&&tr.marker.symbol==='star';});
var bar=buildAdmixFig(2);
var graph=buildRelGraphFig();
var edges=graph.data.filter(function(tr){return tr.meta==='edge-hover';}).map(function(tr){
  return tr.customdata[0];
});
setActiveQuery('B');
console.log(JSON.stringify({
  query:QUERY,
  calling:D.qc.calling_rate_panel_pct,
  starNames:stars.map(function(tr){return tr.name;}),
  tickvals:bar.layout.xaxis2.tickvals,
  edges:edges,
  tags:graph.data.filter(function(tr){return tr.meta==='edge-hover';}).map(function(tr){return tr.text[0];}),
  legend:graph.data.filter(function(tr){return tr.meta==='edge-legend';}).map(function(tr){return tr.name;}),
  panelText:graph.data.filter(function(tr){return tr.name&&String(tr.name).indexOf('Panel')>=0;}).map(function(tr){return tr.text;})[0],
  switcher:document.getElementById('batch-cards').innerHTML.indexOf('batch-card active')>=0,
  activeCard:document.getElementById('batch-cards').innerHTML.indexOf('data-query="B"')>=0,
  author:document.getElementById('author-intake').innerHTML
}));
"""
    )
    assert observed["query"] == "B"
    assert observed["calling"] == 22
    assert observed["starNames"] == ["A", "B", "C"]
    assert observed["tickvals"] == ["A", "B", "C"]
    assert observed["switcher"] is True
    assert observed["activeCard"] is True
    got = {(e[0], e[1], e[2]) for e in observed["edges"]}
    assert ("A", "840", "Parent-Offspring") in got
    assert ("B", "26", "Full Sib") in got
    assert "PO 0.290" in observed["tags"]
    assert "FS 0.190" in observed["tags"]
    assert "Parent-Offspring" in observed["legend"]
    assert "Full Sib" in observed["legend"]
    assert "PINOT NOIR" in observed["panelText"]
    assert "SAVAGNIN BLANC" in observed["panelText"]
    assert "value=\"B\"" in observed["author"] or ">B<" in observed["author"]


def test_batch_init_and_pin_do_not_switch_query() -> None:
    observed = _run_node(
        _DOC
        + r"""
D={
  batch:true,
  query:'V73_query',
  queries:[
    {id:'V73_query'},
    {id:'V74_query'},
    {id:'V114_query'}
  ],
  per_query:{
    V73_query:{qc:{}, conclusions:[], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null},
    V74_query:{qc:{}, conclusions:[], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null},
    V114_query:{qc:{}, conclusions:[], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null}
  },
  pca_points:[],
  graph:{nodes:[
    {id:'V73_query', kind:'query'},
    {id:'V74_query', kind:'query'},
    {id:'V114_query', kind:'query'},
    {id:'26', kind:'panel'}
  ], edges:[]}
};
SROWS=[
  {iid:'26', idx:0, grp:'CG6', acc:'PINOT NOIR'},
  {iid:'V73_query', idx:1, grp:'QUERY', query:true},
  {iid:'V74_query', idx:2, grp:'QUERY', query:true}
];
QUERY=D.query;
initBatchReport();
var sel=document.getElementById('batch-query-select');
sel.value='V74_query';
var change=sel._listeners&&sel._listeners.change;
if(change) change({isTrusted:true});
highlightSample('26');
highlightSample('V74_query');
console.log(JSON.stringify({query:QUERY, pinned:selectedIID}));
"""
    )
    assert observed["query"] == "V73_query"
    assert observed["pinned"] == "V74_query"


def test_relationship_graph_spreads_panel_hits_and_edge_labels() -> None:
    """Distances are Plotly data coordinates. Panel hits sit in a column."""
    observed = _run_node(
        r"""
function pack(n){
  var nodes=[{id:'Q', kind:'query'}];
  var edges=[];
  for(var i=0;i<n;i++){
    nodes.push({id:'H'+i, kind:'panel'});
    edges.push({source:'Q', target:'H'+i, class:'Full Sib', king:0.2, r1:0.3, n:10});
  }
  var pos=layoutRelGraph({nodes:nodes, edges:edges});
  var pts=[];
  for(var j=0;j<n;j++) pts.push(pos['H'+j]);
  var minD=null;
  for(var a=0;a<pts.length;a++){
    for(var b=a+1;b<pts.length;b++){
      var d=Math.hypot(pts[a].x-pts[b].x, pts[a].y-pts[b].y);
      if(minD===null||d<minD) minD=d;
    }
  }
  var labels=edges.map(function(e,i){return edgeLabelXY(e, pos, i);});
  var labelDup=false;
  for(var u=0;u<labels.length;u++){
    for(var v=u+1;v<labels.length;v++){
      if(Math.hypot(labels[u].x-labels[v].x, labels[u].y-labels[v].y)<1e-6) labelDup=true;
    }
  }
  return {minD:minD, labelDup:labelDup, nLabels:labels.length};
}
console.log(JSON.stringify({two:pack(2), four:pack(4)}));
"""
    )
    assert observed["two"]["minD"] >= 0.25
    assert observed["four"]["minD"] >= 0.25
    assert observed["two"]["labelDup"] is False
    assert observed["four"]["labelDup"] is False
    assert observed["two"]["nLabels"] == 2
    assert observed["four"]["nLabels"] == 4


def test_relationship_graph_keeps_clusters_apart_and_drops_isolates() -> None:
    observed = _run_node(
        r"""
var flower=[];
for(var i=0;i<8;i++) flower.push({source:'Q', target:'H'+i, class:'2nd', king:0.1, r1:0.2, n:10});
var nodes=[{id:'Q', kind:'query'}, {id:'Lone', kind:'query'}];
for(var j=0;j<8;j++) nodes.push({id:'H'+j, kind:'panel'});
var pos=layoutRelGraph({nodes:nodes, edges:flower});
var minD=null;
for(var a=0;a<8;a++){
  for(var b=a+1;b<8;b++){
    var d=Math.hypot(pos['H'+a].x-pos['H'+b].x, pos['H'+a].y-pos['H'+b].y);
    if(minD===null||d<minD) minD=d;
  }
}
var pair=layoutRelGraph({
  nodes:[
    {id:'A', kind:'query'}, {id:'B', kind:'query'},
    {id:'C', kind:'query'}, {id:'D', kind:'query'},
    {id:'Z', kind:'query'}
  ],
  edges:[
    {source:'A', target:'B', class:'Full Sib', king:0.2, r1:0.4, n:10},
    {source:'C', target:'D', class:'Full Sib', king:0.2, r1:0.4, n:10}
  ]
});
var gap=Math.abs(((pair.A.x+pair.B.x)/2)-((pair.C.x+pair.D.x)/2));
var yGap=Math.abs(((pair.A.y+pair.B.y)/2)-((pair.C.y+pair.D.y)/2));
console.log(JSON.stringify({
  minD:minD,
  lone:pos.Lone||null,
  gap:gap,
  yGap:yGap,
  short:graphQueryLabel('R-HW71_17_query'),
  spoke:!!layoutRelGraph({
    nodes:[
      {id:'Hub', kind:'query'}, {id:'Tail', kind:'query'},
      {id:'P0', kind:'panel'}, {id:'P1', kind:'panel'}, {id:'P2', kind:'panel'}
    ],
    edges:[
      {source:'Hub', target:'Tail', class:'Full Sib', king:0.2, r1:0.4, n:8},
      {source:'Hub', target:'P0', class:'2nd', king:0.1, r1:0.2, n:8},
      {source:'Hub', target:'P1', class:'2nd', king:0.1, r1:0.2, n:8},
      {source:'Hub', target:'P2', class:'2nd', king:0.1, r1:0.2, n:8}
    ]
  }).Tail
}));
"""
    )
    assert observed["minD"] >= 4.0
    assert observed["lone"] is None
    assert observed["gap"] >= 2.0
    assert observed["yGap"] < observed["gap"]
    assert observed["short"] == "R-HW71_17"
    assert observed["spoke"] is True


def test_related_queries_are_not_drawn_on_one_line() -> None:
    observed = _run_node(
        r"""
var pos=layoutRelGraph({
  nodes:[
    {id:'A', kind:'query'}, {id:'B', kind:'query'}, {id:'C', kind:'query'}
  ],
  edges:[
    {source:'A', target:'B', class:'Identical', king:0.49, r1:1.4, n:7000},
    {source:'B', target:'C', class:'Identical', king:0.48, r1:1.4, n:7000},
    {source:'A', target:'C', class:'Identical', king:0.47, r1:1.4, n:7000}
  ]
});
var area=Math.abs((pos.B.x-pos.A.x)*(pos.C.y-pos.A.y)-(pos.C.x-pos.A.x)*(pos.B.y-pos.A.y));
function off(e){
  var pts=relEdgePoints(e, pos);
  var mid=Math.floor((pts.x.length-1)/2);
  var a=pos[e.source], b=pos[e.target];
  var dx=b.x-a.x, dy=b.y-a.y, len=Math.hypot(dx, dy)||1;
  return Math.abs((pts.x[mid]-a.x)*(-dy/len)+(pts.y[mid]-a.y)*(dx/len));
}
var bows=[
  off({source:'A', target:'B'}),
  off({source:'B', target:'C'}),
  off({source:'A', target:'C'})
];
console.log(JSON.stringify({area:area, bows:bows}));
"""
    )
    assert observed["area"] > 1
    assert min(observed["bows"]) > 0.5


def test_panel_hover_includes_passport_and_kinship() -> None:
    observed = _run_node(
        r"""
SROWS=[{
  iid:'840', acc:'SAVAGNIN BLANC', vivc:'17636', origin:'France',
  grp:'CG6', comments:'accession Savagnin'
}];
var card=relNodeCard('840', {edges:[{
  source:'M-LM_22_query', target:'840', class:'Identical',
  king:0.455918, r1:null, n:7338, ibs0:0.000954, p0:0.549371
}]});
console.log(JSON.stringify({card:card}));
"""
    )
    text = observed["card"]
    assert "840" in text
    assert "SAVAGNIN BLANC" in text
    assert "VIVC 17636" in text
    assert "Identical" in text
    assert "0.456" in text
    assert "7338" in text
    assert "0.000954" in text
    assert "M-LM_22" in text


def test_panel_po_bridges_use_passport_only_on_4k() -> None:
    observed = _run_node(
        r"""
kinRule='4k';
panelPoOn=false;
SROWS=[
  {iid:'840', acc:'SAVAGNIN BLANC', po:'171 | 15'},
  {iid:'171', acc:'ARVINE PETITE', po:'840'}
];
var base={
  nodes:[
    {id:'Q1', kind:'query'}, {id:'Q2', kind:'query'},
    {id:'840', kind:'panel'}, {id:'171', kind:'panel'}
  ],
  edges:[
    {source:'Q1', target:'840', class:'Full Sib', king:0.2, r1:0.4, n:10},
    {source:'Q2', target:'171', class:'Full Sib', king:0.2, r1:0.4, n:10}
  ]
};
var closed=withPanelPoEdges(base).edges.filter(function(e){ return e.bridge; }).length;
panelPoOn=true;
var on=withPanelPoEdges(base);
var bridges=on.edges.filter(function(e){ return e.bridge==='4k-panel-po'; });
var linked=withPanelPoEdges({
  nodes:base.nodes,
  edges:base.edges.concat([{source:'Q1', target:'Q2', class:'Full Sib', king:0.2, r1:0.4, n:10}])
});
var same=linked.edges.filter(function(e){ return e.bridge==='4k-panel-po'; });
kinRule='ramos2019';
var off=withPanelPoEdges(base);
console.log(JSON.stringify({
  n:bridges.length,
  pair:[bridges[0].source, bridges[0].target].sort(),
  span:bridges[0].span,
  sameSpan:same[0].span,
  off:off.edges.filter(function(e){ return e.bridge; }).length,
  closed:closed,
  card:relNodeCard('840', linked)
}));
"""
    )
    assert observed["n"] == 1
    assert observed["pair"] == ["171", "840"]
    assert observed["span"] is True
    assert observed["sameSpan"] is False
    assert observed["off"] == 0
    assert observed["closed"] == 0
    assert "4K panel PO" in observed["card"]
    assert "ARVINE PETITE" in observed["card"]


def test_single_sample_pca_keeps_one_query_star() -> None:
    observed = _run_node(
        r"""
D={
  query:'ONLY',
  pca_points:[
    {iid:'P', grp:'CG1', pcs:[0,0,0]},
    {iid:'ONLY', grp:'QUERY', pcs:[1,2,3], query:true}
  ],
  pca_method:'',
  pca_evals:[],
  grp_colors:{CG1:'#cccccc'}
};
SROWS=[{iid:'ONLY', idx:0, grp:'QUERY'}];
QUERY='ONLY';
var fig=buildPca2dFig(0,1);
var stars=fig.data.filter(function(tr){return tr.marker&&tr.marker.symbol==='star';});
console.log(JSON.stringify({n:stars.length, name:stars[0]&&stars[0].name}));
"""
    )
    assert observed == {"n": 1, "name": "Query / ONLY"}


def test_section_query_pick_follows_active_query() -> None:
    observed = _run_node(
        _DOC
        + r"""
D={
  batch:true,
  query:'A',
  queries:[{id:'A'},{id:'B'}],
  per_query:{
    A:{qc:{}, conclusions:[], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null},
    B:{qc:{}, conclusions:[], query_meta:{}, report_meta:{}, clones:[], ibs_top:[], kinship_top:[], ibs_summary:{}, downloads:[], gs_pred:[], damage:null}
  }
};
QUERY='A';
batchUserAct=true;
var before=sectionQueryPickHtml();
setActiveQuery('B');
console.log(JSON.stringify({before:before, after:sectionQueryPickHtml()}));
"""
    )
    assert 'data-query="A"' in observed["before"]
    assert 'class="sec-q active"' in observed["before"]
    assert observed["before"].index('class="sec-q active"') < observed["before"].index('data-query="B"')
    assert 'data-query="B"' in observed["after"]
    assert 'class="sec-q active" data-query="B"' in observed["after"]


def test_clone_filter_keeps_selected_queries_and_cutoffs() -> None:
    observed = _run_node(
        _DOC
        + r"""
var graph={
  nodes:[
    {id:'A', kind:'query'}, {id:'B', kind:'query'}, {id:'C', kind:'query'},
    {id:'840', kind:'panel'}, {id:'26', kind:'panel'}
  ],
  edges:[
    {source:'A', target:'840', class:'Parent-Offspring', king:0.29, r1:0.8, n:1000},
    {source:'B', target:'26', class:'Full Sib', king:0.19, r1:0.4, n:50},
    {source:'A', target:'B', class:'2nd', king:0.1, r1:0.2, n:800},
    {source:'A', target:'C', class:'Identical', king:0.4, r1:2, n:900}
  ]
};
var pairs=[
  {sample_a:'A', sample_b:'B', relationship:'2nd', KING_Robust:'0.1', R1:'0.2', n_comparable:'800'},
  {sample_a:'A', sample_b:'C', relationship:'Identical', KING_Robust:'0.4', R1:'2', n_comparable:'900'},
  {sample_a:'B', sample_b:'C', relationship:'Unrelated', KING_Robust:'-0.2', R1:'0.01', n_comparable:'100'}
];
function ids(rows){ return rows.map(function(r){return r.query+'|'+r.partner+'|'+r.rel;}); }
function filt(raw){ return parseCloneFilter(raw).filter; }
var base={kingMin:'', kingMax:'', r1Min:'', nMin:''};
function spec(extra){ return filt(Object.assign({}, base, extra)); }
var one=collectCloneRows(graph, pairs, spec({queries:['A'], classes:['Identical','Parent-Offspring']}));
var both=collectCloneRows(graph, pairs, spec({queries:['A','B'], classes:['Parent-Offspring','Full Sib','2nd']}));
var king=collectCloneRows(graph, pairs, spec({queries:['A','B'], classes:['Parent-Offspring','Full Sib'], kingMin:'0.2'}));
var unrel=collectCloneRows(graph, pairs, spec({queries:['B','C'], classes:['Unrelated']}));
var ncut=collectCloneRows(graph, pairs, spec({queries:['A','B'], classes:['Full Sib','Parent-Offspring'], nMin:'100'}));
var r1=collectCloneRows(graph, pairs, spec({queries:['A'], classes:['Identical','Parent-Offspring'], r1Min:'1'}));
var bad=parseCloneFilter(Object.assign({}, base, {queries:['A'], classes:['Identical'], kingMin:'x'}));
var flipped=parseCloneFilter(Object.assign({}, base, {queries:['A'], classes:['Identical'], kingMin:'0.5', kingMax:'0.1'}));
var g=filteredRelGraph(graph, pairs, spec({queries:['A'], classes:['Identical']}));
D={
  batch:true,
  graph:graph,
  pairs:pairs,
  clones:[{rel:'Full Sib', ref:'DECOY', r1:'1', king:'0.2'}],
  ibs_summary:{Identical:1}
};
SROWS=[];
QUERY='A';
cloneFilter=spec({queries:['A'], classes:['Identical']});
fillCloneTable();
var table=document.getElementById('clone-table').innerHTML;
console.log(JSON.stringify({
  one:ids(one), both:ids(both), king:ids(king), unrel:ids(unrel), ncut:ids(ncut), r1:ids(r1),
  bad:bad.ok, flipped:flipped.ok,
  preset:cloneSelectionPreset('current',['A','B'],'B'),
  all:cloneSelectionPreset('all',['A','B'],'A'),
  none:cloneSelectionPreset('none',['A','B'],'A'),
  nodes:g.nodes.map(function(n){return n.id;}),
  edges:g.edges.map(function(e){return e.source+'|'+e.target+'|'+e.class;}),
  tableHasC:table.indexOf('>C<')>=0,
  tableHasDecoy:table.indexOf('DECOY')>=0,
  query:QUERY
}));
"""
    )
    assert observed["one"] == ["A|C|Identical", "A|840|Parent-Offspring"]
    assert observed["both"] == [
        "A|840|Parent-Offspring",
        "A|B|2nd",
        "B|26|Full Sib",
    ]
    assert observed["king"] == ["A|840|Parent-Offspring"]
    assert observed["unrel"] == ["B|C|Unrelated"]
    assert observed["ncut"] == ["A|840|Parent-Offspring"]
    assert observed["r1"] == ["A|C|Identical"]
    assert observed["bad"] is False
    assert observed["flipped"] is False
    assert observed["preset"] == ["B"]
    assert observed["all"] == ["A", "B"]
    assert observed["none"] == []
    assert observed["nodes"] == ["A", "C"]
    assert observed["edges"] == ["A|C|Identical"]
    assert observed["tableHasC"] is True
    assert observed["tableHasDecoy"] is False
    assert observed["query"] == "A"


def test_kin_rule_switches_the_same_pairs() -> None:
    observed = _run_node(
        r"""
D={
  batch:true,
  graph:{nodes:[{id:'A', kind:'query'}], edges:[]},
  pairs:[],
  kin_screen:{
    queries:['A'],
    edges:[
      {source:'A', target:'840', class:'Identical', ramos:'not_in_paper_bins', readv2:'IdenticalTwins/SameIndividual', king:0.456, r1:1.5, n:7000, ibs0:0.00095, p0:0.18, label:'Savagnin Blanc'},
      {source:'A', target:'171', class:'Parent-Offspring', ramos:'Highly_related', readv2:'First Degree', king:0.27, r1:0.8, n:7000, ibs0:0.008, p0:0.22, label:'Arvine Petite'}
    ]
  }
};
function ids(rows){ return rows.map(function(r){return r.query+'|'+r.partner+'|'+r.rel;}); }
function cut(classes){
  return {queries:['A'], classes:classes, kingMin:null, kingMax:null, r1Min:null, nMin:null, rule:kinRule};
}
kinRule='4k';
var four=collectCloneRows(kinViewSources().graph, kinViewSources().pairs, cut(['Identical','Parent-Offspring']));
var g4=relGraphForView();
kinRule='ramos2019';
var ramos=collectCloneRows(kinViewSources().graph, kinViewSources().pairs, cut(['Identical_clone','Highly_related','not_in_paper_bins']));
kinRule='readv2';
var read=collectCloneRows(kinViewSources().graph, kinViewSources().pairs, cut(['IdenticalTwins/SameIndividual','First Degree']));
var missing=kinRuleAvailable('ramos2019');
D.kin_screen=null;
var noScreen=kinRuleAvailable('ramos2019');
console.log(JSON.stringify({
  four:ids(four),
  graph:[g4.edges.map(function(e){return e.class;}), g4.nodes.some(function(n){return n.id==='840'&&n.kind==='panel';})],
  ramos:ids(ramos),
  read:ids(read),
  missing:missing,
  noScreen:noScreen,
  rules:KIN_RULES.map(function(r){return r.id;})
}));
"""
    )
    assert observed["four"] == ["A|840|Identical", "A|171|Parent-Offspring"]
    assert observed["graph"][0] == ["Identical", "Parent-Offspring"]
    assert observed["graph"][1] is True
    assert observed["ramos"] == ["A|171|Highly_related", "A|840|not_in_paper_bins"]
    assert observed["read"] == ["A|840|IdenticalTwins/SameIndividual", "A|171|First Degree"]
    assert observed["missing"] is True
    assert observed["noScreen"] is False
    assert observed["rules"] == ["4k", "ramos2019", "readv2"]


def test_batch_cards_stay_in_the_fixed_top_bar() -> None:
    src = Path(interactive_dashboard.__file__).read_text()
    top = src.index('<div id="top-bar">')
    pin = src.index('<div id="pinned-sample">')
    cards = src.index('<div id="batch-switcher">')
    assert top < cards < pin
    assert "sec-query-pick" in src
    assert "scroll-padding-top:250px" in src
    assert 'sec.id===\'clone\'' in src
    controls = src.index('id="clone-controls"')
    graph = src.index('id="plot-graph"')
    assert controls < graph
    assert 'id="clone-apply"' in src
    assert "clone-king-min" not in src
    assert "kinGateText" in src
    assert 'id="batch-cards-toggle"' in src
    assert "cards-collapsed" in src
    assert "max-height:min(168px,28vh)" in src


def test_many_queries_start_with_sample_cards_collapsed() -> None:
    observed = _run_node(
        _DOC
        + r"""
D={
  batch:true,
  query:'Q1',
  queries:[
    {id:'Q1'},{id:'Q2'},{id:'Q3'},{id:'Q4'},{id:'Q5'},
    {id:'Q6'},{id:'Q7'},{id:'Q8'},{id:'Q9'}
  ],
  per_query:{}
};
QUERY='Q1';
renderBatchSwitcher();
var host=document.getElementById('batch-switcher');
var before=host.className;
var expanded=document.getElementById('batch-cards-toggle').getAttribute('aria-expanded');
document.getElementById('batch-cards-toggle')._listeners.click();
console.log(JSON.stringify({
  before:before,
  after:host.className,
  expanded:expanded,
  opened:document.getElementById('batch-cards-toggle').getAttribute('aria-expanded'),
  count:document.getElementById('batch-cards-count').textContent,
  current:document.getElementById('batch-cards-current').textContent
}));
"""
    )
    assert observed["before"] == "is-on cards-collapsed"
    assert observed["expanded"] == "false"
    assert observed["after"] == "is-on"
    assert observed["opened"] == "true"
    assert observed["count"] == "9"
    assert observed["current"] == "Q1"


def test_kinship_gates_are_options_not_typed_cutoffs() -> None:
    observed = _run_node(
        _DOC
        + r"""
D={batch:true, queries:[{id:'A'}]};
QUERY='A';
kinRule='4k';
var four=kinClassPicksHtml('4k');
var ramos=kinClassPicksHtml('ramos2019');
var read=kinClassPicksHtml('readv2');
var controls=cloneControlsHtml();
console.log(JSON.stringify({
  four:four.indexOf('IBS2*')>=0 && four.indexOf('0.5&lt;R1&lt;1.2')>=0,
  ramos:ramos.indexOf('KING≥0.49')>=0 && ramos.indexOf('IBS0')>=0,
  read:read.indexOf('norm P0&lt;0.625')>=0,
  noNumber:controls.indexOf('type="number"')<0 && controls.indexOf('clone-king-min')<0,
  poSwitch:controls.indexOf('id="panel-po-toggle"')>=0 && controls.indexOf('id="panel-po-toggle" checked')<0,
  options:four.split('data-class=').length-1
}));
"""
    )
    assert observed["four"] is True
    assert observed["ramos"] is True
    assert observed["read"] is True
    assert observed["noNumber"] is True
    assert observed["poSwitch"] is True
    assert observed["options"] == 6


def test_rule_view_uses_every_query_not_the_open_sample() -> None:
    observed = _run_node(
        _DOC
        + r"""
D={
  batch:true,
  query:'IA-LC_01_query',
  queries:[{id:'IA-LC_01_query'},{id:'M-LM_22_query'}],
  kin_screen:{
    queries:['IA-LC_01_query','M-LM_22_query'],
    edges:[
      {source:'IA-LC_01_query', target:'M-C_27_query', class:'Unrelated', ramos:'not_in_paper_bins', readv2:'Unrelated', king:-0.2, r1:0.1, n:5000},
      {source:'M-LM_22_query', target:'840', class:'Identical', ramos:'not_in_paper_bins', readv2:'IdenticalTwins/SameIndividual', king:0.456, r1:1.4, n:7000, label:'840 · Savagnin Blanc'},
      {source:'M-LM_22_query', target:'R-MF_21_query', class:'Parent-Offspring', ramos:'Highly_related', readv2:'First Degree', king:0.25, r1:0.7, n:7000}
    ]
  }
};
QUERY='IA-LC_01_query';
var html=cloneControlsHtml();
function rows(rule, classes, queries){
  kinRule=rule;
  return collectCloneRows(kinViewSources().graph, [], {
    queries:queries, classes:classes, kingMin:null, kingMax:null, r1Min:null, nMin:null, rule:rule
  }).map(function(r){return r.query+'|'+r.partner+'|'+r.rel;});
}
console.log(JSON.stringify({
  pressed:(html.match(/aria-pressed="true"/g)||[]).length,
  off:(html.match(/aria-pressed="false"/g)||[]).length,
  lone:rows('4k', ['Identical','Parent-Offspring'], ['IA-LC_01_query']),
  all4:rows('4k', ['Identical','Parent-Offspring'], ['IA-LC_01_query','M-LM_22_query']),
  allR:rows('ramos2019', ['Identical_clone','Parent-Offspring','Highly_related'], ['IA-LC_01_query','M-LM_22_query'])
}));
"""
    )
    assert observed["pressed"] == 2
    assert observed["off"] == 0
    assert observed["lone"] == []
    assert observed["all4"] == ["M-LM_22_query|840|Identical", "M-LM_22_query|R-MF_21_query|Parent-Offspring"]
    assert observed["allR"] == ["M-LM_22_query|R-MF_21_query|Highly_related"]
