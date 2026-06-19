#!/usr/bin/env python3
import json,re,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R/"briefings";D=R/"data";S=R/"state";P=R/"reports"
CAD=5;KEEP=2500;W=[("now",0),("30m",30),("1h",60),("4h",240),("8h",480),("24h",1440),("72h",4320),("168h",10080)]
def rj(p,d):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return d
def wj(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def o(x):return re.sub(r"\s+"," ",str(x or "")).strip()
def sl(x):
    x=str(x or "").lower();x=re.sub(r"[^a-z0-9._:-]+","-",x);return re.sub(r"-+","-",x).strip("-._")[:96] or "unknown"
def dt(x):
    try:
        t=str(x or "").replace("Z","+00:00");d=datetime.fromisoformat(t);return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    except Exception:return None
def iso(d):return d.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def rid(d):return d.strftime("%Y-%m-%dT%H-%M-%SZ")
def flat(lat):
    if isinstance(lat.get("findings"),list):return [x for x in lat["findings"] if isinstance(x,dict)]
    out=[];sec=lat.get("sections") if isinstance(lat.get("sections"),dict) else {}
    for k in ("high","medium","observe"):
        if isinstance(sec.get(k),list):out += [x for x in sec[k] if isinstance(x,dict)]
    return out
def key(f):
    tx=" ".join([o(f.get("title")),o(f.get("summary")),o(f.get("url"))]).lower()
    m=re.search(r"\bcve-\d{4}-\d{4,7}\b",tx,re.I)
    if m:return "cve:"+m.group(0).upper()
    if "earthquake" in tx or "shakemap" in tx:
        mm=re.search(r"\b(?:magnitude|mag|m)\s*[: ]?\s*(\d+(?:\.\d+)?)\b",tx)
        return "earthquake:"+sl(o(f.get("title"))[:60])+":"+(mm.group(1) if mm else "unknown")
    return "title:"+sl(o(f.get("title")) or f.get("url") or f.get("id"))
def rows(lat,now):
    g={};ix=int(now.timestamp()//(CAD*60));run=rid(now)
    for f in flat(lat):
        k=key(f);a=g.setdefault(k,{"topic_key":k,"topic_label":o(f.get("title")) or k,"score":0.0,"sources":set(),"count":0,"urls":[]})
        try:sc=float(f.get("relevance_score") or f.get("score") or 0)
        except Exception:sc=0
        a["score"]=max(a["score"],sc);a["count"]+=1
        src=f.get("sources") if isinstance(f.get("sources"),list) else [f.get("source")]
        for s in src:
            if s:a["sources"].add(str(s))
        u=str(f.get("url") or "").strip()
        if u and u not in a["urls"]:a["urls"].append(u)
    out=[]
    for a in g.values():
        src=sorted(a["sources"]);sc=round(float(a["score"]),2)
        out.append({"sample_id":f"{run}:{a['topic_key']}","sample_index":ix,"timestamp_utc":iso(now),"run_id":run,"topic_key":a["topic_key"],"topic_label":a["topic_label"],"network_score":sc,"mention_count":a["count"],"source_count":len(src),"sources":src,"score_delta_5m":0.0,"trend_wucht":0.0,"status":"current","urls":a["urls"][:6]})
    return out
def upd_state(rs,now):
    st=rj(S/"topic_timeseries.json",{"schema_version":1,"topics":{}});top=st.get("topics") if isinstance(st,dict) else {}
    if not isinstance(top,dict):top={}
    for r in rs:
        e=top.get(r["topic_key"],{});ss=e.get("samples") if isinstance(e,dict) else []
        if not isinstance(ss,list):ss=[]
        prev=ss[-1] if ss else {};ps=float(prev.get("network_score") or 0) if isinstance(prev,dict) else 0
        de=float(r["network_score"])-ps if ss else float(r["network_score"])
        r["score_delta_5m"]=round(de,2);r["trend_wucht"]=round(float(r["network_score"])+min(12,2*int(r["source_count"]))+(6 if ss and de>0 else 0),2);r["status"]="emerging" if de>0 else "mature"
        by={str(x.get("sample_id")):x for x in ss if isinstance(x,dict) and x.get("sample_id")};by[r["sample_id"]]=r
        e={"topic_key":r["topic_key"],"topic_label":r["topic_label"],"last_seen_at":r["timestamp_utc"],"last_trend_wucht":r["trend_wucht"],"samples":sorted(by.values(),key=lambda x:int(x.get("sample_index") or 0))[-KEEP:]}
        top[r["topic_key"]]=e
    st={"schema_version":2,"generated_at":iso(now),"cadence_minutes":CAD,"retention_samples_per_topic":KEEP,"topics":top};wj(S/"topic_timeseries.json",st);return st
def agg(k,e,ss,now,mins):
    cut=now-timedelta(minutes=mins);ds=[];old=False
    for s in ss:
        d=dt(s.get("timestamp_utc"))
        if not d:continue
        if d<cut:old=True
        elif d<=now:ds.append((d,s))
    if not ds:return None
    ds.sort(key=lambda x:x[0]);samps=[x[1] for x in ds];scores=[float(s.get("network_score") or 0) for s in samps]
    src=set();urls=[];ment=0
    for s in samps:
        ment+=int(s.get("mention_count") or 0)
        for z in s.get("sources") or []: src.add(str(z))
        for u in s.get("urls") or []:
            if u and u not in urls:urls.append(str(u))
    first,last=ds[0][0],ds[-1][0];half=cut+(now-cut)/2
    a=[float(s.get("network_score") or 0) for d,s in ds if d<half];b=[float(s.get("network_score") or 0) for d,s in ds if d>=half]
    acc=(sum(b)/len(b)-sum(a)/len(a)) if a and b else scores[-1]-scores[0]
    age=(now-last).total_seconds()/60;pers=min(1.0,len(samps)/max(1,mins//CAD))
    tr=max(scores)+min(12,2*len(src))+8*pers+max(0,acc)+math.log1p(max(0,ment))
    if not old and first>=cut:status="new"
    elif acc>=3:status="rising"
    elif pers>=.25 and age<=max(30,mins*.25):status="persistent"
    elif age>max(30,mins*.5):status="cooling"
    else:status="watch"
    return {"topic_key":k,"topic_label":o(e.get("topic_label")) or k,"window_minutes":mins,"first_seen_in_window":iso(first),"last_seen_in_window":iso(last),"sample_count":len(samps),"mention_count":ment,"source_count":len(src),"sources":sorted(src),"max_score":round(max(scores),2),"avg_score":round(sum(scores)/len(scores),2),"latest_score":round(scores[-1],2),"score_delta_window":round(scores[-1]-scores[0],2),"acceleration":round(acc,2),"persistence":round(pers,3),"last_age_minutes":round(age,1),"trend_score":round(tr,2),"status":status,"urls":urls[:6]}
def windows(st,rs,now):
    nowr=sorted(rs,key=lambda x:float(x.get("trend_wucht") or 0),reverse=True)
    win={"now":{"window_minutes":0,"generated_at":iso(now),"ranked_topics":nowr[:50],"rising":[x for x in nowr if float(x.get("score_delta_5m") or 0)>0][:20],"persistent":[],"cooling":[],"new":[x for x in nowr if x.get("status")=="emerging"][:20]}}
    top=st.get("topics") if isinstance(st,dict) else {}
    if not isinstance(top,dict):top={}
    for name,mins in W[1:]:
        rr=[]
        for k,e in top.items():
            if isinstance(e,dict) and isinstance(e.get("samples"),list):
                x=agg(str(k),e,e["samples"],now,mins)
                if x:rr.append(x)
        rr.sort(key=lambda x:float(x.get("trend_score") or 0),reverse=True)
        win[name]={"window_minutes":mins,"generated_at":iso(now),"ranked_topics":rr[:50],"rising":[x for x in rr if x["status"]=="rising"][:20],"persistent":[x for x in rr if x["status"]=="persistent"][:20],"cooling":[x for x in rr if x["status"]=="cooling"][:20],"new":[x for x in rr if x["status"]=="new"][:20]}
    return win
def snapshot(lat,net,rs,win,now):
    day=now.strftime("%Y-%m-%d");run=rid(now);snap=D/day/"runs"/f"run_{run}.json"
    wj(snap,{"schema_version":2,"doc_type":"senna.run_snapshot","run_id":run,"generated_at":iso(now),"latest":lat,"network":net,"topic_samples":rs,"trend_windows":win})
    ts=D/"timeseries"/day/"topic_rank_samples.jsonl";ts.parent.mkdir(parents=True,exist_ok=True);old={}
    if ts.exists():
        for line in ts.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict) and x.get("sample_id"):old[str(x["sample_id"])]=x
            except Exception:pass
    for r in rs:old[r["sample_id"]]=r
    ts.write_text("\n".join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in sorted(old.values(),key=lambda x:(x.get("sample_index",0),x.get("topic_key",""))))+("\n" if old else ""),encoding="utf-8")
    return snap,ts
def atom(lat,rs,win,snap,ts,now):
    day=now.strftime("%Y-%m-%d");run=rid(now);p=P/"atoms"/day/f"run_{run}.md";p.parent.mkdir(parents=True,exist_ok=True)
    refs=[f"[ref:{snap.relative_to(R).as_posix()}#root|v:{run}|tags:snapshot,json|src:senna-infoflow]",f"[ref:{ts.relative_to(R).as_posix()}#root|v:dynamic|tags:timeseries,jsonl|src:senna-infoflow]"]
    lines=["---",json.dumps({"doc_type":"senna.report_atom","schema_version":2,"mode":"ATOMIC_REPORT","status":"GENERATED","run_id":run,"generated_at":iso(now),"window_keys":[x[0] for x in W],"refs":refs},ensure_ascii=False),"---","",f"# REPORT_ATOM {run}","","## IDENTITY",f"- run_id: `{run}`",f"- cadence_minutes: `{CAD}`","- trend_windows: `now`, `30m`, `1h`, `4h`, `8h`, `24h`, `72h`, `168h`","","## CANONICAL_REFS"]+[f"- {r}" for r in refs]+["","## FINDING_ATOMS"]
    for i,f in enumerate(flat(lat),1):lines += [f"### F{i:03d} - {o(f.get('title'))}",f"- topic_key: `{key(f)}`",f"- score: `{int(float(f.get('relevance_score') or f.get('score') or 0))}`",f"- source: `{o(f.get('source'))}`",""]
    lines += ["## TOPIC_SAMPLES","```json",json.dumps(rs[:20],ensure_ascii=False,indent=2),"```","","## WINDOW_SUMMARY","```json",json.dumps({k:v.get("ranked_topics",[])[:5] for k,v in win.items()},ensure_ascii=False,indent=2),"```","","END OF DOCUMENT",""]
    p.write_text("\n".join(lines),encoding="utf-8");(P/"latest_atom.md").write_text(p.read_text(encoding="utf-8"),encoding="utf-8")
def trend_md(rs,win,now):
    lines=["# Senna Trend Radar","",f"_Generated: {iso(now)}_","","Verdichtung der 5-Minuten-Atoms in Zeitfenster: `now`, `30m`, `1h`, `4h`, `8h`, `24h`, `72h`, `168h`.","","## Current ranking",""]
    if not rs:lines.append("Keine Topic-Samples im aktuellen Run.")
    else:
        for r in rs[:10]:lines.append(f"- **{r.get('topic_label')}** — wucht `{r.get('trend_wucht')}` / score `{r.get('network_score')}` / Δ5m `{r.get('score_delta_5m')}` / `{r.get('topic_key')}`")
    for name,_ in W:
        lines += ["",f"## Fenster: {name}",""]
        items=(win.get(name) or {}).get("ranked_topics") or []
        if not items:lines.append("- Keine Topics in diesem Fenster.");continue
        for x in items[:12]:
            if name=="now":lines.append(f"- **{x.get('topic_label')}** — wucht `{x.get('trend_wucht')}` / score `{x.get('network_score')}` / status `{x.get('status')}` / `{x.get('topic_key')}`")
            else:lines.append(f"- **{x.get('topic_label')}** — trend `{x.get('trend_score')}` / status `{x.get('status')}` / samples `{x.get('sample_count')}` / sources `{x.get('source_count')}` / Δ `{x.get('score_delta_window')}` / `{x.get('topic_key')}`")
    return "\n".join(lines).rstrip()+"\n"
def main():
    lat=rj(B/"latest.json",{});net=rj(B/"network.json",{})
    now=dt(lat.get("generated_at") if isinstance(lat,dict) else None) or dt(net.get("generated_at") if isinstance(net,dict) else None) or datetime.now(timezone.utc).replace(microsecond=0)
    rs=rows(lat if isinstance(lat,dict) else {},now);st=upd_state(rs,now);win=windows(st,rs,now);rs=sorted(rs,key=lambda x:float(x.get("trend_wucht") or 0),reverse=True)
    snap,ts=snapshot(lat if isinstance(lat,dict) else {},net if isinstance(net,dict) else {},rs,win,now);atom(lat if isinstance(lat,dict) else {},rs,win,snap,ts,now)
    wj(B/"trends.json",{"schema_version":2,"doc_type":"senna.trend_radar","run_id":rid(now),"generated_at":iso(now),"cadence_minutes":CAD,"window_keys":[x[0] for x in W],"ranked_topics":rs,"windows":win})
    (B/"trends.md").write_text(trend_md(rs,win,now),encoding="utf-8")
    print(f"canonical reports written: {snap.relative_to(R)} topics={len(rs)} windows={','.join(win.keys())}")
if __name__=="__main__":main()
