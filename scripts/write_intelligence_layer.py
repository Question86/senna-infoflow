#!/usr/bin/env python3
import json,re
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
R=Path(__file__).resolve().parents[1];B=R/"briefings";M=R/"memory";D=R/"docs";S=R/"state"
HI="zero-day 0-day actively exploited active exploitation ausgenutzt aktive angriffe critical kritisch emergency ransomware unauthenticated rce remote code execution cvss 10 cvss 9.9 cvss 9.8 domain controller netlogon firewall vpn ivanti pan-os exchange sharepoint citrix fortinet palo alto auth bypass privilege escalation container breakout kubernetes gke root privileges".split()
AI=" ai  ki llm openai agent mcp codex claude robot nvidia".split()
ID="axi0m user yps question86 senna-infoflow".split()
OFF="cert-eu cert-bund bsi cisa jvn cve security advisory security-advisories cisa kev known exploited google cloud microsoft palo alto ivanti".split()
EARLY="outage blackout strike protest supply chain wildfire flood earthquake local regional shortage evacuation pipeline outage".split()
TOP={"axiom":ID,"ai":AI,"security":["security","cyber","cve","schwachstelle","vulnerability","exploit","patch","ransomware"],"infra":["outage","blackout","supply chain","pipeline","port closure","vpn","firewall","exchange"],"macro":["fed","ecb","bis","inflation","rate","market"],"disaster":["earthquake","flood","wildfire","storm","drought","volcano"]}
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
    except Exception: return d
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def txt(p,s):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s,encoding="utf-8")
def clip(x,n=240):
    s=" ".join(str(x or "").split()); return s if len(s)<=n else s[:n-1].rstrip()+"…"
def num(x):
    try: return float(x)
    except Exception: return 0.0
def integer(x):
    try: return int(x)
    except Exception: return 0
def blob(x):
    return (" "+" ".join(str(x.get(k) or "") for k in ("title","summary","source","source_type","url","relevance_reason","recommended_action")).casefold()+" ")
def hit(s,terms): return [t for t in terms if t.casefold() in s]
def topics(s):
    r=[k for k,v in TOP.items() if hit(s,v)]
    return r or ["general"]
def key(x):
    for k in ("key","id","url","title"):
        v=str(x.get(k) or "").strip()
        if v: return v.casefold()
    return ""
def dt(v):
    if not v: return None
    s=str(v)
    try: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception: pass
    m=re.search(r"(20\d\d-\d\d-\d\d)",s)
    if m:
        try: return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        except Exception: return None
def pub(x):
    for k in ("published_at","first_seen_at","last_seen_at","fetched_at"):
        if x.get(k): return str(x.get(k))
def age(x):
    d=dt(pub(x)); return max(0,(datetime.now(timezone.utc)-d).total_seconds()/86400) if d else 0
def scount(x):
    ss=x.get("sources") if isinstance(x.get("sources"),list) else []
    return max(integer(x.get("source_count")),len([s for s in ss if str(s).strip()]),1 if x.get("source") or x.get("url") else 0)
def source(x):
    ss=x.get("sources") if isinstance(x.get("sources"),list) else []
    return clip(x.get("source") or ", ".join(map(str,ss[:3])),120)
def merge(lat,net):
    fs=[x for x in lat.get("findings",[]) if isinstance(x,dict)]; cs=[x for x in net.get("clusters",[]) if isinstance(x,dict)]
    by={key(x):dict(x) for x in fs if key(x)}; out=[]; used=set()
    for c in cs:
        k=key(c); m=dict(by.get(k,{})); m.update(c); out.append(m); used.add(k)
    out += [dict(x) for x in fs if key(x) not in used]
    return out
def vdelta(k,x,vel):
    d=integer(x.get("momentum_delta")); e=(vel.get("entities") or {}).get(k,{}) if isinstance(vel,dict) else {}
    if isinstance(e,dict) and isinstance(e.get("history"),list): d=max(d,max(0,len(e["history"][-4:])-1))
    return d
def zhint(k,x,base):
    z=num(x.get("baseline_z_hint")); e=(base.get("entities") or {}).get(k,{}) if isinstance(base,dict) else {}
    return max(z,num(e.get("z_hint"))) if isinstance(e,dict) else z
def score(x,vel,base):
    s=blob(x); k=key(x); ts=topics(s); n=scount(x); d=vdelta(k,x,vel); z=zhint(k,x,base); days=age(x)
    hi=hit(s,HI); early=hit(s,EARLY); ident=hit(s,ID); off=hit(s,OFF); ai=hit(s,AI); sec=("security" in ts) or bool(hi and ("cve" in s or "rce" in s or "cvss" in s))
    official_sec=bool(sec and (hi or off)); single_ai=bool(("ai" in ts or ai) and not sec and not ident and n<=1)
    val=max(num(x.get("network_score")),num(x.get("ranking_score")),num(x.get("max_score")),num(x.get("relevance_score"))); why=[]
    if n>1: val+=min(10,(n-1)*3); why.append(f"source breadth +{n}")
    if d: val+=min(8,max(0,d)*2.5); why.append(f"momentum delta {d:+d}")
    if z: val+=min(6,max(0,z)*.7); why.append(f"baseline z_hint {z:.2f}")
    if early and n<=2: val+=3; why.append("early terms: "+", ".join(early[:3]))
    if hi: val+=5; why.append("high terms: "+", ".join(hi[:3]))
    if official_sec: val+=12; why.append("security high-signal: "+", ".join((hi or off)[:4]))
    if ident: val+=8; why.append("AXI0M/User-Yps identity hit")
    if single_ai: val-=8; why.append("single-source AI hype brake -8.0")
    if days>10:
        pen=min(8,(days-21)*.35) if (n>=2 or d>=3 or hi or official_sec) else min(16,(days-10)*.75)
        if pen>0: val-=pen; why.append(f"aging penalty -{pen:.1f} for {days:.1f}d old signal")
    raw="extreme" if val>=34 or (d>=4 and n>=2) else "krass" if val>=27 else "strong" if val>=20 else "watch" if val>=12 else "quiet"
    band=raw
    can_krass=n>=2 or bool(ident) or official_sec
    can_extreme=(n>=2 and (official_sec or hi)) or bool(ident)
    if raw=="extreme" and not can_extreme: band="strong"; val=min(val,24.9); why.append("extreme gate: needs multi-source high-signal, official security, or identity relevance")
    elif raw=="krass" and not can_krass: band="strong"; val=min(val,24.9); why.append("krass gate: single-source non-official/non-identity signal capped")
    if days>14 and n<=1 and not official_sec and not ident and band in ("strong","krass","extreme"):
        band="watch"; val=min(val,19.9); why.append("stale single-source cap: max watch after 14d without fresh resonance")
    read={"extreme":"Die Dynamik ist verglichen mit dem normalen Speicherbild außergewöhnlich steil.","krass":"Die Dynamik ist verglichen ziemlich krass; nicht automatisch wahrer, aber deutlich bewegter als übliches Rauschen.","strong":"Die Dynamik liegt über Normalniveau und verdient aktive Beobachtung.","watch":"Die Dynamik ist sichtbar, aber noch nicht stark genug für Alarm.","quiet":"Die Dynamik wirkt aktuell wie Hintergrundrauschen."}[band]
    line="Security zuerst. Exposure prüfen, Patchstand sichern, dann erst über Narrative reden." if official_sec and band in ("strong","krass","extreme") else "Interessant, aber Einzelquellen-AI darf nicht die Lage dominieren." if single_ai else "Beobachten, nicht aufblasen."
    return {"title":clip(x.get("title")),"url":x.get("url") or ((x.get("urls") or [None])[0] if isinstance(x.get("urls"),list) else None),"source":source(x),"published_at":pub(x),"age_days":round(days,2),"topics":ts,"dynamics_score":round(max(0,val),2),"raw_band":raw,"dynamic_band":band,"comparative_read":read,"senna_line":line,"source_count":n,"momentum_delta":d,"baseline_z_hint":round(z,2),"security_high_signal":official_sec,"single_source_ai_capped":single_ai or raw!=band,"why":why or ["no strong comparative reason"],"summary":clip(x.get("summary"),320)}
def md(h):
    lines=["# Senna Intelligence Handoff","",f"_Generated: {h.get('generated_at')}_","","## Lageurteil","",h.get("situation_read",""),"","## Top Dynamics",""]
    for r in h.get("top_dynamics",[])[:12]:
        lines += [f"### {r['title']}","",f"- Band: `{r['dynamic_band']}` (raw `{r['raw_band']}`)",f"- Dynamics score: `{r['dynamics_score']}`",f"- Published: `{r.get('published_at') or 'unknown'}` / age_days `{r['age_days']}`",f"- Vergleich: {r['comparative_read']}",f"- Senna: {r['senna_line']}",f"- Warum: {', '.join(r['why'])}",f"- Quelle: {r.get('url') or r.get('source') or 'unbekannt'}",""]
    return "\n".join(lines+["END OF DOCUMENT",""])
def main():
    latest=load(B/"latest.json",{}); net=load(B/"network.json",{}); vel=load(S/"velocity.json",{}); base=load(S/"baseline.json",{})
    rows=[score(x,vel if isinstance(vel,dict) else {},base if isinstance(base,dict) else {}) for x in merge(latest if isinstance(latest,dict) else {},net if isinstance(net,dict) else {})]
    rows.sort(key=lambda r:(r["dynamic_band"] in ("krass","extreme"),r["security_high_signal"],r["dynamics_score"],r["source_count"]),reverse=True); rows=rows[:40]
    bands=Counter(r["dynamic_band"] for r in rows); top=rows[0] if rows else {}
    sit="Keine verwertbaren Dynamiken im aktuellen Run." if not top else f"Stärkste Dynamik: “{top['title']}” — {top['comparative_read']} Band={top['dynamic_band']}, score={top['dynamics_score']}."
    t=now(); dyn={"schema_version":2,"doc_type":"senna.memory.dynamics","generated_at":t,"principle":"Movement is probability, not proof. Krass/extreme requires cross-source breadth, identity relevance, or official high-signal security/incident evidence. Old single-source AI is capped.","counts":{"dynamics":len(rows),"bands":dict(bands)},"top_dynamics":rows}
    hand={"schema_version":2,"doc_type":"senna.intelligence_handoff","generated_at":t,"situation_read":sit,"how_to_use":["Read before latest.json for Lage.","Treat dynamic_band as comparative motion, not factual certainty.","Single-source AI is capped unless AXI0M/User-Yps relevance or official incident evidence exists.","Security high-signal terms outrank AI hype when exposure could matter."],"top_dynamics":rows[:12],"read_order":["briefings/intelligence_handoff.json","memory/dynamics.json","briefings/chat_handoff.json","memory/index.json","briefings/latest.json if details are needed"]}
    mem={"schema_version":2,"doc_type":"senna.memory.real_memory_candidates","generated_at":t,"scope_note":"Repo-local memory candidates only; no private data and no claim of ChatGPT persistent memory.","keep":[{"type":"strategic_preference","text":"User Yps wants event dynamics compared against memory/baselines, not merely feed listings."},{"type":"ranking_rule","text":"Krass requires at least two independent sources or official high-signal security/incident evidence, unless AXI0M/User Yps is directly affected."},{"type":"ranking_rule","text":"Old single-source AI items should be capped below krass and usually below strong after 14 days unless new resonance appears."},{"type":"ranking_rule","text":"Security terms such as actively exploited, unauthenticated RCE, CVSS 9.8/10, domain controller, firewall, VPN, Ivanti, PAN-OS, Exchange should outrank AI hype when exposure is plausible."}],"current_dynamic_memory_candidates":[{"title":r["title"],"band":r["dynamic_band"],"reason":r["comparative_read"]} for r in rows[:8] if r["dynamic_band"] in ("strong","krass","extreme") or "axiom" in r["topics"]]}
    for p,d in [(M/"dynamics.json",dyn),(B/"intelligence_handoff.json",hand),(D/"intelligence_handoff.json",hand),(M/"real_memory_candidates.json",mem)]: dump(p,d)
    txt(B/"intelligence_handoff.md",md(hand)); txt(D/"intelligence_handoff.md",md(hand))
    idx=load(M/"index.json",{}); idx=idx if isinstance(idx,dict) else {}; idx.setdefault("files",{}).update({"dynamics":"memory/dynamics.json","intelligence_handoff":"briefings/intelligence_handoff.json","repo_memory_candidates":"memory/real_memory_candidates.json"}); idx["intelligence_layer"]={"schema_version":2,"generated_at":t,"dynamic_band_counts":dict(bands),"gates":["krass requires cross-source/identity/official high-signal","stale single-source non-official max watch after 14d","single-source AI hype brake","official security high-signal boost"]}; dump(M/"index.json",idx)
    for p in (B/"chat_handoff.json",D/"chat_handoff.json"):
        h=load(p,{})
        if isinstance(h,dict): h["intelligence_layer"]={"situation_read":sit,"read_order":["briefings/intelligence_handoff.json","memory/dynamics.json"],"top_dynamics":rows[:5]}; dump(p,h)
    print(f"Wrote hardened Senna intelligence layer: {len(rows)} dynamics, bands={dict(bands)}.")
if __name__=="__main__": main()
