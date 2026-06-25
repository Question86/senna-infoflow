#!/usr/bin/env python3
import json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/"briefings"; R=ROOT/"reports"; S=ROOT/"state"
UA="senna-infoflow/1.0 global-watchdogs"
START="<!-- SENNA_GLOBAL_WATCHDOGS:START -->"
END="<!-- SENNA_GLOBAL_WATCHDOGS:END -->"

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def jget(url):
    r=requests.get(url,headers={"User-Agent":UA},timeout=8); r.raise_for_status(); return r.json()

def tget(url):
    r=requests.get(url,headers={"User-Agent":UA},timeout=8); r.raise_for_status(); return r.text

def f(x,d=0.0):
    try: return float(x) if x is not None else d
    except Exception: return d

def pct(x):
    v=f(x); return ("+" if v>0 else "")+f"{v:.2f}%"

def iso_ms(x):
    try: return datetime.fromtimestamp(f(x)/1000,timezone.utc).replace(microsecond=0).isoformat()
    except Exception: return ""

def rank(sev):
    return {"critical":4,"high":3,"medium":2,"watch":1}.get(sev,0)

def add(arr, domain, sev, title, summary, source="", url="", ts="", metrics=None):
    arr.append({"domain":domain,"severity":sev,"title":title,"summary":summary,"source":source,"url":url,"published_at":ts,"metrics":metrics or {}})

def security():
    out=[]; err=[]; seen=set()
    feeds=[
      "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.geojson",
      "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson",
      "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_hour.geojson"]
    for url in feeds:
        try: data=jget(url)
        except Exception as e: err.append(f"USGS failed: {e}"); continue
        for ft in data.get("features",[]):
            p=ft.get("properties") or {}; eid=ft.get("id") or p.get("url")
            if not eid or eid in seen: continue
            seen.add(eid); mag=f(p.get("mag")); alert=str(p.get("alert") or "").lower(); sig=f(p.get("sig")); tsu=int(f(p.get("tsunami")))
            place=p.get("place") or "unknown location"
            if alert=="red" or mag>=7.5 or (mag>=7.0 and sig>=800): sev="critical"
            elif alert=="orange" or mag>=7.0 or tsu: sev="high"
            elif mag>=6.0: sev="medium"
            elif mag>=5.5: sev="watch"
            else: continue
            add(out,"security",sev,f"USGS earthquake M{mag:.1f} - {place}",f"M{mag:.1f} - {place}. PAGER alert: {alert or 'none'}. Tsunami flag: {tsu}.","USGS",p.get("url") or "",iso_ms(p.get("time")),{"mag":mag,"alert":alert,"sig":sig,"tsunami":tsu})
    try:
        x=tget("https://www.gdacs.org/xml/rss.xml")
        for it in re.findall(r"<item>(.*?)</item>",x,re.S|re.I)[:10]:
            title=re.sub("<[^>]+>"," ",re.search(r"<title[^>]*>(.*?)</title>",it,re.S|re.I).group(1)).strip() if re.search(r"<title[^>]*>(.*?)</title>",it,re.S|re.I) else "GDACS event"
            link=re.search(r"<link[^>]*>(.*?)</link>",it,re.S|re.I); link=link.group(1).strip() if link else ""
            text=it.lower()
            if any(w in text for w in ["earthquake","tsunami","cyclone","volcano","flood","red alert","orange alert"]):
                sev="high" if any(w in text for w in ["red alert","orange alert","tsunami","death"]) else "medium"
                add(out,"security",sev,"GDACS: "+title,title,"GDACS",link,"",{})
    except Exception as e: err.append(f"GDACS failed: {e}")
    try:
        kev=jget("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
        for v in (kev.get("vulnerabilities") or [])[:5]:
            add(out,"security","high",f"CISA KEV: {v.get('cveID','CVE')} {v.get('vendorProject','')} {v.get('product','')}".strip(),f"Known exploited vulnerability. Added {v.get('dateAdded','')}. Due {v.get('dueDate','')}. {v.get('vulnerabilityName','')}","CISA KEV","https://www.cisa.gov/known-exploited-vulnerabilities-catalog",v.get("dateAdded",""),{"cve":v.get("cveID")})
    except Exception as e: err.append(f"CISA KEV failed: {e}")
    return sorted(out,key=lambda i:(rank(i["severity"]),i.get("published_at","")),reverse=True)[:15],err

def economy():
    syms=["BTC-USD","ETH-USD","GC=F","SI=F","GLD","SLV","SPY","QQQ","^GSPC","^IXIC","^DJI","^VIX","DX-Y.NYB","CL=F","COIN","MSTR","IBIT"]
    err=[]; out=[]
    try:
        q=",".join(quote(s) for s in syms); data=jget("https://query1.finance.yahoo.com/v7/finance/quote?symbols="+q)
        qs={i.get("symbol"):i for i in (data.get("quoteResponse") or {}).get("result",[])}
    except Exception as e:
        return [],[f"Yahoo finance failed: {e}"]
    table=[("BTC-USD","Bitcoin",-2,-3.5),("ETH-USD","Ethereum",-2.5,-4),("GC=F","Gold futures",-1.2,-2.5),("SI=F","Silver futures",-1.8,-3.5),("GLD","GLD gold ETF",-1.2,-2.5),("SLV","SLV silver ETF",-1.8,-3.5),("SPY","S&P 500 ETF",-1.2,-2.5),("QQQ","Nasdaq 100 ETF",-1.5,-3),("^VIX","VIX",-20,7.5),("DX-Y.NYB","US Dollar Index",-1,1)]
    for sym,name,mid,hi in table:
        x=qs.get(sym) or {}; ch=f(x.get("regularMarketChangePercent")); px=f(x.get("regularMarketPrice"))
        sev=None
        if sym=="^VIX":
            if ch>=hi: sev="high"
            elif ch>=abs(mid): sev="medium"
        else:
            if ch<=hi: sev="high"
            elif ch<=mid or ch>=abs(mid): sev="medium"
        if sev:
            add(out,"economy",sev,f"Market move: {name} {pct(ch)}",f"{name} at {px:.2f}, change {pct(ch)}.","Yahoo Finance","https://finance.yahoo.com/quote/"+quote(sym),now(),{"symbol":sym,"price":px,"change_pct":ch})
    def ch(sym): return f((qs.get(sym) or {}).get("regularMarketChangePercent"))
    if ch("BTC-USD")<=-2 and (ch("GLD")<=-1.5 or ch("GC=F")<=-1.5) and (ch("SLV")<=-2 or ch("SI=F")<=-2):
        add(out,"economy","high","Cross-asset stress: Bitcoin + gold + silver sell-off",f"BTC {pct(ch('BTC-USD'))}, GLD {pct(ch('GLD'))}, SLV {pct(ch('SLV'))}.","Yahoo Finance","https://finance.yahoo.com/",now(),{"BTC":ch("BTC-USD"),"GLD":ch("GLD"),"SLV":ch("SLV")})
    if (ch("SPY")<=-2 or ch("QQQ")<=-2.5) and ch("^VIX")>=7.5:
        add(out,"economy","high","Cross-asset stress: equities down + VIX up",f"SPY {pct(ch('SPY'))}, QQQ {pct(ch('QQQ'))}, VIX {pct(ch('^VIX'))}.","Yahoo Finance","https://finance.yahoo.com/",now(),{})
    return sorted(out,key=lambda i:(rank(i["severity"]),i.get("published_at","")),reverse=True)[:20],err

def section(title, items, errs):
    lines=[f"## {title}",""]
    if not items: lines.append("- Kein aktives Signal aus den konfigurierten globalen Sensoren.")
    for i in items:
        link=f" — [Quelle]({i['url']})" if i.get("url") else ""
        lines += [f"- **{i['title']}** — {i['severity']}{link}",f"  - Quelle: {i.get('source','')}",f"  - Zeit: `{i.get('published_at','')}`",f"  - Kurz: {i.get('summary','')}"]
    if errs: lines += ["","- Sensor-Hinweis: "+" | ".join(errs[:5])]
    lines.append("")
    return lines

def insert(md, overlay):
    if START in md and END in md:
        return re.sub(re.escape(START)+r".*?"+re.escape(END)+r"\n", overlay, md, flags=re.S)
    m=re.search(r"\n## Priorität Hoch\n",md)
    return md[:m.start()]+"\n"+overlay+"\n"+md[m.start():] if m else md.rstrip()+"\n\n"+overlay

def main():
    B.mkdir(exist_ok=True); R.mkdir(exist_ok=True); S.mkdir(exist_ok=True)
    sec,se=security(); eco,ee=economy()
    lines=[START]+section("Sicherheitslage global",sec,se)+section("Wirtschaft global",eco,ee)+[END]
    overlay="\n".join(lines)+"\n"
    p=B/"latest.md"; p.write_text(insert(p.read_text(encoding="utf-8") if p.exists() else "# Senna Briefing\n\n",overlay),encoding="utf-8")
    payload={"generated_at":now(),"sections":{"global_security":sec,"global_economy":eco},"source_errors":se+ee}
    for path in [R/"global_watchdogs.json",S/"global_watchdogs.json"]:
        path.parent.mkdir(exist_ok=True); path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Global watchdogs wrote {len(sec)} security and {len(eco)} economy items.")
if __name__=="__main__": main()
