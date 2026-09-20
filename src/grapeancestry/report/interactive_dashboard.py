"""Interactive Plotly dashboard HTML — Italy grouping_663 interaction logic.

Click any tip/bar → yellow pin across PCA / ADMIXTURE / NJ tree.
Sample slider browser + K tabs + pinned detail.
"""

from __future__ import annotations

import json
from pathlib import Path

from grapeancestry.report.build_report import ReportBundle
from grapeancestry.report.interactive_data import build_interactive_payload, payload_to_json


APP_JS = r"""
var D=null, SROWS=[], SIDX={}, TREE_TIPS={}, QUERY='';
var treeShape='circular';
var currentK='8', selectedIID=null, compactAdmix=false, lzIdx=0, lzPlot=null;
var selLzIdx=0, selLzPlot=null, selLzMetric='fst', selLzFocusPos=null;
var selManhMetric='fst', selManhGrp='', selHeatMetric='fst';
var selManhFocus=null;
var pcaXi=0, pcaYi=1; // 0-based PC axes for 2D view
var themeMode='system', themeMedia=null, themeTransitionTimer=null;
var responsiveShellNarrow=null;
var responsiveResizeObserver=null, responsiveResizeObservedMain=null;
var THEME_DEFAULTS={
  light:{
    bg:'#f7f9fc', surface:'#ffffff', 'surface-2':'#eef2f7',
    text:'#172033', muted:'#526079', border:'#cbd5e1',
    'plot-bg':'#ffffff', 'plot-grid':'#dbe3ed',
    accent:'#b4234b', 'on-accent':'#ffffff', blue:'#1d4ed8',
    green:'#15803d', amber:'#a16207', focus:'#1d4ed8',
    'query-marker':'#0b3d91', 'query-marker-outline':'#172033'
  },
  dark:{
    bg:'#0b0f19', surface:'#131b2e', 'surface-2':'#0f172a',
    text:'#e2e8f0', muted:'#a8b3c7', border:'#2b3b59',
    'plot-bg':'#131b2e', 'plot-grid':'#263654',
    accent:'#f06b84', 'on-accent':'#172033', blue:'#93c5fd',
    green:'#86efac', amber:'#fbbf24', focus:'#93c5fd',
    'query-marker':'#f8fafc', 'query-marker-outline':'#fbbf24'
  }
};
function normalizeThemeMode(mode){
  mode=String(mode||'system').toLowerCase();
  return mode==='light'||mode==='dark'?mode:'system';
}
function readStoredTheme(){
  try{
    if(typeof localStorage!=='undefined'){
      var stored=localStorage.getItem('ga-theme');
      return normalizeThemeMode(stored||'system');
    }
    if(typeof window!=='undefined'&&window.localStorage){
      var windowStored=window.localStorage.getItem('ga-theme');
      return normalizeThemeMode(windowStored||'system');
    }
  }catch(err){}
  return 'system';
}
function resolveTheme(mode){
  mode=normalizeThemeMode(mode);
  if(mode!=='system') return mode;
  try{
    return typeof window!=='undefined'&&window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';
  }catch(err){ return 'light'; }
}
function motionBehavior(){
  try{
    return typeof window!=='undefined'&&window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ?'auto':'smooth';
  }catch(err){ return 'smooth'; }
}
function themeTokens(){
  var resolved=resolveTheme(themeMode);
  var out=Object.assign({}, THEME_DEFAULTS[resolved]||THEME_DEFAULTS.light);
  try{
    var root=typeof document!=='undefined'?document.documentElement:null;
    var css=typeof window!=='undefined'&&window.getComputedStyle&&root?
      window.getComputedStyle(root):null;
    if(css){
      Object.keys(out).forEach(function(key){
        var value=css.getPropertyValue('--'+key);
        if(value&&value.trim()) out[key]=value.trim();
      });
    }
  }catch(err){}
  return out;
}
function safePersistTheme(mode){
  try{
    if(typeof localStorage!=='undefined') localStorage.setItem('ga-theme', mode);
    else if(typeof window!=='undefined'&&window.localStorage)
      window.localStorage.setItem('ga-theme', mode);
  }catch(err){}
}
function updateThemeButtons(){
  if(typeof document==='undefined'||!document.querySelectorAll) return;
  var buttons=document.querySelectorAll('.theme-choice');
  Array.prototype.forEach.call(buttons,function(button){
    var active=button.getAttribute('data-theme-choice')===themeMode;
    button.setAttribute('aria-pressed',active?'true':'false');
  });
}
function applyThemeAttributes(mode){
  mode=normalizeThemeMode(mode);
  var resolved=resolveTheme(mode);
  if(typeof document!=='undefined'&&document.documentElement){
    document.documentElement.setAttribute('data-theme-mode',mode);
    document.documentElement.setAttribute('data-theme',resolved);
  }
  return resolved;
}
function setTheme(mode,persist){
  themeMode=normalizeThemeMode(mode);
  var root=typeof document!=='undefined'?document.documentElement:null;
  if(root&&root.classList){
    root.classList.add('theme-transition');
    if(themeTransitionTimer) clearTimeout(themeTransitionTimer);
    if(typeof setTimeout==='function'){
      themeTransitionTimer=setTimeout(function(){
        root.classList.remove('theme-transition');
      },180);
    }
  }
  applyThemeAttributes(themeMode);
  updateThemeButtons();
  if(persist!==false) safePersistTheme(themeMode);
  if(typeof refreshThemedPlots==='function') refreshThemedPlots();
  return resolveTheme(themeMode);
}
function bindThemeController(){
  if(typeof document==='undefined') return;
  var win=typeof window!=='undefined'?window:null;
  if(!win) return;
  if(!win._gaThemeControllerBound){
    var buttons=document.querySelectorAll('.theme-choice');
    Array.prototype.forEach.call(buttons,function(button){
      if(button._gaThemeBound||!button.addEventListener) return;
      button._gaThemeBound=true;
      button.addEventListener('click',function(){
        setTheme(button.getAttribute('data-theme-choice')||'system',true);
      });
    });
    win._gaThemeControllerBound=true;
  }
  if(win._gaThemeMediaBound) return;
  var media;
  try{
    media=win.matchMedia&&win.matchMedia('(prefers-color-scheme: dark)');
  }catch(err){ media=null; }
  if(!media) return;
  themeMedia=media;
  var onChange=function(event){
    if(themeMode!=='system') return;
    var resolved=event&&typeof event.matches==='boolean'
      ?(event.matches?'dark':'light'):resolveTheme('system');
    if(document.documentElement){
      document.documentElement.setAttribute('data-theme',''+resolved);
      document.documentElement.setAttribute('data-theme-mode','system');
    }
    updateThemeButtons();
    if(typeof refreshThemedPlots==='function') refreshThemedPlots();
  };
  if(media.addEventListener) media.addEventListener('change',onChange);
  else if(media.addListener) media.addListener(onChange);
  win._gaThemeMediaBound=true;
}
function initThemeController(){
  themeMode=readStoredTheme();
  applyThemeAttributes(themeMode);
  updateThemeButtons();
  bindThemeController();
}
var langMode='en';
function normalizeLang(mode){
  mode=String(mode||'').toLowerCase();
  if(mode.indexOf('zh')===0||mode==='cn'||mode==='chinese') return 'zh';
  return 'en';
}
function readStoredLang(){
  try{
    if(typeof localStorage!=='undefined'){
      var stored=localStorage.getItem('ga-lang');
      if(stored) return normalizeLang(stored);
    }
    if(typeof window!=='undefined'&&window.localStorage){
      var windowStored=window.localStorage.getItem('ga-lang');
      if(windowStored) return normalizeLang(windowStored);
    }
  }catch(err){}
  try{
    var nav=(typeof navigator!=='undefined'&&(navigator.language||navigator.userLanguage))||'';
    if(nav) return normalizeLang(nav);
  }catch(err){}
  return 'en';
}
function safePersistLang(mode){
  try{
    if(typeof localStorage!=='undefined') localStorage.setItem('ga-lang', mode);
    else if(typeof window!=='undefined'&&window.localStorage)
      window.localStorage.setItem('ga-lang', mode);
  }catch(err){}
}
function applyLangAttributes(mode){
  mode=normalizeLang(mode);
  if(typeof document!=='undefined'&&document.documentElement){
    document.documentElement.setAttribute('data-lang',mode);
    document.documentElement.setAttribute('lang',mode==='zh'?'zh-CN':'en');
  }
  return mode;
}
function updateLangButtons(){
  if(typeof document==='undefined'||!document.querySelectorAll) return;
  var buttons=document.querySelectorAll('.lang-choice');
  Array.prototype.forEach.call(buttons,function(button){
    var active=button.getAttribute('data-lang-choice')===langMode;
    button.setAttribute('aria-pressed',active?'true':'false');
  });
}
function setLang(mode,persist){
  langMode=normalizeLang(mode);
  applyLangAttributes(langMode);
  updateLangButtons();
  refreshStaticControlLabels();
  if(persist!==false) safePersistLang(langMode);
  if(typeof window!=='undefined'&&window._gaLangReady) refreshLangContent();
  return langMode;
}
function bindLangController(){
  if(typeof document==='undefined') return;
  var win=typeof window!=='undefined'?window:null;
  if(!win||win._gaLangControllerBound) return;
  var buttons=document.querySelectorAll('.lang-choice');
  Array.prototype.forEach.call(buttons,function(button){
    if(button._gaLangBound||!button.addEventListener) return;
    button._gaLangBound=true;
    button.addEventListener('click',function(){
      setLang(button.getAttribute('data-lang-choice')||'en',true);
    });
  });
  win._gaLangControllerBound=true;
}
function initLangController(){
  langMode=readStoredLang();
  applyLangAttributes(langMode);
  updateLangButtons();
  bindLangController();
  refreshStaticControlLabels();
}
function bi(en, zh){
  return '<span class="en">'+en+'</span><span class="cn">'+zh+'</span>';
}
function t(en, zh){
  return langMode==='zh'?zh:en;
}
function setLocalizedAttribute(el, attr, en, zh){
  if(el&&el.setAttribute) el.setAttribute(attr,t(en,zh));
}
function refreshStaticControlLabels(){
  if(typeof document==='undefined'||!document.getElementById) return;

  var sidebar=document.getElementById('report-sidebar');
  var toggle=document.getElementById('sidebar-toggle');
  var hidden=!!(sidebar&&sidebar.classList&&sidebar.classList.contains('hidden'));
  if(!sidebar&&toggle) hidden=toggle.getAttribute('aria-expanded')==='false';
  setLocalizedAttribute(
    toggle,
    'aria-label',
    hidden?'Open report navigation':'Close report navigation',
    hidden?'打开报告导航':'关闭报告导航'
  );
  setLocalizedAttribute(
    toggle,
    'title',
    hidden?'Show':'Hide',
    hidden?'显示':'隐藏'
  );

  setLocalizedAttribute(
    document.getElementById('sample-slider'),
    'aria-label',
    'Sample browser position',
    '样本浏览位置'
  );
  setLocalizedAttribute(
    document.getElementById('sample-slider'),
    'title',
    'Browse panel samples',
    '浏览面板样本'
  );
  setLocalizedAttribute(
    document.getElementById('sample-search'),
    'aria-label',
    'Search sample',
    '搜索样本'
  );
  setLocalizedAttribute(
    document.getElementById('sample-search'),
    'placeholder',
    'ID / variety / origin / VIVC',
    'ID / 品种 / 产地 / VIVC'
  );
  setLocalizedAttribute(
    document.getElementById('sample-search'),
    'title',
    'Search by ID, variety, origin, or VIVC',
    '按 ID、品种、产地或 VIVC 搜索'
  );
  if(document.querySelectorAll){
    Array.prototype.forEach.call(
      document.querySelectorAll('.browser-go'),
      function(button){
        setLocalizedAttribute(button,'aria-label','Go to selected sample','跳转到选中样本');
        setLocalizedAttribute(button,'title','Go to selected sample','跳转到选中样本');
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.sample-search-button'),
      function(button){
        setLocalizedAttribute(button,'aria-label','Find sample','查找样本');
        setLocalizedAttribute(button,'title','Find sample','查找样本');
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.clear-highlight'),
      function(button){
        setLocalizedAttribute(button,'aria-label','Clear pinned sample','清除已钉住样本');
        setLocalizedAttribute(button,'title','Clear pinned sample','清除已钉住样本');
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.lang-control'),
      function(control){
        setLocalizedAttribute(control,'aria-label','Report language','报告语言');
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.theme-control'),
      function(control){
        setLocalizedAttribute(control,'aria-label','Report color theme','报告配色');
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.lang-choice'),
      function(button){
        var choice=button.getAttribute('data-lang-choice');
        var en=choice==='zh'?'Use Chinese':'Use English';
        var zh=choice==='zh'?'使用中文':'使用英文';
        setLocalizedAttribute(button,'aria-label',en,zh);
        setLocalizedAttribute(button,'title',en,zh);
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.theme-choice'),
      function(button){
        var choice=button.getAttribute('data-theme-choice');
        var en=choice==='light'?'Use light theme':
          choice==='dark'?'Use dark theme':'Use system theme';
        var zh=choice==='light'?'使用浅色主题':
          choice==='dark'?'使用深色主题':'使用系统主题';
        setLocalizedAttribute(button,'aria-label',en,zh);
        setLocalizedAttribute(button,'title',en,zh);
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.kbtn'),
      function(button){
        var k=button.getAttribute('data-k')||'';
        setLocalizedAttribute(
          button,'aria-label','Show ADMIXTURE K='+k,'查看 ADMIXTURE K='+k
        );
        setLocalizedAttribute(
          button,'title','Show ADMIXTURE K='+k,'查看 ADMIXTURE K='+k
        );
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('.pca-axis-btn'),
      function(button){
        var axes=button.getAttribute('data-axes');
        if(!axes) return;
        var parts=String(axes).split(',');
        var label='PC'+(Number(parts[0])+1)+'–PC'+(Number(parts[1])+1);
        setLocalizedAttribute(button,'aria-label','Show '+label+' axes','显示 '+label+' 轴');
        setLocalizedAttribute(button,'title','Show '+label+' axes','显示 '+label+' 轴');
      }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-i18n-en][data-i18n-zh]'),
      function(node){
        node.textContent=t(
          node.getAttribute('data-i18n-en')||'',
          node.getAttribute('data-i18n-zh')||''
        );
      }
    );
  }
  var controlPairs=[
    ['admix-full-btn','Show full panel','显示完整面板'],
    ['admix-compact-btn','Show compact panel','显示紧凑面板'],
    ['tree-circ-btn','Show circular tree','显示圆形树'],
    ['tree-rect-btn','Show rectangular tree','显示矩形树']
  ];
  controlPairs.forEach(function(pair){
    var button=document.getElementById(pair[0]);
    setLocalizedAttribute(button,'aria-label',pair[1],pair[2]);
    setLocalizedAttribute(button,'title',pair[1],pair[2]);
  });
}
function pickBi(s){
  s=String(s||'');
  var i=s.indexOf(' / ');
  if(i<0) return s;
  return t(s.slice(0,i), s.slice(i+3));
}
function scopeLabel(scope){
  scope=String(scope||'');
  if(scope.indexOf('<span class="en">')>=0) return scope;
  var labels={
    'Query-derived':['Query-derived','查询样本来源'],
    'Source library':['Source library','来源文库'],
    'Query vs 2449 panel':['Query vs 2449 panel','查询样本 vs 2449 面板'],
    '2449 panel only':['2449 panel only','仅 2449 面板']
  };
  var pair=labels[scope]||[scope,scope];
  return bi(pair[0],pair[1]);
}
function runtimeMessage(en, zh, tag){
  return '<'+(tag||'div')+' class="muted">'+bi(en,zh)+'</'+(tag||'div')+'>';
}
function pairBoxOk(box){
  if(!box) return false;
  var tag=String(box.tagName||'').toLowerCase();
  var cls=' '+String(box.className||'')+' ';
  if(cls.indexOf(' sec-guide ')>=0||cls.indexOf(' info-box ')>=0) return true;
  if(cls.indexOf(' gt-head ')>=0||cls.indexOf(' gt-counts ')>=0) return true;
  if(cls.indexOf(' qc-meaning ')>=0||cls.indexOf(' muted ')>=0) return true;
  return tag==='p'||tag==='td'||tag==='li'||tag==='caption'||tag==='label';
}
function pairLangBlocks(root){
  root=root||document;
  if(!root||!root.querySelectorAll) return;
  var cns=root.querySelectorAll('.cn');
  Array.prototype.forEach.call(cns,function(cn){
    var box=cn.parentNode;
    if(!box) return;
    if(!pairBoxOk(box)) return;
    function previousNode(node){
      if(node&&typeof node.previousSibling!=='undefined') return node.previousSibling;
      var nodes=box.childNodes||[];
      var index=Array.prototype.indexOf.call(nodes,node);
      return index>0?nodes[index-1]:null;
    }
    var adjacent=previousNode(cn);
    while(adjacent&&adjacent.nodeType===3&&!String(adjacent.textContent||'').trim()){
      adjacent=previousNode(adjacent);
    }
    if(adjacent&&adjacent.nodeType===1&&
       (' '+String(adjacent.className||'')+' ').indexOf(' en ')>=0){
      if(box.setAttribute) box.setAttribute('data-lang-paired','1');
      return;
    }
    var wrap=[];
    var prev=previousNode(cn);
    while(prev){
      var prevCls=' '+String(prev.className||'')+' ';
      if(prev.nodeType===1 &&
         (prevCls.indexOf(' cn ')>=0||prevCls.indexOf(' en ')>=0)) break;
      wrap.unshift(prev);
      prev=previousNode(prev);
    }
    if(!wrap.length) return;
    if(!document||!document.createElement) return;
    var en=document.createElement('div');
    en.className='en';
    wrap.forEach(function(node){ en.appendChild(node); });
    if(box.insertBefore) box.insertBefore(en, cn);
    if(box.setAttribute) box.setAttribute('data-lang-paired','1');
  });
}
function refreshLangContent(){
  refreshStaticControlLabels();
  pairLangBlocks(document);
  if(!D) return;
  try{
    fillHeroStats();
    fillAuthorIntake();
    fillQuerySnapshot();
    fillReportMeta();
    fillMethodCoverage();
    fillQueryEvidence();
    fillQc();
    fillConclusions();
    fillCloneTable();
    fillIbsKinship();
    fillExtra();
    fillSelFstats();
    fillAdmixMethodNotes();
    if(selectedIID) renderPinnedSummary(selectedIID);
    enhanceReportTables(document);
    pairLangBlocks(document);
    loadPCA();
    loadPCA3d();
    loadBar(currentK);
    loadTree();
    loadDamage();
  }catch(err){}
}

// Names: Dong et al. 2023 Science 379:892–901, doi:10.1126/science.add8655 (Fig. 1D).
var K8_GLOSS={
  'Syl-W1 (WWE1)':'Central European wild V. sylvestris (Syl-W1). / 中欧野生葡萄。',
  'Syl-W2 (WWE2)':'Iberian wild V. sylvestris (Syl-W2). / 伊比利亚野生葡萄。',
  'Syl-E1 (WEE1)':'Western Asian wild V. sylvestris (Syl-E1). / 西亚野生葡萄。',
  'Syl-E2 (WEE2)':'Caucasus wild V. sylvestris (Syl-E2). / 高加索野生葡萄。',
  'CG1':'Western Asian table grapes. Shares the main component with Syl-E1 in the article. / 西亚鲜食葡萄。',
  'CG2':'Caucasian wine grapes. Shares the main component with Syl-E2 in the article. / 高加索酿酒葡萄。',
  'CG3':'Muscat grapevines. / Muscat 芳香品种。',
  'CG4':'Balkan wine grapevines. / 巴尔干酿酒葡萄。',
  'CG5':'Iberian wine grapevines. / 伊比利亚酿酒葡萄。',
  'CG6':'Western European wine grapevines. / 西欧酿酒葡萄。'
};
// Fig. 1D palette (Dong et al. 2023, doi:10.1126/science.add8655). One colour can
// cover two named groups. This freeze's 8 Q columns may not use every colour.
var PAPER_K8=[
  {lab:'Syl-W1 (WWE1)', c:'#4470b7'},
  {lab:'Syl-E1 (WEE1) / CG1', c:'#dc1f26'},
  {lab:'CG6', c:'#981b1e'},
  {lab:'CG4', c:'#f7922c'},
  {lab:'CG3', c:'#835ca6'},
  {lab:'Syl-E2 (WEE2) / CG2', c:'#0b5475'},
  {lab:'CG5', c:'#fbee61'},
  {lab:'Syl-W2 (WWE2)', c:'#f6a3b1'}
];
function glossForLabel(lab){
  lab=String(lab||'');
  if(K8_GLOSS[lab]) return pickBi(K8_GLOSS[lab]);
  if(lab.indexOf(' / ')>=0){
    var bits=lab.split(' / ').map(function(p){return pickBi(K8_GLOSS[p.trim()]||'');}).filter(Boolean);
    if(bits.length){
      return bits.join(' ')+' '+t('They peak on the same K=8 column.','同列。');
    }
  }
  return '';
}

function fillK8PaintNote(){
  var box=document.getElementById('k8-paint-note');
  if(box) box.style.display='none';
}

function esc(v){
  return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function clipIds(s,n){
  n=n||5;
  return String(s||'').split(';').map(function(x){return x.replace(/;+$/,'').trim();})
    .filter(Boolean).slice(0,n).join(';');
}
function idList(s,n){
  n=n||5;
  return String(s||'').split(/[;,]/).map(function(x){return x.replace(/;+$/,'').trim();})
    .filter(Boolean).slice(0,n);
}
function dbHref(kind,id){
  id=String(id||'').trim();
  if(kind==='oiv_list') return 'https://www.oiv.int/node/2830';
  if(!id||!/^[A-Za-z0-9_.:-]+$/.test(id)) return '';
  if(kind==='uniprot') return 'https://www.uniprot.org/uniprotkb/'+id;
  if(kind==='go') return 'https://www.ebi.ac.uk/QuickGO/term/'+id;
  if(kind==='pfam') return 'https://www.ebi.ac.uk/interpro/entry/pfam/'+id;
  if(kind==='interpro') return 'https://www.ebi.ac.uk/interpro/entry/InterPro/'+id;
  if(kind==='kegg') return 'https://www.kegg.jp/entry/'+id;
  if(kind==='ensembl'){
    if(/^Vvsyl/i.test(id)) return '';
    return 'https://plants.ensembl.org/Vitis_vinifera/Psychic?q='+encodeURIComponent(id);
  }
  if(kind==='ncbi') return 'https://www.ncbi.nlm.nih.gov/gene/'+id;
  if(kind==='refseq') return 'https://www.ncbi.nlm.nih.gov/protein/'+id;
  if(kind==='ec') return 'https://enzyme.expasy.org/EC/'+id;
  if(kind==='oiv') return 'http://www.eu-vitis.de/docs/descriptors/oivdesc/OIV%20'+id+'.pdf';
  return '';
}
function oivNum(trait){
  var s=String(trait||'');
  if(s.toLowerCase()==='sdr') return '151';
  var m=s.match(/OIV[\s_]+(\d+(?:-\d+)?)/i);
  if(!m) return '';
  var n=m[1];
  if(n.indexOf('-')>=0){
    var p=n.split('-');
    return ('000'+p[0]).slice(-3)+'-'+p[1];
  }
  return ('000'+n).slice(-3);
}
function oivTraitHtml(trait){
  var num=oivNum(trait);
  if(!num) return esc(trait||'');
  return '<a class="dblink" href="'+esc(dbHref('oiv',num))+'" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" title="EU-Vitis OIV descriptor PDF">'+esc(trait||('OIV '+num))+'</a>';
}
function oivDescHtml(t){
  var trait=t.trait||'';
  var desc=t.descriptor||'';
  var num=oivNum(trait);
  var html=esc(desc);
  if(!num) return html;
  var list='<a class="dblink" href="'+esc(dbHref('oiv_list',''))+'" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">OIV 2009</a>';
  var code='<a class="dblink" href="'+esc(dbHref('oiv',num))+'" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">OIV '+esc(num)+'</a>';
  return code+(desc?' — '+esc(desc):'')+' · '+list;
}
function dbLink(kind,id){
  var href=dbHref(kind,id);
  if(!href) return esc(id);
  return '<a class="dblink" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">'+esc(id)+'</a>';
}
function dbLinks(kind,s,n){
  return idList(s,n).map(function(id){return dbLink(kind,id);}).join('; ');
}
function prodCell(t){
  var prod=t.product||t.top_product||'';
  var gn=t.sprot_gn||t.top_sprot_gn||'';
  if(gn&&prod.indexOf(gn)<0) prod=(gn?gn+': ':'')+prod;
  var pid=t.sprot_pident||t.top_sprot_pident;
  if(pid) prod+=(prod?' · ':'')+Number(pid).toFixed(0)+'% '+(t.sprot_organism||t.top_sprot_organism||'SwissProt');
  var html=esc(prod);
  var acc=t.uniprot||t.top_uniprot||'';
  if(acc) html+=(html?' · ':'')+dbLink('uniprot',acc);
  var ec=t.ec||t.top_ec||'';
  if(ec) html+=(html?' · ':'')+dbLinks('ec',ec,3);
  return html;
}
function keggCell(t){
  return t.kegg_vvi||t.kegg||t.top_kegg_vvi||t.top_kegg||'';
}
function keggCellHtml(t){
  return dbLinks('kegg', keggCell(t), 3);
}
function vitisCellHtml(t){
  var id=t.vitis_id||t.top_vitis_id||'';
  var sy=t.vitis_symbol||t.top_vitis_symbol||'';
  var ncbi=t.ncbi_geneid||t.top_ncbi_geneid||'';
  var xp=t.refseq||t.top_refseq||'';
  var bits=[];
  if(ncbi) bits.push(dbLink('ncbi', ncbi));
  if(xp) bits.push(dbLinks('refseq', xp, 1));
  if(id) bits.push(dbLink('ensembl', id));
  if(sy) bits.push(esc(sy));
  return bits.join(' / ');
}
function siteKey(s){
  return String(s||'').replace(/^chr/i,'').replace(/\s+/g,'');
}
function traitNorm(s){
  return String(s||'').toUpperCase().replace(/_BIN$/i,'').replace(/[^A-Z0-9]/g,'');
}
function scienceNoteHtml(s){
  var html=esc(s||'');
  return html.replace(/Dong 2023/g,
    '<a class="dblink" href="https://doi.org/10.1126/science.add8655" target="_blank" rel="noopener noreferrer">Dong et al. 2023</a>');
}
function lookupCatalogBySite(site){
  var key=siteKey(site), hit=null;
  (D.panel_trait_catalog||D.traits||[]).forEach(function(t){
    if(siteKey(t.site)===key) hit=t;
  });
  return hit;
}
function lookupCatalogByGene(gene){
  var g=String(gene||'');
  if(!g) return null;
  var hit=null;
  (D.panel_trait_catalog||D.traits||[]).forEach(function(t){
    if(t.gene===g || t.alias===g) hit=hit||t;
  });
  return hit;
}
function lookupGwasBySite(site){
  var key=siteKey(site), hit=null;
  (D.gwas_loci||[]).forEach(function(r){
    var loc=siteKey((r.chrom||'')+':'+(r.pos||''));
    if(loc===key) hit=r;
  });
  return hit;
}
function lookupGwasIndex(trait, slug){
  var wantSlug=String(slug||'');
  var want=traitNorm(trait);
  var hit=null;
  (D.gwas_index||[]).forEach(function(r){
    if(wantSlug && String(r.slug||'')===wantSlug){ hit=r; return; }
    if(traitNorm(r.trait)===want) hit=hit||r;
  });
  return hit;
}
function lookupGwasLocusBySlug(slug){
  var hit=null;
  (D.gwas_loci||[]).forEach(function(r){
    if(String(r.slug||'')===String(slug||'')) hit=hit||r;
  });
  return hit;
}
function annotDbHtml(t){
  if(!t) return '';
  var bits=[prodCell(t), dbLinks('go', t.go||t.top_go, 4), dbLinks('pfam', t.pfam||t.top_pfam, 3),
    keggCellHtml(t), vitisCellHtml(t)].filter(Boolean);
  return bits.join(' · ');
}
function evidenceTypeHtml(kind){
  if(kind==='curated_locus') return bi('curated MAS/GWAS tag','策展 MAS/GWAS 标签');
  if(kind==='panel_gwas_lead') return bi('panel GWAS lead','panel GWAS 主位点');
  return esc(kind||'—');
}
function scaleHtml(scale){
  var s=String(scale||'').toLowerCase();
  if(s==='binary') return bi('binary','二元')+'<span class="ev-sub">'+
    bi('0/1 training scale','训练集 0/1 尺度')+'</span>';
  if(s==='ordinal') return bi('ordinal','有序')+'<span class="ev-sub">'+
    bi('OIV ordered grades','OIV 有序等级')+'</span>';
  return esc(scale||'—');
}
function traitNoteHtml(note){
  var raw=String(note||'');
  if(!raw) return '';
  if(/haplotype|H1\/H2|H1–H5|H1-H5/i.test(raw) && /SDR|sex|Science/i.test(raw)){
    return bi(
      'Panel annotation: H1/H2 is a panel SDR label. H1–H5 is Dong et al. literature context, not a full literature classification of this site.',
      '面板注释：H1/H2 是面板 SDR 标签。H1–H5 是 Dong 等文献背景，不是该位点的完整文献分类。'
    );
  }
  if(/H1|H2|H1–H5|haplotype/i.test(raw)){
    return bi(
      'Panel annotation: panel haplotype/SDR label, distinct from Dong et al. H1–H5 literature context.',
      '面板注释：面板单倍型/SDR 标签，有别于 Dong 等 H1–H5 文献背景。'
    );
  }
  return bi('Source metadata: '+esc(raw),'来源元数据：'+esc(raw));
}
function gsFlagHtml(flag){
  var f=String(flag||'');
  if(f==='ok') return bi('ok','通过')+'<span class="ev-sub">'+bi('Panel CV r passed the report flag.',
    'panel 交叉验证 r 已通过本报告标记。')+'</span>';
  if(f==='low_cv_r') return bi('low_cv_r','panel 交叉验证 r 偏低')+'<span class="ev-sub">'+bi('Panel CV r is too low to rank parents.',
    'panel 交叉验证 r 太低，不能用来排亲本。')+'</span>';
  return bi(esc(f||'—'),esc(f||'—'));
}
function rowByIid(iid){
  return SROWS.find(function(r){return r.iid===iid;})||{};
}
function sampleWhoExtraLabel(extra){
  var raw=String(extra||'');
  if(raw==='query') return t('Query sample','查询样本');
  if(raw==='pinned') return t('Pinned sample','已钉住样本');
  return esc(raw);
}
function sampleWho(iid, extra){
  var r=rowByIid(iid);
  var lines=[esc(String(iid||''))];
  if(iid===QUERY){
    var a=(loadAuthorState().sample)||{};
    if(a.name) lines.push(esc(a.name));
    else if(r.acc) lines.push(esc(r.acc));
    if(a.origin) lines.push(esc(a.origin));
    else {
      var bits0=[r.origin,r.con,r.geo].filter(Boolean).map(esc);
      if(bits0.length) lines.push(bits0.join(' · '));
    }
    if(a.date) lines.push(esc(a.date));
    if(extra) lines.push(sampleWhoExtraLabel(extra));
    return lines.join('<br>');
  }
  if(r.acc) lines.push(esc(r.acc));
  if(r.acc_local) lines.push(esc(r.acc_local));
  var bits=[r.origin,r.con,r.geo,r.uti,r.grp_info||((r.grp&&r.grp!=='QUERY')?r.grp:'')].filter(Boolean).map(esc);
  if(bits.length) lines.push(bits.join(' · '));
  if(r.taxon) lines.push(esc(r.taxon));
  if(r.vivc) lines.push('VIVC '+esc(r.vivc));
  if(r.clone_of) lines.push(t('Clone of: ','克隆对应：')+esc(r.clone_of));
  if(extra) lines.push(sampleWhoExtraLabel(extra));
  return lines.join('<br>');
}
function sampleTick(iid){
  var r=rowByIid(iid);
  return r.acc||iid||'';
}
function sampleCell(iid){
  var r=rowByIid(iid);
  var h='<span class="sid">'+esc(iid)+'</span>';
  if(r.acc) h+='<div class="sname">'+esc(r.acc)+'</div>';
  if(r.acc_local) h+='<div class="smeta">'+esc(r.acc_local)+'</div>';
  var bits=[r.origin||r.con,r.geo,r.uti,r.grp_info||((r.grp&&r.grp!=='QUERY')?r.grp:'')].filter(Boolean);
  if(bits.length) h+='<div class="smeta">'+esc(bits.join(' · '))+'</div>';
  return h;
}
function findSample(q){
  q=String(q||'').trim().toLowerCase();
  if(!q) return -1;
  var exact=SROWS.findIndex(function(r){return String(r.iid).toLowerCase()===q;});
  if(exact>=0) return exact;
  return SROWS.findIndex(function(r){
    return [r.iid,r.acc,r.acc_local,r.vivc,r.con,r.origin,r.geo,r.uti,r.grp,r.grp_info,r.taxon,r.clone_of,r.contributor].some(function(v){
      return v && String(v).toLowerCase().indexOf(q)>=0;
    });
  });
}
function findSelPoint(chroms, positions, chrom, pos){
  chroms=chroms||[];
  positions=positions||[];
  var targetChrom=String(chrom);
  var targetPos=Number(pos);
  if(!isFinite(targetPos)) return -1;
  var n=Math.min(chroms.length, positions.length);
  for(var i=0;i<n;i++){
    if(String(chroms[i])===targetChrom && Number(positions[i])===targetPos) return i;
  }
  return -1;
}
function searchGo(){
  var box=document.getElementById('sample-search');
  var i=findSample(box?box.value:'');
  if(i<0) return;
  document.getElementById('sample-slider').value=String(i);
  highlightSample(SROWS[i].iid);
}
function bindRowClicks(root){
  if(!root) return;
  root.querySelectorAll('.clickrow[data-iid]').forEach(function(row){
    row.addEventListener('click',function(){
      highlightSample(row.getAttribute('data-iid')||'');
    });
  });
}
function plotlyCan(method){
  var api=typeof window!=='undefined'&&window.Plotly
    ?window.Plotly
    :(typeof Plotly!=='undefined'?Plotly:null);
  return !!api&&typeof api[method]==='function';
}
function relayoutPlot(el, update){
  if(!el||!plotlyCan('relayout')) return false;
  try{ Plotly.relayout(el, update); return true; }catch(err){ return false; }
}
function restylePlot(el, update, indices){
  if(!el||!plotlyCan('restyle')) return false;
  try{ Plotly.restyle(el, update, indices); return true; }catch(err){ return false; }
}
function purgePlot(el){
  if(el && el._fullLayout && plotlyCan('purge')){
    try{ Plotly.purge(el); }catch(err){}
  }
}
function resetPlot(el){
  if(!el) return;
  purgePlot(el);
  el.innerHTML='';
}
function plotlyCfg(opts){
  return Object.assign({responsive:false, displayModeBar:true, displaylogo:false}, opts||{});
}
function clonePlotLayout(layout){
  try{ return JSON.parse(JSON.stringify(layout||{})); }
  catch(err){ return Object.assign({},layout||{}); }
}
function themeAxis(axis, tokens){
  if(!axis||typeof axis!=='object') return axis;
  var out=Object.assign({},axis);
  out.color=tokens.text;
  out.gridcolor=tokens['plot-grid'];
  out.zerolinecolor=tokens['plot-grid'];
  out.linecolor=tokens.border;
  if(out.tickfont) out.tickfont=Object.assign({},out.tickfont,{color:tokens.text});
  if(out.title&&typeof out.title==='object'){
    out.title=Object.assign({},out.title);
    if(out.title.font) out.title.font=Object.assign({},out.title.font,{color:tokens.text});
  }
  return out;
}
function applyPlotTheme(layout){
  var L=clonePlotLayout(layout);
  var tokens=themeTokens();
  L.paper_bgcolor=tokens['plot-bg'];
  L.plot_bgcolor=tokens['plot-bg'];
  L.font=Object.assign({},L.font||{},{color:tokens.text});
  ['xaxis','yaxis','xaxis2','yaxis2','xaxis3','yaxis3'].forEach(function(key){
    if(L[key]) L[key]=themeAxis(L[key],tokens);
  });
  if(L.scene){
    L.scene=Object.assign({},L.scene,{bgcolor:tokens['plot-bg']});
    ['xaxis','yaxis','zaxis'].forEach(function(key){
      if(L.scene[key]) L.scene[key]=themeAxis(L.scene[key],tokens);
    });
  }
  if(L.legend){
    L.legend=Object.assign({},L.legend);
    L.legend.font=Object.assign({},L.legend.font||{},{color:tokens.text});
    if(L.legend.bgcolor==null) L.legend.bgcolor=tokens.surface;
    if(L.legend.bordercolor==null) L.legend.bordercolor=tokens.border;
  }
  if(L.coloraxis){
    L.coloraxis=Object.assign({},L.coloraxis);
    L.coloraxis.colorbar=Object.assign({},L.coloraxis.colorbar||{});
    L.coloraxis.colorbar.tickfont=Object.assign(
      {},L.coloraxis.colorbar.tickfont||{},{color:tokens.text}
    );
  }
  if(Array.isArray(L.annotations)){
    L.annotations=L.annotations.map(function(annotation){
      var out=Object.assign({},annotation);
      if(out.font) out.font=Object.assign({},out.font,{color:tokens.text});
      return out;
    });
  }
  return L;
}
function withPlotSize(layout, el, h){
  var L=applyPlotTheme(layout);
  L.autosize=false;
  L.height=h;
  var w=hostPlotWidth(el);
  if(w>80) L.width=w;
  return L;
}
function isPcaPlotEl(el){
  var id=el&&el.id;
  return id==='plot-pca'||id==='plot-pca3d';
}
function pcaSquareSize(el){
  var w=hostPlotWidth(el);
  if(!(w>80)) w=(el&&el.clientWidth)||0;
  if(!(w>80)) w=360;
  return {width:w, height:w};
}
function withPcaPlotSize(layout, el){
  var L=applyPlotTheme(layout);
  var sz=pcaSquareSize(el);
  L.autosize=false;
  L.width=sz.width;
  L.height=sz.height;
  return L;
}
function hostPlotWidth(el){
  if(!el) return 0;
  var w=el.clientWidth||0;
  if(w>80) return w;
  var sec=el.closest && el.closest('section');
  if(sec && sec.clientWidth>160) return Math.max(0, sec.clientWidth-8);
  var main=document.getElementById('main-content');
  if(main && main.clientWidth>240) return Math.max(0, main.clientWidth-56);
  return 0;
}
function stretchPlot(el, h){
  if(!el || !el._fullLayout || !plotlyCan('relayout')) return;
  var w=hostPlotWidth(el);
  if(!(w>80)) return;
  var hh=isPcaPlotEl(el)?w:(h || el._fullLayout.height || 420);
  var curW=el._fullLayout.width, curH=el._fullLayout.height;
  if(curW && Math.abs(curW-w)<6 && curH && Math.abs(curH-hh)<6) return;
  relayoutPlot(el, {width:w, height:hh, autosize:false});
}
var RESPONSIVE_PLOT_IDS=[
  'plot-pca','plot-pca3d','plot-bar','plot-tree','plot-damage',
  'plot-damage-len','plot-f3-out','plot-f3','plot-f4','plot-sel-manh',
  'plot-sel-heat','plot-sel-scatter','plot-lz-gt','plot-sel-gt'
];
var responsiveResizePending=false;
function resizeAllPlotsToHosts(){
  if(typeof document==='undefined') return;
  RESPONSIVE_PLOT_IDS.forEach(function(id){
    var el=document.getElementById(id);
    if(el&&el._fullLayout) stretchPlot(el, el._fullLayout.height||420);
  });
  [
    [lzPlot,document.getElementById('plot-lz')],
    [selLzPlot,document.getElementById('plot-sel-lz')]
  ].forEach(function(pair){
    if(pair[0]&&pair[1]) fitLzPlot(pair[0],pair[1]);
  });
}
function scheduleResponsiveResize(){
  if(responsiveResizePending) return;
  responsiveResizePending=true;
  var run=function(){
    responsiveResizePending=false;
    resizeAllPlotsToHosts();
  };
  if(typeof requestAnimationFrame==='function') requestAnimationFrame(run);
  else if(typeof setTimeout==='function') setTimeout(run,0);
  else run();
}
function resizeNarrowPlots(){
  if(isNarrowViewport()) resizeAllPlotsToHosts();
}
function lzPanelSum(layout){
  var h=0;
  (layout.panels||[]).forEach(function(p){ h+=Number(p.height)||0; });
  return h;
}
function locusZoomCan(){
  return typeof LocusZoom!=='undefined'&&LocusZoom&&
    LocusZoom.Layouts&&typeof LocusZoom.Layouts.get==='function'&&
    typeof LocusZoom.DataSources==='function'&&
    typeof LocusZoom.populate==='function';
}
function lzSizeLayout(layout, el){
  var w=hostPlotWidth(el);
  if(w>200) layout.width=w;
  var h=lzPanelSum(layout);
  if(h>0) layout.height=h;
  layout.responsive_resize=false;
}
function fitLzPlot(plot, el){
  if(!plot || !el) return;
  var genes=plot.panels && plot.panels.genes;
  if(genes && typeof genes.scaleHeightToData==='function'){
    try{ genes.scaleHeightToData(); }catch(err){}
  }
  var w=hostPlotWidth(el);
  var h=plot._total_height;
  if(w>200 && h>0 && plot.setDimensions) plot.setDimensions(w, h);
  el.style.height='auto';
  el.style.minHeight='0';
}
function lzAfterRender(plot, el){
  if(!plot || !el) return;
  var run=function(){
    fitLzPlot(plot, el);
    scheduleResponsiveResize();
  };
  if(typeof plot.refresh==='function') Promise.resolve(plot.refresh()).then(run).catch(run);
  else run();
}

var LZ_BINS=[
  {name:'r²≥0.8', lo:0.8, c:'#d62728'},
  {name:'0.6', lo:0.6, c:'#ff7f0e'},
  {name:'0.4', lo:0.4, c:'#2ca02c'},
  {name:'0.2', lo:0.2, c:'#6baed6'},
  {name:'<0.2', lo:0, c:'#08306b'}
];
function lzBin(r2){
  if(r2==null || r2!==r2) return 5;
  for(var i=0;i<LZ_BINS.length;i++) if(Number(r2)>=LZ_BINS[i].lo) return i;
  return 4;
}
function lzFmtP(p){
  if(p==null||p==='') return '—';
  var n=Number(p);
  if(!isFinite(n)) return String(p);
  if(n===0) return '0';
  if(n<1e-3) return n.toExponential(2);
  return n.toPrecision(3);
}
function lzGtLab(g){
  if(g==null||g===''||Number(g)<0) return t('./. missing','./. 缺失');
  var n=Number(g);
  if(n===0) return t('0/0 REF','0/0 参考');
  if(n===1) return t('0/1 het','0/1 杂合');
  if(n===2) return t('1/1 ALT','1/1 替代');
  return String(g);
}
function lzGtClass(g){
  if(g==null||g===''||Number(g)<0) return 'miss';
  var n=Number(g);
  if(n===0) return 'ref';
  if(n===1) return 'het';
  if(n===2) return 'alt';
  return 'miss';
}
function lzGtPill(g){
  var k=lzGtClass(g);
  var lab=lzGtLab(g);
  return '<span class="gt-pill gt-'+k+'">'+lab+'</span>';
}
function lzGtExplain(g){
  var k=lzGtClass(g);
  return {
    ref:{en:'Both copies match the reference (REF/REF).', cn:'两个拷贝都和参考基因组一样。'},
    het:{en:'Heterozygous: one REF copy, one ALT.', cn:'一条染色体是参考，一条是变异。'},
    alt:{en:'Both copies are the variant (ALT/ALT).', cn:'两个拷贝都是变异碱基。'},
    miss:{en:'Not called in this sample’s VCF.', cn:'这个位点在本样品 VCF 里没打出来。'}
  }[k]||{en:'', cn:''};
}
function lzWhyLab(why){
  var m={
    lead:['lead','窗口主 SNP'],
    'named window':['named window','命名窗口内'],
    'design-time':['design-time','芯片设计位点'],
    Bonferroni:['Bonferroni','全基因组显著']
  };
  var pair=m[why];
  if(pair) return bi(esc(pair[0]),esc(pair[1]));
  return esc(String(why||''));
}
function lzGtCounts(r){
  var s=(r&&r.snps)||{};
  var gt=s.gt||[];
  var o={n:gt.length, called:0, ref:0, het:0, alt:0, miss:0};
  for(var i=0;i<gt.length;i++){
    var k=lzGtClass(gt[i]);
    if(k==='miss') o.miss+=1;
    else { o.called+=1; o[k]+=1; }
  }
  return o;
}
function lzKeyGtIdx(r){
  var s=(r&&r.snps)||{};
  var n=(s.pos||[]).length;
  var out=[], seen={};
  function add(j, why){
    if(j==null||j<0||j>=n||seen[j]) return;
    seen[j]=1;
    out.push({j:j, why:why});
  }
  add(r.lead_i, 'lead');
  for(var i=0;i<n;i++) if(Number(s.pos[i])===Number(r.pos)) add(i, 'lead');
  for(i=0;i<n;i++) if(s.mas&&s.mas[i]) add(i, String(s.mas[i]));
  for(i=0;i<n;i++) if(s.design&&Number(s.design[i])) add(i, 'design-time');
  var a=Number(r.span_start||0), b=Number(r.span_end||0);
  if(a&&b){
    for(i=0;i<n;i++){
      var p=Number(s.pos[i]);
      if(p>=a && p<=b) add(i, 'named window');
    }
  }
  if(out.length<12){
    for(i=0;i<n;i++) if(s.bonf&&Number(s.bonf[i])) add(i, 'Bonferroni');
  }
  return out.slice(0, 40);
}
function fillQueryGtCard(id, r, onPick){
  var el=document.getElementById(id);
  if(!el) return;
  if(!r){ el.innerHTML=''; return; }
  var s=r.snps||{};
  var name=r.query_gt_sample||D.query||'query';
  var sel=id==='sel-gt-card';
  if(!s.gt){
    el.innerHTML='<div class="gt-card warn"><div class="en"><strong>This sample’s genotypes are not in this HTML.</strong> '+
      'Fst / −log10 p / r² on the plot are the 2449 map, not calls for '+esc(name)+
      '. Rebuild after <code>results/'+esc(name)+'.vcf.gz</code> exists.</div>'+
      '<div class="cn"><strong>本样品分型不在这份 HTML 里。</strong> '+
      '图上的 Fst / −log10 p / r² 来自 2449 地图，不是 '+esc(name)+
      ' 的分型。请在 <code>results/'+esc(name)+'.vcf.gz</code> 存在后重新生成。</div></div>';
    return;
  }
  var c=lzGtCounts(r);
  var leadJ=r.lead_i;
  if(leadJ==null||leadJ<0){
    for(var i=0;i<(s.pos||[]).length;i++) if(Number(s.pos[i])===Number(r.pos)){ leadJ=i; break; }
  }
  var site=(leadJ!=null&&leadJ>=0&&s.site[leadJ])||(String(r.chrom)+':'+String(r.pos));
  var alle='';
  if(leadJ!=null&&leadJ>=0&&s.ref&&s.alt&&s.ref[leadJ]&&s.alt[leadJ]) alle=s.ref[leadJ]+'>'+s.alt[leadJ];
  var gt=(leadJ!=null&&leadJ>=0)?s.gt[leadJ]:-1;
  var leadLab=sel?bi('Lead SNP (highest Fst on the 2449 map)','窗口主 SNP（2449 上 Fst 最高）'):
    bi('Lead SNP (highest −log10 p on the 2449 map)','窗口主 SNP（2449 上 −log10 p 最高）');
  var ex=lzGtExplain(gt);
  var h='<div class="gt-card">';
  h+='<div class="gt-head"><strong>'+bi('Query genotype overlay','查询基因型叠加')+'</strong> · <strong>'+bi('This sample','本样品分型')+'</strong> '+esc(name);
  if(r.query_gt_note) h+=' <span class="muted">('+esc(r.query_gt_note)+')</span>';
  h+='<div class="muted" style="margin-top:4px">'+t(
    'LocusZoom is the 2449 map. This panel is only what <em>'+esc(name)+'</em> called at these chip sites.',
    'LocusZoom 是 2449 面板地图。这里仅显示 <em>'+esc(name)+'</em> 在这些芯片位点上的分型。')+'</div></div>';
  h+='<div class="gt-legend">';
  h+='<span class="gt-leg">'+lzGtPill(0)+' '+bi('homozygous reference','两个拷贝都和参考一样')+'</span>';
  h+='<span class="gt-leg">'+lzGtPill(1)+' '+bi('heterozygous','一条参考、一条变异')+'</span>';
  h+='<span class="gt-leg">'+lzGtPill(2)+' '+bi('homozygous alt','两个拷贝都是变异')+'</span>';
  h+='<span class="gt-leg">'+lzGtPill(-1)+' '+bi('not called','这个位点没打出来')+'</span>';
  h+='</div>';
  h+='<div class="gt-lead">'+leadLab+' · '+esc(site);
  if(alle) h+=' <span class="muted">'+esc(alle)+'</span>';
  h+=' '+lzGtPill(gt)+'</div>';
  h+='<p class="gt-callout en">'+esc(ex.en||'')+'</p>';
  if(ex.cn) h+='<div class="cn">'+esc(ex.cn)+'</div>';
  h+='<div class="gt-counts">'+t(
    'Chip sites in window '+c.n+' · called '+c.called+' · missing '+c.miss,
    '本窗口芯片位点 '+c.n+' · 打出 '+c.called+' · 缺失 '+c.miss)+'</div>';
  h+=gtCountBars(c);
  h+='<p class="muted" style="margin:8px 0 4px">'+t(
    'Key sites (lead / MAS / design). Click a row to jump LocusZoom. Strip colour is genotype, not LD.',
    '重点位点（主位点 / MAS / 设计位点）。点一行跳到 LocusZoom。色带颜色是基因型，不是 LD。')+'</p>';
  var keys=lzKeyGtIdx(r);
  if(keys.length){
    h+='<div class="table-scroll"><table><caption>'+bi(
      'Key query genotype sites','查询样本重点基因型位点')+'</caption><thead><tr><th>'+
      bi('Why','为什么看')+'</th><th>'+bi('Site','位点')+'</th><th>'+
      bi('Alleles','等位基因')+'</th><th>'+bi('This sample','本样品')+
      '</th><th>'+bi('Gene','基因')+'</th></tr></thead><tbody>';
    keys.forEach(function(row){
      var j=row.j;
      var aa=((s.ref&&s.ref[j])||'')+(((s.ref&&s.ref[j])&&(s.alt&&s.alt[j]))?'>':'')+((s.alt&&s.alt[j])||'');
      h+='<tr class="clickrow" data-gt-snp="'+j+'"><td>'+lzWhyLab(row.why)+'</td><td>'+esc(s.site[j]||'')+
        '</td><td>'+esc(aa)+'</td><td>'+lzGtPill(s.gt[j])+'</td><td>'+esc(s.gene&&s.gene[j]||'')+'</td></tr>';
    });
    h+='</tbody></table></div>';
  }
  h+='</div>';
  el.innerHTML=h;
  el.querySelectorAll('[data-gt-snp]').forEach(function(row){
    row.addEventListener('click', function(){
      if(onPick) onPick(parseInt(row.getAttribute('data-gt-snp'),10));
    });
  });
}
function gtCountBars(c){
  var n=Math.max(c.n,1);
  function row(cls, n0, lab){
    var pct=Math.round(100*n0/n);
    return '<div class="gt-bar-row"><span class="gt-pill gt-'+cls+'">'+lab+'</span><span>'+n0+'</span>'+
      '<div class="gt-bar"><i class="gt-'+cls+'" style="width:'+pct+'%"></i></div></div>';
  }
  return row('ref', c.ref, t('0/0','0/0 参考'))+
    row('het', c.het, t('0/1','0/1 杂合'))+
    row('alt', c.alt, t('1/1','1/1 替代'))+
    row('miss', c.miss, t('./.','./. 缺失'));
}
function drawQueryGtStrip(id, r, onPick){
  var el=document.getElementById(id);
  if(!el) return;
  if(!r||!r.snps||!(r.snps.pos||[]).length){
    resetPlot(el);
    return;
  }
  if(!r.snps.gt){
    resetPlot(el);
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'No query genotypes attached.','没有附带查询样本基因型。')+'</p>';
    return;
  }
  if(!plotlyCan('newPlot')){
    resetPlot(el);
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'Plotly.js unavailable; genotype strip skipped.',
      'Plotly.js 不可用；跳过基因型色带。')+'</p>';
    return;
  }
  resetPlot(el);
  var s=r.snps;
  var labs={ref:'0/0 REF', het:'0/1 het', alt:'1/1 ALT', miss:'./. missing'};
  var cols={ref:'#3b82f6', het:'#eab308', alt:'#ef4444', miss:'#64748b'};
  var ymap={miss:0, ref:1, het:2, alt:3};
  var traces=['miss','ref','het','alt'].map(function(k){
    var x=[], y=[], cd=[], txt=[];
    for(var j=0;j<(s.pos||[]).length;j++){
      if(lzGtClass(s.gt[j])!==k) continue;
      x.push(Number(s.pos[j]));
      y.push(ymap[k]);
      cd.push(j);
      txt.push((s.site[j]||'')+' · '+lzGtLab(s.gt[j]));
    }
    return {
      type:'scattergl', mode:'markers', name:t(labs[k],{
        '0/0 REF':'0/0 参考','0/1 het':'0/1 杂合',
        '1/1 ALT':'1/1 替代','./. missing':'./. 缺失'
      }[labs[k]]||labs[k]),
      x:x, y:y, customdata:cd, text:txt,
      marker:{size:k==='miss'?5:8, color:cols[k], opacity:k==='miss'?0.35:0.9},
      hovertemplate:t('%{text}<extra></extra>','%{text}<extra>基因型</extra>')
    };
  });
  Plotly.newPlot(el, traces, withPlotSize({
    margin:{t:8, r:12, b:36, l:70},
    font:{color:themeTokens().text, size:11},
    showlegend:true, legend:{orientation:'h', y:1.15, font:{size:10}},
    xaxis:{title:t('position (bp)','位置（bp）'), gridcolor:themeTokens()['plot-grid']},
    yaxis:{tickvals:[0,1,2,3], ticktext:['./.','0/0','0/1','1/1'], range:[-0.6,3.6], gridcolor:themeTokens()['plot-grid']},
    title:{text:t('This sample','本样品')+' · '+(r.query_gt_sample||D.query||'query'), font:{size:12}}
  }, el, 150), plotlyCfg());
  el.on('plotly_click', function(ev){
    var p=ev&&ev.points&&ev.points[0];
    if(!p||p.customdata==null||!onPick) return;
    onPick(Number(p.customdata));
  });
}
function lzGeneOf(r, gid){
  if(!gid) return null;
  var genes=r.genes||[];
  for(var i=0;i<genes.length;i++) if(genes[i].id===gid) return genes[i];
  return null;
}
function lzClip(s,n){
  s=String(s||'');
  n=n||90;
  return s.length>n?s.slice(0,n)+'…':s;
}
function lzSnpHover(r,j){
  var s=r.snps||{};
  var site=s.site[j]||'';
  var ref=s.ref&&s.ref[j], alt=s.alt&&s.alt[j];
  var alle=(ref&&alt)?(' '+ref+'>'+alt):'';
  var r2v=s.r2&&s.r2[j];
  var gene=s.gene&&s.gene[j];
  var g=lzGeneOf(r, gene);
  var lines=[
    site+alle+(s.bonf&&Number(s.bonf[j])?' · Bonferroni':''),
    (Number(s.pos[j])/1e6).toFixed(3)+' Mb · −log10p='+fmtNum(Number(s.nlp[j]),2)+
      (r2v!=null&&r2v!==''?' · r²='+fmtNum(Number(r2v),2):'')
  ];
  lines.push('p='+lzFmtP(s.p&&s.p[j])+' · β='+fmtNum(s.beta&&s.beta[j],4)+
    ' · SE='+fmtNum(s.se&&s.se[j],3)+' · MAF='+fmtNum(s.maf&&s.maf[j],3));
  if(gene){
    var dist=s.dist&&s.dist[j];
    var reg=s.region&&s.region[j];
    var alias=g&&g.alias&&g.alias!==gene?(' / '+g.alias):'';
    lines.push(gene+alias+(reg?(' · '+reg):'')+(dist!=null&&dist!==''?' · '+dist+' bp':''));
    if(g&&g.product) lines.push(lzClip(g.product,80));
  }
  if(s.overlap&&s.overlap[j]) lines.push('trait-locus ±50 kb: '+s.overlap[j]);
  if(s.design&&Number(s.design[j])) lines.push('design-time GWAS/MAS site');
  if(s.mas&&s.mas[j]) lines.push(s.mas[j]);
  if(s.gt) lines.push('query GT ('+(r.query_gt_sample||D.query||'')+'): '+lzGtLab(s.gt[j]));
  return lines.join('<br>');
}
function lzGeneHover(g){
  var bits=[g.id+(g.alias&&g.alias!==g.id?(' / '+g.alias):'')];
  bits.push((g.strand||'.')+' · '+g.start+'-'+g.end+(g.biotype?(' · '+g.biotype):''));
  if(g.product) bits.push(lzClip(g.product,90));
  if(g.science_note) bits.push(lzClip(g.science_note,90));
  return bits.join('<br>');
}
function lzLabel(label){
  var labels={
    'span':'范围',
    'biotype':'生物类型',
    'product':'产物',
    'GO':'GO',
    'Pfam':'Pfam',
    'InterPro':'InterPro',
    'KEGG':'KEGG',
    'grape IDs':'葡萄 ID',
    'MAS / Science':'MAS / Science',
    'MAS trait':'MAS 性状',
    'alleles':'等位基因',
    'chr:pos':'染色体:位置',
    'β ± SE':'β ± SE',
    'MAF / n':'MAF / n',
    'r² to lead':'与主位点的 r²',
    'Bonferroni':'Bonferroni',
    'nearest gene':'最近基因',
    'region / dist':'区域 / 距离',
    'strand':'链',
    'trait-locus ±50 kb':'性状位点 ±50 kb',
    'design-time site':'设计期位点',
    'Dong 2023 / MAS':'Dong 2023 / MAS',
    'query GT':'查询基因型',
    'gene':'基因',
    'region':'区域',
    'this sample':'本样品',
    'Fst among Grps':'全体 Grp 的 Fst',
    'Fst among all Grps':'全体 Grp 的 Fst',
    'het / windowed heterozygosity':'杂合 / 窗口杂合度',
    'windowed heterozygosity':'窗口杂合度'
  };
  return t(label,labels[label]||label);
}
function lzDl(rows){
  var h='<dl class="lz-dl">';
  rows.forEach(function(kv){
    if(!kv || kv[1]==null || kv[1]==='') return;
    h+='<dt>'+esc(lzLabel(String(kv[0]||'')))+'</dt><dd>'+kv[1]+'</dd>';
  });
  return h+'</dl>';
}
function fillLzMeta(r){
  var el=document.getElementById('lz-meta');
  if(!el) return;
  if(!r){ el.innerHTML=''; return; }
  var bits=[];
  bits.push(oivTraitHtml(r.trait||''));
  if(r.descriptor) bits.push(esc(r.descriptor));
  if(r.scale) bits.push(t('scale ','尺度 ')+esc(r.scale));
  if(r.n) bits.push('n='+esc(String(r.n)));
  if(r.lambda!=null) bits.push('λ='+fmtNum(Number(r.lambda),3));
  if(r.m) bits.push('m='+esc(String(r.m)));
  if(r.bonf_nlp) bits.push(t('Bonferroni −log10p=','Bonferroni −log10p=')+fmtNum(Number(r.bonf_nlp),2));
  bits.push(t('window SNPs=','窗口 SNP 数=')+esc(String(r.n_snps||''))+
    (r.n_bonf_window!=null?t(' · Bonferroni in window=',' · 窗口内 Bonferroni=')+
      esc(String(r.n_bonf_window)):''));
  if(r.notations) bits.push(t('notes: ','说明：')+esc(lzClip(r.notations,120)));
  var src=t('r² = 2449 panel dosage vs lead. p / β / MAF = panel EMMAX/P3D.',
    'r² = 2449 面板 dosage 对 lead。p / β / MAF = 面板 EMMAX/P3D。');
  if((r.snps&&r.snps.gt)) src+=' '+t(
    'GT = '+esc(r.query_gt_sample||D.query||'query')+' ('+(r.query_gt_called||0)+'/'+(r.query_gt_n||0)+' called).',
    'GT = '+esc(r.query_gt_sample||D.query||'query')+'（'+(r.query_gt_called||0)+'/'+(r.query_gt_n||0)+' 已分型）。');
  el.innerHTML=bits.join(' · ')+'<div class="muted">'+src+'</div>';
}
function fillLzDetail(r, kind, idx){
  var el=document.getElementById('lz-detail');
  if(!el||!r) return;
  if(kind==='gene'){
    var g=(r.genes||[])[idx];
    if(!g){ el.innerHTML=''; return; }
    var title=esc(g.id)+(g.alias&&g.alias!==g.id?(' / '+esc(g.alias)):'');
    el.innerHTML='<strong>'+esc(t('Gene','基因'))+'</strong> '+title+
      lzDl([
        ['span', esc(String(g.start))+'-'+esc(String(g.end))+' ('+esc(g.strand||'.')+')'],
        ['biotype', esc(g.biotype||'')],
        ['product', prodCell(g)],
        ['GO', dbLinks('go', g.go, 8)],
        ['Pfam', dbLinks('pfam', g.pfam, 6)],
        ['InterPro', dbLinks('interpro', g.interpro, 6)],
        ['KEGG', keggCellHtml(g)],
        ['grape IDs', vitisCellHtml(g)],
        ['MAS / Science', esc(g.science_note||'')],
        ['MAS trait', esc(g.mas_trait||'')]
      ]);
    return;
  }
  var s=r.snps||{};
  var j=idx;
  if(j==null||j<0) j=r.lead_i;
  if(j==null||j<0){
    for(var i=0;i<(s.pos||[]).length;i++) if(Number(s.pos[i])===Number(r.pos)){ j=i; break; }
  }
  if(j==null||j<0){ el.innerHTML=''; return; }
  var gene=s.gene&&s.gene[j];
  var g=lzGeneOf(r, gene);
  var ref=s.ref&&s.ref[j], alt=s.alt&&s.alt[j];
  var alle=(ref&&alt)?(esc(ref)+' > '+esc(alt)):'';
  var gtxt='';
  if(gene) gtxt=esc(gene)+(g&&g.alias&&g.alias!==gene?(' / '+esc(g.alias)):'');
  el.innerHTML='<strong>'+esc(t('SNP','SNP'))+'</strong> '+esc(s.site[j]||'')+(Number(s.pos[j])===Number(r.pos)?t(' · lead',' · 主位点'):'')+
    lzDl([
      ['alleles', alle],
      ['chr:pos', esc(r.chrom)+':'+esc(String(s.pos[j]))+' ('+fmtNum(Number(s.pos[j])/1e6,3)+' Mb)'],
      ['−log10 p', esc(fmtNum(Number(s.nlp[j]),3))],
      ['p / q', esc(lzFmtP(s.p&&s.p[j]))+' / '+esc(lzFmtP(s.q&&s.q[j]))],
      ['β ± SE', esc(fmtNum(s.beta&&s.beta[j],5))+' ± '+esc(fmtNum(s.se&&s.se[j],4))],
      ['MAF / n', esc(fmtNum(s.maf&&s.maf[j],4))+' / '+esc(String(s.n&&s.n[j]!=null?s.n[j]:(r.n||'')))],
      ['r² to lead', (s.r2&&s.r2[j]!=null&&s.r2[j]!=='')?esc(fmtNum(Number(s.r2[j]),3)):'—'],
      ['Bonferroni', s.bonf&&Number(s.bonf[j])?t('yes','是'):t('no','否')],
      ['nearest gene', gtxt],
      ['region / dist', esc(s.region&&s.region[j]||'')+(s.dist&&s.dist[j]!=null&&s.dist[j]!==''?(' · '+esc(String(s.dist[j]))+' bp'):'')],
      ['strand', esc(s.strand&&s.strand[j]||'')],
      ['product', g?prodCell(g):''],
      ['GO', g?dbLinks('go', g.go, 8):''],
      ['Pfam', g?dbLinks('pfam', g.pfam, 6):''],
      ['InterPro', g?dbLinks('interpro', g.interpro, 6):''],
      ['KEGG', g?keggCellHtml(g):''],
      ['grape IDs', g?vitisCellHtml(g):''],
      ['trait-locus ±50 kb', esc(s.overlap&&s.overlap[j]||'')],
      ['design-time site', s.design&&Number(s.design[j])?t(
        'yes (GWAS/MAS overlap)','是（GWAS/MAS 重合）'):''],
      ['Dong 2023 / MAS', esc(s.mas&&s.mas[j]||'')],
      ['query GT', s.gt?esc(lzGtLab(s.gt[j]))+' · '+esc(r.query_gt_sample||D.query||'')+
        ' ('+esc(t('this sample','本样品'))+')':'']
    ]);
}
function fillLzBonf(r){
  var el=document.getElementById('lz-bonf');
  if(!el||!r) return;
  var s=r.snps||{};
  var idx=[];
  for(var i=0;i<(s.nlp||[]).length;i++){
    if(s.bonf&&Number(s.bonf[i])) idx.push(i);
  }
  idx.sort(function(a,b){ return Number(s.nlp[b])-Number(s.nlp[a]); });
  var extra=idx.length>20?t(' showing 20/'+idx.length,' 显示 20/'+idx.length):
    t(' n='+idx.length,' n='+idx.length);
  idx=idx.slice(0,20);
  if(!idx.length){ el.innerHTML=''; return; }
  var h='<p class="muted">'+t(
    'Bonferroni SNPs in this ±250 kb window ('+extra+'). Click a row for the card. Panel p.',
    '该 ±250 kb 窗口内的 Bonferroni SNP（'+extra+'）。点一行查看卡片。p 值来自面板。')+'</p>';
  h+='<div class="table-scroll"><table><caption>'+t(
    'Bonferroni SNPs','Bonferroni SNP')+'</caption><thead><tr>'+
    '<th scope="col">'+t('site','位点')+'</th><th scope="col">'+t('alleles','等位基因')+
    '</th><th scope="col">−log10p</th><th scope="col">β</th><th scope="col">MAF</th>'+
    '<th scope="col">r²</th><th scope="col">'+t('gene','基因')+'</th>'+
    '<th scope="col">'+t('region','区域')+'</th><th scope="col">'+t('query GT','查询基因型')+
    '</th></tr></thead><tbody>';
  idx.forEach(function(j){
    var g=lzGeneOf(r, s.gene&&s.gene[j]);
    var alle=((s.ref&&s.ref[j])||'')+(((s.ref&&s.ref[j])&&(s.alt&&s.alt[j]))?'>':'')+((s.alt&&s.alt[j])||'');
    h+='<tr class="clickrow" data-lz-snp="'+j+'"><td>'+esc(s.site[j]||'')+'</td><td>'+esc(alle)+
      '</td><td>'+fmtNum(Number(s.nlp[j]),2)+'</td><td>'+fmtNum(s.beta&&s.beta[j],3)+
      '</td><td>'+fmtNum(s.maf&&s.maf[j],3)+'</td><td>'+((s.r2&&s.r2[j]!=null&&s.r2[j]!=='')?fmtNum(Number(s.r2[j]),2):'—')+
      '</td><td>'+esc(s.gene&&s.gene[j]||'')+(g&&g.alias&&g.alias!==(s.gene&&s.gene[j])?' / '+esc(g.alias):'')+
      '</td><td>'+esc(s.region&&s.region[j]||'')+'</td><td>'+(s.gt?esc(lzGtLab(s.gt[j])):'')+'</td></tr>';
  });
  h+='</tbody></table></div>';
  el.innerHTML=h;
  el.querySelectorAll('[data-lz-snp]').forEach(function(row){
    row.addEventListener('click', function(){
      fillLzDetail(r, 'snp', parseInt(row.getAttribute('data-lz-snp'),10));
    });
  });
}
function lzVariant(r,j){
  var s=r.snps||{};
  var ref=s.ref&&s.ref[j], alt=s.alt&&s.alt[j];
  if(ref&&alt) return String(r.chrom)+':'+s.pos[j]+'_'+ref+'/'+alt;
  return s.site[j]|| (String(r.chrom)+':'+s.pos[j]);
}
function lzPortalFromRec(r){
  var s=r.snps||{};
  var n=(s.pos||[]).length;
  var lead=Number(r.pos);
  var assoc=[], ld=[];
  for(var j=0;j<n;j++){
    var g=lzGeneOf(r, s.gene&&s.gene[j]);
    var isLead=Number(s.pos[j])===lead;
    var row={
      variant:lzVariant(r,j),
      chromosome:String(r.chrom),
      position:Number(s.pos[j]),
      log_pvalue:Number(s.nlp[j]),
      ref_allele:(s.ref&&s.ref[j])||'',
      alt_allele:(s.alt&&s.alt[j])||'',
      beta:s.beta?s.beta[j]:null,
      se:s.se?s.se[j]:null,
      maf:s.maf?s.maf[j]:null,
      nearest_gene:(s.gene&&s.gene[j])||'',
      region:(s.region&&s.region[j])||'',
      dist:s.dist&&s.dist[j],
      mas:(s.mas&&s.mas[j])||'',
      product:(g&&g.product)||'',
      query_gt:s.gt?lzGtLab(s.gt[j]):'',
      lz_is_ld_refvar:isLead
    };
    assoc.push(row);
    var r2=s.r2&&s.r2[j];
    if(isLead) ld.push({variant2:row.variant, position2:row.position, correlation:1});
    else if(r2!=null && r2!=='') ld.push({variant2:row.variant, position2:row.position, correlation:Number(r2)});
  }
  var chrom=String(r.chrom);
  var genes=(r.genes||[]).map(function(g){
    var exons=(g.cds&&g.cds.length?g.cds:[[g.start,g.end]]).map(function(se,i){
      return {chrom:chrom, start:se[0], end:se[1], strand:g.strand||'+', exon_id:g.id+'.e'+i};
    });
    return {
      gene_id:g.id,
      gene_name:g.alias||g.id,
      gene_type:g.biotype||'protein_coding',
      chrom:chrom,
      start:g.start,
      end:g.end,
      strand:g.strand||'+',
      exons:exons,
      transcripts:[{transcript_id:g.id+'.t1', chrom:chrom, start:g.start, end:g.end, strand:g.strand||'+', exons:exons}],
      product:g.product||'',
      uniprot:g.uniprot||'',
      science_note:g.science_note||''
    };
  });
  return {assoc:assoc, ld:ld, genes:genes};
}
function lzJumpToSnp(plot, r, j){
  if(!plot||!r||j==null||j<0) return;
  var s=r.snps||{};
  var pos=Number(s.pos&&s.pos[j]);
  if(!isFinite(pos)||!plot.applyState) return;
  var win0=Number(r.window_start||0), win1=Number(r.window_end||0);
  var pad=Math.max(20000, Math.round((win1-win0)/8)||50000);
  var start=Math.max(1, pos-pad), end=pos+pad;
  try{ plot.applyState({chr:String(r.chrom), start:start, end:end}); }catch(err){}
}
function snpIndexAtPos(r, pos){
  var s=(r&&r.snps)||{};
  var best=-1, d=1e18, p=Number(pos);
  for(var i=0;i<(s.pos||[]).length;i++){
    var dd=Math.abs(Number(s.pos[i])-p);
    if(dd<d){ d=dd; best=i; }
  }
  return best;
}
function pickLzSnp(j){
  var r=(D.gwas_loci||[])[lzIdx];
  if(!r) return;
  fillLzDetail(r, 'snp', j);
  fillQueryGtCard('lz-gt-card', r, pickLzSnp);
  lzJumpToSnp(lzPlot, r, j);
}
function pickSelSnp(j){
  var r=(D.selection_loci||[])[selLzIdx];
  if(!r) return;
  var s=r.snps||{};
  if(s.pos&&s.pos[j]!=null) selLzFocusPos=Number(s.pos[j]);
  fillSelLzSnp(r, j);
  fillQueryGtCard('sel-gt-card', r, pickSelSnp);
  lzJumpToSnp(selLzPlot, r, j);
}
function setLz(i){
  var n=(D.gwas_loci||[]).length;
  lzIdx=Math.max(0, Math.min(i, Math.max(0,n-1)));
  var sel=document.getElementById('lz-pick');
  if(sel) sel.value=String(lzIdx);
  drawLocusZoom();
}
function drawLocusZoom(){
  var el=document.getElementById('plot-lz');
  if(!el) return;
  var r=(D.gwas_loci||[])[lzIdx];
  var snps=r&&r.snps;
  if(!snps || !(snps.pos||[]).length){
    if(lzPlot&&lzPlot.destroy) try{lzPlot.destroy();}catch(err){}
    lzPlot=null;
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'No LocusZoom data for this locus.','没有该位点的 LocusZoom 数据。')+'</p>';
    fillLzMeta(null);
    var d=document.getElementById('lz-detail'); if(d) d.innerHTML='';
    var b=document.getElementById('lz-bonf'); if(b) b.innerHTML='';
    fillQueryGtCard('lz-gt-card', null);
    drawQueryGtStrip('plot-lz-gt', null);
    return;
  }
  fillLzMeta(r);
  fillLzDetail(r, 'snp', r.lead_i);
  fillLzBonf(r);
  fillQueryGtCard('lz-gt-card', r, pickLzSnp);
  drawQueryGtStrip('plot-lz-gt', r, pickLzSnp);
  if(!locusZoomCan()){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'LocusZoom.js failed to load (assets/locuszoom-0.14.0.app.min.js + d3 5.16).',
      'LocusZoom.js 加载失败（assets/locuszoom-0.14.0.app.min.js + d3 5.16）。')+'</p>';
    return;
  }
  try{
  var pack=lzPortalFromRec(r);
  var leadVar=null;
  for(var i=0;i<pack.assoc.length;i++) if(pack.assoc[i].lz_is_ld_refvar){ leadVar=pack.assoc[i].variant; break; }
  var layout=LocusZoom.Layouts.get('plot','standard_association',{
    state:{chr:String(r.chrom), start:Number(r.window_start), end:Number(r.window_end), ldrefvar:leadVar},
    responsive_resize:false
  });
  var assocPanel=layout.panels.filter(function(p){return p.id==='association';})[0];
  if(assocPanel){
    if(assocPanel.toolbar&&assocPanel.toolbar.widgets){
      assocPanel.toolbar.widgets=assocPanel.toolbar.widgets.filter(function(w){
        return w.type!=='remove_panel' && w.type!=='move_panel_up' && w.type!=='move_panel_down';
      });
    }
    assocPanel.data_layers=(assocPanel.data_layers||[]).filter(function(l){return l.id!=='recombrate';});
    if(assocPanel.axes) delete assocPanel.axes.y2;
    (assocPanel.data_layers||[]).forEach(function(l){
      if(l.id==='significance' && r.bonf_nlp) l.offset=Number(r.bonf_nlp);
      if(l.id==='associationpvalues'){
        if(l.color&&l.color[0]&&l.color[0].field==='lz_is_ld_refvar') l.color[0].field='assoc:lz_is_ld_refvar';
        if(l.point_size&&l.point_size.field==='lz_is_ld_refvar') l.point_size.field='assoc:lz_is_ld_refvar';
        if(l.point_shape&&l.point_shape[0]&&l.point_shape[0].field==='lz_is_ld_refvar') l.point_shape[0].field='assoc:lz_is_ld_refvar';
        l.tooltip={
          closable:true,
          show:{or:['highlighted','selected']},
          hide:{and:['unhighlighted','unselected']},
          html:'<strong>{{assoc:variant|htmlescape}}</strong><br>'
            +t('P: ','P：')+'<strong>{{assoc:log_pvalue|logtoscinotation|htmlescape}}</strong><br>'
            +t('β=','β=')+'{{assoc:beta|htmlescape}} ± {{assoc:se|htmlescape}} · MAF={{assoc:maf|htmlescape}}<br>'
            +t('Ref/Alt: ','参考/替代：')+'{{assoc:ref_allele|htmlescape}}/{{assoc:alt_allele|htmlescape}}<br>'
            +t('r² to lead: ','到 lead 的 r²：')+'{{ld:correlation|htmlescape}}<br>'
            +t('Gene: ','基因：')+'{{assoc:nearest_gene|htmlescape}} {{assoc:region|htmlescape}}<br>'
            +'{{assoc:product|htmlescape}}<br>'
            +'{{assoc:mas|htmlescape}}<br>'
            +t('Query genotype overlay: ','查询样本基因型叠加：')+'{{assoc:query_gt|htmlescape}} ('+
              t('this sample','本样品')+')<br>'
            +'{{#if assoc:lz_is_ld_refvar}}<strong>'+t(
              'LD reference (panel dosage r²)','LD 参考（面板 dosage r²）')+'</strong>{{/if}}'
        };
      }
    });
  }
  if(layout.toolbar&&layout.toolbar.widgets){
    layout.toolbar.widgets=layout.toolbar.widgets.filter(function(w){ return w.tag!=='ld_population'; });
  }
  var genePanel=layout.panels.filter(function(p){return p.id==='genes';})[0];
  if(genePanel){
    genePanel.toolbar={widgets:[]};
    if(genePanel.data_layers&&genePanel.data_layers[0]){
      var gl=genePanel.data_layers[0];
      gl.namespace={gene:'gene'};
      gl.id_field='gene_id';
      gl.data_operations=[{type:'fetch', from:['gene']}];
      gl.filters=[];
      gl.tooltip_positioning='bottom';
      gl.tooltip={
        closable:true,
        show:{or:['highlighted','selected']},
        hide:{and:['unhighlighted','unselected']},
        html:'<h4><strong><i>{{gene_name|htmlescape}}</i></strong></h4>'
          +t('VS-1 ','VS-1 ')+'<strong>{{gene_id|htmlescape}}</strong> · {{gene_type|htmlescape}} · {{strand|htmlescape}}<br>'
          +'{{start}}-{{end}}<br>'
          +'{{product|htmlescape}}<br>'
          +'{{#if uniprot}}UniProt {{uniprot|htmlescape}}<br>{{/if}}'
          +'{{science_note|htmlescape}}'
      };
    }
  }
  lzSizeLayout(layout, el);
  if(lzPlot&&lzPlot.destroy) try{lzPlot.destroy();}catch(err){}
  el.innerHTML='';
  function lzCopy(x){ return JSON.parse(JSON.stringify(x)); }
  var sources=new LocusZoom.DataSources()
    .add('assoc', ['StaticJSON', {data:lzCopy(pack.assoc)}])
    .add('ld', ['StaticJSON', {data:lzCopy(pack.ld)}])
    .add('gene', ['StaticJSON', {data:lzCopy(pack.genes), prefix_namespace:false}]);
  lzPlot=LocusZoom.populate('#plot-lz', sources, layout);
  lzAfterRender(lzPlot, el);
  function lzDatumFromEvent(ev){
    var payload=(ev&&ev.data)||ev||{};
    if(payload&&payload.element) return payload.element;
    return payload;
  }
  function lzFillFromDatum(dt){
    if(!dt||typeof dt!=='object') return;
    if(dt['assoc:variant']||dt['assoc:position']||dt.variant){
      var key=String(dt['assoc:variant']||dt.variant||'').split('_')[0];
      var j=(r.snps.site||[]).indexOf(key);
      if(j<0){
        var pos=dt['assoc:position']!=null?dt['assoc:position']:dt.position;
        for(var k=0;k<(r.snps.pos||[]).length;k++) if(Number(r.snps.pos[k])===Number(pos)){ j=k; break; }
      }
      if(j>=0) fillLzDetail(r,'snp',j);
      return;
    }
    var gid=dt.gene_id||dt['gene:gene_id'];
    if(!gid) return;
    var gi=-1;
    (r.genes||[]).forEach(function(g,i){ if(g.id===gid) gi=i; });
    if(gi>=0) fillLzDetail(r,'gene',gi);
  }
  var glive=lzPlot.panels&&lzPlot.panels.genes&&lzPlot.panels.genes.data_layers&&lzPlot.panels.genes.data_layers.genes;
  if(glive&&glive.layout){
    glive.layout.tooltip=glive.layout.tooltip||{};
    glive.layout.tooltip.html='<h4><strong><i>{{gene_name|htmlescape}}</i></strong></h4>'
      +t('VS-1 ','VS-1 ')+'{{gene_id|htmlescape}} · {{gene_type|htmlescape}} · {{strand|htmlescape}}<br>'
      +'{{start}}-{{end}}<br>{{product|htmlescape}}';
  }
  if(!el._gaLinkGuard){
    el._gaLinkGuard=true;
    el.addEventListener('click', function(e){
      var a=e.target&&e.target.closest&&e.target.closest('a');
      if(!a) return;
      a.setAttribute('target','_blank');
      a.setAttribute('rel','noopener noreferrer');
    }, true);
  }
  if(lzPlot&&lzPlot.on){
    lzPlot.on('element_selection', function(ev){
      try{
        var payload=(ev&&ev.data)||{};
        if(payload&&payload.active===false) return;
        lzFillFromDatum(lzDatumFromEvent(ev));
      }catch(err){ console.error(err); }
    });
    lzPlot.on('element_clicked', function(ev){
      try{ lzFillFromDatum(lzDatumFromEvent(ev)); }
      catch(err){ console.error(err); }
    });
  }
  }catch(err){
    lzPlot=null;
    var msg=esc(String((err&&err.message)||err));
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'LocusZoom.js failed: '+msg,
      'LocusZoom.js 加载失败：'+msg)+'</p>';
    return;
  }
}

function selPortalFromRec(r, metric){
  var pack=lzPortalFromRec(r);
  var s=r.snps||{};
  metric=metric||'fst';
  for(var j=0;j<pack.assoc.length;j++){
    var fst=(s.fst&&s.fst[j]!=null)?Number(s.fst[j]):Number(s.nlp&&s.nlp[j]);
    var hetw=(s.het_window&&s.het_window[j]!=null)?Number(s.het_window[j]):null;
    var het=(s.het&&s.het[j]!=null)?Number(s.het[j]):null;
    pack.assoc[j].fst=fst;
    pack.assoc[j].het_window=hetw;
    pack.assoc[j].het=het;
    pack.assoc[j].log_pvalue=(metric==='het'&&hetw!=null&&hetw===hetw)?hetw:fst;
  }
  return pack;
}
function selLocusPrimary(r){
  return String((r&&r.kind)||'')!=='s29';
}
function setSelLz(i, keepFocus){
  var n=(D.selection_loci||[]).length;
  selLzIdx=Math.max(0, Math.min(i, Math.max(0,n-1)));
  if(!keepFocus) selLzFocusPos=null;
  var sel=document.getElementById('sel-lz-pick');
  if(sel) sel.value=String(selLzIdx);
  drawSelLocusZoom();
}
function setSelLzBySlug(slug){
  var idx=(D.selection_loci||[]).findIndex(function(r){
    if(!r || r.slug!==slug) return false;
    if(selLocusPrimary(r)) return true;
    return String(r.kind||'')==='s29' && r.snps && (r.snps.pos||[]).length>0;
  });
  if(idx>=0){ setSelLz(idx); return true; }
  return false;
}
function bindSweepSiteButton(button){
  if(!button || button._gaSweepSiteBound || !button.addEventListener) return;
  button._gaSweepSiteBound=true;
  button.addEventListener('click',function(){
    focusSelManhattan(
      button.getAttribute('data-sw-chr'),
      button.getAttribute('data-sw-pos')
    );
  });
  button.addEventListener('keydown',function(ev){
    if(!ev || (ev.key!=='Enter' && ev.key!==' ')) return;
    if(ev.preventDefault) ev.preventDefault();
    if(ev.repeat) return;
    // Preventing the native default keeps this explicit activation single-shot.
    button.click();
  });
  button.addEventListener('keyup',function(ev){
    if(ev && (ev.key==='Enter'||ev.key===' ')){
      if(ev.preventDefault) ev.preventDefault();
    }
  });
}
function setSelLzNearest(chrom, pos){
  var loci=D.selection_loci||[];
  var target=Number(pos);
  if(!isFinite(target)) return false;
  var hit=-1;
  loci.forEach(function(r,i){
    if(!selLocusPrimary(r)) return;
    if(String(r.chrom)!==String(chrom)) return;
    var a=Number(r.window_start||r.span_start||0), b=Number(r.window_end||r.span_end||0);
    if(hit<0 && target>=a && target<=b) hit=i;
  });
  if(hit>=0){
    selLzFocusPos=target;
    setSelLz(hit, true);
    return true;
  }
  return false;
}
function focusSelManhattan(chrom, pos){
  selManhFocus={chrom:String(chrom), pos:Number(pos)};
  drawSelManhattan();
  var el=document.getElementById('plot-sel-manh');
  if(el && typeof el.scrollIntoView==='function'){
    try{ el.scrollIntoView({behavior:motionBehavior(), block:'center'}); }
    catch(err){ try{ el.scrollIntoView(); }catch(ignore){} }
  }
}
function fillSelLzSnp(r, j){
  var det=document.getElementById('sel-lz-detail');
  if(!det||!r) return;
  var s=r.snps||{};
  if(j==null||j<0){
    j=r.lead_i;
    if(j==null||j<0){
      for(var i=0;i<(s.pos||[]).length;i++) if(Number(s.pos[i])===Number(r.pos)){ j=i; break; }
    }
  }
  if(j==null||j<0){ det.innerHTML=''; return; }
  var alle=((s.ref&&s.ref[j])||'')+(((s.ref&&s.ref[j])&&(s.alt&&s.alt[j]))?'>':'')+((s.alt&&s.alt[j])||'');
  det.innerHTML='<strong>'+esc(t('SNP','SNP'))+'</strong> '+esc(s.site[j]||'')+
    (Number(s.pos[j])===Number(r.pos)?t(' · lead',' · 主位点'):'')+
    ' '+lzGtPill(s.gt?s.gt[j]:-1)+
    lzDl([
      ['this sample', esc(r.query_gt_sample||D.query||'')+' · '+(s.gt?lzGtLab(s.gt[j]):t('not attached','未附带'))],
      ['alleles', esc(alle)],
      ['Fst among Grps', esc(fmtNum(s.fst&&s.fst[j],4))],
      ['het / windowed heterozygosity', esc(fmtNum(s.het&&s.het[j],4))+' / '+esc(fmtNum(s.het_window&&s.het_window[j],4))],
      ['r² to lead', (s.r2&&s.r2[j]!=null&&s.r2[j]!=='')?esc(fmtNum(Number(s.r2[j]),3)):'—'],
      ['gene', esc(s.gene&&s.gene[j]||'')],
      ['region', esc(s.region&&s.region[j]||'')],
      ['MAS / Science', esc(s.mas&&s.mas[j]||'')]
    ]);
}
function drawSelLocusZoom(){
  var el=document.getElementById('plot-sel-lz');
  if(!el) return;
  var r=(D.selection_loci||[])[selLzIdx];
  var snps=r&&r.snps;
  var meta=document.getElementById('sel-lz-meta');
  var det=document.getElementById('sel-lz-detail');
  if(!snps || !(snps.pos||[]).length){
    if(selLzPlot&&selLzPlot.destroy) try{selLzPlot.destroy();}catch(err){}
    selLzPlot=null;
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'No selection LocusZoom for this locus.',
      '该位点没有选择扫描 LocusZoom 数据。')+'</p>';
    if(meta) meta.innerHTML='';
    if(det) det.innerHTML='';
    fillQueryGtCard('sel-gt-card', null);
    drawQueryGtStrip('plot-sel-gt', null);
    return;
  }
  var metric=selLzMetric||'fst';
  if(meta){
    var locusLabel=esc(r.kind||r.trait||'');
    var yEn=metric==='het'?'windowed heterozygosity ±50 kb':(metric==='both'?'Fst among all Grps (top) + windowed heterozygosity (middle)':'Fst among all Grps');
    var yZh=metric==='het'?'窗口杂合度 ±50 kb':(metric==='both'?'全体 Grp 的 Fst（上图）+ 窗口杂合度（中图）':'全体 Grp 的 Fst');
    meta.innerHTML=locusLabel+' · '+esc(r.slug||'')+' · chr'+esc(String(r.chrom))+':'+esc(String(r.window_start))+'-'+esc(String(r.window_end))+
      ' · '+t('lead','主位点')+' '+esc(String(r.chrom)+':'+String(r.pos))+' · n='+esc(String(r.n_snps||''))+
      '<div class="muted">'+bi(
        'Active panel computation: Y = '+yEn+'. Panel map statistic; LocusZoom colour = panel r². Query genotype overlay: table / strip below = this sample’s genotypes.',
        '当前面板计算：纵轴 = '+yZh+'。面板统计量；LocusZoom 颜色 = panel r²。查询样本基因型叠加：下方表格和色带是本样品分型。')+
      '</div>';
  }
  var focusJ=r.lead_i;
  if(selLzFocusPos!=null){
    var at=snpIndexAtPos(r, selLzFocusPos);
    if(at>=0) focusJ=at;
  }
  fillSelLzSnp(r, focusJ);
  fillQueryGtCard('sel-gt-card', r, pickSelSnp);
  drawQueryGtStrip('plot-sel-gt', r, pickSelSnp);
  if(!locusZoomCan()){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'LocusZoom.js unavailable; selection regional context cannot be rendered.',
      'LocusZoom.js 不可用；无法渲染选择扫描区域背景。')+'</p>';
    return;
  }
  try{
  var pack=selPortalFromRec(r, metric);
  var leadVar=null;
  for(var i=0;i<pack.assoc.length;i++) if(pack.assoc[i].lz_is_ld_refvar){ leadVar=pack.assoc[i].variant; break; }
  var layout=LocusZoom.Layouts.get('plot','standard_association',{
    state:{chr:String(r.chrom), start:Number(r.window_start), end:Number(r.window_end), ldrefvar:leadVar},
    responsive_resize:false
  });
  var assocPanel=layout.panels.filter(function(p){return p.id==='association';})[0];
  if(assocPanel){
    if(assocPanel.toolbar&&assocPanel.toolbar.widgets){
      assocPanel.toolbar.widgets=assocPanel.toolbar.widgets.filter(function(w){
        return w.type!=='remove_panel' && w.type!=='move_panel_up' && w.type!=='move_panel_down';
      });
    }
    assocPanel.data_layers=(assocPanel.data_layers||[]).filter(function(l){
      return l.id!=='recombrate' && l.id!=='significance';
    });
    if(assocPanel.axes){
      delete assocPanel.axes.y2;
      assocPanel.axes.y=assocPanel.axes.y||{};
      assocPanel.axes.y.label=t(metric==='het'?'windowed heterozygosity (±50 kb)':'Fst among all Grps',
        metric==='het'?'窗口杂合度（±50 kb）':'全体 Grp 的 Fst');
    }
    (assocPanel.data_layers||[]).forEach(function(l){
      if(l.id==='associationpvalues'){
        if(l.y_axis){ delete l.y_axis.min_extent; delete l.y_axis.floor; }
        if(l.color&&l.color[0]&&l.color[0].field==='lz_is_ld_refvar') l.color[0].field='assoc:lz_is_ld_refvar';
        if(l.point_size&&l.point_size.field==='lz_is_ld_refvar') l.point_size.field='assoc:lz_is_ld_refvar';
        if(l.point_shape&&l.point_shape[0]&&l.point_shape[0].field==='lz_is_ld_refvar') l.point_shape[0].field='assoc:lz_is_ld_refvar';
        l.tooltip={
          closable:true,
          show:{or:['highlighted','selected']},
          hide:{and:['unhighlighted','unselected']},
          html:'<strong>{{assoc:variant|htmlescape}}</strong><br>'
            +t('Fst: ','Fst：')+'<strong>{{assoc:fst|htmlescape}}</strong><br>'
            +t('windowed heterozygosity: ','窗口杂合度：')+'{{assoc:het_window|htmlescape}} · het={{assoc:het|htmlescape}}<br>'
            +t('r² to lead: ','到 lead 的 r²：')+'{{ld:correlation|htmlescape}}<br>'
            +t('Gene: ','基因：')+'{{assoc:nearest_gene|htmlescape}} {{assoc:region|htmlescape}}<br>'
            +t('Query genotype overlay: ','查询样本基因型叠加：')+'{{assoc:query_gt|htmlescape}} ('+t('this sample','本样品')+')<br>'
            +'{{#if assoc:lz_is_ld_refvar}}<strong>'+t('LD reference (panel dosage r²)','LD 参考（面板 dosage r²）')+'</strong>{{/if}}'
        };
      }
    });
    if(metric==='both'){
      assocPanel.axes.y.label=t('Fst among all Grps','全体 Grp 的 Fst');
      assocPanel.height=200;
      var hetPanel=JSON.parse(JSON.stringify(assocPanel));
      hetPanel.id='het';
      hetPanel.y_index=1;
      hetPanel.height=180;
      if(hetPanel.axes&&hetPanel.axes.y) hetPanel.axes.y.label=t(
        'windowed heterozygosity (±50 kb)','窗口杂合度（±50 kb）');
      (hetPanel.data_layers||[]).forEach(function(l){
        if(l.id==='associationpvalues'){
          l.id='het_associationpvalues';
          l.y_axis=l.y_axis||{};
          l.y_axis.field='assoc:het_window';
          delete l.y_axis.min_extent;
          delete l.y_axis.floor;
        }else{
          l.id='het_'+l.id;
        }
      });
      layout.panels.splice(1,0,hetPanel);
    }
  }
  if(layout.toolbar&&layout.toolbar.widgets){
    layout.toolbar.widgets=layout.toolbar.widgets.filter(function(w){ return w.tag!=='ld_population'; });
  }
  var genePanel=layout.panels.filter(function(p){return p.id==='genes';})[0];
  if(genePanel){
    if(metric==='both') genePanel.y_index=2;
    genePanel.toolbar={widgets:[]};
    if(genePanel.data_layers&&genePanel.data_layers[0]){
      var gl=genePanel.data_layers[0];
      gl.namespace={gene:'gene'};
      gl.id_field='gene_id';
      gl.data_operations=[{type:'fetch', from:['gene']}];
      gl.filters=[];
    }
  }
  lzSizeLayout(layout, el);
  if(selLzPlot&&selLzPlot.destroy) try{selLzPlot.destroy();}catch(err){}
  el.innerHTML='';
  function lzCopy(x){ return JSON.parse(JSON.stringify(x)); }
  var sources=new LocusZoom.DataSources()
    .add('assoc', ['StaticJSON', {data:lzCopy(pack.assoc)}])
    .add('ld', ['StaticJSON', {data:lzCopy(pack.ld)}])
    .add('gene', ['StaticJSON', {data:lzCopy(pack.genes), prefix_namespace:false}]);
  selLzPlot=LocusZoom.populate('#plot-sel-lz', sources, layout);
  if(selLzFocusPos!=null) lzJumpToSnp(selLzPlot, r, focusJ);
  lzAfterRender(selLzPlot, el);
  }catch(err){
    selLzPlot=null;
    var msg=esc(String((err&&err.message)||err));
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'LocusZoom.js failed: '+msg,
      'LocusZoom.js 加载失败：'+msg)+'</p>';
  }
}
function sweepS29Hits(chrom, pos){
  var S=D.selection_s29_scatter||{}, out=[], p=Number(pos);
  (S.chrom||[]).forEach(function(ch,i){
    if(String(ch)!==String(chrom)) return;
    var a=Number(S.start&&S.start[i]), b=Number(S.end&&S.end[i]);
    if(!isFinite(p)||!isFinite(a)||!isFinite(b)||p<a||p>b) return;
    out.push({
      label: (S.label&&S.label[i])||(S.name&&S.name[i])||'',
      name: (S.name&&S.name[i])||'',
      interval: String(ch)+':'+String(S.start[i])+'-'+String(S.end[i])
    });
  });
  return out;
}
function sweepLocusHit(chrom, pos){
  var p=Number(pos), hit=null, score=-1;
  (D.selection_loci||[]).forEach(function(r){
    if(String(r.chrom)!==String(chrom)) return;
    var a=Number(r.window_start||r.span_start||0), b=Number(r.window_end||r.span_end||0);
    if(!(a&&b&&isFinite(p)&&p>=a&&p<=b)) return;
    var s=r.snps||{}, gene='', region='';
    (s.pos||[]).forEach(function(pp,j){
      if(Number(pp)===p){
        gene=(s.gene&&s.gene[j])||'';
        region=(s.region&&s.region[j])||'';
      }
    });
    var gRec=null;
    (r.genes||[]).forEach(function(g){
      if(!g) return;
      if(gene && (g.id===gene || g.alias===gene || g.vitis_id===gene)) gRec=gRec||g;
      var gs=Number(g.start), ge=Number(g.end);
      if(!gene && isFinite(gs)&&isFinite(ge)&&p>=gs&&p<=ge){
        gene=g.id||g.alias||'';
        gRec=gRec||g;
      }
    });
    if(!gRec && gene){
      (r.genes||[]).forEach(function(g){ if(g&&g.id===gene) gRec=g; });
    }
    var rec={kind:r.kind||'', slug:r.slug||r.trait||'', gene:gene||r.gene||'', geneRec:gRec, region:region, start:a, end:b};
    var sc=(rec.gene?2:0)+(rec.geneRec?1:0)+(rec.kind==='named'?3:0);
    if(!hit || sc>score){ hit=rec; score=sc; }
  });
  return hit;
}
function sweepGenomeHtml(chrom, pos){
  var ch=String(chrom||'').replace(/^chr/i,''), p=String(pos||'');
  if(!ch || !p) return '';
  var href='https://plants.ensembl.org/Vitis_vinifera/Location/View?r='+encodeURIComponent(ch+':'+p+'-'+p);
  return '<a class="dblink" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer" title="Ensembl Plants Vitis vinifera">Ensembl</a>';
}
function sweepGeneHtml(gene, annot){
  var cat=lookupCatalogByGene(gene);
  var t=cat||annot||null;
  if(!gene && !t) return '—';
  var label=gene||(t&&(t.gene||t.id))||'';
  if(!t) return esc(label||'—');
  var html=esc(label);
  var alias=t.alias||t.vitis_symbol||'';
  if(alias && alias!==label) html+=' <span class="muted">('+esc(alias)+')</span>';
  var db=annotDbHtml(t);
  return html+(db?'<span class="ev-sub">'+db+'</span>':'');
}
function sweepContextHtml(r){
  var bits=[];
  if(r.named) bits.push(bi('Named MAS/GWAS window','命名 MAS/GWAS 窗')+' <strong>'+esc(r.named)+'</strong>');
  var s29=sweepS29Hits(r.chrom, r.pos);
  s29.forEach(function(hit){
    bits.push(bi('S29 interval overlap','S29 区间重合')+' '+esc(hit.label||hit.name)+
      ' <span class="muted">'+esc(hit.interval)+'</span>');
  });
  var loc=sweepLocusHit(r.chrom, r.pos);
  if(loc && loc.kind==='fst_peak'){
    bits.push(bi('Inside an among-Grps Fst peak window','落在全体 Grp 的 Fst 峰窗口')+' <span class="muted">'+esc(loc.slug)+
      (loc.start?' '+esc(String(loc.start)+'-'+String(loc.end)):'')+'</span>');
  }else if(loc && loc.kind==='s29' && !s29.length){
    bits.push(bi('Inside a wider published S29 interval','落在更宽的已发表 S29 区间')+' <span class="muted">'+esc(loc.slug)+'</span>');
  }
  if(!bits.length) bits.push(bi('Genome-wide Grp-vs-rest sweep outside the five named MAS/GWAS windows.',
    '全基因组 Grp vs rest sweep，位于五个命名 MAS/GWAS 窗口之外。'));
  return bits.join('<br>');
}
function fillSelSweepTable(){
  var el=document.getElementById('sel-sweep-table');
  if(!el) return;
  var M=D.selection_manhattan||{};
  var grp=selManhGrp||'';
  var thr=(M.sweep_thr||{})[grp]||{};
  var rows=(M.sweeps||{})[grp]||[];
  if(!grp || grp==='overall'){
    el.innerHTML='<p class="muted">'+bi(
      'Pick a Grp to compute sweep rows. Sweep is simplified Fst (that Grp vs rest) ≥ 95th ∩ within-Grp windowed heterozygosity ≤ 5th. The Fst among all Grps view supplies panel context.',
      '请选择一个 Grp 计算 sweep 行。Sweep = 简化 Fst（该组对其余样品）最高 5% 且组内窗口杂合度最低 5%。全体 Grp 的 Fst 视图提供面板背景。')+'</p>';
    return;
  }
  var n=thr.n!=null?esc(String(thr.n)):'—';
  var focus=selManhFocus||null;
  var h='<div class="info-box" id="sel-sweep-status">';
  if(focus&&focus.chrom&&isFinite(Number(focus.pos))){
    h+='<strong>'+bi('Pinned on the Manhattan above.','已钉在上方 Manhattan 图上。')+'</strong> ';
    h+=bi('White star = '+esc(String(focus.chrom)+':'+String(focus.pos))+
      '. Same 167K site as this row. Red dots stay the sweep set. This action keeps the focus on the exact Manhattan site.',
      '白星 = '+esc(String(focus.chrom)+':'+String(focus.pos))+
      '。就是这一行的 167K 位点。红点仍是 sweep 集合。该操作保持对精确 Manhattan 位点的聚焦。');
  }else{
    h+=bi('Click <em>Show on plot</em> to pin a white star on the Manhattan above and scroll to it. The coordinate is the site; the button is the action.',
      '点「在图上标出」会在上方 Manhattan 钉一颗白星并滚到该图。坐标是位点，按钮是动作。');
  }
  h+='</div>';
  h+='<p class="muted" style="font-size:11px;margin:0 0 8px">'+esc(grp)+' '+
    bi('sweep sites on 167K','个 167K sweep 位点')+': n='+n+
    (thr.fst95!=null?' · Fst ≥ '+Number(thr.fst95).toFixed(3):'')+
    (thr.het05!=null?' · '+t('windowed heterozygosity ≤ ','窗口杂合度 ≤ ')+Number(thr.het05).toFixed(3):'')+
    '. '+bi(
      'Table = top '+rows.length+' by simplified Fst (Grp vs rest). Red dots on the Manhattan. Sweep rows highlight the exact Manhattan site. This is an unphased 167K screen.',
      '表格按简化 Fst（Grp 对其余样品）列出前 '+rows.length+' 行。Manhattan 红点是 sweep。sweep 行对应精确 Manhattan 位点。这是未定相 167K 筛选。')+'</p>';
  h+='<div class="table-scroll"><table><caption>'+bi(
    'Sweep sites for the active Grp','当前 Grp 的 sweep 位点')+
    '</caption><thead><tr><th scope="col">'+bi('Site','位点')+
    '</th><th scope="col">'+bi('Action','操作')+'</th><th scope="col">'+bi(
      'simplified Fst (Grp vs rest)','简化 Fst（Grp 对其余样品）')+'</th>'+
    '<th scope="col">'+bi('windowed heterozygosity in ','组内窗口杂合度：')+esc(grp)+'</th>'+
    '<th scope="col">'+bi('Gene / links','基因 / 外链')+'</th>'+
    '<th scope="col">'+bi('Context','背景')+'</th></tr></thead><tbody>';
  if(!rows.length) h+='<tr><td colspan="6">'+bi(
    'No sweep sites for this Grp','该组没有 sweep 位点')+'</td></tr>';
  rows.forEach(function(r){
    var site=String(r.chrom||'')+':'+String(r.pos||'');
    var active=focus&&String(focus.chrom)===String(r.chrom)&&Number(focus.pos)===Number(r.pos);
    var loc=sweepLocusHit(r.chrom, r.pos);
    var gene=loc&&loc.gene?loc.gene:'';
    var cat=lookupCatalogBySite(site);
    if(cat&&cat.gene) gene=gene||cat.gene;
    var annot=(cat&&(cat.gene===gene||cat.alias===gene)?cat:null)||(loc&&loc.geneRec)||null;
    var geneCell=sweepGeneHtml(gene, annot);
    if(loc&&loc.region) geneCell+='<span class="ev-sub">'+esc(loc.region)+'</span>';
    var genome=sweepGenomeHtml(r.chrom, r.pos);
    var actionEn='Pin '+site+' as a white star on the Manhattan plot';
    var actionZh='将 '+site+' 钉在 Manhattan 图上显示为白星';
    h+='<tr'+(active?' class="is-sweep-focus"':'')+'><td><code>'+esc(site)+'</code>'+(genome?'<span class="ev-sub">'+genome+'</span>':'')+'</td><td><button type="button" class="sel-sweep-focus" data-sw-focus="1" data-sw-chr="'+esc(r.chrom||'')+'" data-sw-pos="'+esc(String(r.pos||''))+'" aria-pressed="'+(active?'true':'false')+'" aria-label="'+esc(t(actionEn,actionZh))+'" title="'+esc(t(actionEn,actionZh))+'">'+
      bi('Show on plot','在图上标出')+'</button></td><td>'+esc(fmtNum(r.fst,3))+'</td><td>'+esc(fmtNum(r.het,3))+
      '</td><td>'+geneCell+'</td><td>'+sweepContextHtml(r)+'</td></tr>';
  });
  h+='</tbody></table></div>';
  el.innerHTML=h;
  el.querySelectorAll('button[data-sw-focus]').forEach(function(button){
    // bindSweepSiteButton owns button.addEventListener('click') and routes to
    // focusSelManhattan(...) for both pointer and explicit keyboard activation.
    bindSweepSiteButton(button);
  });
}
function fillSelScienceRef(){
  var el=document.getElementById('sel-s29-ref');
  if(!el) return;
  var S=D.selection_s29_scatter||{};
  var names=S.name||[];
  var sum={};
  (D.selection_vs_summary||[]).forEach(function(r){
    if(r && r.key) sum[r.key]=r.value;
  });
  var h='';
  if(names.length || sum.n_s29_bins!=null){
    h+='<p class="muted" style="font-size:11px;margin:0 0 8px">'+bi(
      'Published intervals described above are summarized here.',
      '上文所述的发表区间在此汇总。')+'</p>';
  }
  if(sum.n_s29_bins!=null){
    var chipWith=esc(String(sum.n_s29_with_chip||'—'));
    var chipBins=esc(String(sum.n_s29_bins));
    var chipEmpty=sum.n_s29_zero_chip!=null?
      ' ('+esc(String(sum.n_s29_zero_chip))+' empty)':'';
    var fstIn=esc(String(sum.n_fst_top_in_s29||'—'));
    var fstTop=esc(String(sum.n_fst_top||'—'));
    var summaryEn='Chip coverage of those published bins: '+chipWith+' / '+chipBins+
      ' intervals have ≥1 167K SNP'+chipEmpty+
      '. Our genome-wide Fst tops inside a published bin: '+fstIn+' / '+fstTop+
      '. Named-window column = overlap with our five MAS/GWAS windows; it reports interval context.';
    var summaryZh='这些已发表区间的芯片覆盖：'+chipWith+' / '+chipBins+
      ' 个区间至少有 1 个 167K SNP'+
      (sum.n_s29_zero_chip!=null?'（'+esc(String(sum.n_s29_zero_chip))+' 个为空）':'')+
      '。已发表区间内的全基因组 Fst 峰：'+fstIn+' / '+fstTop+
      '。命名窗口列表示与我们的五个 MAS/GWAS 窗口重合，用于报告区间背景。';
    h+='<p class="muted" style="font-size:11px;margin:0 0 8px">'+bi(
      summaryEn,summaryZh)+'</p>';
  }
  h+='<div class="table-scroll"><table><caption>'+bi(
    'Dong 2023 Table S29 overlap check','Dong 2023 表 S29 重合核对')+
    '</caption><thead><tr><th scope="col">'+bi('Published bin','已发表区间')+
    '</th><th scope="col">'+bi('Interval','区间')+'</th><th scope="col">'+bi(
      'n chip SNPs','芯片 SNP 数')+'</th><th scope="col">'+bi('mean het','平均杂合')+
    '</th><th scope="col">'+bi('mean Fst','平均 Fst')+'</th><th scope="col">'+bi(
      'overlaps our named window','与命名窗口重合')+'</th></tr></thead><tbody>';
  if(!names.length){
    h+='<tr><td colspan=6>'+bi('No 167K SNPs inside the published bins','这些已发表区间里没有芯片位点')+'</td></tr>';
  }
  names.forEach(function(nm,i){
    var lab=S.label&&S.label[i]?S.label[i]:nm;
    var chr=S.chrom&&S.chrom[i]?S.chrom[i]:'';
    var st=S.start&&S.start[i]!=null?S.start[i]:'';
    var en=S.end&&S.end[i]!=null?S.end[i]:'';
    h+='<tr class="clickrow" data-s29-slug="'+esc(String(nm))+'" data-s29-chr="'+esc(String(chr))+'" data-s29-pos="'+esc(String(st))+'"><td>'+
      esc(lab)+'</td><td>'+esc(String(chr)+':'+String(st)+'-'+String(en))+
      '</td><td>'+esc(String((S.n_sites&&S.n_sites[i])||''))+
      '</td><td>'+esc(S.het&&S.het[i]!=null?String(S.het[i]):'—')+
      '</td><td>'+esc(S.fst&&S.fst[i]!=null?String(S.fst[i]):'—')+
      '</td><td>'+esc((S.overlap&&S.overlap[i])||'')+'</td></tr>';
  });
  h+='</tbody></table></div>';
  el.innerHTML=h;
  el.querySelectorAll('[data-s29-slug]').forEach(function(row){
    row.addEventListener('click', function(){
      if(!setSelLzBySlug(row.getAttribute('data-s29-slug')||'')) return;
      var lz=document.getElementById('sel-lz');
      if(lz) lz.scrollIntoView({behavior:motionBehavior(), block:'start'});
    });
  });
}
function drawSelManhattan(){
  var el=document.getElementById('plot-sel-manh');
  if(!el) return;
  if(!plotlyCan('newPlot')){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'Plotly.js unavailable; Manhattan plot unavailable.',
      'Plotly.js 不可用；Manhattan 图不可用。')+'</p>';
    fillSelSweepTable();
    return;
  }
  var M=D.selection_manhattan||{};
  var xs=M.x||[], chrom=M.chrom||[], pos=M.pos||[];
  var metric=selManhMetric||'fst';
  var grp=selManhGrp||'overall';
  var byg=M.fst_by_grp||{};
  var hyg=M.het_by_grp||{};
  var sw=(grp!=='overall')?((M.sweep_by_grp||{})[grp]||null):null;
  var thr=(M.sweep_thr||{})[grp]||{};
  var ys, ylab, tlab;
  if(metric==='het'){
    if(grp!=='overall' && hyg[grp]){
      ys=hyg[grp];
      ylab=t('windowed heterozygosity in '+esc(grp)+' ±50 kb','组内窗口杂合度（'+esc(grp)+' ±50 kb）');
    } else {
      ys=M.het||[];
      ylab=t('windowed heterozygosity ±50 kb','窗口杂合度 ±50 kb');
    }
    tlab=t('167K unphased windowed heterozygosity · green = named windows · red = sweep',
      '167K 未定相窗口杂合度 · 绿 = 命名窗口 · 红 = sweep');
  } else if(grp!=='overall' && byg[grp]){
    ys=byg[grp];
    ylab=t('simplified Fst ('+esc(grp)+' vs rest)','简化 Fst（'+esc(grp)+' 对其余样品）');
    tlab=t('Screening: simplified Fst '+esc(grp)+' vs rest · red = sweep (Fst ≥95th ∩ windowed heterozygosity ≤5th)',
      '筛选：简化 Fst '+esc(grp)+' 对其余样品 · 红 = sweep（Fst ≥95% 且窗口杂合度 ≤5%）');
  } else {
    ys=M.fst||[];
    ylab=t('Fst among all Grps','全体 Grp 的 Fst');
    tlab=t('Among-all-Grps Fst provides panel context. Pick a Grp to view the sweep contrast.',
      '全体 Grp 的 Fst 提供面板背景。请选择一个 Grp 查看 sweep 对照。');
  }
  if(grp!=='overall' && thr.n!=null) tlab+=' · n_sweep='+thr.n;
  if(!xs.length){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'No Manhattan pack. Run grapeancestry selection.',
      '没有 Manhattan 数据包。请运行 grapeancestry selection。')+'</p>';
    fillSelSweepTable();
    return;
  }
  var by={}, swX=[], swY=[], swCd=[];
  xs.forEach(function(x,i){
    var c=chrom[i]||'?';
    if(sw && sw[i]){
      swX.push(x); swY.push(ys[i]); swCd.push([c, pos[i]]);
      return;
    }
    if(!by[c]) by[c]={x:[], y:[], cd:[]};
    by[c].x.push(x);
    by[c].y.push(ys[i]);
    by[c].cd.push([c, pos[i]]);
  });
  var pal=['#60a5fa','#fbbf24'];
  var traces=[], k=0;
  Object.keys(by).sort(function(a,b){return (parseInt(a,10)||999)-(parseInt(b,10)||999);}).forEach(function(c){
    traces.push({
      type:'scattergl', mode:'markers', name:t('chr'+esc(c),'染色体'+esc(c)),
      x:by[c].x, y:by[c].y, customdata:by[c].cd,
      marker:{size:4, color:pal[k%2], opacity:0.55},
      hovertemplate:t('chr%{customdata[0]}:%{customdata[1]} · '+ylab+'=%{y:.3f}<extra></extra>',
        '染色体%{customdata[0]}:%{customdata[1]} · '+ylab+'=%{y:.3f}<extra></extra>')
    });
    k+=1;
  });
  if(swX.length){
    traces.push({
      type:'scattergl', mode:'markers', name:t('sweep','sweep'),
      x:swX, y:swY, customdata:swCd,
      marker:{size:7, color:'#e94560', opacity:0.9},
      hovertemplate:t('sweep chr%{customdata[0]}:%{customdata[1]} · '+ylab+'=%{y:.3f}<extra></extra>',
        'sweep 染色体%{customdata[0]}:%{customdata[1]} · '+ylab+'=%{y:.3f}<extra></extra>')
    });
  }
  var focusI=selManhFocus?
    findSelPoint(chrom, pos, selManhFocus.chrom, selManhFocus.pos):-1;
  if(focusI>=0 && xs[focusI]!=null && ys[focusI]!=null &&
     isFinite(Number(xs[focusI])) && isFinite(Number(ys[focusI]))){
    traces.push({
      type:'scatter', mode:'markers', name:'selected site',
      x:[xs[focusI]], y:[ys[focusI]],
      customdata:[[chrom[focusI], pos[focusI], ylab]],
      marker:{size:13, symbol:'star', color:'#fff', line:{color:'#000', width:2}},
      hovertemplate:t('selected site chr%{customdata[0]}:%{customdata[1]} · %{customdata[2]}=%{y:.3f}<extra></extra>',
        '已选位点 染色体%{customdata[0]}:%{customdata[1]} · %{customdata[2]}=%{y:.3f}<extra></extra>')
    });
    traces[traces.length-1].name=t('selected site','已选位点');
  }
  var shapes=[];
  (M.windows||[]).forEach(function(w){
    if(w.kind!=='named') return;
    shapes.push({type:'rect', xref:'x', yref:'paper', x0:w.x0, x1:w.x1, y0:0, y1:1,
      fillcolor:'rgba(74,222,128,0.12)', line:{width:0}});
  });
  Plotly.newPlot(el, traces, withPlotSize({
    margin:{t:24, r:16, b:40, l:48},
    font:{color:themeTokens().text, size:11},
    yaxis:{title:ylab, gridcolor:themeTokens()['plot-grid']},
    xaxis:{title:t('genome (concatenated chr)','基因组（拼接染色体）'), tickvals:(M.ticks||[]).map(function(t){return t.x;}),
      ticktext:(M.ticks||[]).map(function(t){return t.chrom;})},
    shapes:shapes, showlegend:false,
    title:{text:tlab, font:{size:12}}
  }, el, 380), plotlyCfg({scrollZoom:true}));
  el.on('plotly_click', function(ev){
    var p=ev&&ev.points&&ev.points[0];
    if(!p||!p.customdata) return;
    focusSelManhattan(p.customdata[0], p.customdata[1]);
  });
  fillSelSweepTable();
}
function drawSelHeat(){
  var el=document.getElementById('plot-sel-heat');
  if(!el) return;
  if(!plotlyCan('newPlot')){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'Plotly.js unavailable; selection heatmap unavailable.',
      'Plotly.js 不可用；选择热图不可用。')+'</p>';
    return;
  }
  var H=D.selection_heatmap||{};
  var metric=selHeatMetric||'fst';
  var z=(metric==='fst')?(H.fst||[]):(H.het||[]);
  if(!z.length){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'No by-Grp named-window scores.',
      '没有按 Grp 划分的命名窗口统计量。')+'</p>';
    return;
  }
  var xlab=H.window_lab||H.window||[];
  var nSites=H.n_sites||[];
  var chrom=H.chrom||[], st=H.start||[], en=H.end||[];
  var text=z.map(function(row){
    return (row||[]).map(function(v){ return (v==null||v!==v)?'':Number(v).toFixed(3); });
  });
  var custom=[];
  (H.grp||[]).forEach(function(_,ri){
    custom[ri]=xlab.map(function(__,ci){
      return [
        (H.window||[])[ci]||'',
        chrom[ci]||'',
        st[ci]||'',
        en[ci]||'',
        nSites[ci]!=null?nSites[ci]:''
      ];
    });
  });
  var isFst=metric==='fst';
  var zmax=0;
  z.forEach(function(row){ (row||[]).forEach(function(v){ if(v!=null && v===v && v>zmax) zmax=v; }); });
  Plotly.newPlot(el, [{
    type:'heatmap', z:z, x:xlab, y:H.grp, text:text, customdata:custom,
    texttemplate:'%{text}', textfont:{size:10},
    colorscale:isFst?'YlOrRd':'YlGnBu', reversescale:!isFst,
    zmin:0, zmax:isFst?(zmax||0.05):undefined,
    colorbar:{title:isFst?t('mean simplified Fst (Grp vs rest)','平均简化 Fst（Grp 对其余样品）'):
      t('mean windowed heterozygosity in Grp','组内平均窗口杂合度')},
    hovertemplate:t('%{y} at %{customdata[0]}<br>%{customdata[1]}:%{customdata[2]}-%{customdata[3]}<br>n SNPs=%{customdata[4]}<br>',
      '%{y} · %{customdata[0]}<br>%{customdata[1]}:%{customdata[2]}-%{customdata[3]}<br>SNP 数=%{customdata[4]}<br>')+
      t(isFst?'simplified Fst (Grp vs rest)':'windowed heterozygosity',isFst?'简化 Fst（Grp 对其余样品）':'窗口杂合度')+'=%{z:.3f}<extra></extra>'
  }], withPlotSize({
    margin:{t:36, r:72, b:72, l:70},
    font:{color:themeTokens().text, size:11},
    xaxis:{tickfont:{size:10}, tickangle:0},
    title:{text:t(isFst
      ? 'Each cell = mean simplified Fst (Grp vs rest), SNPs inside that locus only'
      : 'Each cell = mean heterozygosity inside that Grp, SNPs inside that locus only',
      isFst
      ? '每格 = 平均简化 Fst（Grp 对其余样品），仅使用该位点内 SNP'
      : '每格 = 该 Grp 内的平均杂合，仅使用该位点内 SNP'),
      font:{size:12}}
  }, el, 460), plotlyCfg());
  el.on('plotly_click', function(ev){
    var p=ev&&ev.points&&ev.points[0];
    if(!p||!p.customdata) return;
    setSelLzBySlug(String(p.customdata[0]||''));
    var lz=document.getElementById('sel-lz');
    if(lz) lz.scrollIntoView({behavior:motionBehavior(), block:'start'});
  });
}
function drawSelScatter(){
  var el=document.getElementById('plot-sel-scatter');
  if(!el) return;
  if(!plotlyCan('newPlot')){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'Plotly.js unavailable; selection scatter unavailable.',
      'Plotly.js 不可用；选择散点图不可用。')+'</p>';
    return;
  }
  var S=D.selection_fst_het_scatter||{};
  var xs=S.het||[], ys=S.fst||[], chrom=S.chrom||[], pos=S.pos||[];
  if(!xs.length){
    el.innerHTML='<p class="muted" style="padding:12px">'+bi(
      'No Fst vs het scatter. Run grapeancestry selection.',
      '没有 Fst 与杂合散点图。请运行 grapeancestry selection。')+'</p>';
    return;
  }
  var traces=[{
    type:'scattergl', mode:'markers', name:t(
      'genome (shared deterministic stride-30 subsample)',
      '基因组（共用确定性 stride-30 子样本）'),
    x:xs, y:ys,
    customdata:xs.map(function(_,i){ return [chrom[i], pos[i]]; }),
    marker:{size:3, color:'#64748b', opacity:0.25},
    hovertemplate:t(
      'chr%{customdata[0]}:%{customdata[1]}<br>het=%{x:.3f} · Fst=%{y:.3f}<extra>subsample</extra>',
      '染色体%{customdata[0]}:%{customdata[1]}<br>het=%{x:.3f} · Fst=%{y:.3f}<extra>子样本</extra>')
  }];
  var nm=S.named_means||[];
  if(nm.length){
    traces.push({
      type:'scatter', mode:'markers+text', name:t(
        'window mean (= table)','窗口均值（=表格）'),
      x:nm.map(function(r){return r.het;}),
      y:nm.map(function(r){return r.fst;}),
      text:nm.map(function(r){return r.label||r.name;}),
      textposition:'top right',
      textfont:{size:11, color:'#4ade80'},
      customdata:nm.map(function(r){return [r.chrom, r.pos, r.name, r.n];}),
      marker:{size:14, symbol:'star', color:'#4ade80', line:{width:1, color:'#0b0f19'}},
      hovertemplate:t(
        '%{customdata[2]} (n=%{customdata[3]})<br>mean het=%{x:.3f} · mean Fst=%{y:.3f}<extra>same as table</extra>',
        '%{customdata[2]}（n=%{customdata[3]}）<br>平均 het=%{x:.3f} · 平均 Fst=%{y:.3f}<extra>与表格相同</extra>')
    });
  }
  Plotly.newPlot(el, traces, withPlotSize({
    margin:{t:36, r:16, b:48, l:52},
    font:{color:themeTokens().text, size:11},
    xaxis:{title:t('heterozygosity (per site, 2449 panel)','杂合度（每位点，2449 面板）')},
    yaxis:{title:t('Fst among all Grps','全体 Grp 的 Fst')},
    title:{text:t(
      'Grey = shared deterministic stride-30 subsample · green star = mean of that window (same numbers as the table)',
      '灰 = 共用确定性 stride-30 子样本 · 绿星 = 该窗口均值（与表格相同）'), font:{size:12}},
    legend:{orientation:'h', y:1.12}
  }, el, 380), plotlyCfg());
  el.on('plotly_click', function(ev){
    var p=ev&&ev.points&&ev.points[0];
    if(!p||!p.customdata) return;
    if(p.customdata[2]){
      setSelLzBySlug(String(p.customdata[2]));
      var lz=document.getElementById('sel-lz');
      if(lz) lz.scrollIntoView({behavior:motionBehavior(), block:'start'});
    }else{
      focusSelManhattan(p.customdata[0], p.customdata[1]);
    }
  });
}

function boot(payload){
  D=payload; SROWS=D.srows||[]; SIDX=D.sidx||{}; QUERY=D.query||'';
  initThemeController();
  initLangController();
  bindPanelResearchToggle();
  initResponsiveShell();
  treeShape='circular';
  TREE_TIPS=D.tree_tips||{};
  document.getElementById('sample-slider').max=Math.max(0,SROWS.length-1);
  document.getElementById('stat-n').textContent=D.n_panel||'—';
  var sm=D.ibs_summary||{};
  document.getElementById('stat-id').textContent=sm['Identical']||0;
  document.getElementById('stat-po').textContent=sm['Parent-Offspring']||0;
  fillHeroStats();
  fillReportMeta();
  fillMethodCoverage();
  fillQueryEvidence();
  fillAuthorIntake();
  fillConclusions();
  fillCloneTable();
  fillIbsKinship();
  fillSelFstats();
  fillQc();
  fillExtra();
  fillQuerySnapshot();
  enhanceReportTables(document);
  pairLangBlocks(document);
  if(typeof window!=='undefined') window._gaLangReady=true;
  fillAdmixMethodNotes();
  var nPc=D.pca_n||2;
  document.querySelectorAll('.pca-axis-btn').forEach(function(b){
    var ax=b.getAttribute('data-axes')||'0,1';
    var need=Math.max.apply(null, ax.split(',').map(Number))+1;
    b.style.display=need<=nPc?'':'none';
  });
  loadPCA();
  loadPCA3d();
  loadBar(currentK);
  loadTree();
  loadDamage();
  updateBrowser();
  if(QUERY) highlightSample(QUERY);
  scheduleResponsiveResize();
}

function fmtNum(v, dig){
  if(v===null||v===undefined||v!==v) return '—';
  if(typeof v!=='number'){ var n=Number(v); if(isNaN(n)) return String(v); v=n; }
  if(!isFinite(v)) return '—';
  if(Math.abs(v)>=100) return v.toFixed(0);
  if(dig==null) dig=2;
  return v.toFixed(dig);
}

function pcaMethodLabel(s){
  s=String(s||'');
  if(!s) return '—';
  if(/gcta/i.test(s)) return t('GCTA64 PCA · 153,483 SNPs','GCTA64 PCA · 153,483 SNPs');
  if(/smartPCA|lsqproject/i.test(s)) return t('least-squares projection · 153,483 SNPs','最小二乘投影 · 153,483 SNPs');
  if(/5k/i.test(s)) return 'PCA · 5k SNPs';
  if(/167k/i.test(s)) return 'PCA · 167k SNPs';
  if(/numpy SVD/i.test(s)) return 'PCA (SVD)';
  return s;
}
function admixMethodsHtml(raw){
  var text=String(raw||'');
  if(!text) return bi('Loading…','加载中…');
  var key=text.toLowerCase();
  if(key.indexOf('13,950')>=0 || key.indexOf('153,483')>=0 || key.indexOf('167k capture')>=0){
    return bi(
      'ADMIXTURE K=2–8 is one unsupervised series on the 2449 reference using 167k capture sites minus GWAS/trait-locus overlap (13,950 dropped; 153,483 kept). No extra LD prune. Q is a clustering affinity, not a qpAdm proportion. Colours follow Dong et al. 2023 Fig. 1D (doi:10.1126/science.add8655); K→K+1 columns are greedy Pearson-matched (Alexander et al. 2009, https://doi.org/10.1101/gr.094052.109). In-panel samples look up this Q; new samples are projected with ADMIXTURE -P onto the frozen P matrix for every K in 2–8.',
      'ADMIXTURE K=2–8 是 2449 参考集上的一套无监督拟合，使用 167k 捕获位点并去掉 GWAS/性状位点重叠（去掉 13,950；保留 153,483）。不再额外 LD 修剪。Q 是聚类亲和度，不是 qpAdm 比例。颜色按 Dong 等 2023 图 1D（doi:10.1126/science.add8655）；相邻 K 的列用贪婪 Pearson 匹配（Alexander 等 2009，https://doi.org/10.1101/gr.094052.109）。面板内样本读取这套 Q；新样本用 ADMIXTURE -P 投影到每个 K=2–8 的冻结等位基因频率矩阵。');
  }
  return bi('Source method: '+esc(text),'来源方法：'+esc(text));
}
function fillAdmixMethodNotes(){
  var label=pcaMethodLabel((D||{}).pca_method);
  var mc=document.getElementById('method-card');
  if(mc) mc.textContent=label;
  if(document.querySelectorAll){
    Array.prototype.forEach.call(document.querySelectorAll('.method-card-slot'), function(el){
      el.textContent=label;
    });
    Array.prototype.forEach.call(document.querySelectorAll('.pca-method-note-slot'), function(el){
      el.textContent=((D||{}).pca_method)?(' · '+label):'';
    });
  }
  var pm=document.getElementById('pca-method-note');
  if(pm) pm.textContent=((D||{}).pca_method)?(' · '+label):'';
  var ap=document.getElementById('admix-provenance');
  if(ap){
    var article=((D||{}).admix_provenance||{}).article||{};
    var doi=article.doi;
    if(doi){
      ap.innerHTML=bi('Dong et al. 2023 DOI: '+esc(doi),'Dong 等 2023 DOI：'+esc(doi));
    }else if(((D||{}).admix_strip_family||(D||{}).admix_run_family)==='panel167k_nogwas'){
      ap.innerHTML=bi(
        'Names follow Dong et al. 2023 doi:10.1126/science.add8655 Fig. 1D. This is the 167k capture-panel ADMIXTURE series.',
        '命名沿用 Dong 等 2023 doi:10.1126/science.add8655 图 1D。这是 167k 捕获面板 ADMIXTURE 系列。');
    }else{
      ap.innerHTML=bi('Source DOI unavailable','来源 DOI 不可用');
    }
  }
  var am=document.getElementById('admix-methods');
  if(am){
    am.innerHTML='<strong>'+bi('ADMIXTURE','ADMIXTURE')+'</strong>: '+admixMethodsHtml((D||{}).admix_methods);
  }
}

function sanitizeReportHtml(s){
  s=String(s||'');
  function bilingualLabel(en, zh){
    return '<span class="en">'+en+'</span><span class="cn">'+zh+'</span>';
  }
  [
    ['results/gs/index.tsv','local GS summary','本地 GS 汇总'],
    ['results/provenance/gs_train.json','GS training provenance','GS 训练溯源'],
    ['results/gwas/euvitis/OIV_241_bin/summary.json','OIV 241 GWAS summary','OIV 241 GWAS 汇总']
  ].forEach(function(item){
    var esc=item[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    var label=bilingualLabel(item[1], item[2]);
    s=s.replace(new RegExp('<code>'+esc+'</code>','g'), label);
    s=s.replace(new RegExp('>'+esc+'<','g'), '>'+label+'<');
    s=s.replace(new RegExp('`'+esc+'`','g'), label);
  });
  s=s.replace(/<code>[^<]*2449\.info[^<]*<\/code>/g, bilingualLabel('the 2449 panel IDs','2449 面板 ID'));
  s=s.replace(/<code>[^<]*panel_dosage[^<]*<\/code>/g, bilingualLabel('the dosage matrix','剂量矩阵'));
  s=s.replace(/<code>[^<]*gwas_exclude[^<]*<\/code>/g, bilingualLabel('the GWAS/trait-locus exclude list','GWAS/性状位点排除表'));
  s=s.replace(/<code>results\/[^<]+<\/code>/g, bilingualLabel('the results tables','结果表'));
  s=s.replace(/<code>data\/panel\/[^<]+<\/code>/g, bilingualLabel('the panel metadata','面板元数据'));
  s=s.replace(/>results\/[^<]+</g, '>'+bilingualLabel('the results tables','结果表')+'<');
  s=s.replace(/>data\/panel\/[^<]+</g, '>'+bilingualLabel('the panel metadata','面板元数据')+'<');
  s=s.replace(/`results\/[^`]+`/g, bilingualLabel('the results tables','结果表'));
  s=s.replace(/`data\/panel\/[^`]+`/g, bilingualLabel('the panel metadata','面板元数据'));
  s=s.replace(/`[^`]*\.(tsv|info|npz|xlsx|json)[^`]*`/g, bilingualLabel('the source table','源表'));
  return s;
}

function formatPurityDisplay(raw){
  var s=String(raw||'');
  var het=(s.match(/het=([0-9.]+)/i)||[])[1];
  var mean=(s.match(/panel mean ([0-9.]+)/i)||s.match(/\bmean ([0-9.]+)/i)||[])[1];
  var sd=(s.match(/±\s*([0-9.]+)/)||[])[1];
  var z=(s.match(/\bz=([-\d.]+)/i)||[])[1];
  var depth=(s.match(/Low mean depth \(([0-9.]+)×\)/i)||[])[1];
  var zNum=z==null?NaN:Number(z);
  var screenEn='Heterozygosity screen, not a purity estimate.';
  var screenZh='杂合度筛查，不是纯度估计。';
  if(/insufficient calls/i.test(s)){
    return {
      en:screenEn+' Insufficient called genotypes to compare query heterozygosity with the reference-panel distribution.',
      zh:screenZh+'分型不足，无法将查询样本杂合度与参考面板分布比较。'
    };
  }
  var statsEn=[], statsZh=[];
  if(mean){
    statsEn.push('mean '+mean+(sd?(' ± '+sd):''));
    statsZh.push('均值 '+mean+(sd?(' ± '+sd):''));
  }
  if(z){ statsEn.push('z='+z); statsZh.push('z='+z); }
  var distEn=statsEn.length?(' ('+statsEn.join(', ')+')'):'';
  var distZh=statsZh.length?('（'+statsZh.join('，')+'）'):'';
  var hetEn=het?(' '+het):'';
  var hetZh=het?(' '+het):'';
  var bodyEn, bodyZh;
  if(/WARNING|excess/i.test(s) || (isFinite(zNum)&&zNum>3)){
    bodyEn='Query heterozygosity'+hetEn+' is above the reference-panel distribution'+distEn+'. This can indicate sample mixture or other sample-level factors.';
    bodyZh='查询样本杂合度'+hetZh+' 高于参考面板分布'+distZh+'。这可能提示样品混合或其他样品层面因素。';
  }else if(/low het/i.test(s) || (isFinite(zNum)&&zNum<-3)){
    bodyEn='Query heterozygosity'+hetEn+' is below the reference-panel distribution'+distEn+'.';
    bodyZh='查询样本杂合度'+hetZh+' 低于参考面板分布'+distZh+'。';
  }else{
    bodyEn='Query heterozygosity'+hetEn+' is within the reference-panel distribution'+distEn+'.';
    bodyZh='查询样本杂合度'+hetZh+' 处于参考面板分布内'+distZh+'。';
  }
  if(depth){
    bodyEn+=' Low mean depth ('+depth+'×) can under-call heterozygotes.';
    bodyZh+='低平均深度（'+depth+'×）可能低估杂合。';
  }
  return {en:screenEn+' '+bodyEn, zh:screenZh+bodyZh};
}
function sanitizeConclusionEnglish(c){
  c=String(c||'');
  if(/^Analysis matrix:/i.test(c)) return '';
  if(/chip-P/i.test(c)) return '';
  if(/not Science-coloured/i.test(c)) return '';
  c=c.replace(/smartPCA lsqproject · 153,483 SNPs/g, pcaMethodLabel('smartPCA'));
  c=c.replace(/PCA \((.*)\)(?=:)/, function(_, inner){ return pcaMethodLabel(inner); });
  c=c.replace(/ADMIXTURE K=8 \([^)]*\) on 2449; Grp=NA; /g, 'ADMIXTURE K=8 on 2449; ');
  c=c.replace(/ADMIXTURE K=8 \([^)]*\) on 2449; /g, 'ADMIXTURE K=8 on 2449; ');
  c=c.replace(/is an out-of-panel query, not (a|the) 2449 lookup row\./g,
    'is not in the 2449 reference panel.');
  c=c.replace(/Panel bars are the 2449 ADMIXTURE Q; the query is projected with admixture -P onto that P\./g,
    'The ADMIXTURE bars are the 2449 Q; this sample is projected onto that model.');
  c=c.replace(/K=2–8 strips use Science Q\/colours \(Dong et al\. 2023 doi:10\.1126\/science\.add8655 Fig\. 1D\)\. /g, '');
  return c.replace(/\s+/g,' ').trim();
}
function cleanConclusionPair(c){
  var raw=String(c||'');
  if(/^Purity\b/i.test(raw)) return formatPurityDisplay(raw);
  var en=sanitizeConclusionEnglish(raw);
  if(!en) return null;
  var m, zh;
  m=en.match(/^(\S+) is not in the 2449 reference panel\. The ADMIXTURE bars are the 2449 Q; this sample is projected onto that model\.$/);
  if(m){
    return {
      en:en,
      zh:m[1]+' 不在 2449 参考面板中。ADMIXTURE 柱是 2449 的 Q；本样品投影到该模型。'
    };
  }
  m=en.match(/^QC: on-target (.+)% ; fold-enrichment (.+) ; covered≥1× (.+) \((.+)%\); mean depth (.+)× ; panel calling rate (.+)% \(called\/167k panel; primary\); VCF-site calling rate (.+)% \((.+) called \/ VCF sites; secondary\); variants (.+)\.$/);
  if(m){
    return {
      en:en,
      zh:'质控：目标区 '+m[1]+'% ；富集倍数 '+m[2]+' ；覆盖≥1× '+m[3]+'（'+m[4]+'%）；平均深度 '+m[5]+'× ；面板分型率 '+m[6]+'%（已分型/167k 面板；主指标）；VCF 位点分型率 '+m[7]+'%（'+m[8]+' 个已分型 / VCF 位点；次指标）；变异位点数 '+m[9]+'。'
    };
  }
  m=en.match(/^Query genotype coverage: (.+) panel sites called \((.+)\); missing sites remain missing\.$/);
  if(m){
    return {
      en:en,
      zh:'查询基因型覆盖：'+m[1]+' 个面板位点已分型（'+m[2]+'）；缺失位点保持缺失。'
    };
  }
  m=en.match(/^Query evidence: (.+) listed sites have a called genotype; missing calls are shown explicitly\.$/);
  if(m){
    return {
      en:en,
      zh:'查询证据：所列位点中 '+m[1]+' 已分型；缺失分型会明确标出。'
    };
  }
  if(/^Identity \(4K\):/.test(en)){
    zh=en.replace('Identity (4K):','身份（4K）：')
      .replace('nearest non-self','最近非自身')
      .replace('self-in-panel','面板内自身')
      .replace('no comparable panel pairs','没有可比较的面板配对')
      .replace('clone-screen','克隆筛查')
      .replace(/Parent-Offspring/g,'亲子')
      .replace(/Full Sib/g,'全同胞')
      .replace(/Identical/g,'完全相同')
      .replace(/Unrelated/g,'无关')
      .replace(/\bPO\b/g,'亲子')
      .replace(/\b2nd\b/g,'二级亲缘')
      .replace(/\b3rd\b/g,'三级亲缘');
    return {en:en, zh:zh};
  }
  m=en.match(/^Identity: nearest → (.+)$/);
  if(m){
    return {en:en, zh:'身份：最近 → '+m[1]};
  }
  m=en.match(/^(.+): (PC1=.+)$/);
  if(m && /PCA|GCTA|least-squares|SNPs/i.test(m[1])){
    return {en:en, zh:m[1]+'：'+m[2].replace(/color=/,'着色=')};
  }
  m=en.match(/^ADMIXTURE K=8 on 2449; dominant ([^.]+?)(?:\. Grp=([^.]+))?\.$/);
  if(m){
    zh='ADMIXTURE K=8（2449）；主成分为 '+m[1]+'。';
    if(m[2]) zh=zh.slice(0,-1)+' Grp='+m[2]+'。';
    return {en:en, zh:zh};
  }
  m=en.match(/^NJ tree: (\d+) tips \((all panel(?: \+ query)?); IBS genotype identity; no Grp subsample\)\.$/);
  if(m){
    zh='NJ 树：'+m[1]+' 个叶（'+(m[2].indexOf('query')>=0?'全部面板 + 查询样本':'全部面板')+'；IBS 基因型同一度；无 Grp 子抽样）。';
    return {en:en, zh:zh};
  }
  if(/^Modern sample \/ modern PE library/i.test(en)||
     /^Modern PE source library/i.test(en)){
    return modernPeConclusionPair();
  }
  m=en.match(/^Damage: 5′ C→T pos1=([0-9.]+); 3′ G→A pos1=([0-9.]+)\.$/);
  if(m){
    return {en:en, zh:'损伤：5′ C→T 第1位='+m[1]+'；3′ G→A 第1位='+m[2]+'。'};
  }
  m=en.match(/^Damage 5′ C→T pos1=([0-9.]+)\.$/);
  if(m){
    return {en:en, zh:'损伤：5′ C→T 第1位='+m[1]+'。'};
  }
  m=en.match(/^Query GS predictions: (\d+) per-query row\(s\); (.+)$/);
  if(m){
    return {en:en, zh:'查询 GS 预测：'+m[1]+' 条逐查询行；'+m[2]};
  }
  if(en==='A merged VCF of the 2449 panel plus this query is in Downloads.'){
    return {en:en, zh:'2449 面板与本查询的合并 VCF 在下载区。'};
  }
  return {en:en, zh:en};
}
function modernPeConclusionPair(){
  return {
    en:'Modern PE source library; the ancient-DNA damage module is not applicable, so no damage plot is displayed.',
    zh:'现代 PE 来源文库；古 DNA 损伤模块不适用，因此不显示损伤图。'
  };
}
function cleanConclusion(c){
  var pair=cleanConclusionPair(c);
  return pair?pair.en:'';
}

function applyQueryIdCard(){
  var qEl=document.getElementById('stat-q');
  var qLbl=document.getElementById('stat-q-lbl');
  var id=QUERY||((D||{}).query)||'';
  if(qEl){
    qEl.textContent=id||'—';
    var overflow=Number(qEl.scrollWidth)>Number(qEl.clientWidth);
    if(overflow && id){
      if(qEl.setAttribute) qEl.setAttribute('title', id);
      else qEl.title=id;
    }
  }
  if(qLbl) qLbl.innerHTML=bi('Query','查询');
}
function fillHeroStats(){
  var qc=D.qc||{}, qm=D.query_meta||{};
  var el;
  applyQueryIdCard();
  el=document.getElementById('stat-depth'); if(el) el.textContent=fmtNum(qc.mean_depth,2)+'×';
  el=document.getElementById('stat-pcr'); if(el) el.textContent=fmtNum(qc.calling_rate_panel_pct,1)+'%';
  el=document.getElementById('stat-dom'); if(el) el.textContent=qm.q8_dom||'—';
  el=document.getElementById('stat-pc');
  if(el){
    var pcs=[qm.pc1,qm.pc2,qm.pc3].map(function(v){return v==null?'—':fmtNum(v,3);});
    el.textContent='PC1 '+pcs[0]+' · PC2 '+pcs[1]+' · PC3 '+pcs[2];
  }
  el=document.getElementById('stat-pca-method'); if(el) el.textContent=pcaMethodLabel(D.pca_method);
  el=document.getElementById('pca-method-note');
  if(el) el.textContent=D.pca_method?(' · '+pcaMethodLabel(D.pca_method)):'';
  el=document.getElementById('method-card');
  if(el) el.textContent=pcaMethodLabel(D.pca_method);
}

var AUTHOR_SAMPLE_FIELDS=[
  {k:'iid', lab:['Sample ID','样本编号'], ph:['e.g. Ages','例如 Ages']},
  {k:'name', lab:['Variety / accession','品种或编号'], ph:''},
  {k:'origin', lab:['Origin / site','来源或遗址'], ph:''},
  {k:'date', lab:['Date / period','年代'], ph:''},
  {k:'material', lab:['Material','材料'], ph:['seed, wood, leaf…','种子、木材、叶片…']},
  {k:'contact', lab:['Contact / lab','联系人'], ph:''}
];
var AUTHOR_ROW_FIELDS=[
  {k:'iid', lab:['Sample ID','样本编号'], ph:['ID','编号']},
  {k:'name', lab:['Variety / accession','品种或编号'], ph:''},
  {k:'origin', lab:['Origin / site','来源或遗址'], ph:''},
  {k:'date', lab:['Date / period','年代'], ph:''},
  {k:'notes', lab:['Notes','备注'], ph:''}
];
function authorFieldLab(f){
  return Array.isArray(f.lab)?bi(esc(f.lab[0]),esc(f.lab[1])):esc(f.lab);
}
function authorFieldPh(f){
  if(Array.isArray(f.ph)) return esc(t(f.ph[0], f.ph[1]));
  return esc(f.ph||'');
}

function authorStoreKey(){ return 'ga-author:'+(QUERY||'report'); }
function blankAuthorRow(){ return {iid:'', name:'', origin:'', date:'', notes:''}; }
function defaultAuthorState(){
  var rows=D.author_samples||D.cohort_samples||[];
  var mode=D.author_mode||((rows.length>1)?'population':'sample');
  var sample={iid:QUERY||'', name:'', origin:'', date:'', material:'', contact:'', notes:''};
  var qm=D.query_meta||{};
  if(qm.name) sample.name=qm.name;
  if(qm.origin) sample.origin=qm.origin;
  var table=rows.length? rows.map(function(r){
    return {
      iid:r.iid||r.id||'', name:r.name||r.acc||'', origin:r.origin||'',
      date:r.date||'', notes:r.notes||''
    };
  }) : [Object.assign(blankAuthorRow(), {iid:QUERY||''}), blankAuthorRow(), blankAuthorRow()];
  return {mode:mode, sample:sample, rows:table};
}
function loadAuthorState(){
  var st=defaultAuthorState();
  try{
    var raw=localStorage.getItem(authorStoreKey());
    if(raw){
      var saved=JSON.parse(raw);
      if(saved && typeof saved==='object'){
        if(saved.mode==='sample'||saved.mode==='population') st.mode=saved.mode;
        if(saved.sample) st.sample=Object.assign(st.sample, saved.sample);
        if(Array.isArray(saved.rows) && saved.rows.length) st.rows=saved.rows;
      }
    }
  }catch(e){}
  if(!st.sample.iid) st.sample.iid=QUERY||'';
  return st;
}
function saveAuthorState(st){
  try{ localStorage.setItem(authorStoreKey(), JSON.stringify(st)); }catch(e){}
}
function authorNorm(s){ return String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim(); }
function authorHay(r){
  return authorNorm([r.iid,r.acc,r.acc_local,r.origin,r.con,r.geo,r.uti,r.grp,r.grp_info,r.taxon].join(' '));
}
function authorNeedles(st){
  var out=[];
  function add(s){
    s=String(s||'').trim();
    if(s && out.indexOf(s)<0) out.push(s);
  }
  if(st.mode==='population') (st.rows||[]).forEach(function(r){ add(r.name); add(r.origin); });
  else { add(st.sample.name); add(st.sample.origin); }
  return out.filter(function(s){ return authorNorm(s).length>=3; });
}
function authorExactIds(st){
  var ids=[], list=st.mode==='population'?(st.rows||[]):[st.sample];
  list.forEach(function(r){
    var id=String(r.iid||'').trim();
    if(id) ids.push(id);
  });
  return ids;
}
function authorMatchRow(r, needles){
  if(!r || r.iid===QUERY) return false;
  var h=authorHay(r);
  var stop={of:1,the:1,and:1,or:1,a:1,an:1,de:1,la:1,le:1,du:1,des:1,von:1,van:1,der:1,di:1,da:1,in:1,on:1,from:1};
  return needles.some(function(n){
    var nn=authorNorm(n);
    if(!nn) return false;
    if(h.indexOf(nn)>=0) return true;
    return nn.split(' ').filter(function(w){ return w.length>=3 && !stop[w]; }).some(function(w){ return h.indexOf(w)>=0; });
  });
}
function majorityField(rows, key){
  var c={};
  rows.forEach(function(r){ var v=String(r[key]||'').trim(); if(v) c[v]=(c[v]||0)+1; });
  var best='', n=0;
  Object.keys(c).forEach(function(k){ if(c[k]>n){ n=c[k]; best=k; } });
  return best? {v:best, n:n} : null;
}
function computeAuthorInference(st){
  var needles=authorNeedles(st);
  var exact=authorExactIds(st);
  var hits=[];
  (SROWS||[]).forEach(function(r){
    if(!r || r.iid===QUERY) return;
    var byId=exact.indexOf(r.iid)>=0;
    if(byId || authorMatchRow(r, needles)) hits.push(r);
  });
  var inPanel=[];
  exact.forEach(function(id){
    if(id===QUERY) return;
    var r=rowByIid(id);
    if(r && r.iid) inPanel.push(r);
  });
  return {
    needles: needles,
    hits: hits,
    inPanel: inPanel,
    geo: majorityField(hits, 'geo'),
    con: majorityField(hits, 'con'),
    grp: majorityField(hits, 'grp_info') || majorityField(hits, 'grp'),
    ids: hits.map(function(r){ return r.iid; })
  };
}
function authorSrcHtml(kind, extra){
  var label=kind==='infer'
    ? t('from author origin','来自作者来源')
    : t('author','作者');
  return ' <span class="author-src">'+label+(extra?(' · '+extra):'')+'</span>';
}
function metaCell(panel, author){
  if(panel) return {html:'<strong>'+esc(panel)+'</strong>', src:'panel'};
  if(author) return {html:esc(author)+authorSrcHtml('author'), src:'author'};
  return {html:'—', src:''};
}
function fillQueryMeta(){
  var meta=document.getElementById('query-meta');
  if(!meta) return;
  var st=loadAuthorState();
  var qm=D.query_meta||{};
  var a=st.sample||{};
  var inf=computeAuthorInference(st);
  var name=metaCell(qm.name, a.name);
  var origin=metaCell(qm.origin, a.origin);
  var geo=qm.geo? metaCell(qm.geo,'') : (inf.geo? {html:esc(inf.geo.v)+authorSrcHtml('infer','n='+inf.geo.n), src:'infer'} : metaCell('',''));
  var con=qm.con? metaCell(qm.con,'') : (inf.con? {html:esc(inf.con.v)+authorSrcHtml('infer','n='+inf.con.n), src:'infer'} : metaCell('',''));
  var h='<table><caption>'+bi('Query metadata','查询元数据')+'</caption><tr><th>'+bi('Field','字段')+'</th><th>'+bi('Value','值')+'</th></tr>';
  h+='<tr><td>'+bi('Sample','样品')+'</td><td><strong>'+esc(a.iid||QUERY)+'</strong></td></tr>';
  if(st.mode==='population'){
    var nLab=((st.rows||[]).filter(function(r){return r.iid||r.name||r.origin;}).length);
    h+='<tr><td>'+bi('Mode','模式')+'</td><td>'+bi('Population','群体')+' ('+nLab+' '+t('labelled','已标注')+')</td></tr>';
    h+='<tr><td colspan=2><div class="table-scroll"><table><tr><th>'+bi('ID','编号')+'</th><th>'+bi('Variety','品种')+'</th><th>'+bi('Origin','来源')+'</th><th>'+bi('Date','年代')+'</th><th>'+bi('In panel','在面板中')+'</th><th>K=8</th></tr>';
    (st.rows||[]).forEach(function(row){
      if(!(row.iid||row.name||row.origin||row.date)) return;
      var pr=rowByIid(row.iid);
      var inP=!!(pr && pr.iid && pr.iid!==QUERY);
      var dom=(pr && pr.qvals && pr.qvals['8_dom'])? pr.qvals['8_dom'] : '—';
      h+='<tr'+(inP?' class="clickrow" data-iid="'+esc(row.iid)+'"':'')+'><td>'+esc(row.iid||'—')+'</td><td>'+esc(row.name||'—')+'</td><td>'+esc(row.origin||'—')+'</td><td>'+esc(row.date||'—')+'</td><td>'+t(inP?'yes':'no', inP?'是':'否')+'</td><td>'+esc(dom)+'</td></tr>';
    });
    h+='</table></div><div class="muted">'+bi(
      'ADMIXTURE / PCA below are for '+esc(QUERY)+'. Extra IDs use panel Q only if that ID is in the 2449 set.',
      '下方 ADMIXTURE / PCA 针对 '+esc(QUERY)+'。额外 ID 仅在该 ID 属于 2449 集合时使用面板 Q。')+'</div></td></tr>';
  } else {
    h+='<tr><td>'+bi('Variety','品种')+'</td><td>'+name.html+(qm.name&&qm.acc_local?' <span class="muted">('+esc(qm.acc_local)+')</span>':'')+'</td></tr>';
    h+='<tr><td>'+bi('Origin','来源')+'</td><td>'+origin.html+'</td></tr>';
    h+='<tr><td>'+bi('Date / period','年代')+'</td><td>'+(a.date?esc(a.date)+authorSrcHtml('author'):'—')+'</td></tr>';
    h+='<tr><td>'+bi('Material','材料')+'</td><td>'+(a.material?esc(a.material)+authorSrcHtml('author'):'—')+'</td></tr>';
    h+='<tr><td>'+bi('Contact / lab','联系人 / 实验室')+'</td><td>'+(a.contact?esc(a.contact)+authorSrcHtml('author'):'—')+'</td></tr>';
    h+='<tr><td>'+bi('Notes','备注')+'</td><td>'+(a.notes?esc(a.notes)+authorSrcHtml('author'):'—')+'</td></tr>';
  }
  h+='<tr><td>VIVC</td><td>'+esc(qm.vivc||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Country (CON)','国家（CON）')+'</td><td>'+con.html+'</td></tr>';
  h+='<tr><td>GEO</td><td>'+geo.html+'</td></tr>';
  h+='<tr><td>'+bi('Use (Uti)','用途（Uti）')+'</td><td>'+esc(qm.uti||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Taxon','分类单元')+'</td><td>'+esc(qm.taxon||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Contributor','提供者')+'</td><td>'+esc(qm.contributor||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Wild','野生')+'</td><td>'+esc(qm.wild||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Flower sex','花性')+'</td><td>'+esc(qm.sex||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Skin colour','果皮颜色')+'</td><td>'+esc(qm.color||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Muscat','麝香')+'</td><td>'+esc(qm.muscat||'—')+'</td></tr>';
  h+='<tr><td>'+bi('PO partners','亲子配对')+'</td><td>'+esc(qm.po||'—')+'</td></tr>';
  h+='<tr><td>'+bi('Clone of','无性系来源')+'</td><td>'+esc(qm.clone_of||'—')+'</td></tr>';
  if(qm.grp) h+='<tr><td>'+bi('Grp','组别')+'</td><td>'+esc(qm.grp)+'</td></tr>';
  h+='<tr><td>'+bi('Dominant K=8','主导 K=8')+'</td><td><strong style="color:var(--amber)">'+esc(qm.q8_dom||'—')+'</strong></td></tr>';
  h+='<tr><td>PC1 / PC2</td><td>'+fmtNum(qm.pc1,3)+' / '+fmtNum(qm.pc2,3)+'</td></tr>';
  h+='<tr><td>PC3</td><td>'+fmtNum(qm.pc3,3)+'</td></tr>';
  h+='<tr><td>'+bi('PCA method','PCA 方法')+'</td><td>'+esc(pcaMethodLabel(qm.pca_method||D.pca_method))+'</td></tr></table>';
  if(inf.hits.length){
    var shown=inf.hits.slice(0,8);
    h+='<div class="author-infer"><strong>'+bi('Panel matches from author record','作者记录匹配的面板样品')+'</strong> · n='+inf.hits.length;
    if(inf.grp) h+=' · '+t('most common Grp','最常见组别')+' '+esc(inf.grp.v);
    if(inf.geo) h+=' · GEO '+esc(inf.geo.v);
    h+='<div class="muted">'+bi(
      'String match on name / origin vs 2449 labels — not a new ADMIXTURE run.',
      '按名称/来源与 2449 标签做字符串匹配，不是新的 ADMIXTURE 运行。')+'</div><div>';
    shown.forEach(function(r){
      h+='<span class="clickrow author-chip" data-iid="'+esc(r.iid)+'">'+esc(r.iid)+(r.acc?(' · '+esc(r.acc)):'')+'</span> ';
    });
    if(inf.hits.length>8) h+='<span class="muted">+'+(inf.hits.length-8)+'</span>';
    h+='</div></div>';
  } else if(authorNeedles(st).length){
    h+='<div class="author-infer muted">'+bi(
      'No 2449 label matches for the author origin / variety yet.',
      '作者来源/品种尚未匹配到 2449 标签。')+'</div>';
  }
  meta.innerHTML=h;
  bindRowClicks(meta);
  if(typeof window!=='undefined') window._authorMatchIds=inf.ids;
}
function authorConclusionBits(st, inf){
  var bits=[];
  if(st.mode==='population'){
    var n=(st.rows||[]).filter(function(r){return r.iid||r.name||r.origin;}).length;
    if(n) bits.push('Author cohort: '+n+' labelled sample'+(n>1?'s':'')+'. Genetic plots are for '+QUERY+'.');
  } else {
    var a=st.sample||{};
    var rec=[a.name&&('variety '+a.name), a.origin&&('origin '+a.origin), a.date&&('date '+a.date)].filter(Boolean);
    if(rec.length) bits.push('Author record: '+rec.join('; ')+'.');
  }
  if(inf && inf.hits && inf.hits.length){
    var line='Author labels match '+inf.hits.length+' panel IDs';
    if(inf.grp) line+='; most common Grp '+inf.grp.v;
    if(inf.geo) line+='; GEO '+inf.geo.v;
    line+=' (name/origin string match, not a new fit).';
    bits.push(line);
  }
  if(inf && inf.inPanel && inf.inPanel.length){
    var doms=inf.inPanel.map(function(r){ return (r.qvals&&r.qvals['8_dom'])||''; }).filter(Boolean);
    if(doms.length) bits.push('Author IDs present in the 2449 panel; their K=8 lookup: '+doms.join(', ')+'.');
  }
  return bits;
}
function applyAuthorContext(){
  var st=loadAuthorState();
  var inf=computeAuthorInference(st);
  window._authorMatchIds=inf.ids;
  fillQueryMeta();
  fillConclusions();
  fillIbsKinship();
  enhanceReportTables(document);
}
function fillAuthorIntake(){
  var box=document.getElementById('author-intake');
  if(!box) return;
  var st=loadAuthorState();
  renderAuthorIntake(box, st);
}
function renderAuthorIntake(box, st){
  var h='<div class="author-head"><div><strong>'+bi('Sample record','送检信息')+'</strong>'+
    '<div class="muted">'+bi('Fill in before sharing. Kept in this browser.','作者填写，保存在本机浏览器。')+'</div></div>'+
    '<div class="author-mode">'+
      '<button type="button" data-mode="sample"'+(st.mode==='sample'?' class="active"':'')+'>'+bi('Sample','单样本')+'</button>'+
      '<button type="button" data-mode="population"'+(st.mode==='population'?' class="active"':'')+'>'+bi('Population','群体')+'</button>'+
    '</div></div>';
  if(st.mode==='population'){
    h+='<div class="table-scroll"><table class="author-table"><tr>';
    AUTHOR_ROW_FIELDS.forEach(function(f){ h+='<th>'+authorFieldLab(f)+'</th>'; });
    h+='<th></th></tr>';
    st.rows.forEach(function(row,i){
      h+='<tr>';
      AUTHOR_ROW_FIELDS.forEach(function(f){
        h+='<td><input data-row="'+i+'" data-k="'+f.k+'" placeholder="'+authorFieldPh(f)+'" value="'+esc(row[f.k]||'')+'"/></td>';
      });
      h+='<td><button type="button" class="author-del" data-del="'+i+'" title="'+esc(t('Remove','移除'))+'" aria-label="'+esc(t('Remove','移除'))+'">✕</button></td></tr>';
    });
    h+='</table></div><button type="button" class="author-add">'+bi('+ Add sample','+ 加一行')+'</button>';
  } else {
    h+='<div class="author-grid">';
    AUTHOR_SAMPLE_FIELDS.forEach(function(f){
      h+='<label class="author-field">'+authorFieldLab(f)+
        '<input data-k="'+f.k+'" placeholder="'+authorFieldPh(f)+'" value="'+esc(st.sample[f.k]||'')+'"/></label>';
    });
    h+='<label class="author-field author-notes">'+bi('Notes','备注')+
      '<textarea data-k="notes" rows="2" placeholder="">'+esc(st.sample.notes||'')+'</textarea></label>';
    h+='</div>';
  }
  box.innerHTML=h;
  box.querySelectorAll('.author-mode button').forEach(function(b){
    b.onclick=function(){
      var next=b.getAttribute('data-mode');
      if(next===st.mode) return;
      if(next==='population' && st.sample && st.sample.iid && !st.rows.some(function(r){return r.iid;})){
        st.rows[0]=Object.assign(blankAuthorRow(), {iid:st.sample.iid, name:st.sample.name, origin:st.sample.origin, date:st.sample.date, notes:st.sample.notes});
      }
      if(next==='sample' && st.rows[0]){
        var r=st.rows[0];
        st.sample.iid=r.iid||st.sample.iid;
        st.sample.name=r.name||st.sample.name;
        st.sample.origin=r.origin||st.sample.origin;
        st.sample.date=r.date||st.sample.date;
        if(r.notes) st.sample.notes=r.notes;
      }
      st.mode=next;
      saveAuthorState(st);
      renderAuthorIntake(box, st);
    };
  });
  box.querySelectorAll('input,textarea').forEach(function(el){
    el.oninput=function(){
      var k=el.getAttribute('data-k');
      var i=el.getAttribute('data-row');
      if(i!=null){ st.rows[parseInt(i,10)][k]=el.value; }
      else { st.sample[k]=el.value; }
      saveAuthorState(st);
      applyAuthorContext();
    };
  });
  var add=box.querySelector('.author-add');
  if(add) add.onclick=function(){ st.rows.push(blankAuthorRow()); saveAuthorState(st); renderAuthorIntake(box, st); };
  box.querySelectorAll('.author-del').forEach(function(b){
    b.onclick=function(){
      var i=parseInt(b.getAttribute('data-del'),10);
      if(st.rows.length<=1){ st.rows[0]=blankAuthorRow(); }
      else st.rows.splice(i,1);
      saveAuthorState(st);
      renderAuthorIntake(box, st);
    };
  });
  applyAuthorContext();
}

function fillConclusions(){
  var el=document.getElementById('concl-list');
  if(!el) return;
  var items=(D.conclusions||[]).map(cleanConclusionPair).filter(function(p){
    return p && (p.en||p.zh);
  });
  if(isModernLibrary()){
    items=items.filter(function(p){
      var en=p.en||'';
      return !/^Damage\b/i.test(en) &&
        !/mapDamage|Ginolhac|Jónsson|Jonsson|C→T|G→A/i.test(en);
    });
    var modernCopy=modernPeConclusionPair();
    items=items.filter(function(p){
      return !/modern sample|modern PE source library/i.test(p.en||'');
    });
    items.push(modernCopy);
  }
  el.innerHTML=items.map(function(p){
    return '<li>'+bi(esc(p.en),esc(p.zh))+'</li>';
  }).join('');
}

function fillQuerySnapshot(){
  var box=document.getElementById('query-q8');
  var q8=D.query_q8||[];
  if(!box) return;
  if(!q8.length){
    box.innerHTML='<p class="muted">'+bi(
      'No K=8 Q on this strip. In-panel IDs look up the 2449 Q. New samples are projected onto that model.',
      '这条带没有 K=8 Q。面板内 ID 读取 2449 Q；新样本投影到该模型。')+'</p>';
  } else {
    var h='<div class="q8-bar">';
    q8.forEach(function(c){
      var pct=(c.value*100);
      if(pct<0.05) return;
      h+='<div class="q8-seg" style="width:'+pct+'%;background:'+esc(c.color)+'" title="'+
        esc(c.label)+': '+pct.toFixed(1)+'%"></div>';
    });
    h+='</div><table><tr><th>'+bi('Ancestry','祖源成分')+'</th><th>%</th><th></th></tr>';
    q8.slice().sort(function(a,b){return b.value-a.value;}).forEach(function(c){
      var note=c.note||glossForLabel(c.label);
      h+='<tr><td><span class="swatch" style="background:'+esc(c.color)+'"></span> <strong>'+esc(c.label)+'</strong>'+
        (note?'<div class="q8-note">'+esc(note)+'</div>':'')+'</td>'+
        '<td style="text-align:right;font-weight:600">'+(c.value*100).toFixed(1)+'</td>'+
        '<td><div class="mini-bar"><i style="width:'+(c.value*100)+'%;background:'+esc(c.color)+'"></i></div></td></tr>';
    });
    h+='</table>';
    box.innerHTML=h;
  }
  var leg=document.getElementById('k8-legend');
  if(leg){
    var L='';
    (D.k8_labels||[]).forEach(function(lab,i){
      var col=(D.k8_colors||[])[i]||'#888';
      L+='<span class="leg" title="'+esc(glossForLabel(lab))+'"><span class="swatch" style="background:'+esc(col)+'"></span>'+esc(lab)+'</span>';
    });
    leg.innerHTML=L;
  }
  fillK8PaintNote();
  fillQueryMeta();
}

function allowQueryDownload(x){
  var q=String(QUERY||((D||{}).query)||'');
  var href=String((x&&x.href)||'').replace(/\\/g,'/');
  if(!q || href.indexOf('..')>=0 || href.indexOf('/')>=0) return false;
  if(href.indexOf(q+'.')!==0) return false;
  var rest=href.slice(q.length+1);
  if(/panel|2449|dosage|nogwas|manual|\.json$/i.test(rest)) return false;
  return /^(qc|damage|pca|ibs_clone_hits|ibs_summary|kinship_top|admix\.K[2-8]\.Q)\.tsv$/.test(rest);
}
function downloadLabelHtml(label){
  var raw=String(label==null?'':label);
  var pairs={
    'QC TSV':['QC TSV','质控 TSV'],
    'IBS class counts':['IBS class counts','IBS 类别计数'],
    'Clone / PO hits':['Clone / PO hits','克隆 / 亲子命中'],
    'Kinship top':['Kinship top','亲缘近邻'],
    'PCA (this sample)':['PCA (this sample)','PCA（本样品）'],
    'Damage TSV':['Damage TSV','损伤 TSV']
  };
  var match=/^ADMIXTURE K=([2-8]) Q$/i.exec(raw);
  if(match) pairs[raw]=[raw,'ADMIXTURE K='+match[1]+' Q（祖源成分）'];
  var pair=pairs[raw]||[raw,raw];
  return bi(esc(pair[0]),esc(pair[1]));
}

function libraryClass(){
  var meta=(D&&D.report_meta)||{};
  var baked='';
  var sec=typeof document!=='undefined'?document.getElementById('damage'):null;
  if(sec&&sec.getAttribute) baked=String(sec.getAttribute('data-library-class')||'');
  var raw=String(meta.library_class||baked||'').toLowerCase();
  if(raw) return raw;
  var typ=String(meta.library_type||'').toLowerCase();
  if(typ==='pe') return 'modern';
  if(typ==='adna') return 'ancient';
  return '';
}
function isModernLibrary(){ return libraryClass()==='modern'; }
function addClassName(el, name){
  if(!el||!name) return;
  if(el.classList&&el.classList.add) el.classList.add(name);
  else {
    var cur=String(el.className||'');
    if((' '+cur+' ').indexOf(' '+name+' ')<0) el.className=cur?(cur+' '+name):name;
  }
}
function setHidden(el, hidden){
  if(!el) return;
  if(hidden){
    el.hidden=true;
    if(el.setAttribute) el.setAttribute('hidden','');
    if(el.style){
      el.style.display='none';
      el.style.height='0px';
      el.style.minHeight='0px';
    }
    return;
  }
  el.hidden=false;
  if(el.removeAttribute) el.removeAttribute('hidden');
  if(el.style){
    el.style.display='';
    el.style.height='';
    el.style.minHeight='';
  }
}
function applyDamageSectionState(){
  var sec=document.getElementById('damage');
  var modernNote=document.getElementById('damage-modern-note');
  var guide=document.getElementById('damage-guide');
  var note=document.getElementById('damage-note');
  var plot=document.getElementById('plot-damage');
  var plotLen=document.getElementById('plot-damage-len');
  if(isModernLibrary()){
    addClassName(sec,'is-modern-library');
    if(sec&&sec.setAttribute) sec.setAttribute('data-library-class','modern');
    if(modernNote){
      modernNote.hidden=false;
      if(modernNote.removeAttribute) modernNote.removeAttribute('hidden');
      if(modernNote.style) modernNote.style.display='block';
    }
    setHidden(guide,true);
    setHidden(note,true);
    if(plot){ if(typeof resetPlot==='function') resetPlot(plot); plot.innerHTML=''; setHidden(plot,true); }
    if(plotLen){ if(typeof resetPlot==='function') resetPlot(plotLen); plotLen.innerHTML=''; setHidden(plotLen,true); }
    return true;
  }
  if(modernNote){
    modernNote.hidden=true;
    if(modernNote.style) modernNote.style.display='none';
  }
  return false;
}
function asDamage(raw){
  if(!raw) return null;
  if(Array.isArray(raw)){
    if(!raw.length) return null;
    return {source:'lite', ct5:raw, ga3:[], subs5:{}, subs3:{}, length:[]};
  }
  var ct=raw.ct5||[];
  var ga=raw.ga3||[];
  if(!ct.length && !ga.length) return null;
  return raw;
}
function plotLabelZh(label){
  var raw=String(label||'This plot');
  var known={
    'This plot':'该图',
    'Damage plot':'损伤图',
    'PCA plot':'PCA 图',
    '3D PCA plot':'3D PCA 图',
    'ADMIXTURE plot':'ADMIXTURE 图',
    'NJ tree':'NJ 树'
  };
  if(known[raw]) return known[raw];
  return raw.replace(/Outgroup-f3/g,'外群 f3')
    .replace(/higher = more shared drift/g,'越高表示共享漂变越多')
    .replace(/query/gi,'查询样本')
    .replace(/among Grps/gi,'全体 Grp')
    .replace(/vs OUT/gi,'vs OUT');
}
function plotlyUnavailable(el, label){
  if(!el) return true;
  if(!plotlyCan('newPlot')){
    var en=String(label||'This plot');
    var zh=plotLabelZh(en);
    el.innerHTML='<div class="muted" style="padding:16px">'+bi(
      'Plotly.js unavailable; '+esc(en)+' could not be rendered. Tables and other report sections remain available.',
      'Plotly.js 不可用；'+esc(zh)+'无法渲染。表格和其他报告部分仍可用。')+'</div>';
    return true;
  }
  return false;
}
function sourceDamageLabel(){
  var m=D.report_meta||{};
  var q=String(m.query_id||D.query||'');
  var s=String(m.source_sample_id||q);
  var path=(m.source_damage_tsv&&m.source_damage_tsv.path)||
    ((D.method_coverage&&D.method_coverage.damage||{}).path)||'';
  var label=s!==q
    ? bi('Source library: '+esc(s)+'; report query: '+esc(q),
         '来源文库：'+esc(s)+'；报告查询：'+esc(q))
    : bi('Query-derived: '+esc(q),'查询样本来源：'+esc(q));
  if(path){
    label+=' · '+bi('damage file: '+esc(path),'损伤文件：'+esc(path));
  }
  return label;
}
function reportSourceScope(){
  var m=D.report_meta||{};
  var q=String(m.query_id||D.query||'');
  var s=String(m.source_sample_id||q);
  return scopeLabel(s&&q&&s!==q?'Source library':'Query-derived');
}
function reportTableCaption(table){
  var host=table.closest?table.closest('section,details'):null;
  var heading=host&&host.querySelector?host.querySelector('h2,h3,summary'):null;
  var text=heading&&heading.textContent?heading.textContent.trim():'';
  return text||'Report data';
}
function reportTableScrollParent(table){
  var parent=table&& (table.parentElement||table.parentNode);
  while(parent){
    var className=parent.className;
    if(!className&&parent.getAttribute) className=parent.getAttribute('class');
    if(parent.classList&&parent.classList.contains&&
        parent.classList.contains('table-scroll')) return parent;
    if((' '+String(className||'').split(/\s+/).join(' ')+' ').indexOf(' table-scroll ')>=0){
      return parent;
    }
    parent=parent.parentElement||parent.parentNode;
  }
  return null;
}
function wrapReportTable(table, root){
  if(!table||reportTableScrollParent(table)) return;
  var parent=table.parentElement||table.parentNode;
  var doc=(table.ownerDocument)||(root&&root.ownerDocument)||
    (typeof document!=='undefined'?document:null);
  if(!parent||!doc||!doc.createElement) return;
  var wrapper=doc.createElement('div');
  if(!wrapper||!wrapper.appendChild) return;
  wrapper.className='table-scroll';
  if(wrapper.setAttribute) wrapper.setAttribute('class','table-scroll');
  if(parent.insertBefore) parent.insertBefore(wrapper,table);
  else if(parent.appendChild) parent.appendChild(wrapper);
  else return;
  wrapper.appendChild(table);
}
function localizeTableScroll(el){
  if(!el||!el.setAttribute) return;
  el.setAttribute('role','region');
  el.setAttribute('tabindex','0');
  setLocalizedAttribute(el,'aria-label','Scrollable results table','可横向滚动的结果表');
  setLocalizedAttribute(el,'title','Scroll horizontally to view all columns','横向滚动可查看全部列');
}
function enhanceReportTables(root){
  root=root||document;
  var tables=root.querySelectorAll?root.querySelectorAll('table'):[];
  Array.prototype.forEach.call(tables,function(table){
    wrapReportTable(table,root);
    var caption=table.querySelector&&table.querySelector('caption');
    if(!caption){
      if(table.createCaption) caption=table.createCaption();
      else if(document.createElement){
        caption=document.createElement('caption');
        if(table.insertBefore) table.insertBefore(caption, table.firstChild||null);
      }
      if(caption){
        caption.className='sr-only';
        caption.textContent=reportTableCaption(table);
      }
    }
    var rows=table.querySelectorAll?table.querySelectorAll('tr'):[];
    var headerRow=null;
    Array.prototype.some.call(rows,function(row){
      var heads=row.querySelectorAll?row.querySelectorAll('th'):[];
      if(heads.length){ headerRow=row; return true; }
      return false;
    });
    if(headerRow){
      var parent=headerRow.parentElement;
      if((!parent||String(parent.tagName||'').toLowerCase()!=='thead')&&table.createTHead){
        var thead=table.tHead||table.createTHead();
        if(thead&&thead.appendChild) thead.appendChild(headerRow);
      }
      Array.prototype.forEach.call(
        headerRow.querySelectorAll?headerRow.querySelectorAll('th'):[],
        function(th){
          if(!th.getAttribute('scope')) th.setAttribute('scope','col');
        }
      );
    }
    if(table.setAttribute) table.setAttribute('data-ga-table-enhanced','1');
  });
  var rows=root.querySelectorAll?root.querySelectorAll('.clickrow'):[];
  Array.prototype.forEach.call(rows,function(row){
    if(row.setAttribute){
      row.setAttribute('role','button');
      row.setAttribute('tabindex','0');
    }
    if(row._gaKeyboardBound || !row.addEventListener) return;
    row._gaKeyboardBound=true;
    row.addEventListener('keydown',function(ev){
      if(ev.key==='Enter'||ev.key===' '){
        ev.preventDefault();
        if(row.click) row.click();
      }
    });
  });
  var scrolls=root.querySelectorAll?root.querySelectorAll('.table-scroll'):[];
  Array.prototype.forEach.call(scrolls, localizeTableScroll);
  pairLangBlocks(root);
}
function metaArtifactCell(sig){
  if(!sig) return bi('not available','不可用');
  var state=sig.available?bi('available','可用'):bi('not available','不可用');
  var bits=[esc(sig.path||'—'), state];
  if(sig.available && sig.size!=null) bits.push(esc(String(sig.size)+' B'));
  return bits.join(' · ');
}
function runtimeReason(reason){
  var raw=String(reason||'');
  var key=raw.toLowerCase();
  var pair=null;
  if(!raw) return bi('—','—');
  if(key==='no per-query gs prediction available.'||
     key==='no per-sample gs prediction available'){
    pair=['No per-query GS prediction available.','没有可用的本查询 GS 预测。'];
  }else if(key==='no selection-window calls'||
           key==='no selection locus genotype coverage'){
    pair=['No selection-window genotype coverage','没有选择窗口分型覆盖'];
  }else if(key==='no gwas-locus calls'||
           key==='no gwas locus genotype coverage'){
    pair=['No GWAS-locus genotype coverage','没有 GWAS 位点分型覆盖'];
  }else if(key==='no damage profile.'||key==='damage profile unavailable'){
    pair=['No damage profile.','没有损伤谱。'];
  }else if(key==='no fstats query sites'){
    pair=['No f3/f4 query sites','没有 f3/f4 查询位点'];
  }else if(key==='no query evidence rows'){
    pair=['No query genotype evidence rows','没有查询样本基因型证据行'];
  }else if(key==='no gwas index'){
    pair=['No GWAS index','没有 GWAS 索引'];
  }else if(key==='no gs index'){
    pair=['No GS index','没有 GS 索引'];
  }
  return pair?bi(pair[0],pair[1]):bi(
    'Source reason: '+esc(raw),
    '来源原因：'+esc(raw));
}
function unavailableMessage(reason){
  return bi('Unavailable','不可用')+' '+runtimeReason(reason);
}
function fillReportMeta(){
  var el=document.getElementById('report-meta');
  if(!el) return;
  var m=D.report_meta||{};
  var h='<table><caption>'+bi('Report metadata and artifact provenance','报告元数据与产物溯源')+'</caption><thead><tr><th scope="col">'+bi('Identifier','标识')+'</th><th scope="col">'+bi('Value','数值')+'</th><th scope="col">'+bi('Scope','范围')+'</th></tr></thead><tbody>';
  h+='<tr><td>'+bi('Report ID','报告编号')+'</td><td>'+esc(m.report_id||'—')+'</td><td>'+scopeLabel('Query-derived')+'</td></tr>';
  h+='<tr><td>'+bi('Query ID','查询编号')+'</td><td>'+esc(m.query_id||D.query||'—')+'</td><td>'+scopeLabel('Query-derived')+'</td></tr>';
  h+='<tr><td>'+bi('Source sample ID','来源样本编号')+'</td><td>'+esc(m.source_sample_id||'—')+'</td><td>'+reportSourceScope()+'</td></tr>';
  h+='<tr><td>'+bi('Generated (UTC)','生成时间（UTC）')+'</td><td>'+esc(m.generated_at_utc||'—')+'</td><td>'+scopeLabel('Query-derived')+'</td></tr>';
  h+='<tr class="qc-group"><td colspan="3">'+bi('Artifact provenance','产物溯源')+'</td></tr>';
  [
    ['Panel dosage cache','面板 dosage 缓存','panel_cache','2449 panel only'],
    ['Query VCF','查询 VCF','query_vcf','Query-derived'],
    ['Source BAM','来源 BAM','source_bam',reportSourceScope()],
    ['Source damage file','来源损伤文件','source_damage_tsv',reportSourceScope()]
  ].forEach(function(pair){
    var label=pair[2];
    var scope=pair[3];
    h+='<tr><td>'+bi(pair[0],pair[1])+'</td><td>'+metaArtifactCell(m[label])+
      '</td><td>'+scopeLabel(scope)+'</td></tr>';
  });
  var shared=m.shared_artifacts||{};
  [
    ['Selection Manhattan','选择 Manhattan','selection','manhattan'],
    ['Selection LocusZoom','选择 LocusZoom','selection','locuszoom'],
    ['GWAS index','GWAS 索引','gwas','index'],
    ['GWAS LocusZoom','GWAS LocusZoom','gwas','locuszoom'],
    ['GS index','GS 索引','gs','index']
  ].forEach(function(row){
    h+='<tr><td>'+bi(row[0],row[1])+'</td><td>'+metaArtifactCell(
      shared[row[2]]&&shared[row[2]][row[3]]
    )+'</td><td>'+scopeLabel('2449 panel only')+'</td></tr>';
  });
  h+='</tbody></table>';
  el.innerHTML=h;
}
function methodCoverageValue(key, row){
  if(!row) return '—';
  if(key==='panel_genotype'){
    var pct=row.coverage==null?'—':fmtNum(Number(row.coverage)*100,2)+'%';
    return esc(String(row.called==null?'—':row.called))+' / '+esc(String(row.total==null?'—':row.total))+
      ' '+bi('called','已分型')+' · '+esc(pct);
  }
  if(key==='selection_locus_gt'||key==='gwas_locus_gt'){
    return esc(String(row.query_gt_called||0))+' / '+esc(String(row.query_gt_n||0))+
      ' '+bi('called','已分型');
  }
  if(key==='fstats') return esc(String(row.query_called_sites||0))+' '+bi('query sites','查询位点');
  if(key==='gs_predictions') return esc(String((row||[]).length))+' '+bi('prediction rows','预测行');
  if(key==='damage'||key==='gs') return row.available?bi('available','可用'):bi('not available','不可用');
  return '—';
}
function fillMethodCoverage(){
  var el=document.getElementById('method-coverage');
  if(!el) return;
  var mc=D.method_coverage||{};
  var rows=[
    {key:'panel_genotype', lab:bi('Panel genotype','芯片分型'), scope:scopeLabel('Query-derived')},
    {key:'selection_locus_gt', lab:bi('Selection-window genotype','选择扫描窗口分型'), scope:scopeLabel('Query vs 2449 panel'),
      caveat_en:'Query GT inside selection LocusZoom windows: 5 named MAS/GWAS + Table S29 bins + among-Grps Fst peaks. Not the panel GWAS index below.',
      caveat_zh:'选择扫描 LocusZoom 窗口内的查询分型：5 个命名 MAS/GWAS 窗 + 表 S29 区间 + 全体 Grp Fst 峰。不是下面那行 panel GWAS 索引。'},
    {key:'gwas_locus_gt', lab:bi('Panel GWAS-locus genotype','panel GWAS 位点分型'), scope:scopeLabel('Query vs 2449 panel'),
      caveat_en:'Query GT inside panel GWAS LocusZoom windows (EMMAX/P3D trait leads). Some genes overlap the five named windows; the SNP set is different.',
      caveat_zh:'panel GWAS LocusZoom 窗口内的查询分型（EMMAX/P3D 性状主位点）。部分基因与五个命名窗重合，但位点集合不同。'},
    {key:'fstats', lab:bi('f3/f4 query sites','f3/f4 查询位点'), scope:scopeLabel('Query vs 2449 panel')},
    {key:'gs_predictions', lab:bi('Per-query GS predictions','本查询 GS 预测'), scope:scopeLabel('Query-derived')},
    {key:'damage', lab:bi('Damage profile','损伤谱'), scope:reportSourceScope()},
    {key:'gs', lab:bi('GS prediction availability','GS 预测是否可用'), scope:scopeLabel('Query-derived')}
  ];
  var h='<table><caption>'+bi('Method coverage','方法覆盖')+'</caption><thead><tr><th scope="col">'+bi('Method','方法')+'</th><th scope="col">'+bi('Scope','范围')+'</th><th scope="col">'+bi('Exact count / coverage','实际数量 / 覆盖度')+'</th><th scope="col">'+bi('Reason / caveat','原因 / 注意')+'</th></tr></thead><tbody>';
  rows.forEach(function(item){
    var row=mc[item.key];
    var reason='';
    if(item.caveat_en){
      reason=bi(item.caveat_en, item.caveat_zh||item.caveat_en);
      if(row&&row.unavailable_reason) reason+=' · '+runtimeReason(row.unavailable_reason);
    }else if(item.key==='gs_predictions'){
      reason=(row&&row.length)?bi('Rows are shown in sample evidence.','行在样本证据里。'):
        runtimeReason((mc.gs||{}).unavailable_reason||'No per-query GS prediction available.');
    }else if(item.key==='damage'){
      var dbits=[];
      var qid=String(((D.report_meta||{}).query_id)||D.query||'');
      var sid=row&&row.source_sample_id?String(row.source_sample_id):'';
      if(sid && sid!==qid){
        dbits.push(bi('Source library','来源文库')+': '+esc(sid));
      }else if(sid){
        dbits.push(bi('Query','查询样本')+': '+esc(sid));
      }
      if(row&&row.path) dbits.push(bi('damage file','损伤文件')+': '+esc(row.path)+' '+
        (row.path_available?bi('available','可用'):bi('not available','不可用')));
      if(row&&row.unavailable_reason) dbits.push(runtimeReason(row.unavailable_reason));
      reason=dbits.join(' · ')||bi('No damage profile.','没有损伤谱。');
    }else reason=runtimeReason((row&&row.unavailable_reason)||'');
    h+='<tr><td>'+item.lab+'</td><td>'+item.scope+'</td><td>'+
      methodCoverageValue(item.key,row)+'</td><td>'+reason+'</td></tr>';
  });
  h+='</tbody></table><p class="muted">'+bi('Counts are reported as observed; no cutoff is applied.','数量按实际观测报告；不应用阈值。')+'</p>';
  el.innerHTML=h;
}
function queryEvidenceContext(ctx){
  if(!ctx) return '—';
  var bits=[];
  if(ctx.source) bits.push(String(ctx.source));
  if(ctx.metric) bits.push(String(ctx.metric)+'='+String(ctx.value==null?'—':ctx.value));
  if(ctx.annotation) bits.push(String(ctx.annotation));
  return bits.length?bits.join(' · '):'—';
}
function evidenceAnnot(row){
  var cat=lookupCatalogBySite(row.site)||{};
  var gwas=lookupGwasBySite(row.site)||{};
  return {
    trait: row.trait||cat.trait||gwas.trait||'',
    descriptor: cat.descriptor||gwas.descriptor||'',
    notations: gwas.notations||'',
    gene: row.gene||cat.gene||gwas.gene||'',
    alias: cat.alias||'',
    product: cat.product||gwas.gene_product||'',
    uniprot: cat.uniprot||gwas.gene_uniprot||'',
    go: cat.go||'',
    pfam: cat.pfam||'',
    kegg: cat.kegg||cat.kegg_vvi||'',
    kegg_vvi: cat.kegg_vvi||'',
    interpro: cat.interpro||'',
    ec: cat.ec||'',
    vitis_id: cat.vitis_id||'',
    vitis_symbol: cat.vitis_symbol||'',
    ncbi_geneid: cat.ncbi_geneid||'',
    refseq: cat.refseq||'',
    note: ((row.panel_context||{}).annotation)||cat.note||''
  };
}
function evidenceTraitHtml(row){
  var a=evidenceAnnot(row);
  var gene=esc(a.gene||'—');
  if(a.alias && a.alias!==a.gene) gene+=' <span class="muted">('+esc(a.alias)+')</span>';
  var html=oivTraitHtml(a.trait||row.trait||'')+' · '+gene;
  if(a.descriptor||a.notations){
    html+='<span class="ev-sub">'+oivDescHtml({trait:a.trait||row.trait, descriptor:a.descriptor});
    if(a.notations) html+='<br>'+esc(a.notations);
    html+='</span>';
  }
  var db=annotDbHtml(a);
  if(db) html+='<span class="ev-sub">'+db+'</span>';
  return html;
}
function evidenceContextHtml(row){
  var ctx=row.panel_context||{};
  var bits=[];
  if(ctx.source) bits.push(esc(String(ctx.source)));
  if(ctx.metric==='nlp'&&ctx.value!=null) bits.push('−log10 p='+fmtNum(Number(ctx.value),2));
  else if(ctx.metric&&ctx.metric!=='curated_locus') bits.push(esc(String(ctx.metric))+'='+esc(String(ctx.value==null?'—':ctx.value)));
  var note=ctx.annotation?esc(String(ctx.annotation)):'';
  if(note) bits.push(note);
  return bits.join(' · ')||'—';
}
function queryCallStatusHtml(status){
  var raw=String(status||'missing');
  var labels={
    called:'已分型',
    missing:'缺失',
    unavailable:'不可用'
  };
  return bi(esc(raw),esc(labels[raw.toLowerCase()]||raw));
}
function gsTraitNote(r){
  var idx=lookupGwasIndex(r.trait, r.slug);
  var loc=lookupGwasLocusBySlug(r.slug);
  var bits=[];
  if(idx&&idx.descriptor) bits.push(oivDescHtml(idx));
  else if(loc&&loc.descriptor) bits.push(oivDescHtml(loc));
  if(loc&&loc.notations) bits.push(esc(loc.notations));
  if(idx&&idx.case_n!=null){
    bits.push(bi('Panel n='+esc(String(idx.n||'—'))+' · case='+esc(String(idx.case_n))+' · control='+esc(String(idx.control_n)),
      'panel n='+esc(String(idx.n||'—'))+' · case='+esc(String(idx.case_n))+' · control='+esc(String(idx.control_n))));
  }else if(idx&&idx.n!=null){
    bits.push('panel n='+esc(String(idx.n)));
  }
  var slug=String(r.slug||r.trait||'');
  if(/225/.test(slug)){
    var cv=Number(r.cv_r);
    var cvEn='', cvZh='';
    if(isFinite(cv)){
      var cvTxt=fmtNum(cv,3);
      cvEn=' based on this row’s panel CV r ('+cvTxt+')';
      cvZh='，依据本行 panel 交叉验证 r（'+cvTxt+'）';
    }
    bits.push(bi(
      'OIV 225 is currently rankable under this report policy'+cvEn+'. All values are model scores requiring phenotype validation.',
      'OIV 225 目前按本报告策略可排序'+cvZh+'。所有数值均为模型分数，需表型验证。'));
  }
  if(/151/.test(slug)) bits.push(bi(
    'GWAS hits the SDR region. H1–H5 is Dong et al. literature context. Panel SDR tags are panel annotations, not the full literature haplotype classification.',
    'GWAS 打到 SDR 区间。H1–H5 仅作 Dong 等文献背景。面板 SDR 标签是面板注释，不是完整的文献单倍型分类。'));
  if(/241/.test(slug)) bits.push(bi(
    'No OIV 241 locus overlap found in the panel GWAS',
    'panel GWAS 未发现 OIV 241 位点重合'));
  return bits.join('<br>');
}
function fillQueryEvidence(){
  var el=document.getElementById('query-evidence');
  if(el){
    var rows=D.query_evidence||[];
    var hasDongSource=rows.some(function(row){
      return /Dong 2023/i.test(String(((row||{}).panel_context||{}).annotation||''));
    });
    var dongSourceLink='<a class="dblink" href="https://doi.org/10.1126/science.add8655" target="_blank" rel="noopener noreferrer">'+
      '<span class="en">Dong et al. 2023</span><span class="cn">Dong 等 2023</span></a>';
    var h='<div class="info-box"><strong>'+bi(
      'Query genotype evidence','查询样本基因型证据')+'</strong> · '+scopeLabel('Query-derived')+
      '<br>'+bi(
      'Observed calls for this query come first. They are not a phenotype call.',
      '先看本查询样本的实际分型；这不是表型判定。')+
      '<div class="ev-sub"><strong>'+bi(
      'Panel annotation / model context','面板注释 / 模型背景')+'</strong> · '+bi(
      'OIV, gene, GO, UniProt, MAS/GWAS, and panel-GWAS labels describe the reference panel; they do not become a phenotype for this sample. curated MAS/GWAS tag = chip tag from MAS_LOCI. panel GWAS lead = EMMAX/P3D lead in a 2449-panel window.',
      'OIV、基因、GO、UniProt、MAS/GWAS 和 panel GWAS 标签描述参考面板；不会因此变成本样品的表型。策展 MAS/GWAS 标签来自 MAS_LOCI；panel GWAS 主位点是 2449 面板窗口中的 EMMAX/P3D lead。')+
      '</div></div>';
    if(hasDongSource) h+='<div class="ev-sub">'+dongSourceLink+' · '+bi(
      'Source context for the published MAS/GWAS annotation.',
      '已发表 MAS/GWAS 注释的来源背景。')+'</div>';
    h+='<div class="table-scroll"><table><caption>'+bi(
      'Query genotype evidence','查询样本基因型证据')+'</caption><thead><tr>'+
      '<th scope="col">'+bi('Site','位点')+'</th>'+
      '<th scope="col">'+bi('Evidence','证据')+'</th>'+
      '<th scope="col">'+bi('Query GT','查询基因型')+'</th>'+
      '<th scope="col">'+bi('Status','状态')+'</th>'+
      // Panel context (2449 panel) is the legacy alias for this scoped column.
      '<th scope="col">'+bi('Panel annotation / model context','面板注释 / 模型背景')+'</th>'+
      '<th scope="col">'+bi('Trait / gene / links','性状 / 基因 / 链接')+'</th>'+
      '<th scope="col">'+bi('Evidence scope','证据范围')+'</th>'+
      '</tr></thead><tbody>';
    var evidenceReasons=[];
    ['selection_locus_gt','gwas_locus_gt'].forEach(function(key){
      var reason=D.method_coverage&&D.method_coverage[key]&&D.method_coverage[key].unavailable_reason;
      if(reason && evidenceReasons.indexOf(reason)<0) evidenceReasons.push(reason);
    });
    if(!rows.length) h+='<tr><td colspan="7">'+unavailableMessage(
      evidenceReasons.join(' · ')||'no query evidence rows')+'</td></tr>';
    rows.forEach(function(r){
      var gt=lzGtExplain(r.query_gt);
      h+='<tr><td><code>'+esc(r.site||'')+'</code></td><td>'+evidenceTypeHtml(r.evidence)+
        '</td><td>'+lzGtPill(r.query_gt)+'<span class="ev-sub">'+bi(esc(gt.en||''),esc(gt.cn||''))+'</span></td><td>'+
        queryCallStatusHtml(r.call_status)+
        '</td><td>'+evidenceContextHtml(r)+'</td><td>'+evidenceTraitHtml(r)+
        '</td><td>'+scopeLabel('Query-derived')+'</td></tr>';
    });
    h+='</tbody></table></div>';
    el.innerHTML=h;
  }
  var pe=document.getElementById('gs-pred');
  if(!pe) return;
  var predictions=D.gs_pred||[];
  var gsReason=(D.method_coverage&&D.method_coverage.gs||{}).unavailable_reason||'No per-query GS prediction available.';
  var ph='<div class="info-box"><strong>'+bi('How to read the scores.','怎么读这些分数。')+'</strong> ';
  ph+=bi(
    '<strong>Binary / ordinal scale</strong>: '+
    'Model score, not probability or observed phenotype. Binary and ordinal scores remain on their training scale. coverage is query genotype coverage; panel CV r is local panel cross-validation. <em>binary</em> = 0/1 case–control (Kang et al. 2010, doi:10.1038/ng.548). <em>ordinal</em> = OIV ordered grades; 0 recorded missing. Flag <code>ok</code> is a panel-CV flag. OIV 225 is currently rankable under this report policy based on the row-specific panel CV r. All values are model scores requiring phenotype validation. OIV links: EU-Vitis descriptor PDFs and the OIV 2009 list.',
    '<strong>二元 / 有序尺度</strong>：'+
    '模型分数，不是概率或观测表型。二元/有序分数仍在训练集尺度上。coverage 是本查询位点覆盖率；panel 交叉验证 r 是本地 panel 交叉验证。<em>binary</em>=0/1 病例对照（Kang 等 2010，doi:10.1038/ng.548）。<em>ordinal</em>=OIV 有序等级；0 记缺失。flag <code>ok</code> 是 panel CV 标记。OIV 225 目前按本报告策略可排序，依据各行 panel 交叉验证 r。所有数值均为模型分数，需表型验证。OIV 外链：EU-Vitis 描述符 PDF 与 OIV 2009 清单。')+'</div>';
  ph+='<table><caption>'+bi('Per-query genomic prediction','本查询基因组预测')+'</caption><thead><tr>'+
    '<th scope="col">'+bi('Trait','性状')+'</th>'+
    '<th scope="col">'+bi('Scale','尺度')+'</th>'+
    '<th scope="col">'+bi('Model score','模型分数')+'</th>'+
    '<th scope="col">'+bi('Coverage','覆盖度')+'</th>'+
    '<th scope="col">'+bi('panel CV r','panel 交叉验证 r')+'</th>'+
    '<th scope="col">'+bi('Flag','标记')+'</th>'+
    '<th scope="col">'+bi('Note','说明')+'</th>'+
    '<th scope="col">'+bi('Scope','范围')+'</th>'+
    '</tr></thead><tbody>';
  if(!predictions.length){
    ph+='<tr><td colspan="8">'+unavailableMessage(gsReason)+'</td></tr>';
  }else{
    predictions.forEach(function(r){
      var pred=r.pred==null||r.pred===''?'—':fmtNum(Number(r.pred),3);
      var coverage=r.coverage==null||r.coverage===''?'—':
        (Number(r.coverage)>=0&&Number(r.coverage)<=1?fmtNum(Number(r.coverage)*100,1)+'%':esc(String(r.coverage)));
      var cvR=r.cv_r==null||r.cv_r===''?'—':fmtNum(Number(r.cv_r),3);
      ph+='<tr><td>'+oivTraitHtml(r.trait||'')+'</td><td>'+scaleHtml(r.scale)+
        '</td><td>'+esc(pred)+'</td><td>'+esc(coverage)+'</td><td>'+esc(cvR)+
        '</td><td>'+gsFlagHtml(r.flag)+'</td><td>'+(gsTraitNote(r)||'—')+'</td><td>'+
        scopeLabel('Query-derived')+'</td></tr>';
    });
  }
  ph+='</tbody></table>';
  pe.innerHTML=ph;
}
function fillExtra(){
  var dmg=asDamage(D.damage);
  var de=document.getElementById('damage-note');
  if(isModernLibrary()){
    applyDamageSectionState();
    if(de) de.textContent='';
  } else if(de){
    if(dmg){
      var ct1=(dmg.ct5&&dmg.ct5.length)?Number(dmg.ct5[0]):NaN;
      var ga1=(dmg.ga3&&dmg.ga3.length)?Number(dmg.ga3[0]):NaN;
      var rawSrc=dmg.source==='mapDamage2'
        ? ('mapDamage2'+(dmg.version?(' '+dmg.version):''))
        : (dmg.source||'damage profile');
      var srcZh=dmg.source==='mapDamage2'
        ? rawSrc
        : (dmg.source||'损伤谱');
      var bits=[sourceDamageLabel(), bi(esc(rawSrc),esc(srcZh))];
      if(isFinite(ct1)) bits.push(bi(
        '5′ C→T pos1='+(100*ct1).toFixed(2)+'%',
        '5′ C→T 第1位='+(100*ct1).toFixed(2)+'%'));
      if(isFinite(ga1)) bits.push(bi(
        '3′ G→A pos1='+(100*ga1).toFixed(2)+'%',
        '3′ G→A 第1位='+(100*ga1).toFixed(2)+'%'));
      de.innerHTML=bits.join(' · ');
    } else {
      var raw=D.damage||{};
      var emptyBits=[sourceDamageLabel()];
      if(raw && !Array.isArray(raw) && (raw.source||raw.version)){
        var emptySrc=raw.source==='mapDamage2'
          ? ('mapDamage2'+(raw.version?(' '+raw.version):''))
          : (raw.source||'damage profile');
        var emptySrcZh=raw.source==='mapDamage2'
          ? emptySrc
          : (raw.source||'损伤谱');
        emptyBits.push(bi(esc(emptySrc),esc(emptySrcZh)));
      }
      emptyBits.push(bi(
        'No damage profile. Ancient libraries need a BAM; chip recapture usually has none.',
        '没有损伤谱。古 DNA 文库需要 BAM；芯片重捕获通常没有。'));
      de.innerHTML=emptyBits.join(' · ');
    }
  }
  var tr=D.panel_trait_catalog||D.traits||[];
  var th='<div class="table-scroll"><table><caption>'+bi(
    'Panel trait-locus annotations','面板性状位点注释')+'</caption><thead><tr>'+
    '<th scope="col">'+bi('Site','位点')+'</th>'+
    '<th scope="col">'+bi('Trait','性状')+'</th>'+
    '<th scope="col">'+bi('Descriptor','描述符')+'</th>'+
    '<th scope="col">'+bi('Gene','基因')+'</th>'+
    '<th scope="col">'+bi('Product','产物')+'</th>'+
    '<th scope="col">GO</th><th scope="col">Pfam</th><th scope="col">KEGG</th>'+
    '<th scope="col">'+bi('Vitis','葡萄 ID')+'</th>'+
    '<th scope="col">'+bi('Distance','距离')+'</th>'+
    '<th scope="col">'+bi('Region','区域')+'</th>'+
    '<th scope="col">'+bi('Strand','链')+'</th>'+
    '<th scope="col">'+bi('Alias','别名')+'</th>'+
    '<th scope="col">'+bi('Note','备注')+'</th>'+
    '</tr></thead><tbody>';
  if(!tr.length) th+='<tr><td colspan="14">'+bi(
    'No trait overlaps','没有性状位点重合')+'</td></tr>';
  tr.forEach(function(t){
    th+='<tr><td>'+esc(t.site||'')+'</td><td>'+oivTraitHtml(t.trait||'')+'</td><td>'+oivDescHtml(t)+
      '</td><td>'+esc(t.gene||'')+'</td><td>'+prodCell(t)+
      '</td><td>'+dbLinks('go',t.go,6)+'</td><td>'+dbLinks('pfam',t.pfam,4)+
      '</td><td>'+keggCellHtml(t)+'</td><td>'+vitisCellHtml(t)+
      '</td><td>'+esc(String(t.dist==null?'':t.dist))+
      '</td><td>'+esc(t.region||'')+'</td><td>'+esc(t.strand||'')+
      '</td><td>'+esc(t.alias||'')+'</td><td>'+traitNoteHtml(t.note)+'</td></tr>';
  });
  th+='</tbody></table></div>';
  var te=document.getElementById('trait-table'); if(te) te.innerHTML=th;
  var be=document.getElementById('breeding-note');
  if(be){
    var statusEn='', statusZh='';
    if(D.gwas_skip){
      statusEn=String(D.gwas_skip);
      statusZh=statusEn.replace(
        /^GWAS\/GS using precomputed results\/gwas\/index\.tsv \(empty\)\. phenotype\.tsv lines≈/i,
        'GWAS/GS 使用预计算 results/gwas/index.tsv（为空）。phenotype.tsv 行数约为 '
      ).replace(/\. Uti is not a breeding trait\.$/i,'。Uti 不是育种性状。');
    }else if((D.gwas_index||[]).length){
      statusEn='Precomputed GWAS traits: '+D.gwas_index.length;
      statusZh='预计算 GWAS 性状：'+D.gwas_index.length;
    }else{
      statusEn='GWAS/GS awaiting a phenotype table (≥50 panel IDs).';
      statusZh='GWAS/GS 等待表型表（至少 50 个 panel ID）。';
    }
    be.innerHTML=bi(esc(statusEn),esc(statusZh));
  }
  var gi=(D.gwas_index||[]);
  var hasBinary=gi.some(function(r){return String(r.scale||'').toLowerCase()==='binary';});
  var gh='';
  if(hasBinary) gh+='<p class="muted">'+bi(
    'Binary traits use the EMMAX/LMM convention described by Kang et al. 2010 (https://doi.org/10.1038/ng.548); imbalanced binary traits need caution.',
    '二元性状采用 Kang 等 2010 描述的 EMMAX/LMM 约定（https://doi.org/10.1038/ng.548）；病例对照不平衡时需谨慎。')+'</p>';
  gh+='<div class="table-scroll"><table><caption>'+bi('Panel GWAS summary','panel GWAS 汇总')+'</caption><thead><tr>'+
    '<th scope="col">'+bi('Source','来源')+'</th>'+
    '<th scope="col">'+bi('Trait','性状')+'</th>'+
    '<th scope="col">'+bi('Scale','尺度')+'</th>'+
    '<th scope="col">'+bi('Descriptor','描述符')+'</th>'+
    '<th scope="col">n</th>'+
    '<th scope="col">'+bi('Cases','病例数')+'</th>'+
    '<th scope="col">'+bi('Controls','对照数')+'</th>'+
    '<th scope="col">λ</th>'+
    '<th scope="col">'+bi('Bonferroni n','Bonferroni 数')+'</th>'+
    '<th scope="col">'+bi('Top site','主位点')+'</th>'+
    '<th scope="col">'+bi('Gene','基因')+'</th>'+
    '<th scope="col">'+bi('Region','区域')+'</th>'+
    '<th scope="col">'+bi('Overlap','重合')+'</th>'+
    '</tr></thead><tbody>';
  if(!gi.length) gh+='<tr><td colspan="13">'+bi(
    'No GWAS index','没有 GWAS 索引')+'</td></tr>';
  gi.forEach(function(r){
    var gtxt=esc(r.top_gene||'')+(r.top_alias?(' / '+esc(r.top_alias)):'');
    if(r.top_product) gtxt+=' · '+esc(r.top_product);
    if(r.top_uniprot) gtxt+=' · '+dbLink('uniprot', r.top_uniprot);
    var db=[dbLinks('go',r.top_go,3),dbLinks('pfam',r.top_pfam,3),keggCellHtml(r),vitisCellHtml(r)].filter(Boolean);
    if(db.length) gtxt+=' · '+db.join(' · ');
    gh+='<tr class="clickrow" role="button" tabindex="0" data-slug="'+esc(r.slug||'')+'"><td>'+esc(r.source||'')+'</td><td>'+oivTraitHtml(r.trait||'')+
      '</td><td>'+esc(r.scale||'')+'</td><td>'+oivDescHtml(r)+'</td><td>'+esc(r.n==null?'':r.n)+
      '</td><td>'+(r.case_n==null?'—':esc(r.case_n))+'</td><td>'+(r.control_n==null?'—':esc(r.control_n))+
      '</td><td>'+esc(String(r.lambda||'').slice(0,6))+'</td><td>'+esc(r.n_bonf==null?'':r.n_bonf)+
      '</td><td>'+esc(r.top_chrom||'')+':'+esc(r.top_pos||'')+
      '</td><td>'+gtxt+'</td><td>'+esc(r.top_region||'')+'</td><td>'+esc(r.trait_locus_overlap||'')+'</td></tr>';
  });
  gh+='</tbody></table></div>';
  var ge=document.getElementById('gwas-index'); if(ge) ge.innerHTML=gh;
  if(ge){
    ge.querySelectorAll('.clickrow[data-slug]').forEach(function(row){
      row.addEventListener('click', function(){
        var slug=row.getAttribute('data-slug')||'';
        var idx=(D.gwas_loci||[]).findIndex(function(r){ return r.slug===slug; });
        if(idx>=0) setLz(idx);
      });
    });
  }
  var lz=(D.gwas_loci||[]);
  var sel=document.getElementById('lz-pick');
  if(sel){
    sel.innerHTML='';
    lz.forEach(function(r,i){
      var o=document.createElement('option');
      o.value=String(i);
      o.textContent=(r.trait||'')+' · '+(r.chrom||'')+':'+(r.pos||'')+
        (r.gene?(' '+r.gene):'')+(r.gene_alias?(' / '+r.gene_alias):'')+
        ' (n='+(r.n_snps||(r.snps&&r.snps.pos||[]).length||'')+')';
      sel.appendChild(o);
    });
    sel.onchange=function(){ setLz(parseInt(sel.value,10)||0); };
    if(lz.length) sel.value=String(lzIdx);
  }
  drawLocusZoom();
  var gs=(D.gs_index||[]);
  var gsh='<div class="table-scroll"><table><caption>'+bi(
    'Panel GS model index','面板 GS 模型索引')+'</caption><thead><tr>'+
    '<th scope="col">'+bi('Source','来源')+'</th>'+
    '<th scope="col">'+bi('Trait','性状')+'</th>'+
    '<th scope="col">'+bi('Best model','最佳模型')+'</th>'+
    '<th scope="col">'+bi('panel CV r','panel 交叉验证 r')+'</th>'+
    '<th scope="col">n</th></tr></thead><tbody>';
  if(!gs.length) gsh+='<tr><td colspan="5">'+bi(
    'No GS index','没有 GS 索引')+'</td></tr>';
  gs.forEach(function(r){
    gsh+='<tr><td>'+esc(r.source||'')+'</td><td>'+oivTraitHtml(r.trait||'')+'</td><td>'+esc(r.best_model||'')+
      '</td><td>'+esc(r.cv_r||'')+'</td><td>'+esc(r.n==null?'':r.n)+'</td></tr>';
  });
  gsh+='</tbody></table></div>';
  var gse=document.getElementById('gs-index'); if(gse) gse.innerHTML=gsh;
  var cr=D.cross_top||[];
  var ch='<div class="table-scroll"><table><caption>'+bi(
    'Top crosses','推荐杂交组合')+'</caption><thead><tr>'+
    '<th scope="col">'+bi('Parent 1','亲本 1')+'</th>'+
    '<th scope="col">'+bi('Parent 2','亲本 2')+'</th>'+
    '<th scope="col">'+bi('Index','指数')+'</th>'+
    '<th scope="col">'+bi('Kinship','亲缘')+'</th></tr></thead><tbody>';
  if(!cr.length) ch+='<tr><td colspan="4">'+bi(
    'No recommendation attached to this query report',
    '本查询报告未附杂交组合推荐')+'</td></tr>';
  cr.forEach(function(r){
    ch+='<tr><td>'+esc(r.p1||'')+'</td><td>'+esc(r.p2||'')+'</td><td>'+esc(String(r.index||'').slice(0,6))+
      '</td><td>'+esc(String(r.kinship||'').slice(0,6))+'</td></tr>';
  });
  ch+='</tbody></table></div>';
  var ce=document.getElementById('cross-top'); if(ce) ce.innerHTML=ch;
  var mh=document.getElementById('methods-embed');
  if(mh && D.methods_html){
    mh.innerHTML=sanitizeReportHtml(D.methods_html);
  }

  var dl=(D.downloads||[]).filter(allowQueryDownload);
  var dh='<div class="info-box"><strong>'+bi(
    'Downloads are query-only','下载仅限查询样本')+'</strong> · '+bi(
    'Missing query sidecars do not indicate analysis failure.',
    '查询 sidecar 缺失不表示分析失败。')+'</div>';
  dl.forEach(function(x){dh+='<a class="dllink" href="'+esc(x.href||'')+'" download>'+
    downloadLabelHtml(x.label||x.href)+'</a> ';});
  if(!dl.length) dh+='<span class="muted">'+bi(
    'No query sidecars yet.','暂未生成查询样本 sidecar。')+'</span>';
  var dle=document.getElementById('downloads'); if(dle) dle.innerHTML=dh;
  var pe=document.getElementById('purity-note');
  if(pe){
    if(!D.purity) pe.innerHTML='';
    else {
      var purity=formatPurityDisplay(D.purity);
      pe.innerHTML=bi(esc(purity.en),esc(purity.zh));
    }
  }
}

function identityLabel(rel){
  var key=String(rel||'');
  var labels={
    'Identical':['Identical','完全相同'],
    'Parent-Offspring':['Parent-Offspring','亲子'],
    'Full Sib':['Full Sib','全同胞'],
    '2nd':['2nd','二级亲缘'],
    '3rd':['3rd','三级亲缘'],
    'Unrelated':['Unrelated','无关'],
    'author match':['author match','作者记录匹配']
  };
  return labels[key]?bi(labels[key][0],labels[key][1]):esc(key||'—');
}
function fillCloneTable(){
  var rows=D.clones||[];
  var h='<div class="table-scroll"><table><tr><th>'+bi('Class','关系类别')+'</th><th>'+bi('Ref','参考样本')+'</th><th>R1</th><th>KING</th></tr>';
  if(!rows.length)h+='<tr><td colspan=4>'+bi('No Identical/PO hits','没有 Identical/PO 命中')+'</td></tr>';
  rows.forEach(function(r){
    h+='<tr class="clickrow" data-iid="'+esc(r.ref)+'"><td>'+identityLabel(r.rel)+'</td><td>'+
      sampleCell(r.ref)+'</td><td>'+esc(r.r1)+'</td><td>'+esc(r.king)+'</td></tr>';
  });
  h+='</table></div>';
  var el=document.getElementById('clone-table'); if(el){el.innerHTML=h;bindRowClicks(el);}
  var sm=D.ibs_summary||{};
  var sh='<div class="table-scroll"><table><tr><th>'+bi('Class','关系类别')+'</th><th>'+bi('Count','数量')+'</th></tr>';
  var keys=['Identical','Parent-Offspring','Full Sib','2nd','3rd','Unrelated'];
  keys.forEach(function(k){ if(sm[k]!=null) sh+='<tr><td>'+identityLabel(k)+'</td><td>'+esc(sm[k])+'</td></tr>'; });
  Object.keys(sm).forEach(function(k){ if(keys.indexOf(k)<0) sh+='<tr><td>'+identityLabel(k)+'</td><td>'+esc(sm[k])+'</td></tr>'; });
  sh+='</table></div>';
  var se=document.getElementById('ibs-summary'); if(se) se.innerHTML=sh;
}

function fillIbsKinship(){
  var rows=D.ibs_top||[];
  var hit=window._authorMatchIds||[];
  var h='<div class="table-scroll"><table><tr><th>#</th><th>'+bi('Ref','参考样本')+'</th><th>'+bi('Rel','关系')+'</th><th>R1</th><th>KING</th><th>IBS2*%</th></tr>';
  if(!rows.length) h+='<tr><td colspan=6>'+bi('No IBS matches','没有 IBS 近邻')+'</td></tr>';
  rows.forEach(function(r,i){
    var mark=hit.indexOf(r.ref)>=0;
    h+='<tr class="clickrow'+(mark?' author-hit':'')+'" data-iid="'+esc(r.ref)+'"><td>'+(i+1)+'</td><td>'+
      sampleCell(r.ref)+'</td><td>'+identityLabel(r.rel)+(mark?' <span class="author-src">'+identityLabel('author match')+'</span>':'')+'</td><td>'+esc(r.r1)+'</td><td>'+
      esc(r.king)+'</td><td>'+esc(r.ibs2p)+'</td></tr>';
  });
  h+='</table></div>';
  var el=document.getElementById('ibs-table'); if(el){el.innerHTML=h;bindRowClicks(el);}
  var kr=D.kinship_top||[];
  var kh='<div class="table-scroll"><table><tr><th>'+bi('Rank','排名')+'</th><th>'+bi('Ref','参考样本')+'</th><th>'+bi('Rel','关系')+'</th><th>KING</th><th>IBS</th><th>n</th></tr>';
  if(!kr.length) kh+='<tr><td colspan=6>'+bi('No kinship matches','没有亲缘近邻')+'</td></tr>';
  kr.forEach(function(r){
    var mark=hit.indexOf(r.ref)>=0;
    kh+='<tr class="clickrow'+(mark?' author-hit':'')+'" data-iid="'+esc(r.ref)+'"><td>'+esc(r.rank)+'</td><td>'+
      sampleCell(r.ref)+'</td><td>'+identityLabel(r.rel)+(mark?' <span class="author-src">'+identityLabel('author match')+'</span>':'')+'</td><td>'+esc(r.king)+'</td><td>'+
      esc(r.ibs)+'</td><td>'+esc(r.n)+'</td></tr>';
  });
  kh+='</table></div>';
  var ke=document.getElementById('kinship-table'); if(ke){ke.innerHTML=kh;bindRowClicks(ke);}
}

function fillSelFstats(){
  var named=D.selection_named||[];
  var by=D.selection_by_grp||[];
  var h='';
  if(named.length){
    h+='<h3>'+bi('Table A · 5 named windows (whole 2449 panel)',
      '表 A · 5 个命名窗口（整个 2449 面板）')+'</h3>';
    h+='<p class="muted" style="font-size:11px;margin:4px 0 8px">'+bi(
      'One row = one window from the box above. mean het / Fst among all Grps = average of chip SNPs inside that interval, using <strong>all 2449 samples together</strong>. Same numbers as the green stars on the scatter. Click a row → LocusZoom.',
      '一行=一个命名窗口。均值是窗口内芯片位点、2449 个样品合在一起算的（全体 Grp 的 Fst），和散点图绿星同一套数。点一行跳 LocusZoom。')+'</p>';
    h+='<div class="table-scroll"><table><caption>'+bi(
      'Active panel computation · named-window summary','当前面板计算 · 命名窗口汇总')+
      '</caption><thead><tr><th scope="col">'+bi('Window','窗口')+
      '</th><th scope="col">'+bi('Interval','区间')+'</th><th scope="col">'+bi(
        'n SNPs','SNP 数')+      '</th><th scope="col">'+bi('mean het','平均杂合')+
      '</th><th scope="col">'+bi('Fst among all Grps','全体 Grp 的 Fst')+'</th></tr></thead><tbody>';
    named.forEach(function(r){
      h+='<tr class="clickrow" data-sel-slug="'+esc(r.name||'')+'"><td>'+esc(r.name||'')+'</td><td>'+esc(String(r.chrom||'')+':'+String(r.start||'')+'-'+String(r.end||''))+
        '</td><td>'+esc(String(r.n_sites||''))+'</td><td>'+esc(String(r.mean_het||''))+
        '</td><td>'+esc(String(r.mean_fst||''))+'</td></tr>';
    });
    h+='</tbody></table></div>';
  }
  if(by.length){
    h+='<h3>'+bi('Table B · same 5 windows, one row per Grp',
      '表 B · 同 5 个窗口，每个 Grp 一行')+'</h3>';
    h+='<p class="muted" style="font-size:11px;margin:4px 0 8px">'+bi(
      'Same five windows as Table A, split by 2449 panel Grp (12 groups × 5 windows). mean het = heterozygosity <em>inside that Grp only</em>. simplified Fst (Grp vs rest) = that Grp versus everyone else. Same numbers as the heatmap. Query genotype overlay is shown separately in Table C.',
      '还是那五个窗口，按 2449 panel 的 Grp 拆开（12 组 × 5 窗口）。杂合=只在该组内；简化 Fst（Grp 对其余样品）=该组对其余样品。和热图同一套数。查询样本基因型叠加单列在表 C。')+'</p>';
    h+='<div class="table-scroll"><table><caption>'+bi(
      'Active panel computation · by-Grp window statistics','当前面板计算 · 按 Grp 的窗口统计')+
      '</caption><thead><tr><th scope="col">'+bi('Grp','组别')+'</th><th scope="col">'+bi(
        'n vines','样本数')+'</th><th scope="col">'+bi('Window','窗口')+
      '</th><th scope="col">'+bi('n SNPs','SNP 数')+'</th><th scope="col">'+bi(
        'mean windowed heterozygosity in Grp','Grp 内平均窗口杂合度')+'</th><th scope="col">'+bi(
        'simplified Fst (Grp vs rest)','简化 Fst（Grp 对其余样品）')+'</th></tr></thead><tbody>';
    by.forEach(function(r){
      h+='<tr><td>'+esc(r.grp||'')+'</td><td>'+esc(String(r.n_samples||''))+'</td><td>'+esc(r.name||'')+
        '</td><td>'+esc(String(r.n_sites||''))+'</td><td>'+esc(String(r.mean_het||''))+
        '</td><td>'+esc(String(r.mean_fst_vs_rest||r.mean_fst||''))+'</td></tr>';
    });
    h+='</tbody></table></div>';
  }
  var se=document.getElementById('sel-table'); if(se) se.innerHTML=h;
  if(se){
    se.querySelectorAll('[data-sel-slug]').forEach(function(row){
      row.addEventListener('click', function(){ setSelLzBySlug(row.getAttribute('data-sel-slug')||''); });
    });
  }
  fillSelScienceRef();
  var lz=(D.selection_loci||[]);
  var pick=document.getElementById('sel-lz-pick');
  if(pick){
    pick.innerHTML='';
    lz.forEach(function(r,i){
      if(!selLocusPrimary(r)) return;
      var o=document.createElement('option');
      o.value=String(i);
      o.textContent=(r.kind||r.trait||'')+' · '+(r.slug||'')+' · '+(r.chrom||'')+':'+(r.pos||'')+' (n='+(r.n_snps||'')+')';
      pick.appendChild(o);
    });
    pick.onchange=function(){ setSelLz(parseInt(pick.value,10)||0); };
    if(!selLocusPrimary(lz[selLzIdx])){
      var fi=lz.findIndex(selLocusPrimary);
      if(fi>=0) selLzIdx=fi;
    }
    if(lz.length) pick.value=String(selLzIdx);
  }
  var met=document.getElementById('sel-lz-metric');
  if(met){
    met.value=selLzMetric||'fst';
    met.onchange=function(){ selLzMetric=met.value||'fst'; drawSelLocusZoom(); };
  }
  var mm=document.getElementById('sel-manh-metric');
  if(mm){
    mm.value=selManhMetric||'fst';
    mm.onchange=function(){
      selManhMetric=mm.value||'fst';
      drawSelManhattan();
    };
  }
  var mg=document.getElementById('sel-manh-grp');
  if(mg){
    var keys=Object.keys((D.selection_manhattan||{}).fst_by_grp||{});
    mg.innerHTML='';
    keys.forEach(function(g){
      var o=document.createElement('option');
      o.value=g; o.textContent=t(g+' · simplified Fst (Grp vs rest)',g+' · 简化 Fst（Grp 对其余样品）');
      mg.appendChild(o);
    });
    var o0=document.createElement('option');
    o0.value='overall'; o0.textContent=t(
      'Fst among all Grps','全体 Grp 的 Fst');
    mg.appendChild(o0);
    if(!selManhGrp || (selManhGrp!=='overall' && keys.indexOf(selManhGrp)<0)) selManhGrp=keys[0]||'overall';
    if(selManhGrp==='overall' || keys.indexOf(selManhGrp)>=0) mg.value=selManhGrp;
    selManhGrp=mg.value||keys[0]||'overall';
    mg.onchange=function(){ selManhGrp=mg.value||'overall'; drawSelManhattan(); };
  }
  var hm=document.getElementById('sel-heat-metric');
  if(hm){
    hm.value=selHeatMetric||'fst';
    hm.onchange=function(){ selHeatMetric=hm.value||'fst'; drawSelHeat(); };
  }
  drawSelLocusZoom();
  drawSelManhattan();
  drawSelHeat();
  drawSelScatter();
  fillSelQuerySites();
  var f3=D.f3||[], f4=D.f4||[], f3out=D.f3_out||[];
  fillFstatsCallout(f3out, f3, f4);
  var fstatsTableHtml='<div class="three-col">';
  fstatsTableHtml+=fstatColTable('Outgroup-f3  f3(OUT; Q, Grp)', ['Grp','f3','SE','Z','n_sites','n_blocks'],
    f3out.slice().sort(function(a,b){
      var av=Number(a.value), bv=Number(b.value);
      if(!Number.isFinite(av)) return Number.isFinite(bv)?1:0;
      if(!Number.isFinite(bv)) return -1;
      return bv-av;
    }),
    function(r){ return [r.grp||r.b||r.label, r.value, r.se, r.z, r.n_sites, r.n_blocks]; });
  fstatsTableHtml+=fstatColTable('Pairwise f3  f3(Q; A, B)', ['A','B','f3','SE','Z','n_sites','n_blocks'],
    f3, function(r){ return [r.a, r.b, r.value, r.se, r.z, r.n_sites, r.n_blocks]; });
  fstatsTableHtml+=fstatColTable('Pairwise f4  f4(Q, OUT; A, B)', ['A','B','f4','SE','Z','n_sites','n_blocks'],
    f4, function(r){ return [r.a, r.b, r.value, r.se, r.z, r.n_sites, r.n_blocks]; });
  fstatsTableHtml+='</div>';
  var te=document.getElementById('fstats-tables'); if(te) te.innerHTML=fstatsTableHtml;
  drawF3Out(f3out);
  drawFstatBars('plot-f4', f4, t('Pairwise f4  f4(Q, OUT; A, B)','成对 f4  f4(Q, OUT; A, B)'), function(r){return (r.a||'')+' vs '+(r.b||'');}, true);
  drawFstatBars('plot-f3', f3, t('Pairwise f3  f3(Q; A, B)','成对 f3  f3(Q; A, B)'), function(r){return (r.a||'')+' vs '+(r.b||'');}, true);
}

function fstatColTable(title, heads, rows, cells){
  var h='<div class="table-scroll"><h3>'+esc(fstatDisplayLabel(title))+'</h3><table><tr style="color:var(--muted)">';
  heads.forEach(function(x){ h+='<th>'+esc(fstatDisplayLabel(x))+'</th>'; });
  h+='</tr>';
  if(!rows||!rows.length) h+='<tr><td colspan="'+heads.length+'">—</td></tr>';
  (rows||[]).forEach(function(r){
    var c=cells(r);
    h+='<tr>';
    c.forEach(function(v,i){
      var name=heads[i];
      if(name==='GEO'||name==='Grp'||name==='A'||name==='B') h+='<td>'+esc(v==null?'':v)+'</td>';
      else h+='<td>'+esc(fmtNum(v, name==='Z'?2:5))+'</td>';
    });
    h+='</tr>';
  });
  return h+'</table></div>';
}
function fstatDisplayLabel(value){
  var raw=String(value==null?'':value);
  var labels={
    'Outgroup-f3  f3(OUT; Q, Grp)':['Outgroup-f3  f3(OUT; Q, Grp)','外群 f3  f3(OUT; Q, Grp)'],
    'Pairwise f3  f3(Q; A, B)':['Pairwise f3  f3(Q; A, B)','成对 f3  f3(Q; A, B)'],
    'Pairwise f4  f4(Q, OUT; A, B)':['Pairwise f4  f4(Q, OUT; A, B)','成对 f4  f4(Q, OUT; A, B)'],
    'Grp':['Grp','组别'],
    'SE':['SE','SE（标准误）'],
    'n_sites':['n_sites','n_sites（有效位点）'],
    'n_blocks':['n_blocks','n_blocks（染色体块）']
  };
  var pair=labels[raw]||[raw,raw];
  return t(pair[0],pair[1]);
}
function _fstatGroups(rows){
  var g=[];
  (rows||[]).forEach(function(r){
    ['a','b','grp'].forEach(function(k){
      var x=r[k];
      if(x && x!=='OUT' && g.indexOf(x)<0) g.push(x);
    });
  });
  return g;
}

function drawFstatBars(id, rows, title, labFn, signed){
  var el=document.getElementById(id);
  if(!el) return;
  if(plotlyUnavailable(el, title)) return;
  resetPlot(el);
  if(!rows||!rows.length){
    var safeTitle=esc(String(title||'this contrast'));
    el.innerHTML='<div class="muted" style="padding:12px">'+bi(
      'No '+safeTitle+' rows',
      '没有 '+safeTitle+' 数据行')+'</div>';
    return;
  }
  var ord=rows.slice().sort(function(a,b){return (Number(a.value)||0)-(Number(b.value)||0);});
  var y=ord.map(labFn);
  var x=ord.map(function(r){return r.value;});
  var se=ord.map(function(r){ var s=r.se; return (s==null||s!==s)?0:s; });
  var col=ord.map(function(r){
    if(signed){
      var v=Number(r.value);
      if(!(v===v)) return '#94a3b8';
      return v>=0?'#b2182b':'#2166ac';
    }
    var zz=r.z;
    if(zz==null||!isFinite(Number(zz))) return '#94a3b8';
    return Math.abs(zz)>=3?'#1d4ed8':'#94a3b8';
  });
  var fh=Math.max(320, 26*ord.length+90);
  Plotly.newPlot(el, [{
    type:'bar', orientation:'h',
    x:x, y:y,
    error_x:{type:'data', array:se, color:'#94a3b8', thickness:1, width:3},
    marker:{color:col},
    customdata:ord.map(function(r){return [r.se, r.z, r.n_sites, r.n_blocks];}),
    hovertemplate:'%{y}<br>'+title+'=%{x:.5f}<br>'+
      fstatDisplayLabel('SE')+'=%{customdata[0]:.5f}<br>Z=%{customdata[1]:.2f}<br>'+
      fstatDisplayLabel('n_sites')+'=%{customdata[2]}<br>'+
      fstatDisplayLabel('n_blocks')+'=%{customdata[3]}<extra></extra>'
  }], withPlotSize({
    title:title,
    height:fh,
    margin:{l:100,r:24,t:48,b:48},
    font:{color:themeTokens().text,size:11},
    xaxis:{zeroline:true, zerolinecolor:themeTokens().border, gridcolor:themeTokens()['plot-grid']},
    yaxis:{title:'', automargin:true, tickfont:{size:11}},
    showlegend:false
  }, el, fh), plotlyCfg({displayModeBar:false}));
}
function drawF3Out(rows){
  var el=document.getElementById('plot-f3-out');
  if(!el) return;
  if(!rows||!rows.length){
    resetPlot(el);
    el.innerHTML='<div class="muted" style="padding:12px">'+bi(
      'No outgroup-f3 (need OUT and Grp labels in the 2449 panel metadata).',
      '没有外群 f3（需要 2449 面板元数据中的 OUT 和 Grp 标签）。')+'</div>';
    return;
  }
  drawFstatBars('plot-f3-out', rows, t(
    'Outgroup-f3  f3(OUT; query, Grp)  ·  higher = more shared drift',
    '外群 f3  f3(OUT; query, Grp)  ·  越高 = 共享漂变越多'),
    function(r){return r.grp||r.b||r.label;}, false);
}
function drawFstatHeat(id, rows, title, signed, useZ){
  drawFstatBars(id, rows, title, function(r){return (r.a||'')+' vs '+(r.b||'');}, !!signed);
}

function fillFstatsCallout(f3out, f3, f4){
  var el=document.getElementById('fstats-callout');
  if(!el) return;
  var outN=Number(D.outgroup_n);
  var hasOut=Number.isFinite(outN)&&outN>0;
  function finiteFstatNumber(x){
    return x!==null&&x!==undefined&&x!==''&&Number.isFinite(Number(x));
  }
  function finiteFstatRow(r){
    return r&&finiteFstatNumber(r.value)&&finiteFstatNumber(r.z);
  }
  var best=hasOut?(f3out||[]).filter(finiteFstatRow).sort(function(a,b){
    return Number(b.value)-Number(a.value);
  })[0]:null;
  var hit=hasOut?(f4||[]).filter(finiteFstatRow).sort(function(a,b){
    return Math.abs(Number(b.z))-Math.abs(Number(a.z));
  })[0]:null;
  var bits=[];
  if(best){
    bits.push(bi(
      'Highest shared drift: <strong>'+esc(best.grp||best.b||'')+'</strong> (f3='+fmtNum(best.value,4)+
      ', Z='+fmtNum(best.z,1)+'). Higher = closer to that Grp mean.',
      '共享漂变最高：<strong>'+esc(best.grp||best.b||'')+'</strong>（f3='+fmtNum(best.value,4)+
      '，Z='+fmtNum(best.z,1)+'）。越高越接近该 Grp 均值。'));
  }
  if(hit){
    var closer=Number(hit.value)>=0?hit.a:hit.b;
    var other=Number(hit.value)>=0?hit.b:hit.a;
    bits.push(bi(
      'Largest |Z| f4: closer to <strong>'+esc(closer)+'</strong> than '+esc(other)+
      ' vs OUT (f4='+fmtNum(hit.value,4)+', Z='+fmtNum(hit.z,1)+').',
      '|Z| 最大的 f4：相对 OUT 更靠近 <strong>'+esc(closer)+'</strong> 而不是 '+esc(other)+'。'));
  }
  var outNote=hasOut?bi(
    'OUT is designated even when n<min_n; actual OUT n='+outN+
    '; it is not treated as satisfying min_n.',
    'OUT 已指定，即使 n<min_n；实际 OUT n='+outN+'，不视为满足 min_n。'):
    bi('No designated OUT was available; outgroup-f3/f4 are unavailable.',
      '没有可用的指定 OUT；外群 f3/f4 不可用。');
  if(!bits.length){
    var hasPairwiseF3=(f3||[]).length>0;
    var hasRawRows=(f3out||[]).length>0||hasPairwiseF3||(f4||[]).length>0;
    var neutral=!hasOut&&hasPairwiseF3?bi(
      'Outgroup-f3/f4 are unavailable.','外群 f3/f4 不可用。'):
      hasRawRows?bi('No finite statistic for this contrast.','该对比没有有限统计量。'):
      bi('No f3/f4 (need OUT in the 2449 panel metadata and query dosages).',
        '没有 f3/f4（需要 2449 面板中的 OUT 和查询样本 dosage）。');
    el.innerHTML='<div class="muted">'+neutral+'<br>'+outNote+
      '</div>';
    return;
  }
  bits.unshift(outNote);
  el.innerHTML=bits.map(function(s){ return '<p style="margin:6px 0">'+s+'</p>'; }).join('');
}

function fillSelQuerySites(){
  var el=document.getElementById('sel-query-sites');
  if(!el) return;
  var loci=D.selection_loci||[];
  var name=D.query||'query';
  var h='<div class="info-box"><strong>'+bi(
    'Query genotype overlay','查询样本基因型叠加')+'</strong> · '+scopeLabel(
    'Query vs 2449 panel')+'<br>'+bi(
    'Active panel computation: Fst values remain the 2449 panel map statistic; this table adds this sample’s observed genotype calls.',
    '当前面板计算：Fst 数值仍是 2449 面板统计量；本表另外展示本样品的实际分型。')+
    '<br>'+bi(
    'Panel map statistic is not a query phenotype or a query association test.',
    '面板统计量不是查询样本表型，也不是查询样本关联检验。')+'</div>';
  h+='<p class="muted">'+bi(
    'Table C · query genotype overlay at SNPs inside the named windows / Fst peaks. '+
      '<strong>This sample</strong> is '+esc(name)+'; Fst column is still the 2449 map. Click a row → LocusZoom.',
    '表 C：本查询样品在命名窗口 / Fst 峰里的芯片位点分型。'+
      '<strong>本样品</strong>是 '+esc(name)+'；Fst 列仍是 2449 地图。点一行跳 LocusZoom。')+'</p>';
  h+='<div class="table-scroll"><table><caption>'+bi(
    'Query genotype overlay at selection sites','选择位点的查询基因型叠加')+
    '</caption><thead><tr><th scope="col">'+bi('Window','窗口')+
    '</th><th scope="col">'+bi('Site','位点')+'</th><th scope="col">'+bi(
      'Alleles','等位基因')+'</th><th scope="col">'+bi('This sample','本样品')+
    '</th><th scope="col">Fst</th><th scope="col">'+bi('Gene','基因')+
    '</th><th scope="col">'+bi('Why','为什么看')+'</th></tr></thead><tbody>';
  var n=0;
  loci.forEach(function(r, li){
    if(!selLocusPrimary(r)) return;
    lzKeyGtIdx(r).forEach(function(row){
      var s=r.snps||{}, j=row.j;
      var alle=((s.ref&&s.ref[j])||'')+(((s.ref&&s.ref[j])&&(s.alt&&s.alt[j]))?'>':'')+((s.alt&&s.alt[j])||'');
      var gt=s.gt?lzGtPill(s.gt[j]):'<span class="muted">—</span>';
      h+='<tr class="clickrow" data-sel-li="'+li+'" data-gt-snp="'+j+'"><td>'+esc(r.slug||r.kind||'')+
        '</td><td>'+esc(s.site&&s.site[j]||'')+'</td><td>'+esc(alle)+'</td><td>'+gt+
        '</td><td>'+esc(fmtNum(s.fst&&s.fst[j],3))+'</td><td>'+esc(s.gene&&s.gene[j]||'')+
        '</td><td>'+lzWhyLab(row.why)+'</td></tr>';
      n+=1;
    });
  });
  if(!n) h+='<tr><td colspan=7>'+bi('No overlapping window sites','没有可定位的窗口位点')+'</td></tr>';
  h+='</tbody></table></div>';
  el.innerHTML=h;
  el.querySelectorAll('[data-sel-li]').forEach(function(row){
    row.addEventListener('click', function(){
      var li=parseInt(row.getAttribute('data-sel-li'),10);
      var j=parseInt(row.getAttribute('data-gt-snp'),10);
      var r=(D.selection_loci||[])[li];
      if(r&&r.snps&&r.snps.pos&&r.snps.pos[j]!=null) selLzFocusPos=Number(r.snps.pos[j]);
      setSelLz(li, true);
      pickSelSnp(j);
      var lz=document.getElementById('sel-lz');
      if(lz) lz.scrollIntoView({behavior:motionBehavior(), block:'start'});
    });
  });
}

var QC_META={
  total_reads:{group:'library', lab:'Total reads', pill:'Total reads', unit:'reads',
    hint:'All reads in the BAM',
    meaning:'Reads in the BAM (flagstat total).',
    meaning_cn:'BAM 中全部 reads。'},
  mapped_reads:{group:'library', lab:'Mapped reads', pill:'Mapped reads', unit:'reads',
    hint:'Aligned to the reference',
    meaning:'Reads mapped to the reference (primary mapped).',
    meaning_cn:'比对到参考基因组的 reads。'},
  unique_reads:{group:'library', lab:'Unique mapped reads', pill:'Unique reads', unit:'reads',
    hint:'Mapped minus duplicates',
    meaning:'Mapped reads minus PCR/optical duplicates.',
    meaning_cn:'比对 reads 减去重复。'},
  on_target_reads:{group:'library', lab:'On-target reads', pill:'On-target reads', unit:'reads',
    hint:'Overlap the 167k chip',
    meaning:'Mapped reads overlapping the 167k chip BED.',
    meaning_cn:'落在 167k 芯片捕获区间内的 reads。'},
  on_target_pct:{group:'library', lab:'On-target rate', pill:'On-target', unit:'%',
    hint:'on-target / mapped',
    meaning:'On-target reads / mapped reads. Capture libraries are typically much higher than shotgun.',
    meaning_cn:'落在芯片区间的 reads / 已比对 reads。捕获文库通常远高于 shotgun。'},
  fold_enrichment:{group:'library', lab:'Fold enrichment', pill:'Fold enrichment', unit:'×',
    hint:'vs whole-genome expectation',
    meaning:'On-target fraction divided by chip length / 486 Mb (QC genome size). 1× = no enrichment.',
    meaning_cn:'on-target 比例 ÷（芯片长度 / 486 Mb）。1× 表示没有富集。'},
  n_panel_sites:{group:'coverage', lab:'Chip sites', pill:'Chip sites', unit:'sites',
    hint:'Sites in the 167k BED',
    meaning:'Number of intervals in the 167k chip BED (one SNP = one site).',
    meaning_cn:'167k 芯片 BED 区间数（一个 SNP 一个位点）。'},
  target_bases:{group:'coverage', lab:'Chip length', pill:'Chip length', unit:'bp',
    hint:'Sum of BED lengths',
    meaning:'Sum of BED interval lengths. Equals chip-site count when each SNP is 1 bp.',
    meaning_cn:'BED 长度之和。每个 SNP 为 1 bp 时与芯片位点数相同。'},
  n_covered_1x:{group:'coverage', lab:'Sites with depth ≥1×', pill:'Covered ≥1×', unit:'sites',
    hint:'At least one covering read',
    meaning:'Chip sites whose mean BAM depth is at least 1×.',
    meaning_cn:'平均 BAM 深度 ≥1× 的芯片位点。'},
  n_covered_5x:{group:'coverage', lab:'Sites with depth ≥5×', pill:'Covered ≥5×', unit:'sites',
    hint:'Usable diploid coverage',
    meaning:'Chip sites whose mean BAM depth is at least 5×.',
    meaning_cn:'平均 BAM 深度 ≥5× 的芯片位点。'},
  n_covered_10x:{group:'coverage', lab:'Sites with depth ≥10×', pill:'Covered ≥10×', unit:'sites',
    hint:'High coverage',
    meaning:'Chip sites whose mean BAM depth is at least 10×.',
    meaning_cn:'平均 BAM 深度 ≥10× 的芯片位点。'},
  pct_covered_1x:{group:'coverage', lab:'Breadth ≥1×', pill:'Breadth ≥1×', unit:'%',
    hint:'% of chip with ≥1×',
    meaning:'Share of 167k chip sites with depth ≥1×. Complements mean depth.',
    meaning_cn:'167k 位点中深度 ≥1× 的比例。和平均深度互补。'},
  pct_covered_5x:{group:'coverage', lab:'Breadth ≥5×', pill:'Breadth ≥5×', unit:'%',
    hint:'% of chip with ≥5×',
    meaning:'Share of 167k chip sites with depth ≥5×.',
    meaning_cn:'167k 位点中深度 ≥5× 的比例。'},
  pct_covered_10x:{group:'coverage', lab:'Breadth ≥10×', pill:'Breadth ≥10×', unit:'%',
    hint:'% of chip with ≥10×',
    meaning:'Share of 167k chip sites with depth ≥10×.',
    meaning_cn:'167k 位点中深度 ≥10× 的比例。'},
  mean_depth:{group:'coverage', lab:'Mean depth (all 167k sites)', pill:'Mean depth', unit:'×',
    hint:'Zeros included',
    meaning:'Average BAM depth across every chip site, including uncovered sites as 0×. Low in aDNA / shotgun.',
    meaning_cn:'全部芯片位点的平均 BAM 深度，未覆盖计为 0×。古 DNA / shotgun 通常很低。'},
  median_depth:{group:'coverage', lab:'Median depth (all 167k sites)', pill:'Median depth', unit:'×',
    hint:'Zeros included',
    meaning:'Median per-site BAM depth, zeros included. 0× means more than half the chip has no covering read.',
    meaning_cn:'每位点 BAM 深度的中位数，含 0。0× 表示一半以上芯片位点没有覆盖。'},
  mean_depth_covered:{group:'coverage', lab:'Mean depth (covered ≥1× only)', pill:'Depth if covered', unit:'×',
    hint:'Ignore uncovered sites',
    meaning:'Average BAM depth on sites that have at least one covering read.',
    meaning_cn:'只在深度 ≥1× 的位点上平均。'},
  n_sites_vcf:{group:'calling', lab:'Sites in this VCF', pill:'VCF sites', unit:'sites',
    hint:'Written to the VCF',
    meaning:'Chip sites present in this sample VCF. Often far below 167k for aDNA.',
    meaning_cn:'本样本 VCF 里出现的芯片位点。古 DNA 往往远少于 167k。'},
  n_called:{group:'calling', lab:'Called genotypes', pill:'Called', unit:'sites',
    hint:'Non-missing GT',
    meaning:'Sites with a non-missing genotype.',
    meaning_cn:'有明确基因型（非 missing）的位点。'},
  n_missing:{group:'calling', lab:'Missing genotypes', pill:'Missing', unit:'sites',
    hint:'GT = ./.',
    meaning:'Sites in the VCF with a missing genotype.',
    meaning_cn:'VCF 中基因型缺失的位点。'},
  calling_rate_panel_pct:{group:'calling', lab:'Panel calling rate', pill:'Panel calling rate', unit:'%', primary:1,
    hint:'called / 167k chip sites',
    meaning:'Called genotypes / 167k chip sites. Main metric: sites never written to the VCF count as failure.',
    meaning_cn:'已分型 / 167k 芯片位点。主指标：没写进 VCF 的位点也算失败。'},
  calling_rate_pct:{group:'calling', lab:'VCF-site calling rate', pill:'VCF calling rate', unit:'%',
    hint:'called / sites in this VCF',
    meaning:'Called / sites present in this VCF. Usually ~100% once a site is written; do not use this as capture success.',
    meaning_cn:'已分型 / 本 VCF 位点数。位点一旦写出通常接近 100%；不能当作捕获成功率。'},
  sites_recovered_pct:{group:'calling', lab:'VCF recovery vs chip', pill:'Sites recovered', unit:'%',
    hint:'VCF sites / 167k',
    meaning:'Sites in the VCF / 167k chip sites. How much of the chip was even attempted in this VCF.',
    meaning_cn:'VCF 位点数 / 167k。芯片有多少被写进了这份 VCF。'},
  n_hom_ref:{group:'gt', lab:'Homozygous reference', pill:'Hom-ref', unit:'sites',
    hint:'0/0 among called',
    meaning:'Called sites with genotype 0/0.',
    meaning_cn:'已分型位点中的 0/0。'},
  n_het:{group:'gt', lab:'Heterozygous', pill:'Het', unit:'sites',
    hint:'0/1 among called',
    meaning:'Called sites with two different alleles.',
    meaning_cn:'已分型位点中的杂合。'},
  n_hom_alt:{group:'gt', lab:'Homozygous alternate', pill:'Hom-alt', unit:'sites',
    hint:'1/1 among called',
    meaning:'Called sites with genotype 1/1 (or 2/2, …).',
    meaning_cn:'已分型位点中的 1/1（或 2/2 等）。'},
  n_variant:{group:'gt', lab:'Variant sites', pill:'Variants', unit:'sites',
    hint:'het + hom-alt',
    meaning:'Called sites that are not homozygous reference (het + hom-alt).',
    meaning_cn:'非 0/0 的已分型位点（杂合 + 纯合突变）。'},
  variant_rate:{group:'gt', lab:'Variant rate among called', pill:'Variant rate', unit:'%', scale:100,
    hint:'(het + hom-alt) / called',
    meaning:'(het + hom-alt) / called sites.',
    meaning_cn:'（杂合 + 纯合突变）/ 已分型位点。'},
  het_rate:{group:'gt', lab:'Heterozygosity among called', pill:'Het rate', unit:'%', scale:100,
    hint:'het / called',
    meaning:'Heterozygous sites / called sites. Not a population He; just this sample’s called set.',
    meaning_cn:'杂合位点 / 已分型位点。不是群体 He，只描述本样本已分型集合。'},
  mean_dp_called:{group:'gt', lab:'Mean DP at called sites', pill:'Mean DP', unit:'×',
    hint:'VCF FORMAT/DP',
    meaning:'Mean FORMAT/DP on called sites (genotype field, not BAM bedcov).',
    meaning_cn:'已分型位点的 FORMAT/DP 均值（来自 VCF，不是 BAM 覆盖）。'},
  median_dp_called:{group:'gt', lab:'Median DP at called sites', pill:'Median DP', unit:'×',
    hint:'VCF FORMAT/DP',
    meaning:'Median FORMAT/DP on called sites.',
    meaning_cn:'已分型位点的 FORMAT/DP 中位数。'}
};
var QC_PILL=['calling_rate_panel_pct','calling_rate_pct','mean_depth','median_depth','pct_covered_1x','pct_covered_5x','pct_covered_10x','on_target_pct','fold_enrichment','n_called','n_variant'];
var QC_SKIP={calling_rate:1, calling_rate_panel:1, breadth_1x:1, breadth_5x:1, n_panel_sites_ref:1};
var QC_ORDER=['total_reads','mapped_reads','unique_reads','on_target_reads','on_target_pct','fold_enrichment','n_panel_sites','target_bases','n_covered_1x','n_covered_5x','n_covered_10x','pct_covered_1x','pct_covered_5x','pct_covered_10x','mean_depth','median_depth','mean_depth_covered','n_sites_vcf','n_called','n_missing','calling_rate_panel_pct','calling_rate_pct','sites_recovered_pct','n_hom_ref','n_het','n_hom_alt','n_variant','variant_rate','het_rate','mean_dp_called','median_dp_called'];
var QC_GROUP_LAB={
  library:['Library / capture','文库 / 捕获'],
  coverage:['Coverage on the 167k chip','芯片覆盖'],
  calling:['Calling rates','分型率'],
  gt:['Called genotypes','已分型组成']
};
var QC_LABEL_ZH={
  total_reads:'总 reads',
  mapped_reads:'已比对 reads',
  unique_reads:'唯一比对 reads',
  on_target_reads:'目标区 reads',
  on_target_pct:'目标区比例',
  fold_enrichment:'富集倍数',
  n_panel_sites:'芯片位点数',
  target_bases:'芯片长度',
  n_covered_1x:'深度 ≥1× 的位点',
  n_covered_5x:'深度 ≥5× 的位点',
  n_covered_10x:'深度 ≥10× 的位点',
  pct_covered_1x:'覆盖广度 ≥1×',
  pct_covered_5x:'覆盖广度 ≥5×',
  pct_covered_10x:'覆盖广度 ≥10×',
  mean_depth:'平均深度（全部 167k 位点）',
  median_depth:'中位深度（全部 167k 位点）',
  mean_depth_covered:'平均深度（仅已覆盖位点）',
  n_sites_vcf:'本 VCF 中的位点',
  n_called:'已分型基因型',
  n_missing:'缺失基因型',
  calling_rate_panel_pct:'面板分型率',
  calling_rate_pct:'VCF 位点分型率',
  sites_recovered_pct:'相对芯片的 VCF 恢复率',
  n_hom_ref:'纯合参考',
  n_het:'杂合',
  n_hom_alt:'纯合替代',
  n_variant:'变异位点',
  variant_rate:'已分型位点中的变异率',
  het_rate:'已分型位点中的杂合率',
  mean_dp_called:'已分型位点平均 DP',
  median_dp_called:'已分型位点中位 DP'
};

function qcMeta(k){
  var key=String(k||'');
  return QC_META[key]||QC_META[key.toLowerCase()]||{lab:key.replace(/_/g,' '), unit:'', pill:key.replace(/_/g,' '), group:'', hint:'', meaning:'', meaning_cn:''};
}
function qcLabel(k, field){
  var m=qcMeta(k);
  var en=m[field]||'';
  var zh=field==='hint'
    ?(m.meaning_cn||QC_LABEL_ZH[String(k||'').toLowerCase()]||en)
    :(QC_LABEL_ZH[String(k||'').toLowerCase()]||m.meaning_cn||en);
  return bi(esc(en),esc(zh));
}
function qcValue(k,v){
  var m=qcMeta(k);
  var unit=m.unit||'';
  if(v===null||v===undefined||v!==v) return '—';
  var n=Number(v);
  if(!isFinite(n)) return '—';
  if(m.scale) n=n*m.scale;
  var core;
  if(unit==='%') return fmtNum(n,2)+'%';
  if(unit==='×') return fmtNum(n, n>=10?1:3)+'×';
  if(unit==='reads'||unit==='sites'||unit==='bp'){
    core=String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g,',');
    return core+'\u00a0'+unit;
  }
  return fmtNum(n,3);
}

function fillQc(){
  var qc=D.qc||{};
  var hi=document.getElementById('qc-highlights');
  if(hi){
    var hh='<div class="qc-grid">';
    QC_PILL.forEach(function(k){
      if(qc[k]==null) return;
      var m=qcMeta(k);
      hh+='<div class="'+(m.primary?'qc-pill primary':'qc-pill')+'">';
      hh+='<div class="lbl">'+qcLabel(k,'pill')+'</div>';
      hh+='<div class="val">'+esc(qcValue(k,qc[k]))+'</div>';
      if(m.hint) hh+='<div class="hint">'+qcLabel(k,'hint')+'</div>';
      hh+='</div>';
    });
    hh+='</div>';
    hi.innerHTML=hh;
  }
  var used={};
  var h='<table class="qc-table"><tr><th>'+bi('Metric','指标')+'</th><th>'+bi('Value','数值')+'</th><th>'+bi('Meaning','含义')+'</th></tr>';
  ['library','coverage','calling','gt'].forEach(function(g){
    var rows=QC_ORDER.filter(function(k){ return qc[k]!=null && !QC_SKIP[k] && qcMeta(k).group===g; });
    if(!rows.length) return;
    var gl=QC_GROUP_LAB[g]||['',''];
    h+='<tr class="qc-group"><td colspan="3">'+bi(esc(gl[0]),esc(gl[1]))+'</td></tr>';
    rows.forEach(function(k){
      used[k]=1;
      var m=qcMeta(k);
      h+='<tr><td>'+qcLabel(k,'lab')+'</td><td class="qc-val">'+esc(qcValue(k,qc[k]))+'</td>';
      h+='<td class="qc-meaning"><span class="en">'+esc(m.meaning||'')+'</span>';
      if(m.meaning_cn) h+='<span class="cn">'+esc(m.meaning_cn)+'</span>';
      h+='</td></tr>';
    });
  });
  Object.keys(qc).forEach(function(k){
    if(qc[k]==null||QC_SKIP[k]||used[k]) return;
    var m=qcMeta(k);
    h+='<tr><td>'+qcLabel(k,'lab')+'</td><td class="qc-val">'+esc(qcValue(k,qc[k]))+'</td>';
    h+='<td class="qc-meaning">'+bi(esc(m.meaning||''),esc(m.meaning_cn||m.meaning||''))+'</td></tr>';
  });
  h+='</table>';
  var te=document.getElementById('qc-table'); if(te) te.innerHTML=h;
}

function loadDamage(){
  if(applyDamageSectionState()) return;
  var el=document.getElementById('plot-damage');
  var elLen=document.getElementById('plot-damage-len');
  if(!el) return;
  if(plotlyUnavailable(el, 'Damage plot')){
    if(elLen) elLen.innerHTML='';
    return;
  }
  resetPlot(el);
  var dmg=asDamage(D.damage);
  if(!dmg){
    el.innerHTML=runtimeMessage('No damage profile','没有损伤谱');
    if(elLen){ resetPlot(elLen); elLen.style.display='none'; }
    return;
  }
  var ct=dmg.ct5||[];
  var ga=dmg.ga3||[];
  var subs5=dmg.subs5||{};
  var subs3=dmg.subs3||{};
  var ymax=0.05;
  function bump(arr){ for(var i=0;i<(arr||[]).length;i++) if(arr[i]>ymax) ymax=arr[i]; }
  bump(ct); bump(ga);
  Object.keys(subs5).forEach(function(k){ bump(subs5[k]); });
  Object.keys(subs3).forEach(function(k){ bump(subs3[k]); });
  ymax=Math.min(0.5, Math.max(0.08, ymax*1.15));
  var traces=[];
  function addSubs(subs, hero, xaxis, yaxis){
    Object.keys(subs).forEach(function(name){
      if(name===hero) return;
      var ys=subs[name]||[];
      if(!ys.length) return;
      var xs=[]; for(var i=0;i<ys.length;i++) xs.push(i+1);
      traces.push({
        type:'scatter', mode:'lines', x:xs, y:ys, name:name, legendgroup:'other',
        line:{color:'#8b9cb3', width:1}, opacity:0.7, xaxis:xaxis, yaxis:yaxis,
        showlegend:false,
        hovertemplate:t(name+' %{x}: %{y:.3f}<extra></extra>',
          name+' %{x}：%{y:.3f}<extra></extra>')
      });
    });
  }
  addSubs(subs5, 'C>T', 'x', 'y');
  addSubs(subs3, 'G>A', 'x2', 'y2');
  if(ct.length){
    var xs=[]; for(var i=0;i<ct.length;i++) xs.push(i+1);
    traces.push({
      type:'scatter', mode:'lines+markers', x:xs, y:ct, name:t('5′ C→T','5′ C→T'),
      line:{color:'#e74c3c', width:2.4}, marker:{size:5, color:'#e74c3c'},
      xaxis:'x', yaxis:'y',
      hovertemplate:t('5′ pos %{x}<br>C→T %{y:.3f}<extra></extra>',
        '5′ 位点 %{x}<br>C→T %{y:.3f}<extra></extra>')
    });
  }
  if(ga.length){
    var xs2=[]; for(var j=0;j<ga.length;j++) xs2.push(j+1);
    traces.push({
      type:'scatter', mode:'lines+markers', x:xs2, y:ga, name:t('3′ G→A','3′ G→A'),
      line:{color:'#3498db', width:2.4}, marker:{size:5, color:'#3498db'},
      xaxis:'x2', yaxis:'y2',
      hovertemplate:t('3′ pos %{x}<br>G→A %{y:.3f}<extra></extra>',
        '3′ 位点 %{x}<br>G→A %{y:.3f}<extra></extra>')
    });
  }
  Plotly.newPlot(el, traces, withPlotSize({
    paper_bgcolor:themeTokens()['plot-bg'], plot_bgcolor:themeTokens()['plot-bg'], font:{color:themeTokens().text, size:11},
    height:360, margin:{l:48,r:16,t:36,b:44},
    title:{text:t('Misincorporation (mapDamage)','误掺入（mapDamage）'), font:{size:13}},
    legend:{orientation:'h', y:1.08, x:0, font:{size:11}},
    xaxis:{title:t('Position from 5′','距 5′ 位置'), domain:[0, 0.46], gridcolor:themeTokens()['plot-grid'], zeroline:false, dtick:5},
    xaxis2:{title:t('Position from 3′','距 3′ 位置'), domain:[0.54, 1], gridcolor:themeTokens()['plot-grid'], zeroline:false, dtick:5, autorange:'reversed'},
    yaxis:{title:t('Frequency','频率'), range:[0, ymax], gridcolor:themeTokens()['plot-grid'], zeroline:false, tickformat:'.0%'},
    yaxis2:{range:[0, ymax], gridcolor:themeTokens()['plot-grid'], zeroline:false, tickformat:'.0%', anchor:'x2', matches:'y'}
  }, el, 360), plotlyCfg({displayModeBar:false}));

  if(!elLen) return;
  var lens=dmg.length||[];
  if(!lens.length){ resetPlot(elLen); elLen.style.display='none'; return; }
  elLen.style.display='';
  resetPlot(elLen);
  var lx=[], ly=[];
  lens.forEach(function(r){ lx.push(r.len); ly.push(r.n); });
  Plotly.newPlot(elLen, [{
    type:'bar', x:lx, y:ly, marker:{color:'#64748b'},
    hovertemplate:t('length %{x} bp<br>reads %{y:,}<extra></extra>',
      '长度 %{x} bp<br>读段 %{y:,}<extra></extra>')
  }], withPlotSize({
    paper_bgcolor:themeTokens()['plot-bg'], plot_bgcolor:themeTokens()['plot-bg'], font:{color:themeTokens().text, size:11},
    height:240, margin:{l:56,r:16,t:32,b:44},
    title:{text:t('Fragment length','片段长度'), font:{size:13}},
    xaxis:{title:t('Length (bp)','长度（bp）'), gridcolor:themeTokens()['plot-grid']},
    yaxis:{title:t('Reads','读段'), gridcolor:themeTokens()['plot-grid']}
  }, elLen, 240), plotlyCfg({displayModeBar:false}));
}

function loadK(k){
  currentK=String(k);
  document.querySelectorAll('#ktabs .kbtn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-k')===currentK);
  });
  loadBar(currentK);
  updateBrowser();
  if(selectedIID) highlightSample(selectedIID);
}

function makeClickHandler(el){
  el.on('plotly_click', function(data){
    if(!data||!data.points||!data.points.length)return;
    var p=data.points[0], iid=null;
    if(p.customdata && typeof p.customdata==='string') iid=p.customdata;
    if(!iid && p.data && p.data.customdata && p.pointIndex!==undefined){
      var cd=p.data.customdata;
      if(Array.isArray(cd)&&cd[p.pointIndex]!=null) iid=String(cd[p.pointIndex]);
    }
    if(iid) highlightSample(iid);
  });
}

function loadPCA(){
  var el=document.getElementById('plot-pca');
  if(!el) return;
  if(plotlyUnavailable(el, 'PCA plot')) return;
  resetPlot(el);
  if(D.pca_points && D.pca_points.length){
    var fig=buildPca2dFig(pcaXi, pcaYi);
    Plotly.newPlot(el, fig.data, withPcaPlotSize(fig.layout, el), plotlyCfg({scrollZoom:true}))
      .then(function(){ makeClickHandler(el); if(selectedIID) highlightSample(selectedIID); });
    return;
  }
  if(!D.pca){el.innerHTML=runtimeMessage('No PCA','没有 PCA');return;}
  Plotly.newPlot(el, D.pca.data, withPcaPlotSize(D.pca.layout, el), plotlyCfg({scrollZoom:true}))
    .then(function(){ makeClickHandler(el); if(selectedIID) highlightSample(selectedIID); });
}

function loadPCA3d(){
  var el=document.getElementById('plot-pca3d');
  if(!el) return;
  if(plotlyUnavailable(el, '3D PCA plot')) return;
  resetPlot(el);
  var n=D.pca_n||0;
  if(!D.pca_points || !D.pca_points.length || n<3){
    el.innerHTML='<div class="muted" style="padding:24px;text-align:center">'+bi(
      'Need ≥3 PCs for 3D','3D 需要至少 3 个主成分')+'</div>';
    return;
  }
  var fig=buildPca3dFig();
  Plotly.newPlot(el, fig.data, withPcaPlotSize(fig.layout, el), plotlyCfg())
    .then(function(){ makeClickHandler(el); if(selectedIID) refreshPca3dHighlight(); });
}

function setPcaAxes(xi, yi){
  pcaXi=xi; pcaYi=yi;
  document.querySelectorAll('.pca-axis-btn').forEach(function(b){
    var ax=b.getAttribute('data-axes');
    b.classList.toggle('active', ax===String(xi)+','+String(yi));
  });
  loadPCA();
}

function _pcaGrpColor(g, i){
  var gc=D.grp_colors||{};
  if(gc[g]) return gc[g];
  var SET1=['#E41A1C','#377EB8','#4DAF4A','#984EA3','#FF7F00','#A65628','#F781BF','#66C2A5'];
  return SET1[i%SET1.length];
}

function _pcaGroupPoints(){
  var by={}, query=null, order=[];
  (D.pca_points||[]).forEach(function(p){
    if(p.query){ query=p; return; }
    var g=p.grp||'NA';
    if(!by[g]){ by[g]=[]; order.push(g); }
    by[g].push(p);
  });
  var BG={'C-Ad':1,'W-Ad':1,'OUT':1,'NA':1,'':1};
  var grps=order.filter(function(g){return BG[g];})
    .concat(order.filter(function(g){return !BG[g];}));
  return {by:by, grps:grps, query:query, BG:BG};
}

function _pcLabel(i){
  var ev=D.pca_evals||[];
  var lab=t('PC'+(i+1),'主成分'+(i+1));
  var frac=Number(ev[i]);
  if(isFinite(frac) && frac>=0 && frac<=1) lab+=' ('+(frac*100).toFixed(1)+'%)';
  return lab;
}

var PCA_PC2_RANGE=[-0.01,0.01];
function pcaAxisRange(axis){
  if(Number(axis)===1) return PCA_PC2_RANGE.slice();
  var vals=[];
  (D.pca_points||[]).forEach(function(p){
    var v=p.pcs && p.pcs[axis];
    if(v!=null && isFinite(Number(v))) vals.push(Number(v));
  });
  if(!vals.length) return null;
  var lo=Math.min.apply(null, vals), hi=Math.max.apply(null, vals);
  if(!(hi>lo)) return [lo-0.01, hi+0.01];
  var pad=(hi-lo)*0.04;
  if(!(pad>0)) pad=0.01;
  return [lo-pad, hi+pad];
}

function pcaCubeRanges(){
  return [pcaAxisRange(0), pcaAxisRange(1), pcaAxisRange(2)];
}

function buildPca2dFig(xi, yi){
  var ginfo=_pcaGroupPoints();
  var traces=[], BG=ginfo.BG;
  var tokens=themeTokens();
  var xr=pcaAxisRange(xi), yr=pcaAxisRange(yi);
  ginfo.grps.forEach(function(g,i){
    var pts=ginfo.by[g];
    if(!pts.length) return;
    var isBg=!!BG[g];
    traces.push({
      type:'scattergl', mode:'markers', name:g,
      x:pts.map(function(p){return p.pcs[xi];}),
      y:pts.map(function(p){return p.pcs[yi];}),
      customdata:pts.map(function(p){return p.iid;}),
      text:pts.map(function(p){return sampleWho(p.iid);}),
      marker:{size:isBg?4:5, opacity:isBg?0.45:0.85, color:_pcaGrpColor(g,i),
        line:{width:isBg?0.4:0, color:'#999'}},
      cliponaxis:true,
      hovertemplate:'%{text}<extra>'+t('panel group','面板组')+' · '+g+'</extra>'
    });
  });
  if(ginfo.query){
    var q=ginfo.query;
    traces.push({
      type:'scatter', mode:'markers', name:t('Query / ','查询样本 / ')+q.iid,
      x:[q.pcs[xi]], y:[q.pcs[yi]],
      customdata:[q.iid], text:[sampleWho(q.iid,'query')],
      marker:{size:14, color:tokens['query-marker'], symbol:'star',
        line:{width:1,color:tokens['query-marker-outline']}},
      hovertemplate:'%{text}<extra>'+t('query overlay','查询样本叠加')+'</extra>'
    });
  }
  var method=pcaMethodLabel(D.pca_method);
  if(method==='—') method='PCA';
  return {data:traces, layout:{
    paper_bgcolor:tokens['plot-bg'], plot_bgcolor:tokens['plot-bg'],
    height:520, margin:{l:54,r:16,t:44,b:92},
    title:t('Frozen panel PCA','冻结面板 PCA')+' ('+method+') · '+
      t('Query overlay','查询样本叠加')+' · '+_pcLabel(xi)+' vs '+_pcLabel(yi)+
      ' · '+t('query','查询样本')+'='+QUERY,
    xaxis:{title:_pcLabel(xi), zeroline:false, range:xr||undefined, automargin:true},
    yaxis:{title:_pcLabel(yi), zeroline:false, range:yr||undefined, automargin:true},
    legend:{orientation:'h', y:-0.22, x:0, xanchor:'left', font:{size:9}},
    hovermode:'closest'
  }};
}

function buildPca3dFig(){
  var ginfo=_pcaGroupPoints();
  var traces=[], BG=ginfo.BG;
  var tokens=themeTokens();
  var cube=pcaCubeRanges();
  var xr=cube[0], yr=cube[1], zr=cube[2];
  ginfo.grps.forEach(function(g,i){
    var pts=ginfo.by[g];
    if(!pts.length) return;
    var isBg=!!BG[g];
    traces.push({
      type:'scatter3d', mode:'markers', name:g, showlegend:false,
      x:pts.map(function(p){return p.pcs[0];}),
      y:pts.map(function(p){return p.pcs[1];}),
      z:pts.map(function(p){return p.pcs[2];}),
      customdata:pts.map(function(p){return p.iid;}),
      text:pts.map(function(p){return sampleWho(p.iid);}),
      marker:{size:isBg?2:3, opacity:isBg?0.4:0.85, color:_pcaGrpColor(g,i)},
      hovertemplate:'%{text}<extra>'+t('panel group','面板组')+' · '+g+'</extra>'
    });
  });
  if(ginfo.query){
    var q=ginfo.query;
    traces.push({
      type:'scatter3d', mode:'markers', name:t('Query / ','查询样本 / ')+q.iid, showlegend:false,
      x:[q.pcs[0]], y:[q.pcs[1]], z:[q.pcs[2]],
      customdata:[q.iid], text:[sampleWho(q.iid,'query')],
      marker:{size:7, color:tokens['query-marker'], symbol:'diamond',
        line:{width:1,color:tokens['query-marker-outline']}},
      hovertemplate:'%{text}<extra>'+t('query overlay','查询样本叠加')+'</extra>'
    });
  }
  if(selectedIID){
    var selected=(D.pca_points||[]).find(function(p){return p.iid===selectedIID;});
    if(selected){
      traces.push({
        type:'scatter3d', mode:'markers', name:'selected3d', showlegend:false,
        x:[selected.pcs[0]], y:[selected.pcs[1]], z:[selected.pcs[2]],
        customdata:[selected.iid], text:[sampleWho(selected.iid,'pinned')],
        marker:{size:10, color:'#fbee61', symbol:'diamond',
          line:{width:2,color:'#111'}},
        hovertemplate:'%{text}<extra>'+t('pinned sample','已钉住样本')+'</extra>'
      });
    }
  }
  var tokens=themeTokens();
  return {data:traces, layout:{
    paper_bgcolor:tokens['plot-bg'], height:520, margin:{l:0,r:0,t:40,b:0},
    title:t('Frozen panel PCA','冻结面板 PCA')+' ('+
      (pcaMethodLabel(D.pca_method)==='—'?'PCA':pcaMethodLabel(D.pca_method))+
      ') · '+t('Query overlay','查询样本叠加')+' · 3D',
    showlegend:false,
    scene:{
      bgcolor:tokens['plot-bg'],
      xaxis:{title:_pcLabel(0), range:xr||undefined},
      yaxis:{title:_pcLabel(1), range:yr||undefined},
      zaxis:{title:_pcLabel(2), range:zr||undefined},
      aspectmode:'cube'
    },
    hovermode:'closest'
  }};
}

function refreshPca3dHighlight(){
  var el=document.getElementById('plot-pca3d');
  if(!el || !el._fullLayout || !D.pca_points || !D.pca_points.length) return;
  if(plotlyUnavailable(el, '3D PCA plot')) return;
  var fig=buildPca3dFig();
  resetPlot(el);
  Plotly.newPlot(el, fig.data, withPcaPlotSize(fig.layout, el), plotlyCfg())
    .then(function(){makeClickHandler(el);});
}

function evenlySpacedRows(rows, maxItems){
  if(maxItems<=0) return [];
  if(rows.length<=maxItems) return rows.slice();
  var picked=[];
  for(var i=0;i<maxItems;i++){
    var pos=Math.floor(i*(rows.length-1)/(maxItems-1));
    if(!picked.some(function(r){return r.idx===rows[pos].idx;})) picked.push(rows[pos]);
  }
  return picked;
}

function admixItems(k){
  var queryRow=SROWS.find(function(r){return r.iid===QUERY;});
  var rows=SROWS.filter(function(r){
    return D.admix_query_in_panel || r.iid!==QUERY;
  });
  if(compactAdmix){
    var by={}, groups=[];
    rows.forEach(function(r){
      var g=r.grp||'NA';
      if(!by[g]){by[g]=[];groups.push(g);}
      by[g].push(r);
    });
    var declared=D.admix_group_order||[];
    groups=declared.filter(function(g){return by[g];})
      .concat(groups.filter(function(g){return declared.indexOf(g)<0;}));
    rows=[];
    groups.forEach(function(g){
      var chosen=evenlySpacedRows(by[g],40);
      if(D.admix_query_in_panel && queryRow && (queryRow.grp||'NA')===g &&
         !chosen.some(function(r){return r.iid===QUERY;})){
        if(chosen.length) chosen[chosen.length-1]=queryRow;
        else chosen=[queryRow];
        chosen.sort(function(a,b){return a.idx-b.idx;});
      }
      rows=rows.concat(chosen);
    });
  }
  var items=rows.map(function(r){return {iid:r.iid,row:r};});
  return items;
}

function admixQueryRow(k){
  var queryRow=SROWS.find(function(r){return r.iid===QUERY;});
  if(!queryRow) return null;
  var qv=queryRow.qvals && queryRow.qvals[String(k)];
  if(qv && qv.length) return queryRow;
  return null;
}

function buildAdmixFig(k){
  var meta=(D.admix_meta||{})[String(k)];
  if(!meta) return null;
  var items=admixItems(k), boundaries=[], last=null;
  items.forEach(function(item,i){
    var group=(item.row&&item.row.grp)||'NA';
    if(group!==last){
      boundaries.push({group:group,start:i,count:0});
      last=group;
    }
    boundaries[boundaries.length-1].count++;
  });
  var qrow=admixQueryRow(k);
  var traces=[];
  for(var j=0;j<k;j++){
    var label=meta.labels&&meta.labels[j]?meta.labels[j]:'A'+(j+1);
    traces.push({
      type:'bar', name:label,
      x:items.map(function(_item,i){return i;}),
      y:items.map(function(item){
        var qv=item.row&&item.row.qvals?item.row.qvals[String(k)]:null;
        return qv&&j<qv.length?qv[j]:null;
      }),
      marker:{color:(meta.colors&&meta.colors[j])||'#888'},
      customdata:items.map(function(item){return item.iid;}),
      text:items.map(function(item){return sampleWho(item.iid);}),
      textposition:'none',
      hovertemplate:'%{text}<br>'+label+'=%{y:.3f}<extra>'+
        t('2449 panel','2449 面板')+'</extra>'
    });
  }
  if(qrow){
    var qv=qrow.qvals[String(k)];
    for(var qj=0;qj<k;qj++){
      var qlabel=meta.labels&&meta.labels[qj]?meta.labels[qj]:'A'+(qj+1);
      traces.push({
        type:'bar', name:qlabel, showlegend:false,
        x:[QUERY], y:[qv&&qj<qv.length?qv[qj]:null],
        xaxis:'x2',
        width:0.55,
        marker:{color:(meta.colors&&meta.colors[qj])||'#888',
          line:{color:'#111',width:0.8}},
        customdata:[QUERY],
        text:[sampleWho(QUERY,'query')],
        textposition:'none',
        hovertemplate:'%{text}<br>'+qlabel+'=%{y:.3f}<extra>'+
          t('query projection','查询样本投影')+'</extra>'
      });
    }
  }
  var tokens=themeTokens();
  var layout={
    paper_bgcolor:tokens['plot-bg'], plot_bgcolor:tokens['plot-bg'],
    font:{color:tokens.text,size:11},
    barmode:'stack', height:420,
    margin:{l:44,r:10,t:48,b:118},
    title:t('Frozen 2449-panel ADMIXTURE K='+k,
      '冻结 2449 面板 ADMIXTURE K='+k)+
      (qrow?' · '+t('query projection','查询样本投影'):''),
    yaxis:{title:t('Ancestry proportion','祖源比例'),range:[0,1],
      gridcolor:tokens['plot-grid'],zerolinecolor:tokens.border},
    xaxis:{
      domain:qrow?[0,0.93]:[0,1],
      tickmode:'array',
      tickvals:boundaries.map(function(b){return b.start;}),
      ticktext:boundaries.map(function(b){return b.group+' (n='+b.count+')';}),
      tickangle:-40,tickfont:{size:9},gridcolor:tokens['plot-grid']
    },
    shapes:boundaries.slice(1).map(function(b){
      return {type:'line',xref:'x',yref:'paper',x0:b.start-.5,x1:b.start-.5,
        y0:0,y1:1,line:{color:'#c9c9c9',width:1,dash:'dot'}};
    }),
    showlegend:true,
    legend:{orientation:'h',y:-0.42,yanchor:'top',font:{size:9,color:tokens.text},
      title:{text:t('Frozen 2449-panel components','冻结 2449 面板成分')}},
    hovermode:'closest'
  };
  if(qrow){
    layout.xaxis2={
      domain:[0.955,1],
      tickmode:'array', tickvals:[QUERY], ticktext:[sampleTick(QUERY)],
      tickangle:-90, tickfont:{size:9},
      anchor:'y',
      showgrid:false
    };
  }
  return {data:traces, layout:layout};
}

function setAdmixView(compact){
  compactAdmix=!!compact;
  document.getElementById('admix-full-btn').classList.toggle('active',!compactAdmix);
  document.getElementById('admix-compact-btn').classList.toggle('active',compactAdmix);
  loadBar(currentK);
}

function loadBar(k){
  var el=document.getElementById('plot-bar');
  if(!el) return;
  if(plotlyUnavailable(el, 'ADMIXTURE plot')) return;
  resetPlot(el);
  var fig=buildAdmixFig(k);
  if(!fig){el.innerHTML=runtimeMessage(
    'No ADMIXTURE K='+String(k),'没有 ADMIXTURE K='+String(k));return;}
  Plotly.newPlot(el, fig.data, withPlotSize(fig.layout, el, 420), plotlyCfg())
    .then(function(){
      makeClickHandler(el);
      if(selectedIID) highlightSample(selectedIID);
      requestAnimationFrame(function(){ stretchPlot(el, 420); });
    });
}

function activeTreeFig(){
  if(treeShape==='rectangular' && D.tree_rect) return D.tree_rect;
  return D.tree;
}

function setTreeShape(shape){
  treeShape=(shape==='rectangular' && D.tree_rect)?'rectangular':'circular';
  var circ=document.getElementById('tree-circ-btn');
  var rect=document.getElementById('tree-rect-btn');
  if(circ) circ.classList.toggle('active', treeShape==='circular');
  if(rect) rect.classList.toggle('active', treeShape==='rectangular');
  var frame=document.getElementById('tree-frame');
  if(frame){
    frame.classList.toggle('tree-rect', treeShape==='rectangular');
    frame.classList.toggle('tree-circ', treeShape!=='rectangular');
  }
  TREE_TIPS=treeShape==='rectangular'?(D.tree_tips_rect||{}):(D.tree_tips||{});
  loadTree();
}

function loadTree(){
  var el=document.getElementById('plot-tree');
  if(!el) return;
  if(plotlyUnavailable(el, 'NJ tree')) return;
  resetPlot(el);
  var fig=activeTreeFig();
  if(!fig){el.innerHTML=runtimeMessage('No NJ tree','没有 NJ 树');return;}
  var frame=document.getElementById('tree-frame');
  if(frame){
    frame.classList.toggle('tree-rect', treeShape==='rectangular');
    frame.classList.toggle('tree-circ', treeShape!=='rectangular');
  }
  TREE_TIPS=treeShape==='rectangular'?(D.tree_tips_rect||{}):(D.tree_tips||{});
  var tokens=themeTokens();
  var data=(fig.data||[]).map(function(tr){
    var o=Object.assign({}, tr);
    if(o.customdata && o.customdata.length && typeof o.customdata[0]==='string'){
      if(o.marker){
        o.marker=Object.assign({},o.marker);
        var markerColor=o.marker.color;
        if(Array.isArray(o.customdata)){
          o.marker.color=Array.isArray(markerColor)
            ?markerColor.map(function(color,i){
              return String(o.customdata[i])===String(QUERY)
                ?tokens['query-marker']:color;
            })
            :(o.customdata.some(function(id){return String(id)===String(QUERY);})
              ?o.customdata.map(function(id){
                return String(id)===String(QUERY)
                  ?tokens['query-marker']:markerColor;
              }):markerColor);
          if(o.marker.line){
            o.marker.line=Object.assign({},o.marker.line);
            var lineColor=o.marker.line.color;
            o.marker.line.color=o.customdata.map(function(id){
              return String(id)===String(QUERY)
                ?tokens['query-marker-outline']:lineColor;
            });
          }
        }
      }
      o.text=o.customdata.map(function(id){return sampleWho(id);});
      o.hovertemplate='%{text}<extra>'+
        t('2449 panel / query overlay','2449 面板 / 查询样本叠加')+'</extra>';
    }
    return o;
  });
  var lay=applyPlotTheme(fig.layout||{});
  lay.title=t('Frozen 2449-panel NJ tree · query overlay',
    '冻结 2449 面板 NJ 树 · 查询样本叠加');
  lay.autosize=false;
  var host=frame||el;
  var tw=host.clientWidth;
  var th=host.clientHeight||720;
  el.style.width='100%';
  if(treeShape==='circular'){
    if(tw>80) lay.width=tw;
    lay.height=Math.max(560, th);
    el.style.height=lay.height+'px';
    var xr=lay.xaxis&&lay.xaxis.range;
    if(xr&&xr.length===2){
      var lim=Math.max(Math.abs(xr[0]), Math.abs(xr[1]), 1e-6);
      lay.xaxis=Object.assign({}, lay.xaxis, {
        range:[-lim,lim], scaleanchor:'y', scaleratio:1,
        constrain:'domain', constraintoward:'center',
        visible:false, showgrid:false, zeroline:false, showticklabels:false,
        automargin:false
      });
      lay.yaxis=Object.assign({}, lay.yaxis||{}, {
        range:[-lim,lim],
        visible:false, showgrid:false, zeroline:false, showticklabels:false,
        automargin:false
      });
      delete lay.yaxis.constrain;
      delete lay.yaxis.constraintoward;
      delete lay.yaxis.scaleanchor;
    }
    lay.margin=Object.assign({}, lay.margin||{}, {l:24,r:24,t:48,b:24});
    lay.legend=Object.assign({}, lay.legend||{}, {
      x:1, y:1, xanchor:'right', yanchor:'top',
      bgcolor:themeTokens().surface, bordercolor:themeTokens().border, borderwidth:0
    });
  } else {
    el.style.height='';
    if(tw>80) lay.width=tw;
    if(!(lay.height>400)) lay.height=720;
  }
  Plotly.newPlot(el, data, lay, plotlyCfg({scrollZoom:true}))
    .then(function(){
      makeClickHandler(el);
      if(selectedIID) highlightSample(selectedIID);
      requestAnimationFrame(function(){ sizeCircularTree(); });
    });
}

function sizeCircularTree(){
  if(treeShape!=='circular') return;
  var el=document.getElementById('plot-tree');
  var frame=document.getElementById('tree-frame');
  if(!el || !el._fullLayout || !plotlyCan('relayout')) return;
  var w=(frame&&frame.clientWidth)||el.clientWidth||0;
  var h=(frame&&frame.clientHeight)||720;
  if(!(w>80)) return;
  el.style.width='100%';
  el.style.height=h+'px';
  if(Math.abs((el._fullLayout.width||0)-w)<6 && Math.abs((el._fullLayout.height||0)-h)<6) return;
  relayoutPlot(el, {width:w, height:h, autosize:false});
}

function renderPinnedSummary(iid){
  if(!iid) return false;
  var row=(SROWS||[]).find(function(r){return r.iid===iid;});
  var pinIid=document.getElementById('pin-iid');
  var pinAcc=document.getElementById('pin-acc');
  var pinDet=document.getElementById('pin-detail');
  var pinBar=document.getElementById('pinned-sample');
  if(pinIid) pinIid.textContent=iid;
  var pinBits=[];
  if(row&&row.acc) pinBits.push(row.acc);
  if(row&&row.acc_local) pinBits.push(row.acc_local);
  if(row&&row.origin) pinBits.push(row.origin);
  else if(row&&row.con) pinBits.push(row.con);
  if(row&&row.geo) pinBits.push(row.geo);
  if(row&&row.uti) pinBits.push(row.uti);
  if(row&&row.vivc) pinBits.push('VIVC '+row.vivc);
  if(row&&row.clone_of) pinBits.push(t('Clone of: ','克隆对应：')+row.clone_of);
  if(pinAcc) pinAcc.textContent=pinBits.length?(' | '+pinBits.join(' · ')):'';
  var det='';
  var gShow=(row&&(row.grp_info||row.grp))||'';
  if(gShow) det+=' Grp=<b>'+esc(gShow)+'</b>';
  if(row&&row.qvals&&row.qvals[currentK]){
    var qv=row.qvals[currentK], qdom=row.qvals[currentK+'_dom']||'';
    det+=' Q'+currentK+'=['+qv.map(function(v){return fmtNum(Number(v),2);}).join(',')+'] '+esc(qdom);
    var mx=Math.max.apply(null,qv);
    det+=' <span class="tag '+(mx>0.75?'tag-green':'tag-red')+'">'+
      (mx>0.75?t('CORE','核心'):t('ADMIXED','混合'))+'</span>';
  }
  if(row && row.pc1!=null && row.pc2!=null){
    det+=' | PC1='+fmtNum(Number(row.pc1),3)+' PC2='+fmtNum(Number(row.pc2),3);
    if(row.pc3!=null) det+=' PC3='+fmtNum(Number(row.pc3),3);
  }
  if(pinDet) pinDet.innerHTML=det;
  if(pinBar&&pinBar.style) pinBar.style.display='block';
  return true;
}
function highlightSample(iid){
  if(!iid)return;
  selectedIID=iid;
  var row=SROWS.find(function(r){return r.iid===iid;});
  renderPinnedSummary(iid);
  if(row){ document.getElementById('sample-slider').value=row.idx; updateBrowser(); }

  // clear shapes
  ['plot-pca','plot-bar','plot-tree'].forEach(function(pid){
    var el=document.getElementById(pid);
    if(el&&el._fullLayout) relayoutPlot(el,{shapes:[]});
  });

  // PCA 2D circle (current axes)
  var elP=document.getElementById('plot-pca');
  if(elP&&elP._fullLayout){
    var sx=null,sy=null;
    for(var t=0;t<(elP.data||[]).length;t++){
      var tr=elP.data[t]; if(!tr||tr.mode!=='markers') continue;
      var cd=tr.customdata;
      if(cd&&Array.isArray(cd)){
        for(var ci=0;ci<cd.length;ci++){
          if(String(cd[ci])===iid && tr.x[ci]!==undefined){ sx=tr.x[ci]; sy=tr.y[ci]; break; }
        }
      }
      if(sx!==null) break;
    }
    if(sx!==null){
      var xr=elP._fullLayout.xaxis.range, pad=(xr[1]-xr[0])*0.012;
      relayoutPlot(elP,{shapes:[{
        type:'circle', x0:sx-pad, x1:sx+pad, y0:sy-pad, y1:sy+pad,
        line:{color:'#ffff00',width:3}, fillcolor:'rgba(255,255,0,0.15)'
      }]});
    }
  }

  // Bar highlight: query lives on xaxis2 (own column)
  var elB=document.getElementById('plot-bar');
  var bxs=[], qHit=false;
  if(elB&&elB.data){
    for(var bt=0;bt<elB.data.length;bt++){
      var bcd=elB.data[bt].customdata||[];
      var onX2=(elB.data[bt].xaxis==='x2');
      for(var bi=0;bi<bcd.length;bi++){
        if(String(bcd[bi])!==String(iid)) continue;
        if(onX2) qHit=true;
        else bxs.push(bi);
      }
    }
  }
  if(elB&&elB._fullLayout && (qHit || bxs.length)){
    var shapes=[];
    if(qHit){
      shapes.push({
        type:'rect', xref:'x2', yref:'y', x0:-0.45, x1:0.45, y0:0, y1:1,
        line:{color:'#ffff00',width:2}, fillcolor:'rgba(255,255,0,0.12)'
      });
    } else {
      var runStart=bxs[0], runEnd=bxs[0];
      for(var hi=1;hi<bxs.length;hi++){
        if(bxs[hi]===bxs[hi-1]+1) runEnd=bxs[hi];
        else { runStart=bxs[hi]; runEnd=bxs[hi]; }
      }
      shapes.push({
        type:'rect', x0:runStart-0.5, x1:runEnd+0.5, y0:0, y1:1,
        line:{color:'#ffff00',width:2}, fillcolor:'rgba(255,255,0,0.12)'
      });
    }
    relayoutPlot(elB,{shapes:shapes});
  }

  // Tree highlight
  var elT=document.getElementById('plot-tree');
  var pos=TREE_TIPS[iid];
  if(elT&&elT._fullLayout && pos){
    var xr2=elT._fullLayout.xaxis.range, s=(xr2[1]-xr2[0])*0.01;
    relayoutPlot(elT,{shapes:[{
      type:'circle', x0:pos[0]-s, x1:pos[0]+s, y0:pos[1]-s, y1:pos[1]+s,
      line:{color:'#ffff00',width:3}, fillcolor:'rgba(255,255,0,0.2)'
    }]});
  }

  // 3D scenes cannot use layout shapes; rebuild with a dedicated pin trace.
  refreshPca3dHighlight(iid);
}

function clearHighlight(){
  selectedIID=null;
  document.getElementById('pinned-sample').style.display='none';
  ['plot-pca','plot-bar','plot-tree'].forEach(function(id){
    var el=document.getElementById(id);
    if(el&&el._fullLayout) relayoutPlot(el,{shapes:[]});
  });
  refreshPca3dHighlight('');
}

function updateBrowser(){
  var idx=parseInt(document.getElementById('sample-slider').value,10);
  var row=SROWS[idx]; if(!row)return;
  document.getElementById('browser-idx').textContent=idx+'/'+(SROWS.length-1);
  var km=(D.admix_meta||{})[currentK]||{};
  var CLRS=km.colors||D.k8_colors||['#E41A1C','#377EB8','#4DAF4A','#984EA3','#FF7F00','#A65628','#F781BF','#66C2A5'];
  var info=esc(row.iid);
  if(row.acc) info+=' | <b>'+esc(row.acc)+'</b>';
  if(row.acc_local) info+=' | '+esc(row.acc_local);
  var bits=[row.origin||row.con,row.geo,row.uti,row.grp_info||row.grp].filter(Boolean);
  if(bits.length) info+=' | '+esc(bits.join(' · '));
  if(row.vivc) info+=' | VIVC '+esc(row.vivc);
  var qv=row.qvals&&row.qvals[currentK]?row.qvals[currentK]:null;
  if(qv){
    info+=' | <span style="display:inline-flex;gap:1px;height:14px;width:100px;background:var(--surface-2);border-radius:2px;overflow:hidden;vertical-align:middle;margin:0 4px">';
    for(var j=0;j<qv.length;j++) info+='<span style="width:'+(qv[j]*100)+'%;background:'+CLRS[j]+';height:100%"></span>';
    info+='</span> '+esc(row.qvals[currentK+'_dom']||'');
  }
  if(row.pc1!=null && row.pc2!=null){
    info+=' | PC1='+fmtNum(Number(row.pc1),3)+' PC2='+fmtNum(Number(row.pc2),3);
    if(row.pc3!=null) info+=' PC3='+fmtNum(Number(row.pc3),3);
  }
  document.getElementById('browser-info').innerHTML=info;
}
function highlightOnSlide(){
  var idx=parseInt(document.getElementById('sample-slider').value,10);
  var row=SROWS[idx]; if(row) highlightSample(row.iid);
}
function browserGo(){ highlightOnSlide(); }

function isNarrowViewport(){
  if(typeof window==='undefined') return false;
  var width=Number(window.innerWidth);
  if(isFinite(width)&&width>0) return width<=760;
  try{
    return !!(window.matchMedia&&window.matchMedia('(max-width: 760px)').matches);
  }catch(err){ return false; }
}
function setSidebarAccessibility(sb, btn, hidden){
  if(!sb||!btn) return;
  var sidebarId=String(sb.id||'report-sidebar');
  if(!sb.id) sb.id=sidebarId;
  if(sb.setAttribute){
    sb.setAttribute('aria-hidden',hidden?'true':'false');
    if(hidden) sb.setAttribute('inert','');
    else if(sb.removeAttribute) sb.removeAttribute('inert');
  }
  try{ sb.inert=!!hidden; }catch(err){}
  if(btn.setAttribute){
    btn.setAttribute('aria-controls',sidebarId);
    btn.setAttribute('aria-expanded',hidden?'false':'true');
    btn.setAttribute(
      'aria-label',
      hidden?t('Open report navigation','打开报告导航'):
        t('Close report navigation','关闭报告导航')
    );
    btn.setAttribute('title',hidden?t('Show','显示'):t('Hide','隐藏'));
  }
}
function setSidebarState(hidden){
  var sb=document.querySelector('.sidebar');
  var btn=document.getElementById('sidebar-toggle');
  var main=document.getElementById('main-content');
  var tb=document.getElementById('top-bar');
  if(!sb||!btn||!main||!tb) return;
  var narrow=isNarrowViewport();
  sb.classList.toggle('hidden',!!hidden);
  sb.classList.toggle('open',!hidden);
  btn.classList.toggle('shifted',!!hidden);
  btn.textContent=hidden?'▶':'◀';
  btn.title=hidden?t('Show','显示'):t('Hide','隐藏');
  setSidebarAccessibility(sb,btn,!!hidden);
  if(narrow){
    // The sidebar is an overlay at phone widths; never move the report under it.
    tb.style.left='0';
    main.style.marginLeft='0';
    main.classList.add('expanded');
  }else{
    tb.style.left=hidden?'0':'200px';
    main.style.marginLeft=hidden?'0':'200px';
    main.classList.toggle('expanded',!!hidden);
  }
}
function bindResponsiveResizeObserver(){
  if(typeof window==='undefined'||typeof document==='undefined') return;
  var main=document.getElementById('main-content');
  var Observer=window.ResizeObserver;
  if(!main||typeof Observer!=='function') return;
  if(responsiveResizeObserver&&responsiveResizeObservedMain===main) return;
  if(responsiveResizeObserver&&responsiveResizeObserver.disconnect){
    try{ responsiveResizeObserver.disconnect(); }catch(err){}
  }
  responsiveResizeObserver=null;
  responsiveResizeObservedMain=null;
  try{
    responsiveResizeObserver=new Observer(function(){
      scheduleResponsiveResize();
    });
    responsiveResizeObserver.observe(main);
    responsiveResizeObservedMain=main;
  }catch(err){
    if(responsiveResizeObserver&&responsiveResizeObserver.disconnect){
      try{ responsiveResizeObserver.disconnect(); }catch(ignore){}
    }
    responsiveResizeObserver=null;
  }
}
function initResponsiveShell(){
  if(typeof document==='undefined') return;
  var sb=document.querySelector('.sidebar');
  if(!sb) return;
  responsiveShellNarrow=isNarrowViewport();
  setSidebarState(responsiveShellNarrow||sb.classList.contains('hidden'));
  bindResponsiveResizeObserver();
  if(typeof window==='undefined'||window._gaResponsiveShellBound) return;
  if(!window.addEventListener) return;
  window._gaResponsiveShellBound=true;
  window.addEventListener('resize',function(){
    var narrow=isNarrowViewport();
    if(narrow!==responsiveShellNarrow){
      setSidebarState(narrow);
      responsiveShellNarrow=narrow;
    }else{
      setSidebarAccessibility(
        sb,
        document.getElementById('sidebar-toggle'),
        sb.classList.contains('hidden')
      );
    }
    scheduleResponsiveResize();
  });
}
function toggleSidebar(){
  var sb=document.querySelector('.sidebar');
  if(!sb) return;
  setSidebarState(!sb.classList.contains('hidden'));
  scheduleResponsiveResize();
}
function themeExistingPlot(el){
  if(!el||!plotlyCan('relayout')) return false;
  var source=el.layout||el._fullLayout||{};
  var tokens=themeTokens();
  var update={
    paper_bgcolor:tokens['plot-bg'],
    plot_bgcolor:tokens['plot-bg'],
    'font.color':tokens.text
  };
  ['xaxis','yaxis','xaxis2','yaxis2','xaxis3','yaxis3'].forEach(function(key){
    if(source[key]||(el._fullLayout&&el._fullLayout[key])){
      update[key+'.color']=tokens.text;
      update[key+'.gridcolor']=tokens['plot-grid'];
      update[key+'.zerolinecolor']=tokens['plot-grid'];
      update[key+'.linecolor']=tokens.border;
    }
  });
  if(source.scene||(el._fullLayout&&el._fullLayout.scene)){
    update['scene.bgcolor']=tokens['plot-bg'];
    ['xaxis','yaxis','zaxis'].forEach(function(key){
      update['scene.'+key+'.color']=tokens.text;
      update['scene.'+key+'.gridcolor']=tokens['plot-grid'];
      update['scene.'+key+'.zerolinecolor']=tokens['plot-grid'];
    });
  }
  if(!relayoutPlot(el,update)) return false;
  if(plotlyCan('restyle')&&Array.isArray(el.data)){
    el.data.forEach(function(trace,i){
      if(!trace||!trace.marker) return;
      var custom=Array.isArray(trace.customdata)?trace.customdata:null;
      var hasQuery=String(trace.name||'')===String(QUERY)||
        !!(custom&&custom.some(function(id){return String(id)===String(QUERY);}));
      if(!hasQuery) return;
      var markerColor=trace.marker.color;
      var markerUpdate={};
      if(custom&&custom.length){
        markerUpdate['marker.color']=(Array.isArray(markerColor)
          ?markerColor:custom.map(function(){return markerColor;})
        ).map(function(color,j){
          return String(custom[j])===String(QUERY)
            ?tokens['query-marker']:color;
        });
        if(trace.marker.line){
          var lineColor=trace.marker.line.color||tokens.border;
          markerUpdate['marker.line.color']=custom.map(function(id){
            return String(id)===String(QUERY)
              ?tokens['query-marker-outline']:lineColor;
          });
        }
      }else{
        markerUpdate['marker.color']=tokens['query-marker'];
        markerUpdate['marker.line.color']=tokens['query-marker-outline'];
      }
      restylePlot(el,markerUpdate,[i]);
    });
  }
  return true;
}
function themeLocusZoomExisting(plot, el){
  if(!el) return;
  var tokens=themeTokens();
  var svg=el.querySelector&&el.querySelector('svg.lz-locuszoom');
  if(svg){
    svg.style.backgroundColor=tokens['plot-bg'];
    svg.style.color=tokens.text;
    if(svg.querySelectorAll){
      Array.prototype.forEach.call(svg.querySelectorAll('text'),function(node){
        node.setAttribute('fill',tokens.text);
      });
      Array.prototype.forEach.call(svg.querySelectorAll('.lz-axis path,.lz-axis line'),function(node){
        node.setAttribute('stroke',tokens.border);
      });
    }
  }
  if(plot&&typeof plot.setDimensions==='function'){
    try{ plot.setDimensions(hostPlotWidth(el),plot._total_height); }catch(err){}
  }
}
function refreshThemedPlots(){
  if(!D) return;
  var details=[];
  if(typeof document!=='undefined'&&document.querySelectorAll){
    Array.prototype.forEach.call(document.querySelectorAll('details[id]'),function(node){
      details.push({node:node,open:!!node.open});
    });
  }
  var redraw=function(){
    ['plot-pca','plot-pca3d','plot-bar','plot-tree','plot-damage',
      'plot-damage-len','plot-f3-out','plot-f3','plot-f4','plot-sel-manh',
      'plot-sel-heat','plot-sel-scatter','plot-lz-gt','plot-sel-gt'
    ].forEach(function(id){
      if((id==='plot-damage'||id==='plot-damage-len')&&isModernLibrary()) return;
      var el=document.getElementById(id);
      if(el) themeExistingPlot(el);
    });
    themeLocusZoomExisting(lzPlot,document.getElementById('plot-lz'));
    themeLocusZoomExisting(selLzPlot,document.getElementById('plot-sel-lz'));
    details.forEach(function(item){ if(item.node) item.node.open=item.open; });
  };
  if(typeof requestAnimationFrame==='function') requestAnimationFrame(redraw);
  else redraw();
}
function refreshPanelResearchPlots(){
  var redraw=function(){
    enhanceReportTables(document);
    if(typeof drawLocusZoom==='function') drawLocusZoom();
    if(typeof drawSelLocusZoom==='function') drawSelLocusZoom();
    if(typeof drawSelManhattan==='function') drawSelManhattan();
    if(typeof drawSelHeat==='function') drawSelHeat();
    if(typeof drawSelScatter==='function') drawSelScatter();
    scheduleResponsiveResize();
  };
  if(typeof requestAnimationFrame==='function') requestAnimationFrame(redraw);
  else if(typeof setTimeout==='function') setTimeout(redraw,0);
  else redraw();
}
function bindPanelResearchToggle(){
  var details=document.getElementById('panel-research');
  if(!details || details._gaToggleBound) return;
  details._gaToggleBound=true;
  details.addEventListener('toggle', function(){
    if(details.open) refreshPanelResearchPlots();
  });
  if(details.open) refreshPanelResearchPlots();
}
function scrollToId(id){
  var el=document.getElementById(id);
  var node=el;
  var inPanel=false;
  var panelWasOpen=false;
  while(node){
    if(String(node.tagName||'').toLowerCase()==='details'){
      if(node.id==='panel-research'){
        inPanel=true;
        panelWasOpen=!!node.open;
      }
      node.open=true;
    }
    node=node.parentElement;
  }
  if(inPanel&&panelWasOpen) refreshPanelResearchPlots();
  if(el) el.scrollIntoView({behavior:motionBehavior()});
  document.querySelectorAll('.sidebar a').forEach(function(a){a.classList.remove('active');});
  var link=document.querySelector('.sidebar a[href="#'+id+'"]');
  if(link) link.classList.add('active');
  return false;
}
"""


def payload_library_class(data_json: str) -> str:
    """Return report_meta.library_class from a dashboard payload JSON string."""
    try:
        payload = json.loads(data_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    meta = payload.get("report_meta") or {}
    if not isinstance(meta, dict):
        return ""
    raw = str(meta.get("library_class") or "").strip().lower()
    if raw:
        return raw
    typ = str(meta.get("library_type") or "").strip().lower()
    if typ == "pe":
        return "modern"
    if typ == "adna":
        return "ancient"
    return ""


def apply_damage_library_class(html: str, data_json: str) -> str:
    """Bake modern/ancient library class onto #damage so plots stay hidden without JS."""
    library_class = payload_library_class(data_json)
    if not library_class:
        return html
    extra = f' data-library-class="{library_class}"'
    if library_class == "modern":
        extra += ' class="is-modern-library"'
    return html.replace('<section id="damage">', f'<section id="damage"{extra}>', 1)


def render_interactive_dashboard(bundle: ReportBundle, out_html: Path, root: Path) -> Path:
    payload = build_interactive_payload(bundle, root)
    data_json = payload_to_json(payload)
    return write_dashboard_html(
        bundle.sample,
        data_json,
        out_html,
        root,
        merged_vcf_note=bundle.merged_vcf_note or "",
    )


def write_dashboard_html(
    sample: str,
    data_json: str,
    out_html: Path,
    root: Path,
    *,
    write_sidecar: bool = True,
    merged_vcf_note: str = "",
) -> Path:
    # Prefer local Plotly (offline); CDN fallback
    plotly_local = root / "assets" / "plotly-2.32.0.min.js"
    if plotly_local.exists():
        plotly_src = "../assets/plotly-2.32.0.min.js"
    else:
        plotly_src = "https://cdn.plot.ly/plotly-2.32.0.min.js"
    d3_local = root / "assets" / "d3-5.16.0.min.js"
    d3_src = "../assets/d3-5.16.0.min.js" if d3_local.exists() else "https://cdn.jsdelivr.net/npm/d3@5.16.0/dist/d3.min.js"
    lz_js_local = root / "assets" / "locuszoom-0.14.0.app.min.js"
    lz_js = (
        "../assets/locuszoom-0.14.0.app.min.js"
        if lz_js_local.exists()
        else "https://cdn.jsdelivr.net/npm/locuszoom@0.14.0/dist/locuszoom.app.min.js"
    )
    lz_css_local = root / "assets" / "locuszoom-0.14.0.css"
    lz_css = (
        "../assets/locuszoom-0.14.0.css"
        if lz_css_local.exists()
        else "https://cdn.jsdelivr.net/npm/locuszoom@0.14.0/dist/locuszoom.css"
    )

    html = apply_damage_library_class(f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GrapeAncestry Interactive — {sample}</title>
<script data-ga-theme-bootstrap>
(function(){{
  var mode='system';
  try{{ mode=localStorage.getItem('ga-theme')||'system'; }}catch(err){{}}
  if(mode!=='light'&&mode!=='dark') mode='system';
  var resolved=mode;
  if(mode==='system'){{
    var dark=false;
    try{{ dark=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches; }}catch(err){{}}
    resolved=dark?'dark':'light';
  }}
  document.documentElement.setAttribute('data-theme-mode',mode);
  document.documentElement.setAttribute('data-theme',resolved);
  var lang='en';
  try{{ lang=localStorage.getItem('ga-lang')||''; }}catch(err){{}}
  if(!lang){{
    try{{
      var nav=navigator.language||navigator.userLanguage||'';
      lang=(String(nav).toLowerCase().indexOf('zh')===0)?'zh':'en';
    }}catch(err){{ lang='en'; }}
  }}else{{
    lang=String(lang).toLowerCase();
    if(lang.indexOf('zh')===0||lang==='cn'||lang==='chinese') lang='zh';
    else lang='en';
  }}
  document.documentElement.setAttribute('data-lang',lang);
  document.documentElement.setAttribute('lang',lang==='zh'?'zh-CN':'en');
}})();
</script>
<link rel="stylesheet" href="{lz_css}"/>
<script src="{plotly_src}"></script>
<script src="{d3_src}"></script>
<script src="{lz_js}"></script>
<style>
:root{{--bg:#f7f9fc;--surface:#ffffff;--surface-2:#eef2f7;--text:#172033;--muted:#526079;--border:#cbd5e1;--plot-bg:#ffffff;--plot-grid:#dbe3ed;--accent:#b4234b;--on-accent:#ffffff;--blue:#1d4ed8;--green:#15803d;--amber:#a16207;--focus:#1d4ed8;--input-bg:#ffffff;--input-text:#172033;--info-bg:#eaf2ff;--warning-bg:#fff7db;--hover-bg:#f1f5f9;--shadow:#0f172a2e;--accent-soft:#b4234b14;--warning-soft:#a1620714;--info-soft:#1d4ed814;--success-soft:#15803d26;--danger-soft:#dc262626;--danger:#dc2626;--query-marker:#0b3d91;--query-marker-outline:#172033;color-scheme:light}}
:root[data-theme="light"]{{--bg:#f7f9fc;--surface:#ffffff;--surface-2:#eef2f7;--text:#172033;--muted:#526079;--border:#cbd5e1;--plot-bg:#ffffff;--plot-grid:#dbe3ed;--accent:#b4234b;--on-accent:#ffffff;--blue:#1d4ed8;--green:#15803d;--amber:#a16207;--focus:#1d4ed8;--input-bg:#ffffff;--input-text:#172033;--info-bg:#eaf2ff;--warning-bg:#fff7db;--hover-bg:#f1f5f9;--shadow:#0f172a2e;--accent-soft:#b4234b14;--warning-soft:#a1620714;--info-soft:#1d4ed814;--success-soft:#15803d26;--danger-soft:#dc262626;--danger:#dc2626;--query-marker:#0b3d91;--query-marker-outline:#172033;color-scheme:light}}
:root[data-theme="dark"]{{--bg:#0b0f19;--surface:#131b2e;--surface-2:#0f172a;--text:#e2e8f0;--muted:#a8b3c7;--border:#2b3b59;--plot-bg:#131b2e;--plot-grid:#263654;--accent:#f06b84;--on-accent:#172033;--blue:#93c5fd;--green:#86efac;--amber:#fbbf24;--focus:#93c5fd;--input-bg:#0f172a;--input-text:#e2e8f0;--info-bg:#17243d;--warning-bg:#302816;--hover-bg:#1b2943;--shadow:#00000066;--accent-soft:#f06b8426;--warning-soft:#fbbf2426;--info-soft:#93c5fd1f;--success-soft:#86efac26;--danger-soft:#f8717126;--danger:#f87171;--query-marker:#f8fafc;--query-marker-outline:#fbbf24;color-scheme:dark}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]):not([data-theme="dark"]){{--bg:#0b0f19;--surface:#131b2e;--surface-2:#0f172a;--text:#e2e8f0;--muted:#a8b3c7;--border:#2b3b59;--plot-bg:#131b2e;--plot-grid:#263654;--accent:#f06b84;--on-accent:#172033;--blue:#93c5fd;--green:#86efac;--amber:#fbbf24;--focus:#93c5fd;--input-bg:#0f172a;--input-text:#e2e8f0;--info-bg:#17243d;--warning-bg:#302816;--hover-bg:#1b2943;--shadow:#00000066;--accent-soft:#f06b8426;--warning-soft:#fbbf2426;--info-soft:#93c5fd1f;--success-soft:#86efac26;--danger-soft:#f8717126;--danger:#f87171;--query-marker:#f8fafc;--query-marker-outline:#fbbf24;color-scheme:dark}}}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.55}}
html,body{{width:100%;max-width:100%;overflow-x:hidden}}
.main,section,.plot-box,.plot-frame,.table-scroll,.js-plotly-plot,.plot-container.plotly,.svg-container{{min-width:0;max-width:100%}}
.plot-box .js-plotly-plot,.plot-box .plot-container.plotly,.plot-box .svg-container{{width:100%;min-width:0;max-width:100%}}
#plot-lz svg.lz-locuszoom,#plot-sel-lz svg.lz-locuszoom{{min-width:0;max-width:100%}}
#js-plotly-tester{{position:fixed!important;left:0!important;top:0!important;width:1px!important;height:1px!important;max-width:1px!important;max-height:1px!important;overflow:hidden!important;pointer-events:none!important;visibility:hidden!important}}
.sidebar{{position:fixed;left:0;top:0;bottom:0;width:200px;background:var(--surface);border-right:1px solid var(--border);overflow-y:auto;z-index:50;padding:16px 0;transition:transform .25s}}
.sidebar.hidden{{transform:translateX(-200px)}}
.sidebar .brand{{padding:0 16px;font-weight:700;font-size:13px;color:var(--accent)}}
.sidebar .sub{{padding:4px 16px 8px;font-size:10px;color:var(--muted)}}
.sidebar h2{{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);padding:0 16px;margin:14px 0 4px}}
.sidebar a{{display:block;padding:5px 16px;font-size:12.5px;color:var(--muted);text-decoration:none;border-left:2px solid transparent}}
.sidebar a:hover,.sidebar a.active{{color:var(--text);border-left-color:var(--accent);background:var(--accent-soft)}}
.sidebar-toggle{{position:fixed;left:208px;top:8px;z-index:60;background:var(--surface);border:1px solid var(--border);color:var(--muted);width:24px;height:24px;border-radius:4px;cursor:pointer;font-size:14px;line-height:20px;text-align:center;transition:left .25s}}
.sidebar-toggle.shifted{{left:8px}}
.main{{margin-left:200px;transition:margin-left .25s;padding-top:108px}}
.main.expanded{{margin-left:0}}
#top-bar{{position:fixed;top:0;left:200px;right:0;z-index:45;background:var(--surface);border-bottom:1px solid var(--border);box-shadow:0 2px 8px var(--shadow);transition:left .25s}}
#pinned-sample{{display:none;padding:5px 20px;background:var(--warning-soft);border-bottom:1px solid var(--amber);font-size:11px}}
.browser-row{{padding:5px 20px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--bg)}}
.ktabs{{padding:6px 20px;border-top:1px solid var(--border);display:flex;gap:4px;flex-wrap:wrap;align-items:center}}
.ktabs button{{padding:4px 11px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:11px;font-weight:600;background:var(--surface);color:var(--muted)}}
.ktabs button.active{{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}}
.pca-axis-btn{{padding:4px 11px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:11px;font-weight:600;background:var(--surface);color:var(--muted);margin-right:4px}}
.pca-axis-btn.active{{background:var(--blue);border-color:var(--blue);color:var(--on-accent)}}
html:not([data-lang="zh"]) .cn{{display:none!important}}
html[data-lang="zh"] .en{{display:none!important}}
.theme-control,.lang-control{{display:inline-flex;align-items:center;gap:4px;white-space:nowrap}}
.theme-control{{margin-left:auto}}
.theme-label{{font-size:10px;color:var(--muted);font-weight:600}}
.theme-choice,.lang-choice{{padding:3px 8px;border:1px solid var(--border);border-radius:5px;cursor:pointer;font-size:10px;font-weight:600;background:var(--surface);color:var(--muted)}}
.theme-choice[aria-pressed="true"],.lang-choice[aria-pressed="true"]{{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}}
.theme-choice:hover,.lang-choice:hover{{border-color:var(--focus);color:var(--text)}}
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,.clickrow:focus-visible{{outline:2px solid var(--focus);outline-offset:2px}}
.theme-transition body,.theme-transition .sidebar,.theme-transition #top-bar,.theme-transition .main,.theme-transition .theme-control,.theme-transition .card,.theme-transition .plot-box,.theme-transition table,.theme-transition input,.theme-transition select,.theme-transition button,.theme-transition .info-box,.theme-transition .sec-guide{{transition:background-color .18s ease,color .18s ease,border-color .18s ease,box-shadow .18s ease}}
@media (prefers-reduced-motion: reduce){{.sidebar,.sidebar-toggle,.main,#top-bar,.theme-control,.theme-choice{{transition:none!important;animation:none!important}}.theme-transition body,.theme-transition .sidebar,.theme-transition #top-bar,.theme-transition .main,.theme-transition .theme-control,.theme-transition .card,.theme-transition .plot-box,.theme-transition table,.theme-transition input,.theme-transition select,.theme-transition button,.theme-transition .info-box,.theme-transition .sec-guide{{transition:none!important;animation:none!important}}*{{scroll-behavior:auto!important;animation:none!important}}}}
.stats{{display:flex;gap:12px;padding:12px 28px;flex-wrap:wrap;border-bottom:1px solid var(--border);background:var(--surface)}}
.author-intake{{padding:12px 28px 16px;border-bottom:1px solid var(--border);background:var(--surface)}}
.author-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:10px}}
.author-head strong{{font-size:13px}}
.author-mode{{display:flex;gap:4px}}
.author-mode button{{padding:4px 11px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:11px;font-weight:600;background:var(--bg);color:var(--muted)}}
.author-mode button.active{{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}}
.author-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px 14px}}
.author-field{{display:flex;flex-direction:column;gap:4px;font-size:11px;color:var(--muted)}}
.author-field input,.author-field textarea,.author-table input{{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:12px;font-family:inherit}}
.author-notes{{grid-column:1/-1}}
.author-add{{margin-top:8px;padding:4px 11px;border:1px dashed var(--border);border-radius:6px;background:transparent;color:var(--blue);cursor:pointer;font-size:11px}}
.author-del{{background:transparent;border:none;color:var(--muted);cursor:pointer;font-size:12px}}
.author-table th,.author-table td{{padding:4px 6px}}
.author-src{{display:inline-block;margin-left:6px;padding:0 5px;border-radius:3px;font-size:9px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--amber);background:var(--warning-soft)}}
.author-infer{{margin-top:10px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;font-size:12px}}
.author-chip{{display:inline-block;margin:3px 4px 0 0;padding:2px 8px;border:1px solid var(--border);border-radius:12px;cursor:pointer;font-size:11px}}
.author-chip:hover,.author-hit{{background:var(--warning-soft)}}
.card{{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px 16px;min-width:90px}}
.card .num{{font-size:18px;font-weight:800;color:var(--accent)}}.card .lbl{{font-size:10px;color:var(--muted);text-transform:uppercase}}
section{{padding:22px 28px;border-bottom:1px solid var(--border)}}
section h2{{font-size:18px;font-weight:700;margin-bottom:8px;line-height:1.3}}
#main-content > section > h2,
#panel-research > summary{{
  font-size:22px;font-weight:700;margin-bottom:10px;line-height:1.25
}}
section h3{{font-size:15px;color:var(--blue);margin:14px 0 6px}}
.info-box{{background:var(--info-bg);border-left:3px solid var(--blue);padding:8px 14px;border-radius:0 6px 6px 0;margin-bottom:12px;font-size:12px;color:var(--muted)}}
.info-box strong{{color:var(--blue)}}
.plot-box{{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:16px;min-height:480px;width:100%;box-sizing:border-box}}
#plot-pca,#plot-pca3d{{aspect-ratio:1/1;width:100%;height:auto;min-height:0}}
#plot-bar{{height:420px;min-height:420px;width:100%}}
#plot-bar .js-plotly-plot,#plot-bar .plot-container.plotly,#plot-bar .svg-container{{width:100%!important;max-width:100%}}
#tree-frame{{height:720px;overflow:hidden;background:var(--surface);border:1px solid var(--border);border-radius:10px;margin-bottom:16px;display:flex;justify-content:center;align-items:stretch}}
#tree-frame.tree-circ{{overflow:hidden}}
#tree-frame.tree-rect{{overflow:auto;justify-content:stretch;align-items:flex-start}}
#plot-tree{{min-height:0;height:100%;width:100%;overflow:visible;background:transparent;border:0;margin:0}}
#tree-frame.tree-circ #plot-tree{{width:100%;height:100%;min-height:0;background:var(--plot-bg)}}
#tree-frame.tree-circ .js-plotly-plot,#tree-frame.tree-circ .plot-container.plotly,#tree-frame.tree-circ .svg-container{{width:100%!important;height:100%!important}}
#tree-frame.tree-rect #plot-tree{{height:auto;width:100%;background:transparent}}
.tree-shape-btn{{padding:4px 11px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:11px;font-weight:600;background:var(--surface);color:var(--muted);margin-right:4px}}
.tree-shape-btn.active{{background:var(--blue);border-color:var(--blue);color:var(--on-accent)}}
#plot-damage{{height:360px;min-height:360px}}
#plot-damage-len{{height:240px;min-height:240px}}
#damage-modern-note{{display:none}}
#damage.is-modern-library #damage-modern-note{{display:block}}
#damage.is-modern-library #plot-damage,
#damage.is-modern-library #plot-damage-len,
#damage.is-modern-library #damage-guide,
#damage.is-modern-library #damage-note{{
  display:none!important;height:0!important;min-height:0!important;
  margin:0!important;padding:0!important;border:none!important;overflow:hidden!important
}}
#damage.is-modern-library #plot-damage .js-plotly-plot,
#damage.is-modern-library #plot-damage-len .js-plotly-plot{{display:none!important}}
#plot-f3-out{{min-height:320px;height:auto}}
#plot-f3,#plot-f4{{min-height:420px;height:auto}}
.plot-static{{height:auto;overflow:hidden;background:var(--plot-bg);border-radius:8px;border:1px solid var(--border);margin-bottom:16px}}
.plot-static img{{width:100%;height:auto;max-width:100%;display:block}}
#admix-k28 .plot-static{{margin-top:4px}}
#fstats-callout{{background:var(--info-soft);border:1px solid var(--blue);border-radius:8px;padding:10px 14px;margin:0 0 12px;font-size:13px;line-height:1.5}}
.sec-guide{{background:var(--warning-bg);border-left:3px solid var(--amber);padding:8px 14px;border-radius:0 6px 6px 0;margin-bottom:10px;font-size:12.5px;color:var(--text);line-height:1.45}}
.sec-guide .cn, .gt-card .cn, .info-box .cn, #fstats-callout .cn, #sel-query-sites .cn, #sel-lz-meta .cn, #sel details.ref-only .cn{{color:var(--muted);margin-top:4px;display:block}}
#sel details.ref-only{{background:var(--warning-bg);border-left:3px solid var(--amber);padding:8px 14px;border-radius:0 6px 6px 0;margin:16px 0 10px;font-size:12.5px;color:var(--text);line-height:1.45}}
#sel details.ref-only summary{{cursor:pointer}}
.lz-fig{{margin:10px 0 16px}}
.lz-fig img{{max-width:100%;height:auto;background:var(--plot-bg);border-radius:8px;border:1px solid var(--border)}}
.lz-fig figcaption{{font-size:11px;color:var(--muted);margin-bottom:4px}}
#lz-pick,#sel-lz-pick,#sel-lz-metric,#sel-manh-metric,#sel-manh-grp,#sel-heat-metric{{background:var(--surface);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:4px 8px;font-size:12px;max-width:100%}}
#plot-lz,#plot-sel-lz{{height:auto;min-height:0;background:var(--plot-bg);color:var(--text);padding:8px;overflow:visible}}
#plot-lz svg.lz-locuszoom,#plot-sel-lz svg.lz-locuszoom{{max-width:100%;width:100%;height:auto;display:block}}
#plot-lz svg.lz-locuszoom,#plot-sel-lz svg.lz-locuszoom{{background-color:var(--plot-bg);color:var(--text)}}
#plot-lz svg.lz-locuszoom text,#plot-sel-lz svg.lz-locuszoom text{{fill:var(--text)}}
#plot-lz svg.lz-locuszoom .lz-axis path,#plot-lz svg.lz-locuszoom .lz-axis line,#plot-sel-lz svg.lz-locuszoom .lz-axis path,#plot-sel-lz svg.lz-locuszoom .lz-axis line{{stroke:var(--border)}}
#plot-lz svg.lz-locuszoom .lz-panel-background,#plot-sel-lz svg.lz-locuszoom .lz-panel-background{{fill:var(--plot-bg)}}
#plot-lz .lz-toolbar,#plot-sel-lz .lz-toolbar,#plot-lz .lz-plot-toolbar,#plot-sel-lz .lz-plot-toolbar,#plot-lz .lz-panel-toolbar,#plot-sel-lz .lz-panel-toolbar{{background:var(--surface-2);color:var(--text);border-color:var(--border)}}
#plot-lz .lz-toolbar button,#plot-sel-lz .lz-toolbar button,#plot-lz .lz-toolbar-button,#plot-sel-lz .lz-toolbar-button,#plot-lz .lz-tooltip,#plot-sel-lz .lz-tooltip,#plot-lz .lz-data_layer-tooltip,#plot-sel-lz .lz-data_layer-tooltip{{background:var(--surface);color:var(--text);border-color:var(--border)}}
#plot-lz .lz-tooltip text,#plot-sel-lz .lz-tooltip text,#plot-lz .lz-data_layer-tooltip text,#plot-sel-lz .lz-data_layer-tooltip text,#plot-lz svg.lz-locuszoom .lz-legend text,#plot-sel-lz svg.lz-locuszoom .lz-legend text{{fill:var(--text)}}
#plot-lz svg.lz-locuszoom .lz-legend-background,#plot-sel-lz svg.lz-locuszoom .lz-legend-background{{fill:var(--surface);stroke:var(--border)}}
#plot-lz .lz-data_layer-tooltip button,#plot-sel-lz .lz-data_layer-tooltip button,#plot-lz .lz-data_layer-tooltip .lz-tooltip-close-button,#plot-sel-lz .lz-data_layer-tooltip .lz-tooltip-close-button,#plot-lz .lz-tooltip-close-button,#plot-sel-lz .lz-tooltip-close-button{{background:var(--surface-2);color:var(--text);border:1px solid var(--border)}}
#plot-lz .lz-data_layer-tooltip table,#plot-sel-lz .lz-data_layer-tooltip table,#plot-lz .lz-data_layer-tooltip th,#plot-sel-lz .lz-data_layer-tooltip th,#plot-lz .lz-data_layer-tooltip td,#plot-sel-lz .lz-data_layer-tooltip td{{background:var(--surface);color:var(--text);border-color:var(--border)}}
#plot-lz .lz-toolbar-menu,#plot-sel-lz .lz-toolbar-menu,#plot-lz .lz-toolbar-menu-content,#plot-sel-lz .lz-toolbar-menu-content{{background:var(--surface);color:var(--text);border-color:var(--border)}}
#plot-lz .lz-toolbar-menu .lz-toolbar-button,#plot-sel-lz .lz-toolbar-menu .lz-toolbar-button,#plot-lz .lz-toolbar-menu a,#plot-sel-lz .lz-toolbar-menu a{{background:var(--surface-2);color:var(--text);border-color:var(--border)}}
#plot-lz .lz-toolbar-menu .lz-toolbar-button:hover,#plot-sel-lz .lz-toolbar-menu .lz-toolbar-button:hover,#plot-lz .lz-toolbar-menu a:hover,#plot-sel-lz .lz-toolbar-menu a:hover{{background:var(--hover-bg);color:var(--text)}}
#plot-lz .lz-data_layer-tooltip button:focus-visible,#plot-sel-lz .lz-data_layer-tooltip button:focus-visible,#plot-lz .lz-toolbar-menu .lz-toolbar-button:focus-visible,#plot-sel-lz .lz-toolbar-menu .lz-toolbar-button:focus-visible,#plot-lz .lz-toolbar-menu a:focus-visible,#plot-sel-lz .lz-toolbar-menu a:focus-visible{{outline:2px solid var(--focus);outline-offset:2px}}
.js-plotly-plot .plotly .modebar{{background:var(--surface-2)!important;border:1px solid var(--border);border-radius:4px}}
.js-plotly-plot .plotly .modebar-btn{{color:var(--text)!important;fill:var(--text)!important}}
.js-plotly-plot .plotly .modebar-btn:hover{{background:var(--hover-bg)!important;color:var(--text)!important;fill:var(--text)!important}}
.js-plotly-plot .plotly .hovertext{{fill:var(--surface);stroke:var(--border)}}
.js-plotly-plot .plotly .hovertext text{{fill:var(--text)!important}}
#plot-sel-manh,#plot-sel-scatter{{height:380px;min-height:320px}}
#plot-sel-heat{{height:480px;min-height:420px}}
#plot-lz-gt,#plot-sel-gt{{height:150px;min-height:140px;margin:0 0 12px;background:var(--surface);border:1px solid var(--border);border-radius:10px}}
.gt-card{{background:var(--warning-soft);border:1px solid var(--amber);border-radius:8px;padding:10px 14px;margin:10px 0 8px;font-size:13px}}
.gt-card.warn{{background:var(--danger-soft);border-color:var(--danger)}}
.gt-head{{margin-bottom:6px}}
.gt-legend{{display:flex;flex-wrap:wrap;gap:8px 14px;margin:8px 0}}
.gt-leg{{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);max-width:280px}}
.gt-lead{{font-size:15px;font-weight:700;margin:8px 0 4px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.gt-callout{{font-size:13px;margin:4px 0 8px}}
.gt-counts{{font-size:12px;color:var(--text)}}
.gt-bar-row{{display:grid;grid-template-columns:72px 36px 1fr;gap:8px;align-items:center;margin:3px 0}}
.gt-bar{{height:8px;background:var(--surface-2);border-radius:4px;overflow:hidden}}
.gt-bar i{{display:block;height:100%}}
.gt-bar i.gt-ref{{background:#1d4ed8}}
.gt-bar i.gt-het{{background:#eab308}}
.gt-bar i.gt-alt{{background:#dc2626}}
.gt-bar i.gt-miss{{background:#64748b}}
.gt-pill{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:800;letter-spacing:.02em}}
.gt-pill.gt-ref{{background:#1d4ed8;color:#fff}}
.gt-pill.gt-het{{background:#eab308;color:#111}}
.gt-pill.gt-alt{{background:#dc2626;color:#fff}}
.gt-pill.gt-miss{{background:#475569;color:#e2e8f0}}
#lz-meta{{margin:6px 0 8px;font-size:12px;line-height:1.45}}
#lz-detail{{margin:10px 0}}
.lz-dl{{display:grid;grid-template-columns:160px 1fr;gap:3px 12px;margin:8px 0 0}}
.lz-dl dt{{color:var(--muted);font-size:11px}}
.lz-dl dd{{font-size:12px;overflow-wrap:anywhere}}
#lz-bonf{{margin-top:8px}}
.table-scroll{{overflow-x:auto;min-width:0;max-width:100%;width:100%}}
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:12px}}
.table-scroll>table{{width:max-content;min-width:100%;max-width:none}}
th{{background:var(--surface-2);padding:6px 10px;text-align:left;border-bottom:2px solid var(--border);color:var(--muted);font-size:11px}}
td{{padding:6px 10px;border-bottom:1px solid var(--border)}}
.clickrow{{cursor:pointer}}.clickrow:hover{{background:var(--hover-bg)}}
.sel-sweep-focus{{padding:2px 8px;border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--text);cursor:pointer;font-size:10px;font-weight:600}}
.sel-sweep-focus[aria-pressed="true"],tr.is-sweep-focus .sel-sweep-focus{{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}}
tr.is-sweep-focus{{background:var(--warning-soft)}}
#sel-sweep-status{{margin:0 0 8px}}
.sname{{color:var(--amber);font-size:11px;font-weight:600}}
.smeta{{color:var(--muted);font-size:10px}}
.sid{{font-weight:600}}
#sample-search{{background:var(--surface);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:2px 8px;font-size:11px;min-width:168px}}
#stat-q{{font-size:14px;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.tag{{display:inline-block;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:600}}
.scope-label{{display:inline-block;padding:2px 7px;border:1px solid var(--border);border-radius:3px;font-size:10px;font-weight:700;color:var(--blue);letter-spacing:.02em}}
.sr-only{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
.tag-green{{background:var(--success-soft);color:var(--green)}}
.tag-red{{background:var(--accent-soft);color:var(--accent)}}
.muted{{color:var(--muted);font-size:12px}}
.dllink{{display:inline-block;margin:4px 6px 4px 0;padding:4px 10px;border:1px solid var(--border);border-radius:6px;color:var(--blue);text-decoration:none;font-size:11px}}
.dllink:hover{{border-color:var(--blue)}}
a.dblink{{color:var(--blue);text-decoration:none;white-space:nowrap}}
a.dblink:hover{{text-decoration:underline}}
.ev-sub{{display:block;font-size:11px;color:var(--muted);margin-top:3px;line-height:1.45;white-space:normal}}
.ev-sub .dblink{{white-space:nowrap}}
.two-col{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;min-width:0;max-width:100%}}
.three-col{{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr) minmax(0,1fr);gap:16px;min-width:0;max-width:100%}}
.two-col>*,.three-col>*{{min-width:0;max-width:100%}}
.two-col .plot-box,.three-col .plot-box{{min-width:0;max-width:100%}}
#fstats-tables .three-col{{grid-template-columns:1fr 1fr 1fr}}
@media(max-width:1100px){{.two-col,.three-col{{grid-template-columns:1fr}}}}
.q8-bar{{display:flex;height:22px;border-radius:6px;overflow:hidden;background:var(--surface-2);margin:8px 0 12px;border:1px solid var(--border)}}
.q8-seg{{height:100%;min-width:1px}}
.swatch{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}}
.leg.unused{{opacity:.45;text-decoration:line-through}}
.paper-k8{{margin-bottom:8px}}
.q8-note{{font-size:11px;color:var(--muted);font-weight:400;margin-top:2px;line-height:1.35}}
.mini-bar i{{display:block;height:100%}}
.qc-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}}
.qc-pill{{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:8px 12px;min-width:148px;max-width:220px}}
.qc-pill.primary{{border-color:var(--amber);background:var(--warning-soft)}}
.qc-pill .lbl{{font-size:11px;color:var(--muted);font-weight:600;line-height:1.25}}
.qc-pill .val{{font-size:16px;font-weight:700;color:var(--amber);margin-top:3px}}
.qc-pill .hint{{font-size:10px;color:var(--muted);margin-top:3px;line-height:1.3}}
.qc-table .qc-val{{white-space:nowrap;font-variant-numeric:tabular-nums}}
.qc-table .qc-meaning{{color:var(--muted);font-size:11px;line-height:1.4;max-width:520px}}
.qc-table .qc-meaning .cn{{display:block;margin-top:2px}}
.qc-table tr.qc-group td{{background:var(--bg);color:var(--blue);font-weight:700;font-size:12px;padding-top:12px}}
.methods-breeding{{font-size:13px;max-width:960px}}
.methods-breeding h1{{font-size:18px;margin:8px 0 12px}}
.methods-breeding h2{{font-size:15px;margin:18px 0 8px}}
.methods-breeding h3{{font-size:13px;margin:12px 0 6px}}
.methods-breeding p{{margin:8px 0}}
.methods-breeding code{{background:var(--bg);padding:1px 5px;border-radius:3px;font-size:12px}}
.methods-breeding pre{{background:var(--bg);padding:10px;border-radius:8px;overflow-x:auto;font-size:11px;border:1px solid var(--border)}}
.methods-breeding ul{{margin:8px 0 8px 18px}}
.methods-breeding a{{color:var(--blue)}}
.methods-breeding table{{display:block;overflow-x:auto}}
@media(max-width:760px){{
  html,body{{width:100%;max-width:100%;overflow-x:hidden}}
  .sidebar{{transform:translateX(-200px);pointer-events:none}}
  .sidebar.hidden{{transform:translateX(-200px)}}
  .sidebar.open{{transform:translateX(0);pointer-events:auto;box-shadow:4px 0 18px var(--shadow)}}
  .sidebar-toggle{{left:8px;top:8px}}
  .main{{margin-left:0;padding-top:0;width:100%;max-width:100%}}
  #top-bar{{position:sticky;top:0;left:0;right:0;width:100%;max-width:100%}}
  .browser-row{{padding:8px 12px 8px 44px;gap:6px;max-width:100%;min-width:0}}
  #browser-info,.browser-info{{min-width:0;max-width:100%;overflow-x:auto;white-space:nowrap;flex:1 1 160px}}
  .theme-control,.lang-control{{margin-left:0;flex-wrap:wrap;flex:1 1 100%;max-width:100%;white-space:normal}}
  .theme-choice,.lang-choice{{flex:0 0 auto}}
  .ktabs{{padding:6px 12px 8px 44px;max-width:100%;min-width:0;overflow-x:auto;flex-wrap:nowrap}}
  .stats{{padding:10px 12px;gap:8px}}
  .author-intake{{padding:10px 12px 14px}}
  .author-grid{{grid-template-columns:minmax(0,1fr);min-width:0}}
  section{{padding:16px 12px;min-width:0;max-width:100%}}
  .plot-box,.plot-frame,.table-scroll{{min-width:0;max-width:100%;width:100%}}
  .plot-box .js-plotly-plot,.plot-box .plot-container.plotly,.plot-box .svg-container{{width:100%!important;min-width:0;max-width:100%!important}}
  #plot-lz,#plot-sel-lz{{min-width:0;max-width:100%;overflow-x:hidden}}
  #plot-lz svg.lz-locuszoom,#plot-sel-lz svg.lz-locuszoom{{width:100%;min-width:0;max-width:100%}}
  .table-scroll>table{{width:max-content;min-width:100%;max-width:none}}
  .two-col,.three-col{{grid-template-columns:minmax(0,1fr);min-width:0;max-width:100%}}
}}
footer{{text-align:center;padding:16px;color:var(--muted);font-size:11px}}
</style>
</head><body>
<nav class="sidebar" id="report-sidebar" aria-hidden="false">
  <div class="brand">GrapeAncestry</div>
  <div class="sub"><span class="en">Interactive</span><span class="cn">交互报告</span></div>
  <h2><span class="en">Report</span><span class="cn">报告</span></h2>
  <a href="#sample-validity" class="active" onclick="return scrollToId('sample-validity')"><span class="en">Sample validity</span><span class="cn">样本有效性</span></a>
  <a href="#identity-placement" onclick="return scrollToId('identity-placement')"><span class="en">Identity &amp; placement</span><span class="cn">身份与定位</span></a>
  <a href="#population-placement" onclick="return scrollToId('population-placement')"><span class="en">Population placement</span><span class="cn">群体定位</span></a>
  <a href="#sample-evidence" onclick="return scrollToId('sample-evidence')"><span class="en">Sample evidence</span><span class="cn">样本证据</span></a>
  <a href="#panel-research" onclick="return scrollToId('panel-research')"><span class="en">Panel research</span><span class="cn">面板研究</span></a>
  <a href="#methods" onclick="return scrollToId('methods')"><span class="en">Methods</span><span class="cn">方法</span></a>
  <a href="#dl" onclick="return scrollToId('dl')"><span class="en">Downloads</span><span class="cn">下载</span></a>
</nav>
<button type="button" class="sidebar-toggle" id="sidebar-toggle" aria-controls="report-sidebar" aria-expanded="true" aria-label="Close report navigation" onclick="toggleSidebar()" title="Hide">◀</button>

<div class="main" id="main-content">
<div id="top-bar">
  <div id="pinned-sample">
    🔍 <span id="pin-iid" style="font-weight:700;color:var(--amber)">—</span>
    <span id="pin-acc" style="color:var(--muted)"></span>
    <span id="pin-detail" style="margin-left:8px"></span>
    <button class="clear-highlight" onclick="clearHighlight()" aria-label="Clear pinned sample" title="Clear pinned sample" style="float:right;background:var(--border);color:var(--text);border:none;padding:1px 8px;border-radius:3px;cursor:pointer;font-size:10px">✕</button>
  </div>
  <div class="browser-row">
    <span style="font-weight:600;font-size:11px;color:var(--accent)">🔍</span>
    <input type="range" id="sample-slider" min="0" max="0" value="0" aria-label="Sample browser position" title="Browse panel samples" oninput="updateBrowser();highlightOnSlide()" style="flex:1;min-width:100px;accent-color:var(--accent)"/>
    <span id="browser-idx" style="font-weight:700;color:var(--accent);font-size:11px;min-width:48px;text-align:center">0/0</span>
    <button class="browser-go" onclick="browserGo()" aria-label="Go to selected sample" title="Go to selected sample" style="padding:2px 10px;background:var(--accent);color:var(--on-accent);border:none;border-radius:3px;cursor:pointer;font-size:10px;font-weight:600"><span class="en">Go</span><span class="cn">前往</span>→</button>
    <input id="sample-search" type="search" aria-label="Search sample" title="Search by ID, variety, origin, or VIVC" placeholder="ID / variety / origin / VIVC" onkeydown="if(event.key==='Enter')searchGo()"/>
    <button class="sample-search-button" onclick="searchGo()" aria-label="Find sample" title="Find sample" style="padding:2px 10px;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:3px;cursor:pointer;font-size:10px;font-weight:600"><span class="en">Find</span><span class="cn">查找</span></button>
    <span id="browser-info" class="browser-info" style="font-size:11px;color:var(--muted);overflow-x:auto;white-space:nowrap;flex:1"></span>
    <div class="lang-control" role="group" aria-label="Report language">
      <span class="theme-label"><span class="en">Lang</span><span class="cn">语言</span></span>
      <button type="button" class="lang-choice" data-lang-choice="en" aria-pressed="true" aria-label="Use English" title="Use English">EN</button>
      <button type="button" class="lang-choice" data-lang-choice="zh" aria-pressed="false" aria-label="Use Chinese" title="Use Chinese">中文</button>
    </div>
    <div class="theme-control" role="group" aria-label="Report color theme">
      <span class="theme-label"><span class="en">Theme</span><span class="cn">主题</span></span>
      <button type="button" class="theme-choice" data-theme-choice="system" aria-pressed="true" aria-label="Use system theme" title="Use system theme"><span class="en">System</span><span class="cn">系统</span></button>
      <button type="button" class="theme-choice" data-theme-choice="light" aria-pressed="false" aria-label="Use light theme" title="Use light theme"><span class="en">Light</span><span class="cn">浅色</span></button>
      <button type="button" class="theme-choice" data-theme-choice="dark" aria-pressed="false" aria-label="Use dark theme" title="Use dark theme"><span class="en">Dark</span><span class="cn">深色</span></button>
    </div>
  </div>
  <div class="ktabs" id="ktabs">
    <span class="ktab-label" style="color:var(--muted);font-size:11px;margin-right:6px"><span class="en">ADMIXTURE K:</span><span class="cn">ADMIXTURE K：</span></span>
    <button class="kbtn" data-k="2" aria-label="Show ADMIXTURE K=2" title="Show ADMIXTURE K=2" onclick="loadK(2)">2</button>
    <button class="kbtn" data-k="3" aria-label="Show ADMIXTURE K=3" title="Show ADMIXTURE K=3" onclick="loadK(3)">3</button>
    <button class="kbtn" data-k="4" aria-label="Show ADMIXTURE K=4" title="Show ADMIXTURE K=4" onclick="loadK(4)">4</button>
    <button class="kbtn" data-k="5" aria-label="Show ADMIXTURE K=5" title="Show ADMIXTURE K=5" onclick="loadK(5)">5</button>
    <button class="kbtn" data-k="6" aria-label="Show ADMIXTURE K=6" title="Show ADMIXTURE K=6" onclick="loadK(6)">6</button>
    <button class="kbtn" data-k="7" aria-label="Show ADMIXTURE K=7" title="Show ADMIXTURE K=7" onclick="loadK(7)">7</button>
    <button class="kbtn active" data-k="8" aria-label="Show ADMIXTURE K=8" title="Show ADMIXTURE K=8" onclick="loadK(8)">8</button>
    <span class="muted" style="margin-left:12px"><span class="en">Black ★/◆ = query · yellow ◆ = pinned sample</span><span class="cn">黑色★/◆=查询样本 · 黄色◆=已钉住样本</span></span>
  </div>
</div>

<div class="stats">
  <div class="card"><div class="num" id="stat-n">—</div><div class="lbl"><span class="en">Panel</span><span class="cn">面板</span></div></div>
  <div class="card"><div class="num" id="stat-q">—</div><div class="lbl" id="stat-q-lbl"><span class="en">Query</span><span class="cn">查询</span></div></div>
  <div class="card"><div class="num" id="stat-dom">—</div><div class="lbl"><span class="en">K8 dominant</span><span class="cn">K8 主组分</span></div></div>
  <div class="card"><div class="num" id="stat-depth">—</div><div class="lbl"><span class="en">Mean depth</span><span class="cn">平均深度</span></div></div>
  <div class="card"><div class="num" id="stat-pcr">—</div><div class="lbl"><span class="en">Panel call%</span><span class="cn">面板分型率</span></div></div>
  <div class="card"><div class="num" id="stat-pc">—</div><div class="lbl"><span class="en">PC1–PC3</span><span class="cn">PC1–PC3</span></div></div>
  <div class="card"><div class="num" id="stat-pca-method">—</div><div class="lbl"><span class="en">PCA method</span><span class="cn">PCA 方法</span></div></div>
  <div class="card"><div class="num" id="stat-id">0</div><div class="lbl"><span class="en">Identical</span><span class="cn">完全相同</span></div></div>
  <div class="card"><div class="num" id="stat-po">0</div><div class="lbl"><span class="en">PO</span><span class="cn">亲子</span></div></div>
</div>
<div class="author-intake" id="author-intake"></div>

<section id="sample-validity"><h2><span class="en">Sample validity</span><span class="cn">样本有效性</span> <span class="scope-label"><span class="en">Query-derived</span><span class="cn">查询样本来源</span></span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> Start with the report identity, artifact provenance, method coverage, QC, and damage availability before interpreting placement or panel context.</div><div class="cn">怎么看：先确认报告身份、产物溯源、方法覆盖、质控和损伤信息，再解释样本定位或 panel 背景。</div></div>
<div id="report-meta"></div>
<div id="method-coverage"></div>

<section id="summary"><h2><span class="en">Conclusions</span><span class="cn">结论</span></h2>
<div class="sec-guide"><strong>How to read.</strong> Auto-written takeaways from the tables and plots below. Black ★/◆ is this query; yellow ◆ is a sample you pin by clicking a point, bar, or tree tip.
<div class="cn">怎么看：本页对各图/表的自动摘要。黑色★/◆是本查询样本；在图上点击可钉住一个对照样本（黄色◆）。</div></div>
<div class="info-box"><div class="en"><strong>Interaction</strong>: click a point/bar/tip to pin the sample.
Black ★/◆ identifies the query; yellow ◆ identifies the pinned sample.</div>
<div class="cn"><strong>交互</strong>：点击点/柱/叶即可钉住样本。黑色★/◆是查询样本；黄色◆是钉住的对照。</div></div>
<ul id="concl-list" class="muted"></ul>
<p class="muted">{merged_vcf_note}</p>
</section>

<section id="snapshot"><h2><span class="en">Query snapshot</span><span class="cn">样本速览</span></h2>
<div class="sec-guide"><strong>How to read.</strong> This sample’s ADMIXTURE K=8 after projection onto the 2449 model. The largest slice is the component it most resembles.
<div class="cn">怎么看：本样本投影到 2449 模型后的 K=8 组成。最大的一块就是最像的组分。</div></div>
<div class="info-box"><div class="en"><strong>Passport</strong>: filled only if this exact ID is in the 2449 panel
(<a href="https://doi.org/10.1126/science.add8655">Dong et al. 2023</a>
· <a href="https://www.vivc.de/">VIVC</a>).</div>
<div class="cn"><strong>护照信息</strong>：仅当该精确 ID 在 2449 面板中时填写
（<a href="https://doi.org/10.1126/science.add8655">Dong 等 2023</a>
· <a href="https://www.vivc.de/">VIVC</a>）。</div></div>
<div id="k8-legend" style="margin-bottom:8px"></div>
<div id="k8-paint-note" class="info-box"></div>
<div class="three-col">
  <div><h3><span class="en">K=8 composition</span><span class="cn">K=8 组成</span></h3><div id="query-q8"></div></div>
  <div><h3><span class="en">Metadata</span><span class="cn">元数据</span></h3><div id="query-meta"></div></div>
  <div><h3><span class="en">4K class counts</span><span class="cn">4K 类别计数</span></h3><div id="ibs-summary"></div></div>
</div>
</section>

<section id="qc"><h2><span class="en">Capture QC</span><span class="cn">捕获质控</span></h2>
<div class="sec-guide"><strong>How to read.</strong> Two calling rates are not the same.
<strong>Panel calling rate</strong> (highlighted) = called genotypes ÷ 167,433 chip sites — sites never written to the VCF count as failure.
<strong>VCF-site calling rate</strong> = called ÷ sites in this VCF (usually ~100% once a site is written; not capture success).
Depth includes zeros; median 0× means more than half the chip has no covering read.
<div class="cn">怎么看：两个分型率不是一回事。
<strong>Panel calling rate</strong>（高亮）= 已分型 ÷ 167,433 芯片位点（没写进 VCF 的位点也算失败）。
<strong>VCF-site calling rate</strong> = 已分型 ÷ 本 VCF 位点（位点一旦写出通常接近 100%，不能当捕获成功率）。
深度含 0；中位深度 0× 表示一半以上芯片位点没有覆盖 reads。</div></div>
<div id="qc-highlights"></div>
<div id="qc-table"></div>
<p class="muted" id="purity-note"></p>
</section>

<section id="damage"><h2><span class="en">Damage</span><span class="cn">损伤</span></h2>
<div class="info-box" id="damage-modern-note" hidden>
<strong><span class="en">Modern sample.</span><span class="cn">现代样品。</span></strong>
<div class="en">This is a modern PE source library. The ancient-DNA damage module is not applicable, so no damage plot is displayed.</div>
<div class="cn">这是现代 PE 来源文库。古 DNA 损伤模块不适用，因此不显示损伤图。</div>
</div>
<div class="sec-guide" id="damage-guide"><div class="en"><strong>How to read.</strong> mapDamage2 misincorporation
(<a href="https://doi.org/10.1093/bioinformatics/btr347">Ginolhac et al. 2011</a>;
<a href="https://doi.org/10.1093/bioinformatics/btt193">Jónsson et al. 2013</a>).
Left: from the 5′ end, red = C→T. Right: from the 3′ end (axis reversed so the terminus is on the right), blue = G→A. Grey = other substitutions.
Ancient DNA: both termini high, falling inward. The bar plot is the fragment-length histogram from the BAM.</div>
<div class="cn">怎么看：mapDamage2 误掺入
(<a href="https://doi.org/10.1093/bioinformatics/btr347">Ginolhac et al. 2011</a>；
<a href="https://doi.org/10.1093/bioinformatics/btt193">Jónsson et al. 2013</a>)。
左：从 5′ 起，红 = C→T。右：从 3′ 起（坐标反向，末端在右侧），蓝 = G→A。灰 = 其他替换。
古 DNA：两端升高、向内下降。柱图是 BAM 片段长度分布。</div></div>
<p id="damage-note" class="muted"></p>
<div class="plot-box" id="plot-damage"></div>
<div class="plot-box" id="plot-damage-len"></div>
</section>

</section>

<section id="identity-placement"><h2><span class="en">Identity &amp; placement</span><span class="cn">身份与定位</span> <span class="scope-label"><span class="en">Query vs 2449 panel</span><span class="cn">查询样本 vs 2449 面板</span></span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> Identity screens compare this query with the 4K reference set; clone/PO, IBS, KING, and nearest-reference results are query-versus-panel evidence.</div><div class="cn">怎么看：身份筛查把本查询与 4K 参考集比较；clone/亲子、IBS、KING 和最近参考样本都属于查询与 panel 的比较证据。</div></div>

<section id="clone"><h2><span class="en">Clone + PO list</span><span class="cn">克隆与亲子列表</span></h2>
<div class="sec-guide"><div class="en"><strong>How to use.</strong> Italy 4K Identical + Parent-Offspring hits. Click a row to pin that ref on PCA / ADMIXTURE / NJ.</div><div class="cn">怎么用：4K 筛到的 Identical / 亲子。点一行即可在 PCA、ADMIXTURE、NJ 上钉住该对照。</div></div>
<div class="info-box"><div class="en"><strong>Italy 4K screen</strong>: Identical + Parent-Offspring. Click a row to pin.</div>
<div class="cn"><strong>意大利 4K 筛查</strong>：完全相同 + 亲子。点一行即可钉住。</div></div>
<div id="clone-table"></div>
</section>

<section id="ibs"><h2><span class="en">IBS neighbors + Kinship</span><span class="cn">近邻与亲缘</span></h2>
<div class="sec-guide"><strong>How to read.</strong> Ranked 4K IBS neighbors and KING kinship. Click a ref ID to pin it on the ancestry plots.
<div class="cn">怎么看：4K IBS 近邻和 KING 亲缘排序。点对照 ID 可钉到祖源图上。</div></div>
<div class="info-box"><div class="en">Top 4K IBS rows and kinship ranking. Click ref to pin on plots.</div>
<div class="cn">4K IBS 近邻行和亲缘排序。点对照即可钉到图上。</div></div>
<div class="two-col">
  <div><h3><span class="en">IBS top</span><span class="cn">IBS 近邻</span></h3><div id="ibs-table"></div></div>
  <div><h3><span class="en">Kinship top</span><span class="cn">亲缘</span></h3><div id="kinship-table"></div></div>
</div>
</section>

 </section>

<section id="population-placement"><h2><span class="en">Population placement</span><span class="cn">群体定位</span> <span class="scope-label"><span class="en">Query vs 2449 panel</span><span class="cn">查询样本 vs 2449 面板</span></span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> PCA, ADMIXTURE, and the NJ tree show where this query sits relative to the 2449 panel. Panel summaries remain panel context; the query marker is a projection or observed genotype.</div><div class="cn">怎么看：PCA、ADMIXTURE 和 NJ 树显示本查询相对 2449 panel 的位置。panel 汇总只是 panel 背景；查询标记是投影或实际基因型。</div></div>

<section id="pca"><h2><span class="en">PCA</span><span class="cn">PCA</span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> The 2449 cloud uses frozen GCTA64 GRM-PCA reference axes on 153,483 non-GWAS chip sites
(<a href="https://doi.org/10.1016/j.ajhg.2010.11.011">Yang et al. 2011</a>; Vitis autosomes = 19).
This query is least-squares projected onto those axes
(<a href="https://doi.org/10.1371/journal.pgen.0020190">Patterson et al. 2006</a>).
2D (left) and 3D (right) use square canvases. PC2 is fixed at −0.01…0.01; other axes follow the data min/max. Points outside the PC2 window are not shown. Switch PC1–PC2 / PC1–PC3 / PC2–PC3. Click a point to pin.
Black ★/◆ = query; yellow ◆ = pinned.</div>
<div class="cn">怎么看：2449 点云使用冻结的 GCTA64 GRM-PCA 参考坐标轴（153,483 个非 GWAS 芯片位点；<a href="https://doi.org/10.1016/j.ajhg.2010.11.011">Yang 等 2011</a>）。本查询样本以最小二乘投影到这些轴上（<a href="https://doi.org/10.1371/journal.pgen.0020190">Patterson 等 2006</a>）。
二维/三维画布为正方形。PC2 固定 −0.01…0.01；其余轴按数据最小最大值。PC2 窗外的点不显示。可切换 PC 轴；点击钉住。黑★/◆=查询样本，黄◆=钉住的对照。</div></div>
<div class="info-box"><div class="en"><strong>PCA</strong>: switch PC axes on the left; 3D on the right.
Black ★/◆ = query; yellow ◆ = pinned sample. Click a point or tip to pin.
<span id="pca-method-note" class="pca-method-note-slot muted"></span></div>
<div class="cn"><strong>PCA</strong>：左侧切换 PC 轴；右侧为 3D。黑色★/◆=查询样本；黄色◆=钉住对照。点击点或叶即可钉住。
<span class="pca-method-note-slot muted"></span></div></div>
<div style="margin-bottom:10px">
  <span class="muted" style="margin-right:8px"><span class="en">2D axes:</span><span class="cn">二维坐标轴：</span></span>
  <button type="button" class="pca-axis-btn active" data-axes="0,1" aria-label="Show PC1–PC2 axes" title="Show PC1–PC2 axes" onclick="setPcaAxes(0,1)">PC1–PC2</button>
  <button type="button" class="pca-axis-btn" data-axes="0,2" aria-label="Show PC1–PC3 axes" title="Show PC1–PC3 axes" onclick="setPcaAxes(0,2)">PC1–PC3</button>
  <button type="button" class="pca-axis-btn" data-axes="1,2" aria-label="Show PC2–PC3 axes" title="Show PC2–PC3 axes" onclick="setPcaAxes(1,2)">PC2–PC3</button>
</div>
<div class="two-col">
  <div><h3><span class="en">2D</span><span class="cn">二维</span></h3><div class="plot-box" id="plot-pca"></div></div>
  <div><h3><span class="en">3D</span><span class="cn">三维</span></h3><div class="plot-box" id="plot-pca3d"></div></div>
</div></section>

<section id="admix-k28"><h2><span class="en">ADMIXTURE K=2–8</span><span class="cn">ADMIXTURE K=2–8</span></h2>
<div class="sec-guide"><strong>How to read.</strong>
Unsupervised ADMIXTURE at K=2–8 on the 2449 reference
(<a href="https://doi.org/10.1101/gr.094052.109">Alexander et al. 2009</a>).
Rows share one sample order. Colours are matched K→K+1 by greedy Pearson correlation of Q (label switching).
A colour that continues down a column is the same component; a new colour is a split at that K.
Palette follows <a href="https://doi.org/10.1126/science.add8655">Dong et al. 2023</a> Fig. 1D.
The right-hand column is this sample projected onto the frozen allele-frequency matrix (ADMIXTURE <code>-P</code>), not a new unsupervised run.
<div class="cn">怎么看：2449 参考集上 K=2–8 的无监督 ADMIXTURE。各行样本顺序相同。颜色按相邻 K 的 Q 列 Pearson 相关贪婪匹配（label switching）。一列上下同色=同一组分；新颜色=该 K 发生分裂。右侧一列是本样本投影到冻结的等位基因频率矩阵（ADMIXTURE -P），不是一次新的无监督拟合。</div></div>
<div class="plot-static"><img src="{sample}.admixture_k2_8.png" alt="ADMIXTURE K=2 to K=8"/></div>
</section>

<section id="admix"><h2><span class="en">ADMIXTURE bar (K tabs)</span><span class="cn">ADMIXTURE 柱图（K 标签）</span></h2>
<div class="sec-guide"><strong>How to use.</strong> One K at a time (top K tabs). Full = whole panel; Compact = even subsample per group. In-panel query uses lookup Q; when Q exists it is a separate right-hand column. Click a bar to pin.
<div class="cn">怎么用：顶部 K 标签一次看一个 K。Full=全 panel；Compact=每组均匀抽。库内样本用 lookup Q；有 Q 时查询样本单独一列。点柱钉住。</div></div>
<div class="info-box"><div class="en"><strong>Bar</strong>: stacked Q in deterministic report-group order.
Default shows the full panel; compact mode samples evenly within groups. In-panel query uses
<strong>lookup</strong> Q at its group position. When Q exists on this strip, the query is a
<strong>separate right-hand column</strong>.</div>
<div class="cn"><strong>柱图</strong>：按确定的报告分组顺序堆叠 Q。默认显示完整面板；紧凑模式在组内均匀抽样。面板内查询在其组位置使用 <strong>lookup</strong> Q。当本条带有 Q 时，查询样本单独占<strong>右侧一列</strong>。</div></div>
<div style="display:flex;align-items:center;gap:6px;margin:8px 0">
  <span class="muted" style="font-size:11px"><span class="en">View:</span><span class="cn">视图：</span></span>
  <button type="button" id="admix-full-btn" class="pca-axis-btn active" aria-label="Show full panel" title="Show full panel" onclick="setAdmixView(false)"><span class="en">Full</span><span class="cn">完整</span></button>
  <button type="button" id="admix-compact-btn" class="pca-axis-btn" aria-label="Show compact panel" title="Show compact panel" onclick="setAdmixView(true)"><span class="en">Compact</span><span class="cn">紧凑</span></button>
</div>
<div class="plot-box" id="plot-bar"></div></section>

<section id="tree"><h2><span class="en">NJ Tree</span><span class="cn">NJ 树</span></h2>
<div class="sec-guide"><strong>How to use.</strong> Neighbor-Joining on IBS genotype-identity (Saitou &amp; Nei 1987). Default view is a centered equal-angle circular phylogram (radius = path length from the root). Switch to rectangular to scroll the ladder. Click a tip to pin.
<div class="cn">怎么用：IBS 基因型距离的 NJ 树（Saitou &amp; Nei 1987）。默认居中等角圆形树（半径=到根的路径长）。可切到矩形阶梯图并在框内滚动。点叶钉住。</div></div>
<div class="info-box"><div class="en"><strong>NJ</strong>: IBS genotype-identity distance → Neighbor-Joining
(Saitou &amp; Nei 1987, doi:10.1093/oxfordjournals.molbev.a040454). <strong>All 2449 + query</strong>.
Circular = equal-angle phylogram; rectangular = rooted ladder (scroll in the 720px box).</div>
<div class="cn"><strong>NJ</strong>：IBS 基因型同一度距离 → 邻接法
（Saitou &amp; Nei 1987，doi:10.1093/oxfordjournals.molbev.a040454）。<strong>全部 2449 + 查询样本</strong>。
圆形=等角系统树；矩形=有根阶梯图（在 720px 框内滚动）。</div></div>
<div style="margin-bottom:8px">
  <span class="muted" style="font-size:11px"><span class="en">Layout:</span><span class="cn">布局：</span></span>
  <button type="button" id="tree-circ-btn" class="tree-shape-btn active" aria-label="Show circular tree" title="Show circular tree" onclick="setTreeShape('circular')"><span class="en">Circular</span><span class="cn">圆形</span></button>
  <button type="button" id="tree-rect-btn" class="tree-shape-btn" aria-label="Show rectangular tree" title="Show rectangular tree" onclick="setTreeShape('rectangular')"><span class="en">Rectangular</span><span class="cn">矩形</span></button>
</div>
<div class="plot-frame tree-circ" id="tree-frame"><div class="plot-box" id="plot-tree"></div></div></section>

<section id="fstats"><h2><span class="en">f3 / f4</span><span class="cn">f3 / f4</span></h2>
<details class="advanced-fstats" open>
<summary><span class="en">Advanced exploratory allele sharing</span><span class="cn">探索性等位基因共享</span></summary>
<div class="sec-guide"><strong>How to read.</strong> Reference means are 2449 panel <strong>Grp</strong> means. The query is <strong>one query genotype, not a target population</strong>. Missing query sites are excluded per contrast. Top left: outgroup-f3 <em>f3(OUT; query, Grp)</em> — higher = more shared drift with that Grp mean (whiskers = chromosome-block jackknife SE; blue |Z|≥3). Top right: pairwise <em>f4(query, OUT; A, B)</em>. Bottom: exploratory f3 <em>f3(query; A, B)</em>; it is not a formal qp3Pop/qpDstat/qpAdm/qpGraph result.
<div class="cn">怎么看：参考均值来自 2449 panel 的 <strong>Grp</strong>。查询是<strong>一个基因型，不是目标群体</strong>；每个 contrast 排除缺失查询位点。上排左 outgroup-f3 越高越接近该 Grp 均值。上排右 f4 成对柱。下图是探索性 f3，不是正式的 qp3Pop/qpDstat/qpAdm/qpGraph 结果。</div></div>
<div class="info-box"><div class="en"><strong>Advanced exploratory allele sharing</strong>: Patterson et al. 2012 <em>Genetics</em> 192:1065–1093,
https://doi.org/10.1534/genetics.112.145037.
Reference means = 2449 panel Grp means; one query genotype, not a target population; missing query sites are excluded per contrast.
Tables and tooltips show complete-case <strong>n_sites</strong> and chromosome-block <strong>n_blocks</strong>.
OUT handling is conditional: when designated OUT is present, its actual n is reported and it is retained even when n &lt; min_n without satisfying min_n; when no designated OUT is available, outgroup-f3/f4 are unavailable.
This is not qp3Pop/qpDstat/qpAdm/qpGraph; no formal population-mixture or graph fit is claimed.</div>
<div class="cn"><strong>探索性等位基因共享</strong>：Patterson 等 2012 <em>Genetics</em> 192:1065–1093，
https://doi.org/10.1534/genetics.112.145037。
参考均值=2449 panel 的 Grp 均值；查询是一个基因型，不是目标群体；每个 contrast 排除缺失查询位点。
表格和提示显示完整案例 <strong>n_sites</strong> 与染色体块 <strong>n_blocks</strong>。
OUT 处理是条件的：有指定 OUT 时报告实际 n，即使 n &lt; min_n 也保留，但不视为满足 min_n；没有指定 OUT 时，外群 f3/f4 不可用。
这不是 qp3Pop/qpDstat/qpAdm/qpGraph；不声称正式的群体混合或图拟合。</div></div>
<div id="fstats-callout"></div>
<div class="two-col">
  <div class="plot-box" id="plot-f3-out"></div>
  <div class="plot-box" id="plot-f4"></div>
</div>
<h3><span class="en">Exploratory f3  f3(Q; A, B)</span><span class="cn">探索性 f3：f3(Q; A, B)</span></h3>
<div class="plot-box" id="plot-f3"></div>
<div id="fstats-tables"></div>
</details>
</section>

 </section>

<section id="sample-evidence"><h2><span class="en">Observed in this sample</span><span class="cn">本样品实际观测</span> <span class="scope-label"><span class="en">Query-derived</span><span class="cn">查询样本来源</span></span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> This section reports query genotypes and per-query predictions. A panel association, trait label, or CV score supplies context; the active evidence is the query call.</div><div class="cn">怎么看：本节只报告查询样本的实际基因型和逐样本预测。panel 关联、性状标签或交叉验证分数提供背景；当前证据以查询样本分型为主。</div></div>
<h3><span class="en">Query genotype evidence</span><span class="cn">查询样本基因型证据</span></h3>
<div id="query-evidence"></div>
<h3><span class="en">Per-query GS predictions</span><span class="cn">本查询 GS 预测</span> <span class="scope-label"><span class="en">Query-derived</span><span class="cn">查询样本来源</span></span></h3>
<div id="gs-pred"></div>
</section>

<details id="panel-research" open>
<summary><span class="en">Panel research context</span><span class="cn">2449 panel 研究背景</span></summary>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> The following analyses describe the 2449 panel or published reference context. Query genotype overlays are labelled as overlays; panel statistics remain the active computation.</div><div class="cn">怎么看：以下分析描述 2449 panel 或已发表参考背景。查询基因型叠加会明确标为 overlay；面板统计量仍是当前计算。</div></div>

<section id="sel"><h2><span class="en">Selection scan</span><span class="cn">选择扫描</span> <span class="tag tag-red">unphased 167K</span> <span class="scope-label"><span class="en">2449 panel only</span><span class="cn">仅 2449 面板</span></span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> Screening contrast is <strong>simplified Fst (Grp vs rest)</strong> — pick a Grp. Red = sweep: that Grp’s simplified Fst (Grp vs rest) in the top 5% <em>and</em> within-Grp windowed heterozygosity in the bottom 5%. Blue/yellow = chromosomes. Green bands = our five named MAS/GWAS windows. The heatmap summarizes the same two statistics at those windows, followed by this sample’s overlapping sites → LocusZoom. Unphased 167K; active computation is shown below.</div><div class="cn">怎么看：筛选对照是<strong>简化 Fst（Grp 对其余样品）</strong>，请先选组。红点 = sweep：该组简化 Fst（Grp 对其余样品）最高 5% 且组内窗口杂合度最低 5%。蓝/黄=染色体。绿带=五个命名 MAS/GWAS 窗口。热图汇总这些窗口的同一套统计，随后查看本样品重合位点 → LocusZoom。未定相 167K；下方展示当前计算。</div></div>
<div class="info-box"><div class="en"><strong>Selection data and method.</strong> Unphased ±50 kb windowed heterozygosity + simplified Fst (Grp vs rest) on the 167K chip. LocusZoom.js 0.14.0 (Boughton et al. 2021, https://doi.org/10.1093/bioinformatics/btab186). Named MAS/GWAS windows are summarized in the active plots.</div><div class="cn"><strong>选择数据与方法。</strong> 167K 芯片上的未定相 ±50 kb 窗口杂合度 + 简化 Fst（Grp 对其余样品）。LocusZoom.js 0.14.0（Boughton 等 2021，https://doi.org/10.1093/bioinformatics/btab186）。命名 MAS/GWAS 窗口由当前图表汇总。</div></div>
<h3><span class="en">1. Genome-wide (2449 panel)</span><span class="cn">1. 全基因组（2449 面板）</span></h3>
<label for="sel-manh-metric"><span class="en">Y</span><span class="cn">纵轴</span></label>
<select id="sel-manh-metric">
  <option value="fst" data-i18n-en="simplified Fst (Grp vs rest)" data-i18n-zh="简化 Fst（Grp 对其余样品）">simplified Fst (Grp vs rest)</option>
  <option value="het" data-i18n-en="windowed heterozygosity (this Grp)" data-i18n-zh="组内窗口杂合度">windowed heterozygosity (this Grp)</option>
</select>
<span id="sel-manh-grp-wrap">
<label for="sel-manh-grp"><span class="en">Grp</span><span class="cn">组别</span></label>
<select id="sel-manh-grp"></select>
</span>
<div class="muted" style="font-size:11px;margin:4px 0 8px"><div class="en">Default Grp = largest n. Red = sweep. The last menu item reports Fst among all Grps. Blue/yellow identify chromosomes.</div><div class="cn">默认 Grp = n 最大的组。红点 = sweep。最后一个菜单项报告全体 Grp 的 Fst。蓝/黄表示染色体。</div></div>
<div class="plot-box" id="plot-sel-manh"></div>
<h3><span class="en">Sweep sites (this Grp)</span><span class="cn">Sweep 位点（该 Grp）</span></h3>
<div class="muted" style="font-size:11px;margin:4px 0 8px"><div class="en">Our 167K sweep calls are shown here; literature intervals are checked separately. Red dots = this Grp’s simplified Fst (Grp vs rest) ≥ 95th <em>and</em> within-Grp windowed heterozygosity ≤ 5%. Sweep rows highlight the exact Manhattan site: the button pins a white star on the plot above and scrolls to it.</div><div class="cn">这里展示 167K sweep；文献区间另行核对。红点 = 该组简化 Fst（Grp 对其余样品）≥95% 且组内窗口杂合度 ≤5%。Sweep 行会高亮精确 Manhattan 位点：按钮在上方图里钉一颗白星并滚到该图。</div></div>
<div id="sel-sweep-table"></div>
<h3><span class="en">5 named loci × Grp</span><span class="cn">5 个命名位点 × Grp</span></h3>
<div class="info-box" id="named-window-why">
<div class="en"><strong>Why these five.</strong>
These five windows are the MAS/GWAS windows on the 167K chip.
(<code>data/panel/selection_windows.tsv</code>). Dong 2023 Table S29 intervals are checked separately in the Reference-only section, while genome-wide red sweeps use a different rule.
<strong>Colour (OIV 225)</strong>: classic VvMybA (<code>2:5116947</code> ±10 kb) plus two Science GWAS predictors
(<em>Vvsyl02G000229</em>, <em>Vvsyl02G001064</em>).
<a href="https://doi.org/10.1126/science.add8655">Dong et al. 2023</a>
call those two <em>better predictors of berry skin colors</em> than VvMybA.
<strong>Flower sex (OIV 151)</strong>: the SDR interval chr2:14,165,010–14,345,273.
H1–H5 is Dong et al. literature context. Panel H1/H2 or other SDR tags are panel annotations.
<strong>Muscat (OIV 236)</strong>: VvDXS window around Science chr5:19,419,686
(panel tag <code>5:19418903</code> is 783 bp away).
No OIV 241 locus overlap found in the panel GWAS. Green bands, heatmap columns, green stars, and Table A use this list.</div>
<div class="cn">为什么是这五个：这五个窗口是 167K 芯片上的 MAS/GWAS 窗口。(<code>data/panel/selection_windows.tsv</code>)。Dong 2023 表 S29 区间在“仅作参考”部分单独核对；全基因组红色 sweep 使用另一套规则。
<strong>皮色（OIV 225）</strong>：经典 VvMybA（<code>2:5116947</code> ±10 kb），加上论文里两个皮色 GWAS 预测基因 <em>Vvsyl02G000229</em>、<em>Vvsyl02G001064</em>（Dong 等 2023 写它们比 VvMybA 更能预测果皮颜色）。
<strong>花性（OIV 151）</strong>：SDR 区间 chr2:14,165,010–14,345,273。H1–H5 仅作 Dong 等文献背景。面板 H1/H2 或其他 SDR 标签是面板注释。
<strong>麝香（OIV 236）</strong>：VvDXS 窗口，论文坐标 chr5:19,419,686（芯片标签 <code>5:19418903</code> 相差 783 bp）。
panel GWAS 未发现 OIV 241 位点重合。绿带、热图列、绿星和 Table A 均使用这份清单。</div>
</div>
<label for="sel-heat-metric"><span class="en">Number in cell</span><span class="cn">单元格数值</span></label>
<select id="sel-heat-metric">
  <option value="fst" data-i18n-en="simplified Fst (Grp vs rest)" data-i18n-zh="简化 Fst（Grp 对其余样品）">simplified Fst (Grp vs rest)</option>
  <option value="het" data-i18n-en="windowed heterozygosity (this Grp)" data-i18n-zh="组内窗口杂合度">windowed heterozygosity (this Grp)</option>
</select>
<div class="muted" style="font-size:11px;margin:4px 0 8px"><div class="en">Columns are the five windows; rows are 2449 panel Grps. One cell = mean of chip SNPs <em>inside that window only</em>. The Fst cells are simplified Fst (Grp vs rest). Numbers on cells are the values; colour ranks this 12×5 table (Fst here tops out near 0.04). Click a cell → LocusZoom.</div><div class="cn">横轴是五个窗口；纵轴是 2449 面板 Grp。一格 = 该窗口内芯片位点的平均。Fst 格是简化 Fst（Grp 对其余样品）。格子上的数字才是数值，颜色表示这张 12×5 表的相对深浅（这里 Fst 最高约 0.04）。点一格跳 LocusZoom。</div></div>
<div class="plot-box" id="plot-sel-heat"></div>
<h3><span class="en">Fst vs het</span><span class="cn">Fst 与杂合度</span></h3>
<div class="muted" style="font-size:11px;margin:4px 0 8px"><div class="en">Grey is the shared deterministic stride-30 subsample; green stars are <strong>means of all SNPs in the named windows</strong> — the same mean het / Fst among all Grps as Table A. The y-axis is Fst among all Grps. The SDR window stays heterozygous in the panel; H1–H5 remains Dong et al. literature context, and panel SDR tags are panel annotations.</div><div class="cn">灰点是共用确定性 stride-30 子样本；绿星是<strong>命名窗口内所有 SNP 的均值</strong>，与表 A 的 mean het / 全体 Grp 的 Fst 相同。纵轴是全体 Grp 的 Fst。SDR 窗口在 panel 中仍保持杂合；H1–H5 仅作 Dong 等文献背景，面板 SDR 标签是面板注释。</div></div>
<div class="plot-box" id="plot-sel-scatter"></div>
<div id="sel-table"></div>
<h3><span class="en">2. This sample at overlapping sites</span><span class="cn">2. 本样品重合位点</span></h3>
<div id="sel-query-sites"></div>
<h3 id="sel-lz"><span class="en">3. Panel regional context (among-Grps Fst)</span><span class="cn">3. 面板区域背景（全体 Grp 的 Fst）</span></h3>
<div class="muted" style="font-size:11px;margin:4px 0 8px"><div class="en"><strong>Panel regional context (among-Grps Fst).</strong> LocusZoom covers the five named windows, S29 windows with chip coverage, and overall among-Grps peaks already present in <code>selection_loci</code>. This view reports regional panel context; the active sweep contrast is shown above.</div><div class="cn"><strong>面板区域背景（全体 Grp 的 Fst）。</strong> LocusZoom 覆盖五个命名窗口、有芯片覆盖的 S29 窗口，以及 <code>selection_loci</code> 中已有的全体 Grp 峰。这里报告面板区域背景；上方展示当前 sweep 对照。</div></div>
<label for="sel-lz-pick"><span class="en">Window</span><span class="cn">窗口</span></label>
<select id="sel-lz-pick"></select>
<label for="sel-lz-metric"><span class="en">Y</span><span class="cn">纵轴</span></label>
<select id="sel-lz-metric">
  <option value="fst" data-i18n-en="Fst among all Grps" data-i18n-zh="全体 Grp 的 Fst">Fst among all Grps</option>
  <option value="het" data-i18n-en="windowed heterozygosity" data-i18n-zh="窗口杂合度">windowed heterozygosity</option>
  <option value="both" data-i18n-en="Fst + het (stacked)" data-i18n-zh="Fst + 杂合度（上下堆叠）">Fst + het (stacked)</option>
</select>
<div id="sel-lz-meta" class="muted"></div>
<div class="plot-box" id="plot-sel-lz"></div>
<div id="sel-gt-card"></div>
<div id="plot-sel-gt"></div>
<div id="sel-lz-detail" class="info-box"></div>
<details class="ref-only" open>
<summary><strong><span class="en">Reference only.</span><span class="cn">仅作核对。</span></strong> <span class="scope-label"><span class="en">Reference only</span><span class="cn">仅作核对</span></span> <span class="en">Reference-only S29 overlap check. Dong 2023 shared CG1∩CG2 domestication bins (paper Table S29) — reference context.</span><span class="cn">仅作参考的 S29 重合核对。Dong 2023 CG1∩CG2 共同驯化区间（论文表 S29）— 文献背景。</span></summary>
<div class="muted" style="font-size:12px;margin:8px 0"><div class="en">Dong et al. 2023 <em>Science</em> 379:892–901, <a href="https://doi.org/10.1126/science.add8655">doi:10.1126/science.add8655</a>. They scanned Syl-E1/CG1 and Syl-E2/CG2 against their wild pairs; the main-text rule used increased nucleotide-diversity difference and population differentiation, both top 5% (Fig. 3D). Table S28 contains the two group lists; <strong>Table S29 is the intersection of the two lists</strong>: 189 genes in 31 regions. This section reports the 167K chip interval-overlap check and the overlap with our five MAS/GWAS windows. Our extract has 30 unique intervals (paper: 31 regions).</div><div class="cn">Dong 等 2023《Science》379:892–901，<a href="https://doi.org/10.1126/science.add8655">doi:10.1126/science.add8655</a>。论文比较 Syl-E1/CG1 和 Syl-E2/CG2 与野生配对组，正文规则要求核苷酸多样性差异和群体分化均进入前 5%（图 3D）。表 S28 是两组清单；<strong>表 S29 是两组清单的交集</strong>，含 189 个基因、31 个区间。本节报告 167K 芯片区间重合，以及与五个 MAS/GWAS 窗口的重合。我们的提取有 30 个不重复区间（论文为 31 个）。</div></div>
<div id="sel-s29-ref"></div>
</details>
</section>

<section id="traits"><h2><span class="en">Trait loci</span><span class="cn">性状位点</span> <span class="scope-label"><span class="en">2449 panel only</span><span class="cn">仅 2449 面板</span></span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> Design-time overlap of this 167K panel with GWAS/MAS trait loci. IDs in the table are outbound database links. Gene product/GO are SwissProt BLAST xrefs (homology).</div><div class="cn">怎么看：167K panel 与 GWAS/MAS 性状位点的设计期重叠。表中 ID 是外链。产物/GO 是 SwissProt BLAST 同源注释。</div></div>
<div class="info-box"><div class="en"><strong>Panel overlap</strong> with design-time GWAS/MAS loci
(up to 40 rows, round-robin across traits; Dong 2023 MAS colour/SDR sites first).
Gene span / strand / region from the VS-1 annotation.
OIV descriptors from the OIV 2009 list.
OIV codes link to EU-Vitis descriptor PDFs
(http://www.eu-vitis.de/docs/descriptors/oivdesc/) and the OIV 2009 2nd edition
list (https://www.oiv.int/node/2830). Some des-cep-only codes have no PDF.
Product / GO / Pfam / InterPro / EC are <strong>SwissProt BLAST xrefs</strong>
(DIAMOND bits ≥ 100; UniProt REST of the hit accession — homology).
Grape IDs: Ensembl Plants PN40024.T2T <code>ASM3070453v1</code> pep (gene / gene_symbol),
Entrez / RefSeq TSV, KEGG <code>vvi</code> via NCBI GeneID.
Buchfink et al. 2021 <em>Nat Methods</em> 18:366, https://doi.org/10.1038/s41592-021-01101-x;
UniProt API https://www.uniprot.org/help/api_queries ;
Ensembl Plants https://plants.ensembl.org/Vitis_vinifera/Info/Index ;
KEGG REST https://www.kegg.jp/kegg/rest/keggapi.html ;
NCBI gene_info https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Plants/ .
IDs in the table are outbound record links (QuickGO, InterPro/Pfam, KEGG, Ensembl Plants, NCBI Gene, UniProt, Expasy EC, OIV).
Known aliases from Dong et al. 2023 <em>Science</em> 379:892–901
(doi:10.1126/science.add8655).</div><div class="cn"><strong>面板与设计期 GWAS/MAS 位点的重合</strong>
（最多 40 行，按性状轮转；Dong 2023 的皮色/SDR 位点优先）。
基因跨度 / 链 / 区域来自 VS-1 注释。
OIV 描述符来自 OIV 2009 清单。
OIV 代码链到 EU-Vitis 描述符 PDF
（http://www.eu-vitis.de/docs/descriptors/oivdesc/）和 OIV 2009 第 2 版清单
（https://www.oiv.int/node/2830）。部分仅 des-cep 代码没有 PDF。
产物 / GO / Pfam / InterPro / EC 是 <strong>SwissProt BLAST 交叉引用</strong>
（DIAMOND bits ≥ 100；命中登录号的 UniProt REST — 同源）。
葡萄 ID：Ensembl Plants PN40024.T2T <code>ASM3070453v1</code> pep（gene / gene_symbol）、
Entrez / RefSeq TSV、经 NCBI GeneID 的 KEGG <code>vvi</code>。
Buchfink 等 2021 <em>Nat Methods</em> 18:366，https://doi.org/10.1038/s41592-021-01101-x；
UniProt API https://www.uniprot.org/help/api_queries ；
Ensembl Plants https://plants.ensembl.org/Vitis_vinifera/Info/Index ；
KEGG REST https://www.kegg.jp/kegg/rest/keggapi.html ；
NCBI gene_info https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Plants/ 。
表中 ID 是外链记录（QuickGO、InterPro/Pfam、KEGG、Ensembl Plants、NCBI Gene、UniProt、Expasy EC、OIV）。
已知别名来自 Dong 等 2023 <em>Science</em> 379:892–901
（doi:10.1126/science.add8655）。</div></div>
<div id="trait-table"></div>
</section>

<section id="breeding"><h2><span class="en">Panel GWAS / panel GS</span><span class="cn">面板育种</span> <span class="scope-label"><span class="en">2449 panel only</span><span class="cn">仅 2449 面板</span></span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> Panel GWAS/GS index. LocusZoom: drag to pan, scroll to zoom, click a SNP or gene. Association / r² / β are panel EMMAX/P3D. The panel track supplies the query genotype overlay; per-query GS predictions are reported above.</div><div class="cn">怎么看：panel 的 GWAS/GS 索引。LocusZoom 可拖动平移、滚轮缩放、点击 SNP 或基因。关联/r²/β 来自 2449；panel 轨道提供查询样本基因型叠加；逐样本 GS 预测见上方。</div></div>
<div class="info-box"><div class="en"><strong>GWAS / GS panel index and regional context.</strong> Regional plot is <strong>LocusZoom.js 0.14.0</strong>
(Boughton et al. 2021, https://doi.org/10.1093/bioinformatics/btab186;
classic layout Pruim et al. 2010, https://doi.org/10.1093/bioinformatics/btq419).
Association points and gene track are the library.
LD colour = panel-dosage r² to the lead (2449 freeze).
Genes = VS-1 GFF. Query GT is this sample.
Panel GWAS sites: 13,950 design-time loci; n≈400.
Binary case/control counts come from each trait’s <code>summary.json</code>; imbalanced binary traits need caution.
See <code>docs/METHODS_breeding.md</code> and Kang et al. 2010 EMMAX/LMM
(https://doi.org/10.1038/ng.548).</div><div class="cn"><strong>GWAS / GS 面板索引与区域背景。</strong> 区域图是 <strong>LocusZoom.js 0.14.0</strong>
（Boughton 等 2021，https://doi.org/10.1093/bioinformatics/btab186；
经典布局 Pruim 等 2010，https://doi.org/10.1093/bioinformatics/btq419）。
关联点和基因轨道来自该库。
LD 颜色 = 相对主位点的面板 dosage r²（2449 冻结）。
基因 = VS-1 GFF。Query GT 是本样品。
面板 GWAS 位点：13,950 个设计期位点；n≈400。
二元病例/对照计数来自各性状的 <code>summary.json</code>；不平衡二元性状需谨慎。
见 <code>docs/METHODS_breeding.md</code> 与 Kang 等 2010 EMMAX/LMM
（https://doi.org/10.1038/ng.548）。</div></div>
<p id="breeding-note" class="muted"></p>
<div id="gwas-index"></div>
<h3><span class="en">LocusZoom (panel GWAS)</span><span class="cn">LocusZoom（面板 GWAS）</span></h3>
<div id="gwas-loci">
<div class="muted"><div class="en">Official LocusZoom.js: drag to pan, scroll to zoom, click a SNP or gene. Association / r² / β = panel EMMAX/P3D. Genes = VS-1. Query GT = this sample. Boughton et al. 2021, https://doi.org/10.1093/bioinformatics/btab186.</div><div class="cn">官方 LocusZoom.js：拖动平移、滚轮缩放、点击 SNP 或基因。关联/r²/β = panel EMMAX/P3D；基因 = VS-1；Query GT = 本样品分型。Boughton 等 2021，https://doi.org/10.1093/bioinformatics/btab186。</div></div>
<label for="lz-pick"><span class="en">Locus</span><span class="cn">位点</span></label>
<select id="lz-pick"></select>
<div id="lz-meta" class="muted"></div>
<div class="plot-box" id="plot-lz"></div>
<div id="lz-gt-card"></div>
<div id="plot-lz-gt"></div>
<div id="lz-detail" class="info-box"></div>
<div id="lz-bonf"></div>
</div>
<h3><span class="en">GS accuracy</span><span class="cn">GS 准确度</span></h3>
<div id="gs-index"></div>
<h3><span class="en">Top crosses</span><span class="cn">推荐杂交组合</span></h3>
<div id="cross-top"></div>
</section>

</details>

<section id="methods"><h2><span class="en">Methods</span><span class="cn">方法说明</span></h2>
<div class="sec-guide"><div class="en"><strong>How to read.</strong> Appendix: PCA method, 4K identity cutoffs, ADMIXTURE K=2–8 colours, QC rate definitions, and selection/f3 caveats. Read this last; the plots above are the working view.</div><div class="cn">怎么看：附录。PCA 方法、4K 身份阈值、ADMIXTURE 着色、QC 定义、选择/f3 限制。工作浏览请看上面各节，方法放最后。</div></div>
<div class="info-box"><div class="en"><strong>PCA method</strong>: <span id="method-card" class="method-card-slot">Loading…</span>.
PC1–PC3 are displayed when available; reported percentages use explained-variance fractions only.</div>
<div class="cn"><strong>PCA 方法</strong>：<span class="method-card-slot">加载中…</span>。
有 PC1–PC3 时显示；报告百分比只用解释方差分数。</div></div>
<div class="info-box"><div class="en"><strong>Identity (4K)</strong>: Identical R1≥1.2 + IBS2*%≥0.99 + KING≥0.3426;
PO: 0.5&lt;R1&lt;1.2 + 0.21≤KING&lt;0.3426 + R0≤0.096. Self-in-panel reported as QC then nearest non-self.</div>
<div class="cn"><strong>身份（4K）</strong>：完全相同 R1≥1.2 + IBS2*%≥0.99 + KING≥0.3426；
亲子：0.5&lt;R1&lt;1.2 + 0.21≤KING&lt;0.3426 + R0≤0.096。面板内自身先作质控，再报告最近非自身。</div></div>
<div class="info-box" id="admix-methods"><div class="en"><strong>ADMIXTURE</strong>: Loading…</div>
<div class="cn"><strong>ADMIXTURE</strong>：加载中…</div></div>
<div class="info-box"><div class="en"><strong>Source</strong>:</div>
<div class="cn"><strong>来源</strong>：</div>
<div id="admix-provenance"><span class="en">Loading…</span><span class="cn">加载中…</span></div></div>
<div class="info-box"><div class="en"><strong>QC calling rates</strong>: <em>panel</em> rate = called / 167K panel sites (primary);
<em>VCF-site</em> rate = called / sites present in the sample VCF.</div>
<div class="cn"><strong>QC 分型率</strong>：<em>panel</em> 分型率 = 已分型 / 167K 面板位点（主指标）；
<em>VCF-site</em> 分型率 = 已分型 / 本样品 VCF 中的位点。</div></div>
<div class="info-box"><div class="en"><strong>Scope boundary: exclusions and literature comparisons are summarized here.</strong> Reader-facing panels above lead with their active computation. Selection: unphased ±50 kb windowed heterozygosity + simplified Fst (Grp vs rest) on the 167K chip; sweep = Fst ≥95th ∩ within-Grp windowed heterozygosity ≤5th. Regional / Table A context uses Fst among all Grps. These Fst values are a simplified estimator, not a canonical Weir–Cockerham implementation. Dong 2023 Table S29 (doi:10.1126/science.add8655) is the CG1∩CG2 shared-bin reference (189 genes / 31 regions), and its interval overlap is reported separately. Regional view is LocusZoom.js (Y = Fst among all Grps or windowed heterozygosity). Displayed PCA uses frozen GCTA64 GRM-PCA axes with least-squares query projection, not a 5k-SNP SVD. f3/f4 are exploratory 2449 panel Grp-mean allele-frequency summaries with complete-case n_sites and n_blocks (Patterson et al. 2012, doi:10.1534/genetics.112.145037).</div><div class="cn"><strong>范围边界：排除项和文献比较统一在这里说明。</strong> 上方读者区域优先展示当前计算。选择扫描使用 167K 未定相窗口杂合度与简化 Fst（Grp 对其余样品）；sweep 使用 Fst ≥95% 且组内窗口杂合度 ≤5%。区域 / 表 A 使用全体 Grp 的 Fst。这些 Fst 是简化估计，不是规范 Weir–Cockerham 实现。Dong 2023 表 S29（doi:10.1126/science.add8655）是 CG1∩CG2 共同区间参考（189 个基因 / 31 个区间），其区间重合单独报告。区域图使用 LocusZoom.js；显示的 PCA 使用冻结 GCTA64 GRM-PCA 轴加最小二乘查询投影，不是 5k SNP 的 SVD。f3/f4 是探索性的 2449 面板 Grp 均值等位基因频率汇总，并报告完整案例 n_sites 和 n_blocks（Patterson 等 2012，doi:10.1534/genetics.112.145037）。</div></div>
<div id="methods-embed"></div>
</section>

<section id="dl"><h2><span class="en">Downloads</span><span class="cn">下载</span></h2>
<div class="sec-guide"><span class="en"><strong>How to use.</strong> This query’s own tables only (QC, this sample’s Q, damage, clone/PO, kinship). The 2449 reference is not included. Missing query sidecars do not indicate analysis failure.</span><span class="cn">怎么用：只下载本检测样本的结果。2449 参考库不提供下载。查询 sidecar 缺失不表示分析失败。</span></div>
<div id="downloads"></div>
</section>

<footer><span class="en">GrapeAncestry interactive report</span><span class="cn">GrapeAncestry 交互报告</span></footer>
</div>

<script>
{APP_JS}
var PAYLOAD = {data_json};
boot(PAYLOAD);
</script>
</body></html>""", data_json)

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html)
    if write_sidecar:
        (out_html.with_suffix(".data.json")).write_text(data_json)
    return out_html
