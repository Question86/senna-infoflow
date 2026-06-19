#!/usr/bin/env python3
import json,re,tempfile,yaml
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from urllib.parse import urlparse

R=Path(__file__).resolve().parents[1]; C=R/"config"; B=R/"briefings"; S=R/"state"
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
def wj(p,o): wt(p,json.dumps(o,ensure_ascii=False, indent=2, sort_keys=True)+"\n")
def host(u):
    try: return urlparse(str(u or "")).netloc.lower()
    except Exception: return ""
def text(i):
    return " ".join(str(x or "") for x in [i.get("title"),i.get("summary"),i.get("url"),i.get("source"),i.get("source_type"),i.get("relevance_reason")," ".join(i.get("matched_keywords") or [])," ".join(i.get("watchgraph_modules") or [])," ".join(i.get("watchgraph_reasons") or [])]).lower()
def sc(i):
    try: return int(i.get("relevance_score") or 0)
    except Exception: return 0
def note(i,n):
    q=i.setdefault("quality_notes",[])
    if n not in q: q.append(n)
    r=str(i.get("relevance_reason") or ""); m="quality_gate: "+n
    if m not in r: i["relevance_reason"]=(r+"; " if r else "")+m
def cap(i,n,why):
    if sc(i)>n: i["relevance_score"]=n; note(i,f"{why}; capped at {n}")
def klass(i):
    h=host(i.get("url")); s=str(i.get("source") or "").lower(); t=str(i.get("source_type") or "").lower()
    if t=="github_search" or h.endswith("github.com") or "github" in s: return "github"
    if any(x in h+s for x in ("polymarket","kalshi","electionbettingodds")): return "odds"
    if any(x in h+s for x in ("snyk","portswigger")): return "vendor"
    if any(x in h+s for x in ("gdacs","usgs","noaa","nhc")): return "disaster"
    return "normal"
def high(i):
    x=text(i); return any(t in x for t in ("actively exploited","exploited in the wild","cisa kev","zero-day","emergency patch","state of emergency","evacuation order","red alert","orange alert","tsunami warning","market halted","trading suspended","pipeline outage","port closure","export ban"))
def ident(i):
    x=text(i); return "axi0m" in x or "user yps" in x
def debias(i,caps):
    i=dict(i); x=text(i); k=klass(i); i["source_bias_class"]=k
    title=str(i.get("title") or "").lower()
    if "public_health_biosecurity" in (i.get("watchgraph_modules") or []) and re.search(r"\bwho\s+(kill|is|won|would|can|gets|leads|wins|should|has|could|might)\b",title) and not any(t in x for t in ("world health organization","who.int","outbreak","biosecurity","pandemic","vaccine","pathogen","disease","hospital")):
        i["watchgraph_modules"]=[m for m in i.get("watchgraph_modules") or [] if m!="public_health_biosecurity"]
        i["watchgraph_reasons"]=[r for r in i.get("watchgraph_reasons") or [] if str(r).lower()!="public_health_biosecurity: who"]
        i["matched_keywords"]=[m for m in i.get("matched_keywords") or [] if str(m).lower()!="who"]
        i["relevance_score"]=max(0,sc(i)-3); note(i,"removed WHO acronym false positive")
    if k!="github" and any(str(m).lower()=="github" for m in i.get("matched_keywords") or []):
        i["matched_keywords"]=[m for m in i.get("matched_keywords") or [] if str(m).lower()!="github"]
        i["relevance_score"]=max(0,sc(i)-2); note(i,"removed GitHub keyword leakage")
    if k=="github" and str(i.get("source_type") or "").lower()=="github_search" and not high(i) and not ident(i):
        i["signal_class"]="raw_dev_signal"; cap(i,int(caps.get("single_platform_github",10)),"single GitHub/repo signal")
    if k=="odds" and not high(i):
        i["signal_class"]="market_odds_proxy"; cap(i,int(caps.get("market_odds_proxy",10)),"prediction-market proxy signal")
    if k=="vendor" and not high(i):
        i["signal_class"]="vendor_self_feed"; cap(i,int(caps.get("vendor_self_feed",9)),"vendor/self-feed signal")
    if k=="disaster" and "green" in x and not high(i):
        i["signal_class"]="raw_disaster_signal"; cap(i,int(caps.get("raw_disaster_signal",10)),"green disaster/weather alert")
    return i
def group(d):
    x=" ".join(str(d.get(k) or "") for k in ("id","source_id","name","source_name","type","source_type","url","query","subreddit")).lower()
    if any(t in x for t in ("reddit","mastodon","bluesky","bsky","twitter","x.com")): return "social"
    if any(t in x for t in ("polymarket","kalshi","electionbettingodds")): return "prediction_markets"
    if any(t in x for t in ("fred","worldbank","world bank","imf","ecb","federalreserve")): return "macro_finance"
    if any(t in x for t in ("reliefweb","who","health","outbreak")): return "public_health"
    if any(t in x for t in ("gdacs","usgs","noaa","nhc","earthquake","storm","fire")): return "disaster_humanitarian"
    if any(t in x for t in ("cisa","nvd","snyk","portswigger","security","cve")): return "security"
    if "github" in x: return "github"
    return "other"
def sections(lat,th):
    fs=[f for f in lat.get("findings",[]) if isinstance(f,dict)]
    hi,me,ob=int(th.get("high",24)).int(th.get("medium",14)),int(th.get("observe",3))