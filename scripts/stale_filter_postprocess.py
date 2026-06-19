#!/usr/bin/env python3
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; BR=ROOT/"briefings"; MAX_DAYS=14
M={m:i for i,ms in enumerate([[],["jan","january"],["feb","february"],["mar","march"],["apr","april"],["may"],["jun","june"],["jul","july"],["aug","august"],["sep","sept","september"],["oct","october"],["nov","november"],["dec","december"]]) for m in ms}
def now(): return datetime.now(timezone.utc).replace(microsecond=0)
def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d
def write(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def dt(v):
    if not v or str(v).lower() in ("unknown","unbekannt","none"): return None
    try:
        if isinstance(v,(int,float)): return datetime.fromtimestamp(v,tz=timezone.utc)
        x=datetime.fromisoformat(str(v).strip().replace("Z","+00:00"))
        return (x if x.tzinfo else x.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except Exception: return None
def textdates(s):
    out=[]
    for y,m,d in re.findall(r"(?<!\d)(20\d{2})[/-](0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])(?!\d)",s or ""):
        try: out.append(datetime(int(y),int(m),int(d),tzinfo=timezone.utc))
        except ValueError: pass
    mr="|".join(sorted(M,key=len,reverse=True))
    for a,b,c in re.findall(rf"\b({mr})[-\s,_]+(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?[-\s,_]+(20\d{{2}})\b",s or "",re.I):
        try: out.append(datetime(int(c),M[a.lower()],int(b),tzinfo=timezone.utc))
        except ValueError: pass
    for a,b,c in re.findall(rf"\b(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?[-\s,_]+({mr})[-\s,_]+(20\d{{2}})\b",s or "",re.I):
        try: out.append(datetime(int(c),M[b.lower()],int(a),tzinfo=timezone.utc))
        except ValueError: pass
    return out
def evidence(x):
    p=dt(x.get("published_at"))
    if p: return p,"published_at"
    ds=textdates(" ".join(str(x.get(k) or "") for k in ("url","title","summary")))
    return (max(ds),"explicit_date") if ds else (None,"none")
def stale(x,n):
    d,b=evidence(x)
    if not d: return False,"no_date"
    age=(n-d).total_seconds()/86400
    return age>MAX_DAYS or age<-2, f"{'stale' if age>MAX_DAYS else 'future' if age<-2 else 'fresh'}:{b}:{d.date()}:age_days={age:.1f}"
def filt(xs,n):
    k=[]; r=[]
    for x in xs or []:
        if not isinstance(x,dict): continue
        bad,why=stale(x,n)
        (r if bad else k).append(dict(x,stale_filter_reason=why) if bad else x)
    return k,r
def item(x):
    u=x.get("url") or ""; link=f" — [Quelle]({u})" if str(u).startswith(("http://","https://")) else ""
    return f"- **{x.get('title','Untitled')}** — Score {x.get('relevance_score',0)}, {x.get('risk_or_opportunity','observation')}{link}\n  - Quelle: {x.get('source','?')} / `{x.get('source_type','?')}`\n  - Zeit: published `{x.get('published_at') or 'unbekannt'}`, fetched `{x.get('fetched_at') or 'unbekannt'}`\n  - Kurz: {x.get('summary') or ''}"
def md(p):
    sec=p.get("sections") if isinstance(p.get("sections"),dict) else {}
    high,med,obs=sec.get("high") or [],sec.get("medium") or [],sec.get("observe") or []
    top=(high or med or obs or [None])[0]
    sit=(f"{len(p.get('findings') or [])} neue relevante Treffer nach 14-Tage-Frischefilter. Stärkstes Signal: „{top.get('title')}“ aus {top.get('source')}." if top else "Keine neuen relevanten Treffer nach 14-Tage-Frischefilter.")
    lines=["# Senna Briefing","",f"_Generiert: {now().isoformat()}_","","## Kurzlage","",sit,"",f"_Frischefilter: keine News älter als {MAX_DAYS} Tage._","","## Priorität Hoch",""]
    lines += [item(x) for x in high] or ["Keine neuen Hochprioritäts-Treffer."]
    lines += ["","## Priorität Mittel",""] + ([item(x) for x in med] or ["Keine neuen mittleren Treffer."])
    lines += ["","## Nur beobachten",""] + ([item(x) for x in obs] or ["Keine neuen Beobachtungssignale."])
    (BR/"latest.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
def main():
    n=now(); removed=[]
    fp=DATA/n.strftime("%Y-%m-%d")/"findings.json"; xs=load(fp,[])
    if isinstance(xs,list):
        k,r=filt(xs,n); removed+=r; write(fp,k)
    lp=BR/"latest.json"; p=load(lp,{})
    if isinstance(p,dict):
        sec=p.setdefault("sections",{})
        if isinstance(sec,dict):
            for s in ("high","medium","observe"):
                k,r=filt(sec.get(s) or [],n); sec[s]=k; removed+=r
        k,r=filt(p.get("findings") or [],n); p["findings"]=k; removed+=r
        c=p.setdefault("counts",{}); c.update(stale_removed=len(removed),max_news_age_days=MAX_DAYS,new_relevant_findings=len(k),high=len(sec.get("high") or []),medium=len(sec.get("medium") or []),observe=len(sec.get("observe") or []))
        write(lp,p); md(p)
    write(BR/"stale_filter.json",{"generated_at":n.isoformat(),"max_news_age_days":MAX_DAYS,"removed_count":len(removed),"removed":removed[:500]})
    print(f"Stale filter removed {len(removed)} item(s); max news age {MAX_DAYS} days.")
if __name__=="__main__": main()
