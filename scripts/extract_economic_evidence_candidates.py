#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, html, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
D_DAILY=ROOT/"briefings/daily.json"; D_LEDGER=ROOT/"data/economic_events.jsonl"
D_CAND=ROOT/"data/economic_evidence_candidates.jsonl"
D_JSON=ROOT/"briefings/economic_evidence_candidates.json"
D_MD=ROOT/"briefings/economic_evidence_candidates.md"

PATTERNS=[
 ("USD",re.compile(r"(?<!\\w)(?:US\\$|\\$)\\s?(\\d[\\d,]*(?:\\.\\d+)?)\\s?(trillion|billion|million|thousand|tn|bn|mn|m|k)?\\b",re.I)),
 ("EUR",re.compile(r"(?<!\\w)(?:€|EUR)\\s?(\\d[\\d.,]*(?:\\.\\d+)?)\\s?(trillion|billion|million|thousand|tn|bn|mn|m|k|milliarden?|millionen?)?\\b",re.I)),
 ("GBP",re.compile(r"(?<!\\w)(?:£|GBP)\\s?(\\d[\\d,]*(?:\\.\\d+)?)\\s?(trillion|billion|million|thousand|tn|bn|mn|m|k)?\\b",re.I)),
 ("JPY",re.compile(r"(?<!\\w)(?:¥|JPY)\\s?(\\d[\\d,]*(?:\\.\\d+)?)\\s?(trillion|billion|million|thousand|tn|bn|mn|m|k)?\\b",re.I)),
]
MULT={"trillion":1e12,"tn":1e12,"billion":1e9,"bn":1e9,"milliarde":1e9,"milliarden":1e9,
      "million":1e6,"mn":1e6,"m":1e6,"millionen":1e6,"thousand":1e3,"k":1e3}
PRIMARY=(".gov",".europa.eu","sec.gov","cisa.gov","usgs.gov","github.com","investor.","/press/","/newsroom/","/filing")
CONTEXT=("cost","loss","damage","revenue","funding","investment","valuation","market cap","budget","fine",
         "penalty","insurance","claims","sales","umsatz","schaden","kosten","investition","bewertung","bußgeld")

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def read_json(p): return json.loads(p.read_text(encoding="utf-8"))
def read_jsonl(p):
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
def write_jsonl(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows),encoding="utf-8")
def sid(event_id,url,currency,amount,snippet):
    raw=f"{event_id}|{url}|{currency}|{amount:.6f}|{snippet}"
    return "cand_"+hashlib.sha256(raw.encode()).hexdigest()[:20]
def fetch_text(url,timeout=12,max_bytes=750000):
    req=urllib.request.Request(url,headers={"User-Agent":"senna-infoflow/1.0 public-evidence-extractor"})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        ctype=resp.headers.get("Content-Type","")
        if not any(x in ctype for x in ("text","html","json")): return ""
        raw=resp.read(max_bytes)
    text=raw.decode("utf-8",errors="replace")
    text=re.sub(r"<script\\b[^>]*>.*?</script>"," ",text,flags=re.I|re.S)
    text=re.sub(r"<style\\b[^>]*>.*?</style>"," ",text,flags=re.I|re.S)
    text=re.sub(r"<[^>]+>"," ",text)
    return re.sub(r"\\s+"," ",html.unescape(text)).strip()
def parse_number(raw,suffix):
    return float(raw.replace(",",""))*MULT.get((suffix or "").lower(),1.0)
def conf(url,snippet):
    s=.35; lu=url.lower(); ls=snippet.lower()
    if any(x in lu for x in PRIMARY): s+=.25
    if any(x in ls for x in CONTEXT): s+=.20
    if re.search(r"\\b(according to|reported|announced|filed|estimated|said)\\b",ls): s+=.08
    return round(min(s,.90),2)
def extract_from_text(event_id,url,text):
    out=[]
    for currency,pat in PATTERNS:
        for m in pat.finditer(text):
            amount=parse_number(m.group(1),m.group(2))
            if amount<=0: continue
            snippet=text[max(0,m.start()-180):min(len(text),m.end()+180)].strip()
            out.append({
              "candidate_id":sid(event_id,url,currency,amount,snippet),"event_id":event_id,"source_url":url,
              "observed_at":now(),"currency":currency,"amount_native":amount,
              "amount_usd":amount if currency=="USD" else None,
              "conversion_status":"not_required" if currency=="USD" else "pending_fx",
              "component_suggestion":"unknown","overlap_group_suggestion":f"{event_id}:unclassified",
              "attribution_probability":None,"snippet":snippet,"extraction_method":"regex_context_v1",
              "source_priority":"primary_hint" if any(x in url.lower() for x in PRIMARY) else "secondary_or_unknown",
              "candidate_confidence":conf(url,snippet),"review_status":"pending"})
    return out
def event_url_map(daily,ledger):
    by_key={str(r.get("event_key")):str(r.get("event_id")) for r in ledger if r.get("event_key")}
    out=[]
    for c in daily.get("current_clusters",[]):
        eid=by_key.get(str(c.get("key")))
        if not eid: continue
        for url in c.get("urls",[]) or []:
            if isinstance(url,str) and url.startswith(("http://","https://")): out.append((eid,url))
    return out
def write_reports(rows,jp,mp):
    ordered=sorted(rows,key=lambda r:(r["candidate_confidence"],r["amount_native"]),reverse=True)
    payload={"version":1,"generated_at":now(),"candidate_count":len(ordered),"candidates":ordered}
    jp.parent.mkdir(parents=True,exist_ok=True); jp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Economic Evidence Candidates","",f"Generated: `{payload['generated_at']}`","",
           "> Candidates are not accepted evidence and carry no causal attribution.","",
           "| Event | Amount | Currency | Confidence | Source | Status |","|---|---:|---|---:|---|---|"]
    for r in ordered[:40]:
        lines.append(f"| `{r['event_id']}` | {r['amount_native']:,.0f} | {r['currency']} | {r['candidate_confidence']:.2f} | {r['source_priority']} | {r['review_status']} |")
    mp.write_text("\n".join(lines)+"\n",encoding="utf-8")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily",type=Path,default=D_DAILY); ap.add_argument("--ledger",type=Path,default=D_LEDGER)
    ap.add_argument("--candidates",type=Path,default=D_CAND; ap.add_argument("--json-report",type=Path,default=D_JSON)
    ap.add_argument("--md-report",type=Path,default=D_MD); a=ap.parse_args()
    daily=read_json(a.daily); ledger=read_jsonla.ledger)
    existing={r["candidate_id"]:r for r in read_jsonla.candidates) if r.get("candidate_id")}
    failures=0
    for eid,url in event_url_map(daily,ledger):
        try: text=fetch_text(url)
        except Exception: failures+=1; continue
        for row in extract_from_text(eid,url,text): existing.setdefault(row["candidate_id"],row)
    rows=list(existing.values()); write_jsonl(a.candidates,rows); write_reports(rows,a.json_report,a.md_report)
    print(f"Evidence candidates: {len(rows)} total; {failures} source fetch failures.")
    return 0
if __name__=="__main__": raise SystemExit(main())
