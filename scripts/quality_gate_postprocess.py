#!/usr/bin/env python3
import json,re,tempfile,yaml
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"config"; B=ROOT/"briefings"; S=ROOT/"state"
A="<!-- SENNA_QUALITY_GATE_START -->"; Z="<!-- SENNA_QUALITY_GATE_END -->"

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def rj(p,d):
    try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
    except Exception: return d
def ry(p,d):
    try: return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else d
    except Exception: return d
def wt(p,s):
    p.parent.mkdir(parents=True,exist_ok=True); fd,t=tempfile.mkstemp(prefix="."+p.name+".",suffix=".tmp",dir=str(p.parent))
    with open(fd,"w",encoding="utf-8") as f: f.write(s)
    Path(t).replace(p)
def wj(p,o): wt(p,json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
def score(x):
    try: return int(x.get("relevance_score") or 0)
    except Exception: return 0
def host(u):
    try: return urlparse(str(u or "")).netloc.lower()
    except Exception: return ""
def txt(x):
    vals=[x.get("title"),x.get("summary"),x.get("url"),x.get("source"),x.get("source_type"),x.get("relevance_reason")," ".join(x.get("matched_keywords") or [])," ".join(x.get("watchgraph_modules") or [])," ".join(x.get("watchgraph_reasons") or [])]
    return " ".join(str(v or "") for v in vals).lower()
def note(x,n):
    q=x.setdefault("quality_notes",[])
    if n not in q: q.append(n)
def cap(x,n,why):
    if score(x)>n:
        x["relevance_score"]=n; note(x,f"{why}; capped at {n}")
def kind(x):
    h=host(x.get("url")); s=str(x.get("source") or "").lower(); t=str(x.get("source_type") or "").lower()
    if t=="github_search" or h.endswith("github.com") or "github" in s: return "github"
    if any(v in h+s for v in ("polymarket","kalshi","electionbettingodds")): return "odds"
    if any(v in h+s for v in ("snyk","portswigger")): return "vendor"
    if any(v in h+s for v in ("gdacs","usgs","noaa","nhc")): return "disaster"
    return "normal"
def high(x):
    t=txt(x); return any(v in t for v in ("actively exploited","exploited in the wild","cisa kev","zero-day","emergency patch","state of emergency","evacuation order","red alert","orange alert","tsunami warning","market halted","trading suspended","pipeline outage","port closure","export ban"))
def ident(x):
    t=txt(x); return "axi0m" in t or "user yps" in t
def debias(x,caps):
    x=dict(x); t=txt(x); k=kind(x); x["source_bias_class"]=k
    title=str(x.get("title") or "").lower()
    if "public_health_biosecurity" in (x.get("watchgraph_modules") or []) and re.search(r"\bwho\s+(will|is|won|would|can|gets|leads|wins|should|has|could|might)\b",title) and "world health organization" not in t and "who.int" not in t and "outbreak" not in t:
        x["watchgraph_modules"]=[m for m in x.get("watchgraph_modules") or [] if m!="public_health_biosecurity"]
        x["watchgraph_reasons"]=[r for r in x.get("watchgraph_reasons") or [] if str(r).lower()!="public_health_biosecurity: who"]
        x["matched_keywords"]=[m for m in x.get("matched_keywords") or [] if str(m).lower()!="who"]
        x["relevance_score"]=max(0,score(x)-3); note(x,"removed WHO acronym false positive")
    if k!="github" and any(str(m).lower()=="github" for m in x.get("matched_keywords") or []):
        x["matched_keywords"]=[m for m in x.get("matched_keywords") or [] if str(m).lower()!="github"]
        x["relevance_score"]=max(0,score(x)-2); note(x,"removed GitHub keyword leakage")
    if k=="github" and str(x.get("source_type") or "").lower()=="github_search" and not high(x) and not ident(x):
        x["signal_class"]="raw_dev_signal"; cap(x,int(caps.get("single_platform_github",10)),"single GitHub/repo signal")
    if k=="odds" and not high(x):
        x["signal_class"]="market_odds_proxy"; cap(x,int(caps.get("market_odds_proxy",10)),"prediction-market proxy signal")
    if k=="vendor" and not high(x):
        x["signal_class"]="vendor_self_feed"; cap(x,int(caps.get("vendor_self_feed",9)),"vendor/self-feed signal")
    if k=="disaster" and "green" in t and not high(x):
        x["signal_class"]="raw_disaster_signal"; cap(x,int(caps.get("raw_disaster_signal",10)),"green disaster/weather alert")
    return x
def rebuild(lat,th):
    fs=[f for f in lat.get("findings",[]) if isinstance(f,dict)]
    hi=int(th.get("high",24)); me=int(th.get("medium",14)); ob=int(th.get("observe",3))
    key=lambda f:(score(f),str(f.get("published_at") or ""),str(f.get("title") or ""))
    lat["sections"]={
        "high":sorted([f for f in fs if score(f)>=hi],key=key,reverse=True),
        "medium":sorted([f for f in fs if me<=score(f)<hi],key=key,reverse=True),
        "observe":sorted([f for f in fs if ob<=score(f)<me],key=key,reverse=True)}
    lat.setdefault("counts",{}).update({k:len(v) for k,v in lat["sections"].items()})
    lat["counts"]["new_relevant_findings"]=len(fs)
def group(d):
    s=" ".join(str(d.get(k) or "") for k in ("id","source_id","name","source_name","type","source_type","url","query","subreddit")).lower()
    for g,terms in {"social":("reddit","mastodon","bluesky","twitter","x.com"),"prediction_markets":("polymarket","kalshi","electionbettingodds"),"macro_finance":("fred","worldbank","imf","ecb","federalreserve"),"public_health":("reliefweb","who","health","outbreak"),"disaster_humanitarian":("gdacs","usgs","noaa","nhc","earthquake","storm","fire"),"security":("cisa","nvd","snyk","portswigger","security","cve"),"github":("github",)}.items():
        if any(t in s for t in terms): return g
    return "other"
def audit(lat,crit,ts):
    fs=[f for f in lat.get("findings",[]) if isinstance(f,dict)]
    errs=[e for e in lat.get("source_errors",[]) if isinstance(e,dict)]
    fg=Counter(group(e) for e in errs)
    active=Counter(group(s) for s in ((ry(C/"sources.yaml",{}) or {}).get("sources") or []) if isinstance(s,dict) and s.get("enabled",True) is not False)
    w=[]
    if errs: w.append("source_errors_present")
    if len(errs)>len(fs): w.append("source_errors_exceed_findings")
    for c in crit:
        if fg.get(c): w.append("critical_sensor_group_failed:"+c)
    if lat.get("counts",{}).get("high",0)==0 and len(fs)>=50: w.append("many_candidates_zero_high")
    if any(f.get("quality_notes") for f in fs): w.append("quality_gate_adjusted_findings")
    conf="low" if any(x.startswith("critical_sensor_group_failed") or x=="source_errors_exceed_findings" for x in w) else "limited" if w else "normal"
    c=lat.get("counts",{})
    return {"schema_version":1,"generated_at":ts,"scope":"configured_public_sources_only","coverage_confidence":conf,"counts":{"findings":len(fs),"source_errors":len(errs),"high":c.get("high",0),"medium":c.get("medium",0),"observe":c.get("observe",0)},"active_sensor_groups":dict(sorted(active.items())),"failed_sensor_groups":dict(sorted(fg.items())),"warnings":w,"principles":["Scoring is not truth.","Surviving sources are not a representative world picture.","Single-source proxy signals stay provisional."]}
def warnblock(a):
    if not a.get("warnings"): return ""
    c=a["counts"]; failed=a.get("failed_sensor_groups") or {}
    lines=[A,"## Coverage Warning","","**Dieses Briefing ist kein repräsentatives Weltbild.** Es zeigt überlebende Signale aus konfigurierten öffentlichen Quellen.","",f"- Coverage confidence: `{a['coverage_confidence']}`",f"- Findings after quality gate: `{c['findings']}`",f"- Source errors: `{c['source_errors']}`",f"- Priority after gate: high `{c['high']}`, medium `{c['medium']}`, observe `{c['observe']}`"]
    if failed: lines.append("- Failed sensor groups: "+", ".join(f"`{k}`={v}" for k,v in sorted(failed.items())))
    lines+=["","> Score ist nicht Wahrheit. Er ist eine strukturierte Vermutung über ein unvollständiges Sensorfeld.","",Z,""]
    return "\n".join(lines)
def md(block):
    p=B/"latest.md"; cur=p.read_text(encoding="utf-8") if p.exists() else "# Senna Briefing\n"
    cur=re.sub(re.escape(A)+r".*?"+re.escape(Z)+r"\n*","",cur,flags=re.S)
    wt(p,(block+cur).rstrip()+"\n")
def main():
    lat=rj(B/"latest.json",{})
    if not isinstance(lat,dict): print("No valid latest.json"); return 0
    cfg=ry(C/"false_positives.yaml",{}) or {}; q=cfg.get("quality_gate") or {}
    th=q.get("thresholds") or {"high":24,"medium":14,"observe":3}; caps=q.get("single_source_caps") or {}
    lat["findings"]=[debias(f,caps) if isinstance(f,dict) else f for f in lat.get("findings",[])]
    rebuild(lat,th); ts=now(); qa=audit(lat,list((q.get("coverage_warning") or {}).get("critical_sensor_groups") or []),ts)
    lat["quality_gate"]={"schema_version":1,"generated_at":ts,"thresholds":th,"single_source_caps":caps,"audit_path":"briefings/quality_audit.json"}
    lat["coverage"]=qa
    wj(B/"latest.json",lat); wj(B/"quality_audit.json",qa); wj(S/"quality_audit.json",qa); md(warnblock(qa))
    print(f"quality gate complete: confidence={qa['coverage_confidence']}, warnings={len(qa['warnings'])}, findings={qa['counts']['findings']}")
    return 0
if __name__=="__main__": raise SystemExit(main())
