#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

R=Path(__file__).resolve().parents[1]; B=R/"briefings"; M=R/"memory"; D=R/"docs"; S=R/"state"
HIGH=["zero-day","actively exploited","ausgenutzt","critical","kritisch","ransomware","emergency","port closure","pipeline outage"]
EARLY=["outage","blackout","strike","protest","supply chain","wildfire","flood","earthquake","local","regional"]
IDENT=["axi0m","user yps","question86","senna-infoflow"]
TOP={"axiom":IDENT,"ai":["ai","ki","llm","openai","agent","mcp","codex"],"security":["security","cyber","cve","schwachstelle","exploit","patch"],"infra":["outage","blackout","supply chain","pipeline","port"],"macro":["fed","ecb","bis","inflation","rate","market"]}

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
    except Exception: return d
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def clip(x,n=220):
    s=" ".join(str(x or "").split()); return s if len(s)<=n else s[:n-1]+"…"
def blob(x):
    return " ".join(str(x.get(k) or "") for k in ("title","summary","source","source_type","url","relevance_reason")).casefold()
def hits(s,words): return [w for w in words if w in s]
def topics(s):
    r=[k for k,v in TOP.items() if hits(s,v)]
    return r or ["general"]
def n(x):
    try: return float(x)
    except Exception: return 0.0
def i(x):
    try: return int(x)
    except Exception: return 0
def key(x): return str(x.get("key") or x.get("id") or x.get("url") or x.get("title") or "").casefold()

def main():
    latest=load(B/"latest.json",{}); net=load(B/"network.json",{}); vel=load(S/"velocity.json",{}); base=load(S/"baseline.json",{})
    items=[x for x in latest.get("findings",[]) if isinstance(x,dict)] if isinstance(latest,dict) else []
    clusters=[x for x in net.get("clusters",[]) if isinstance(x,dict)] if isinstance(net,dict) else []
    by={key(x):x for x in items}; rows=[]
    for c in (clusters or items):
        x=dict(by.get(str(c.get("key") or ""),{})); x.update(c)
        s=blob(x); k=key(x); srcs=x.get("sources") if isinstance(x.get("sources"),list) else []
        sc=max(i(x.get("source_count")),len(srcs),1 if x.get("source") else 0)
        delta=i(x.get("momentum_delta")); ent=(vel.get("entities") or {}).get(k,{}) if isinstance(vel,dict) else {}
        if isinstance(ent,dict) and isinstance(ent.get("history"),list): delta=max(delta,len(ent["history"][-3:])-1)
        b=(base.get("entities") or {}).get(k,{}) if isinstance(base,dict) else {}; z=n(b.get("z_hint")) if isinstance(b,dict) else 0
        hi,ea,idn=hits(s,HIGH),hits(s,EARLY),bool(hits(s,IDENT))
        score=max(n(x.get("network_score") or x.get("ranking_score")),n(x.get("max_score") or x.get("relevance_score")))
        score+=min(8,(sc-1)*2.5)+min(8,max(0,delta)*2.5)+min(6,max(0,z)*.7)+(5 if hi else 0)+(4 if ea and sc<=2 else 0)+(6 if idn else 0)
        if score>=34 or (delta>=4 and sc>=2): band,read="extreme","Die Dynamik ist verglichen mit dem normalen Speicherbild außergewöhnlich steil."
        elif score>=27: band,read="krass","Die Dynamik ist verglichen ziemlich krass; nicht automatisch wahrer, aber deutlich bewegter als übliches Rauschen."
        elif score>=20: band,read="strong","Die Dynamik liegt über Normalniveau und verdient aktive Beobachtung."
        elif score>=12: band,read="watch","Die Dynamik ist sichtbar, aber noch nicht stark genug für Alarm."
        else: band,read="quiet","Die Dynamik wirkt aktuell wie Hintergrundrauschen."
        why=[]
        if sc>1: why.append(f"source breadth {sc}")
        if delta: why.append(f"momentum delta {delta:+d}")
        if z: why.append(f"baseline z_hint {z:.2f}")
        if ea: why.append("early terms: "+", ".join(ea[:3]))
        if hi: why.append("high terms: "+", ".join(hi[:3]))
        if idn: why.append("AXI0M/User-Yps identity hit")
        line="Beobachten, nicht aufblasen."
        if band in ("krass","extreme"): line="Nicht automatisch handeln. Erst sichern, dann vergleichen; die Steilheit ist der Befund."
        if band in ("krass","extreme") and ea: line="Frühes Signal, aber die Bewegung ist bereits zu steil, um sie als bloßes Rauschen zu behandeln."
        rows.append({"title":clip(x.get("title")),"url":x.get("url") or ((x.get("urls") or [None])[0] if isinstance(x.get("urls"),list) else None),"source":clip(x.get("source"),120),"topics":topics(s),"dynamics_score":round(score,2),"dynamic_band":band,"comparative_read":read,"senna_line":line,"source_count":sc,"momentum_delta":delta,"baseline_z_hint":round(z,2),"why":why or ["no strong comparative reason"],"summary":clip(x.get("summary"),300)})
    rows=sorted(rows,key=lambda r:(r["dynamics_score"],r["dynamic_band"] in ("krass","extreme"),r["source_count"]),reverse=True)[:30]
    bands=Counter(r["dynamic_band"] for r in rows); top=rows[0] if rows else {}
    sit="Keine verwertbaren Dynamiken im aktuellen Run." if not top else f"Stärkste Dynamik: “{top['title']}” — {top['comparative_read']} Band={top['dynamic_band']}, score={top['dynamics_score']}."
    payload={"schema_version":1,"doc_type":"senna.memory.dynamics","generated_at":now(),"principle":"Movement is probability, not proof. Compare speed, breadth, baseline deviation, early-signal character, high-signal terms, and AXI0M/User-Yps relevance.","counts":{"dynamics":len(rows),"bands":dict(bands)},"top_dynamics":rows}
    handoff={"schema_version":1,"doc_type":"senna.intelligence_handoff","generated_at":now(),"situation_read":sit,"how_to_use":["Read before latest.json for Lage.","Say quiet/watch/strong/krass/extreme compared with memory.","Dynamics are comparative movement, not certainty."],"top_dynamics":rows[:12],"read_order":["briefings/intelligence_handoff.json","memory/dynamics.json","briefings/chat_handoff.json","memory/index.json","briefings/latest.json if details are needed"]}
    candidates={"schema_version":1,"doc_type":"senna.memory.real_memory_candidates","generated_at":now(),"scope_note":"Repo-local memory candidates only; no private data and no claim of ChatGPT persistent memory.","keep":[{"type":"strategic_preference","text":"User Yps wants Senna to compare event dynamics against memory/baselines, not merely list feed items."},{"type":"architecture","text":"Senna should read intelligence_handoff, dynamics, chat_handoff, memory index, network, velocity and baseline before a Lageurteil."}],"current_dynamic_memory_candidates":[{"title":r["title"],"band":r["dynamic_band"],"reason":r["comparative_read"]} for r in rows[:8] if r["dynamic_band"] in ("krass","extreme") or "axiom" in r["topics"]]}
    for p,d in [(M/"dynamics.json",payload),(B/"intelligence_handoff.json",handoff),(D/"intelligence_handoff.json",handoff),(M/"real_memory_candidates.json",candidates)]: dump(p,d)
    md=["# Senna Intelligence Handoff","",f"_Generated: {handoff['generated_at']}_","","## Lageurteil","",sit,"","## Top Dynamics",""]
    for r in rows[:12]: md += [f"### {r['title']}","",f"- Band: `{r['dynamic_band']}`",f"- Dynamics score: `{r['dynamics_score']}`",f"- Vergleich: {r['comparative_read']}",f"- Senna: {r['senna_line']}",f"- Warum: {', '.join(r['why'])}",f"- Quelle: {r.get('url') or r.get('source') or 'unbekannt'}",""]
    for p in (B/"intelligence_handoff.md",D/"intelligence_handoff.md"): p.parent.mkdir(parents=True,exist_ok=True); p.write_text("\n".join(md)+"\n",encoding="utf-8")
    idx=load(M/"index.json",{}); idx=idx if isinstance(idx,dict) else {}; idx.setdefault("files",{}).update({"dynamics":"memory/dynamics.json","intelligence_handoff":"briefings/intelligence_handoff.json","repo_memory_candidates":"memory/real_memory_candidates.json"}); idx["intelligence_layer"]={"schema_version":1,"generated_at":now(),"dynamic_band_counts":dict(bands)}; dump(M/"index.json",idx)
    for p in (B/"chat_handoff.json",D/"chat_handoff.json"):
        h=load(p,{})
        if isinstance(h,dict): h["intelligence_layer"]={"situation_read":sit,"read_order":["briefings/intelligence_handoff.json","memory/dynamics.json"],"top_dynamics":rows[:5]}; dump(p,h)
    print(f"Wrote Senna intelligence layer: {len(rows)} dynamics, bands={dict(bands)}.")
if __name__=="__main__": main()
