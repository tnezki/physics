#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys, shutil
from copy import deepcopy
from html import unescape, escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
from http.server import ThreadingHTTPServer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'planner'))
import planner_server as base

VERSION='1.1-weekly-warmups'
PHYSICS_ROOT=base.PHYSICS_ROOT
PUBLIC_BASE=base.PUBLIC_BASE
PRACTICE_CFG=ROOT/'practice_builder'/'sections'
PRACTICE_LOCAL=ROOT/'library'/'practice_sets'
WARMUP_CFG=ROOT/'warmup_builder'/'weeks'
WARMUP_LOCAL=ROOT/'library'/'warmups'
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

def atomic(path:Path,text:str):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(text,encoding='utf-8'); tmp.replace(path)

def safe_section(v):
    v=str(v or '').strip()
    if not re.fullmatch(r'\d+\.\d+',v): raise ValueError('Section must look like 2.1.')
    return v

def safe_unit(v):
    n=int(v)
    if n<0 or n>20: raise ValueError('Invalid unit.')
    return n

def text_only(html):
    return re.sub(r'\s+',' ',unescape(re.sub(r'<[^>]+>',' ',html))).strip()

class Capture(HTMLParser):
    def __init__(self,tag,cls):
        super().__init__(convert_charrefs=False); self.tag=tag; self.cls=cls; self.cap=False; self.depth=0; self.buf=[]; self.blocks=[]
    def handle_starttag(self,tag,attrs):
        raw=self.get_starttag_text() or '<'+tag+'>'
        classes=dict(attrs).get('class','').split()
        if not self.cap and tag==self.tag and self.cls in classes:
            self.cap=True; self.depth=1; self.buf=[raw]; return
        if self.cap:
            self.buf.append(raw)
            if tag not in VOID:self.depth+=1
    def handle_startendtag(self,tag,attrs):
        if self.cap:self.buf.append(self.get_starttag_text() or '<'+tag+'/>')
    def handle_endtag(self,tag):
        if not self.cap:return
        self.buf.append(f'</{tag}>')
        self.depth-=1
        if self.depth==0:
            self.blocks.append(''.join(self.buf)); self.cap=False; self.buf=[]
    def handle_data(self,data):
        if self.cap:self.buf.append(data)
    def handle_entityref(self,name):
        if self.cap:self.buf.append('&'+name+';')
    def handle_charref(self,name):
        if self.cap:self.buf.append('&#'+name+';')
    def handle_comment(self,data):
        if self.cap:self.buf.append('<!--'+data+'-->')

def blocks(html,tag,cls):
    p=Capture(tag,cls); p.feed(html); return p.blocks

def body_content(block):
    m=re.search(r'<div\s+class=["\']problem-body["\'][^>]*>(.*)</div>\s*</(?:div|article)>\s*$',block,re.S|re.I)
    inner=m.group(1) if m else block
    inner=re.sub(r'<div\s+class=["\']workspace[^"\']*["\'][^>]*>.*?</div>\s*$','',inner,flags=re.S|re.I)
    inner=re.sub(r'<span\s+class=["\']qnum["\'][^>]*>.*?</span>\s*','',inner,flags=re.S|re.I)
    return inner.strip()

def workspace_from(block,default=1.0):
    m=re.search(r'\b(?:ws|wu-ws)-(\d+)',block)
    if m:
        try:return max(0,min(5,int(m.group(1))/100))
        except:pass
    return default

def practice_file(section):
    tag=section.replace('.','_'); return PHYSICS_ROOT/'practice_sets'/f'practice_sets_{tag}'/f'practice_set_{tag}.html'

def practice_public(section):
    tag=section.replace('.','_'); return PUBLIC_BASE+f'practice_sets/practice_sets_{tag}/practice_set_{tag}.html'

def practice_cfg_path(section): return PRACTICE_CFG/f'u{section.replace(".","_")}.json'

def seed_practice(section):
    section=safe_section(section); path=practice_file(section)
    if not path.is_file(): raise FileNotFoundError(f'No published Practice Set for {section}.')
    html=path.read_text(encoding='utf-8')
    titlem=re.search(r'<h1[^>]*>(.*?)</h1>',html,re.S|re.I); title=text_only(titlem.group(1)) if titlem else f'Section {section} Practice Set'
    title=re.sub(r'^Section\s+'+re.escape(section)+r'\s*[—-]\s*','',title,flags=re.I)
    qs=[]
    for i,b in enumerate(blocks(html,'div','problem'),1):
        start=b[:b.find('>')+1]
        qs.append({'id':f'q{i}','visible':True,'workspace':workspace_from(b,1.0),'figure_width':390,'page_break':False,'outer_start':start,'active_instance':0,'instances':[{'label':'Original','html':body_content(b)}]})
    cfg={'schema_version':1,'section':section,'title':title,'settings':{'spacing':'normal','margins':'normal','workspace':1.0,'figure_width':390,'show_title':True},'questions':qs,'public_url':practice_public(section)}
    atomic(practice_cfg_path(section),json.dumps(cfg,indent=2)+'\n'); return cfg

def load_practice(section):
    p=practice_cfg_path(safe_section(section))
    if p.is_file():
        cfg=json.loads(p.read_text(encoding='utf-8')); cfg['public_url']=practice_public(section); return validate_practice(cfg)
    return seed_practice(section)

def validate_practice(cfg):
    cfg=deepcopy(cfg); sec=safe_section(cfg.get('section')); cfg['section']=sec; cfg['title']=str(cfg.get('title') or sec); st=cfg.setdefault('settings',{})
    st['spacing']=st.get('spacing') if st.get('spacing') in {'compact','normal','roomy'} else 'normal'; st['margins']=st.get('margins') if st.get('margins') in {'narrow','normal','wide'} else 'normal'; st['workspace']=max(0,min(5,float(st.get('workspace',1)))); st['figure_width']=max(0,min(704,float(st.get('figure_width',390)))); st['show_title']=bool(st.get('show_title',True))
    clean=[]
    for i,q in enumerate(cfg.get('questions') or [],1):
        if not isinstance(q,dict):continue
        ins=[]
        for j,x in enumerate(q.get('instances') or []):
            if isinstance(x,dict):ins.append({'label':str(x.get('label') or f'Instance {j+1}'),'html':str(x.get('html') or '')})
        if not ins:ins=[{'label':'Original','html':'<p></p>'}]
        a=max(0,min(int(q.get('active_instance',0) or 0),len(ins)-1)); clean.append({'id':str(q.get('id') or f'q{i}'),'visible':bool(q.get('visible',True)),'workspace':max(0,min(5,float(q.get('workspace',st['workspace'])))),'figure_width':max(0,min(704,float(q.get('figure_width',st['figure_width'])))),'page_break':bool(q.get('page_break',False)),'outer_start':str(q.get('outer_start') or '<div class="problem">'),'active_instance':a,'instances':ins})
    cfg['questions']=clean; cfg['public_url']=practice_public(sec); return cfg

def inject_num(html,n):
    html=re.sub(r'<span\s+class=["\']qnum["\'][^>]*>.*?</span>\s*','',html,flags=re.S|re.I)
    if re.search(r'<p[^>]*>',html,re.I): return re.sub(r'(<p[^>]*>)',r'\1<span class="qnum">'+str(n)+'.</span> ',html,count=1,flags=re.I)
    return f'<p><span class="qnum">{n}.</span> {html}</p>'

def render_practice(cfg):
    cfg=validate_practice(cfg); sec=cfg['section']; st=cfg['settings']; questions=[]; n=0
    for q in cfg['questions']:
        if not q['visible']:continue
        n+=1; ins=q['instances'][q['active_instance']]; content=inject_num(ins['html'],n); pb=' page-break' if q['page_break'] else ''
        questions.append(f'<div class="problem{pb}" style="--qws:{q["workspace"]}in;--qfig:{q["figure_width"]}px"><div class="problem-body">{content}<div class="workspace"></div></div></div>')
    title=f'Section {sec} — {cfg["title"]}'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><link rel="stylesheet" href="../../css/base.css"><link rel="stylesheet" href="../../css/practice_set.css"><script>window.MathJax={{tex:{{inlineMath:[["$","$"]],displayMath:[["$$","$$"]],processEscapes:true}}}};</script><script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script><style>.screen-tools{{position:sticky;top:0;z-index:5;background:#173f6d;color:#fff;padding:10px 14px;text-align:center}}.screen-tools button{{background:#fff;color:#173f6d;border:0;border-radius:8px;padding:9px 13px;font-weight:900}}.container{{max-width:8.5in;margin:18px auto;background:#fff;padding:{'.4in' if st['margins']=='narrow' else '.75in' if st['margins']=='wide' else '.55in .58in'}}}.problem{{break-inside:avoid;padding:10px 0}}.problem.page-break{{break-before:page}}.workspace{{height:var(--qws);background:repeating-linear-gradient(to bottom,transparent 0,transparent 27px,#edf1f5 28px)}}.problem img,.problem svg{{max-width:100%;width:min(var(--qfig),100%)}}.spacing-compact .problem{{padding:6px 0}}.spacing-roomy .problem{{padding:15px 0}}@media print{{.screen-tools{{display:none}}.container{{margin:0;max-width:none}}}}</style></head><body class="spacing-{st['spacing']}"><div class="screen-tools"><button onclick="window.print()">Print / Share PDF</button></div><div class="container">{f'<h1>{escape(title)}</h1>' if st['show_title'] else ''}<div class="student-line">Name ____________________ &nbsp;&nbsp; Date __________ &nbsp;&nbsp; Period ______</div><div class="dok-section">{''.join(questions)}</div></div></body></html>'''

def save_practice(cfg,publish=False):
    cfg=validate_practice(cfg); atomic(practice_cfg_path(cfg['section']),json.dumps(cfg,indent=2)+'\n'); local=PRACTICE_LOCAL/f'u{cfg["section"].replace(".","_")}'/'index.html'; html=render_practice(cfg); atomic(local,html)
    if publish: atomic(practice_file(cfg['section']),html); atomic(base.AGENDA_PATH,base.build_student_agenda(base.get_state()))
    return {'ok':True,'config':cfg,'message':('Published Practice Set and refreshed the Student Agenda. Use GitHub Sync when ready.' if publish else 'Saved local Practice Set draft.')}

def safe_week(v):
    n=int(v)
    if n<1 or n>60: raise ValueError('Warm-up week must be between 1 and 60.')
    return n

def warmup_folder(week): return f'week_{safe_week(week):02d}_warmups'
def warmup_file(week):
    folder=warmup_folder(week); return PHYSICS_ROOT/'warmups'/folder/f'{folder}.html'
def warmup_public(week):
    folder=warmup_folder(week); return PUBLIC_BASE+f'warmups/{folder}/{folder}.html'
def warmup_cfg_path(week): return WARMUP_CFG/f'week_{safe_week(week):02d}.json'

def validate_warmup(cfg):
    if not isinstance(cfg,dict): raise ValueError('Warm-up config is required.')
    cfg=deepcopy(cfg); week=safe_week(cfg.get('week_number')); cfg['schema_version']=2; cfg['week_number']=week
    cfg['title']=str(cfg.get('title') or f'Week {week} Warm-Ups').strip() or f'Week {week} Warm-Ups'
    cfg['intro']=str(cfg.get('intro') or 'Three short review questions each day: two free-response and one multiple-choice. Every question comes from a section completed before the section scheduled for that day.').strip()
    st=cfg.setdefault('settings',{}); st['workspace']=max(0,min(3,float(st.get('workspace',.55))))
    clean_warmups=[]
    for wi,w in enumerate((cfg.get('warmups') or [])[:5],1):
        if not isinstance(w,dict): continue
        try:number=int(w.get('number') or wi)
        except:number=wi
        label=str(w.get('label') or f'Warm-Up {number}')
        current_section=str(w.get('current_section') or '')
        questions=[]
        for qi,q in enumerate((w.get('questions') or [])[:6],1):
            if not isinstance(q,dict): continue
            response=str(q.get('response_type') or ('MC' if qi==3 else 'FRQ')).upper()
            if response not in {'FRQ','MC'}: response='FRQ'
            instances=[]
            for ii,inst in enumerate(q.get('instances') or [],1):
                if not isinstance(inst,dict): continue
                choices=inst.get('choices') if isinstance(inst.get('choices'),list) else []
                choices=[str(x) for x in choices[:5]]
                while len(choices)<5: choices.append('')
                instances.append({'label':str(inst.get('label') or f'Instance {ii}'),'stem_html':str(inst.get('stem_html') or inst.get('html') or ''),'choices':choices})
            if not instances: instances=[{'label':'Original','stem_html':'<p></p>','choices':['','','','','']}]
            try:a=int(q.get('active_instance',0) or 0)
            except:a=0
            a=max(0,min(a,len(instances)-1))
            questions.append({
                'id':str(q.get('id') or f'w{number}q{qi}'),
                'visible':bool(q.get('visible',True)),
                'response_type':response,
                'source_section':str(q.get('source_section') or '').strip(),
                'topic':str(q.get('topic') or 'Previous section review').strip(),
                'workspace':max(0,min(3,float(q.get('workspace',st['workspace'])))),
                'active_instance':a,
                'instances':instances,
            })
        clean_warmups.append({'number':number,'label':label,'current_section':current_section,'questions':questions})
    cfg['warmups']=clean_warmups; cfg['public_url']=warmup_public(week); return cfg

def load_warmup(week):
    p=warmup_cfg_path(safe_week(week))
    if not p.is_file(): raise FileNotFoundError(f'No weekly warm-up config exists for Week {safe_week(week)} yet.')
    c=json.loads(p.read_text(encoding='utf-8')); c['public_url']=warmup_public(week); return validate_warmup(c)

def render_warmup(cfg):
    cfg=validate_warmup(cfg); week=cfg['week_number']; ws=cfg['settings']['workspace']; cards=[]
    for warm in cfg['warmups']:
        qblocks=[]; shown=0
        for q in warm['questions']:
            if not q['visible']: continue
            shown+=1; inst=q['instances'][q['active_instance']]; typ=q['response_type']; badge='Free Response' if typ=='FRQ' else 'Multiple Choice'
            choices=''
            if typ=='MC':
                choices='<ol class="choices" type="A">'+''.join(f'<li>{c}</li>' for c in inst['choices'])+'</ol>'
            qblocks.append(f'''<article class="question {typ.lower()}"><div class="meta"><span class="qnum">{shown}</span><span class="badge">{badge}</span><span class="source">{escape(q['source_section'])} · {escape(q['topic'])}</span></div><div class="stem">{inst['stem_html']}</div>{choices}<div class="workspace" style="height:{q['workspace']}in"></div></article>''')
        cards.append(f'''<section class="warmup" id="w{warm['number']}"><header class="warmup-head"><h2>{warm['number']}</h2><div><strong>{escape(warm['label'])}</strong><span>{escape(warm['current_section'])}</span></div></header>{''.join(qblocks)}</section>''')
    jumps=''.join(f'<a href="#w{w["number"]}">{w["number"]}</a>' for w in cfg['warmups'])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Physics · {escape(cfg['title'])}</title><script>window.MathJax={{tex:{{inlineMath:[["$","$"]],displayMath:[["$$","$$"]],processEscapes:true}}}};</script><script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script><style>
:root{{--navy:#173f6d;--gold:#e0bd4f;--ink:#1f2937;--muted:#64748b;--line:#d6dde6;--bg:#eef2f6;--paper:#fff;--pale:#fff8dc}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font-family:Arial,Helvetica,sans-serif;color:var(--ink)}}.screen-tools{{position:sticky;top:0;z-index:5;background:var(--navy);color:#fff;padding:10px 14px;display:flex;justify-content:center;align-items:center;gap:10px}}.screen-tools button{{border:1px solid rgba(255,255,255,.7);background:#fff;color:var(--navy);border-radius:9px;padding:9px 13px;font-weight:900;cursor:pointer}}.screen-tools span{{font-size:.78rem;opacity:.9}}main{{width:min(900px,calc(100% - 24px));margin:22px auto 48px}}.title{{background:var(--navy);color:#fff;padding:18px 20px;border-radius:16px 16px 0 0}}.title .kicker{{font-size:.78rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;opacity:.85}}.title h1{{margin:5px 0 0;font-size:1.8rem}}.intro{{background:#fff;border:1px solid var(--line);border-top:0;padding:14px 18px;color:var(--muted);line-height:1.45}}.jump{{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}}.jump a{{color:var(--navy);font-weight:900;text-decoration:none;border:1px solid var(--gold);border-radius:999px;padding:5px 10px;background:#fff}}.warmup{{background:var(--paper);border:1px solid var(--line);border-radius:14px;margin:16px 0;overflow:hidden;box-shadow:0 5px 16px rgba(23,63,109,.05)}}.warmup-head{{display:flex;gap:12px;align-items:center;background:var(--pale);border-bottom:1px solid #ead690;padding:12px 16px}}.warmup-head h2{{margin:0;color:var(--navy);font-size:1.5rem;width:32px}}.warmup-head div{{display:flex;flex-direction:column;gap:2px}}.warmup-head span{{font-size:.78rem;color:#725d18}}.question{{padding:15px 16px;border-bottom:1px solid #e8ebef}}.question:last-child{{border-bottom:0}}.meta{{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:8px}}.qnum{{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:var(--navy);color:#fff;font-weight:900}}.badge{{font-size:.68rem;font-weight:900;text-transform:uppercase;letter-spacing:.04em;padding:5px 8px;border-radius:999px;background:#fff1bd;color:#725d18}}.source{{font-size:.76rem;color:var(--muted);font-weight:800}}.stem{{font-size:1rem;line-height:1.45}}.choices{{margin:9px 0 0 30px;padding-left:16px}}.choices li{{padding:3px 0;line-height:1.35}}.workspace{{height:{ws}in}}.foot{{font-size:.78rem;color:var(--muted);text-align:center;margin-top:16px}}@media print{{body{{background:#fff}}.no-print,.intro,.foot{{display:none!important}}main{{width:100%;margin:0}}.title{{border-radius:0;padding:10px 14px}}.warmup{{box-shadow:none;break-inside:avoid;margin:8px 0;border-radius:0}}.warmup-head{{padding:7px 11px}}.question{{padding:9px 11px}}.stem,.choices{{font-size:10pt}}.workspace{{height:.32in}}}}
</style></head><body><div class="screen-tools no-print"><button type="button" onclick="window.print()">Print / Share to Notability</button><span>On iPad: open print preview, then Share → Notability.</span></div><main><header class="title"><div class="kicker">Physics · Weekly Retrieval</div><h1>{escape(cfg['title'])}</h1></header><section class="intro">{escape(cfg['intro'])}<div class="jump">{jumps}</div></section>{''.join(cards)}<div class="foot">Week {week} · 2 FRQ + 1 MC each warm-up · previous sections only.</div></main></body></html>'''

def save_warmup(cfg,publish=False):
    cfg=validate_warmup(cfg); week=cfg['week_number']; WARMUP_CFG.mkdir(parents=True,exist_ok=True); atomic(warmup_cfg_path(week),json.dumps(cfg,indent=2)+'\n')
    folder=warmup_folder(week); local=WARMUP_LOCAL/folder/f'{folder}.html'; html=render_warmup(cfg); atomic(local,html)
    if publish:
        atomic(warmup_file(week),html); atomic(base.AGENDA_PATH,base.build_student_agenda(base.get_state()))
    return {'ok':True,'config':cfg,'message':(f'Published Week {week} Warm-Ups and refreshed the Student Agenda. Use GitHub Sync when ready.' if publish else f'Saved Week {week} Warm-Ups locally.')}

def warmup_weeks_payload():
    WARMUP_CFG.mkdir(parents=True,exist_ok=True); weeks=[]
    for p in sorted(WARMUP_CFG.glob('week_*.json')):
        m=re.fullmatch(r'week_(\d+)\.json',p.name)
        if not m: continue
        n=int(m.group(1)); weeks.append({'week_number':n,'public_url':warmup_public(n),'published':warmup_file(n).is_file()})
    return {'ok':True,'weeks':weeks}

def library_payload():
    cats={k:[] for k in ['notes','practice_sets','warmups','investigations','activities','demo','performance_tasks','reviews']}
    def add(cat,title,path,editor=None):
        rel=path.relative_to(PHYSICS_ROOT).as_posix(); cats[cat].append({'title':title,'path':rel,'public_url':PUBLIC_BASE+quote(rel,safe='/._-'),'editor_url':editor})
    for d in sorted((PHYSICS_ROOT/'notes').glob('u*_notes')) if (PHYSICS_ROOT/'notes').is_dir() else []:
        f=d/(d.name+'.html');
        if f.is_file(): add('notes',d.name,f)
    for d in sorted((PHYSICS_ROOT/'practice_sets').glob('practice_sets_*')) if (PHYSICS_ROOT/'practice_sets').is_dir() else []:
        m=re.fullmatch(r'practice_sets_(\d+)_(\d+)',d.name)
        if m:
            sec=f'{int(m.group(1))}.{int(m.group(2))}'; f=d/f'practice_set_{m.group(1)}_{m.group(2)}.html'
            if f.is_file(): add('practice_sets',sec+' Practice Set',f,f'/practice_builder/?section={sec}')
    for d in sorted((PHYSICS_ROOT/'warmups').glob('week_*_warmups')) if (PHYSICS_ROOT/'warmups').is_dir() else []:
        m=re.fullmatch(r'week_(\d+)_warmups',d.name)
        if m:
            n=int(m.group(1)); f=d/f'week_{n:02d}_warmups.html'
            if f.is_file(): add('warmups',f'Week {n} Warm-Ups',f,f'/warmup_builder/editor.html?week={n}')
    for cat,rootname,pat,filefn in [('investigations','investigations','u*_investigation',lambda d:d/(d.name+'.html')),('activities','activities','u*_act1',lambda d:d/(d.name+'.html')),('demo','demo','u*_demo',lambda d:d/(d.name+'.html'))]:
        root=PHYSICS_ROOT/rootname
        if root.is_dir():
            for d in sorted(root.glob(pat)):
                f=filefn(d)
                if f.is_file(): add(cat,d.name,f)
    pr=PHYSICS_ROOT/'performance_task___5134zrt'
    if pr.is_dir():
        for d in sorted(pr.glob('u*_performance_task')):
            f=d/(d.name+'.html')
            if f.is_file(): add('performance_tasks',d.name,f)
    rr=PHYSICS_ROOT/'reviews'
    if rr.is_dir():
        for d in sorted(rr.glob('review*')):
            m=re.search(r'(\d+)',d.name); f=d/(f'review_{m.group(1)}.html' if m else 'index.html')
            if f.is_file(): add('reviews',d.name,f)
    return {'ok':True,'categories':cats}

class Handler(base.PlannerHandler):
    def do_GET(self):
        u=urlparse(self.path); path=u.path; qs=parse_qs(u.query)
        try:
            if path=='/api/version': return self._json(200,{'ok':True,'version':VERSION})
            if path=='/api/library': return self._json(200,library_payload())
            if path=='/api/practice/sections':
                ss=[]
                root=PHYSICS_ROOT/'practice_sets'
                if root.is_dir():
                    for d in sorted(root.glob('practice_sets_*')):
                        m=re.fullmatch(r'practice_sets_(\d+)_(\d+)',d.name)
                        if m:
                            s=f'{int(m.group(1))}.{int(m.group(2))}'; f=practice_file(s)
                            if f.is_file(): ss.append({'section':s,'title':load_practice(s).get('title',s),'public_url':practice_public(s)})
                return self._json(200,{'ok':True,'sections':ss})
            if path=='/api/practice/section': return self._json(200,{'ok':True,'config':load_practice(qs.get('section',[''])[0])})
            if path=='/api/warmups/weeks': return self._json(200,warmup_weeks_payload())
            if path=='/api/warmups/week': return self._json(200,{'ok':True,'config':load_warmup(qs.get('week',['0'])[0])})
            if path=='/': self.path='/index.html'; return super().do_GET()
            return super().do_GET()
        except Exception as e: return self._json(400,{'ok':False,'error':str(e)})
    def do_POST(self):
        path=urlparse(self.path).path
        if path in {'/api/practice/save','/api/practice/publish','/api/warmups/save','/api/warmups/publish'}:
            try:
                payload=self._read_json(); cfg=payload.get('config') if isinstance(payload,dict) else None
                if path.startswith('/api/practice/'): out=save_practice(cfg,publish=path.endswith('/publish'))
                else: out=save_warmup(cfg,publish=path.endswith('/publish'))
                return self._json(200,out)
            except Exception as e:return self._json(400,{'ok':False,'error':str(e)})
        return super().do_POST()

def main():
    base.ensure_teacher_shared_layout()
    h=lambda *a,**kw: Handler(*a,directory=str(ROOT),**kw)
    server=ThreadingHTTPServer((base.HOST,base.PORT),h)
    print(f'Physics Tools {VERSION} running at http://{base.HOST}:{base.PORT}/')
    server.serve_forever()
if __name__=='__main__': main()
