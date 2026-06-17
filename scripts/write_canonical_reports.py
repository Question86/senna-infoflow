#!/usr/bin/env python3
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/"briefings"; D=ROOT/"data"; S=ROOT/"state"; R=ROOT/"reports"; CAD=5
def rj(p,d):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return d
def wj(p,d):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def one(x):return re.sub(r"\s+"," ",str(x or "")).strip()
def slug(x):return re.sub(r"-+","-",re.sub(r"[^a-z0-9._:-]+","-",str(x).lower())).strip("-._")[:96] or "unknown"
def dt(x):
    t=str(x or "").replace("Z","+00:00")
    return (datetime.fromisoformat(t) if t else datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
def iso(x):return x.isoformat().replace("+00:00","Z")
def rid(x):return x.strftime("%Y-%m-%dT%H-%M-%SZ")
def key(f):
    tx=" ".join([one(f.get("title")),one(f.get("summary")),one(f.get("url"))]).lower()
    m=re.search(r"\bcve-\d{4}-\d{4,7}\b",tx,re.I)
    if m:return "cve:"+m.group(0).upper()
    if "earthquake" in tx or "shakemap" in tx:
        mm=re.search(r"\b(?:magnitude|mag|m)\s*[: ]?\s*(\d+(?:\.\d+)?)\b",tx); mag=mm.group(1) if mm else "unknown"
        loc="mid-atlantic-ridge" if "atlantic ridge" in tx else slug(one(f.get("title"))[:60])
        return f"earthquake:{loc}:{mag}"
    return "title:"+slug(one(f.get("title")) or f.get("url") or f.get("id"))
def findings(lat):
    if isinstance(lat.get("findings"),list): return [x for x in lat["findings"] if isinstance(x,dict)]
    out=[]; sec=lat.get("sections") if isinstance(lat.get("sections"),dict) else {}
    for k in ("high","medium","observe"):
        if isinstance(sec.get(k),list): out += [x for x in sec[k] if isinstance(x,dict)]
    return out
def main():
    lat=rj(B/"latest.json",{}); net=rj(B/"network.json",{}); now=dt(lat.get("generated_at") or net.get("generated_at"))
    run=rid(now); day=now.strftime("%Y-%m-%d"); idx=int(now.timestamp()//(CAD*60)); fs=findings(lat)
    groups={}
    for f in fs:
        k=key(f); g=groups.setdefault(k,{"topic_key":k,"topic_label":one(f.get("title")) or k,"score":0,"sources":set(),"count":0,"urls":[]})
        g["score"]=max(g["score"],float(f.get("relevance_score") or 0)); g["count"]+=1
        if f.get("source"):g["sources"].add(str(f["source"]))
        if f.get("url") and f.get("url") not in g["urls"]:g["urls"].append(str(f["url"]))
    st=rj(S/"topic_timeseries.json",{"topics":{}}); topics=st.get("topics",{})
    rows=[]
    for g in groups.values():
        old=(topics.get(g["topic_key"]) or {}).get("samples") or []; prev=old[-1] if old else {}
        sc=float(g["score"]); d5=sc-float(prev.get("network_score") or 0) if old else sc
        w=sc+min(12,2*len(g["sources"]))+(6 if d5>0 and len(old)>0 else 0)
        row={"sample_id":f"{run}:{g['topic_key']}","sample_index":idx,"timestamp_utc":iso(now),"run_id":run,"topic_key":g["topic_key"],"topic_label":g["topic_label"],"network_score":round(sc,2),"mention_count":g["count"],"source_count":len(g["sources"]),"sources":sorted(g["sources"]),"score_delta_5m":round(d5,2),"trend_wucht":round(w,2),"status":"emerging" if d5>0 else "mature","urls":g["urls"][:6]}
        rows.append(row)
        e=topics.get(row["topic_key"],{}); samples=e.get("samples",[]); by={s["sample_id"]:s for s in samples if "sample_id" in s}; by[row["sample_id"]]=row
        e.update({"topic_key":row["topic_key"],"topic_label":row["topic_label"],"last_seen_at":row["timestamp_utc"],"last_trend_wucht":row["trend_wucht"],"samples":sorted(by.values(),key=lambda x:x["sample_index"])[-864:]}); topics[row["topic_key"]]=e
    rows=sorted(rows,key=lambda x:x["trend_wucht"],reverse=True)
    wj(S/"topic_timeseries.json",{"schema_version":1,"generated_at":iso(now),"topics":topics})
    snap=D/day/"runs"/f"run_{run}.json"; wj(snap,{"schema_version":1,"doc_type":"senna.run_snapshot","run_id":run,"generated_at":iso(now),"latest":lat,"network":net,"topic_samples":rows})
    ts=D/"timeseries"/day/"topic_rank_samples.jsonl"; ts.parent.mkdir(parents=True,exist_ok=True); old={}
    if ts.exists():
        for line in ts.read_text(encoding="utf-8").splitlines():
            try:o=json.loads(line); old[o["sample_id"]]=o
            except Exception:pass
    for r in rows:old[r["sample_id"]]=r
    ts.write_text("\n".join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in sorted(old.values(),key=lambda x:(x["sample_index"],x["topic_key"])))+"\n",encoding="utf-8")
    atom=R/"atoms"/day/f"run_{run}.md"; atom.parent.mkdir(parents=True,exist_ok=True)
    refs=[f"[ref:{snap.relative_to(ROOT).as_posix()}#root|v:{run}|tags:snapshot,json|src:senna-infoflow]",f"[ref:{ts.relative_to(ROOT).as_posix()}#root|v:dynamic|tags:timeseries,jsonl|src:senna-infoflow]"]
    lines=["---",json.dumps({"doc_type":"senna.report_atom","schema_version":1,"mode":"ATOMIC_REPORT","status":"GENERATED","run_id":run,"generated_at":iso(now),"refs":refs},ensure_ascii=False),"---","",f"# REPORT_ATOM {run}","","## IDENTITY",f"- run_id: `{run}`","- cadence_minutes: `5`","","## CANONICAL_REFS"]+[f"- {r}" for r in refs]+["","## FINDING_ATOMS"]
    for i,f in enumerate(fs,1):lines += [f"### F{i:03d} - {one(f.get('title'))}",f"- topic_key: `{key(f)}`",f"- score: `{int(f.get('relevance_score') or 0)}`",f"- source: `{one(f.get('source'))}`",""]
    lines += ["## TOPIC_SAMPLES","```json",json.dumps(rows[:10],ensure_ascii=False,indent=2),"```","","END OF DOCUMENT",""]
    atom.write_text("\n".join(lines),encoding="utf-8"); (R/"latest_atom.md").write_text(atom.read_text(encoding="utf-8"),encoding="utf-8")
    wj(B/"trends.json",{"schema_version":1,"doc_type":"senna.trend_ranking","run_id":run,"generated_at":iso(now),"ranked_topics":rows})
    (B/"trends.md").write_text("# Senna Trend Ranking\n\n"+("Keine Topic-Samples.\n" if not rows else "\n".join([f"- **{r['topic_label']}** — `{r['trend_wucht']}` `{r['status']}` `{r['topic_key']}`" for r in rows[:10]]))+"\n",encoding="utf-8")
    print(f"canonical reports written: {atom.relative_to(ROOT)} topics={len(rows)}")
if __name__=="__main__":main()
