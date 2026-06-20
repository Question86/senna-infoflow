#!/usr/bin/env python3
from __future__ import annotations
import atexit,json,logging,os,random,time
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import requests
import monitor

DOCS_DIR = monitor.ROOT / "docs"

METRICS={"schema_version":1,"doc_type":"senna.http_fetch_metrics","started_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"requests":0,"retries":0,"failures":0,"retry_statuses":{},"retry_exceptions":{}}

def utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def http_rules():
    r=monitor.load_yaml(monitor.CONFIG_DIR/"rules.yaml",{})
    return (r.get("http") or {}) if isinstance(r,dict) else {}
def atomic_text(path:Path,text:str):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text,encoding="utf-8")
    tmp.replace(path)
def atomic_json(path:Path,data:Any): atomic_text(path,json.dumps(data,ensure_ascii=False,indent=2)+"\n")
def retry_after(resp):
    try: return max(0.0,min(float(resp.headers.get("Retry-After","")),60.0))
    except Exception: return None
def bump(bucket,key): METRICS[bucket][str(key)]=int(METRICS[bucket].get(str(key),0))+1

def request_get(session,url,timeout,headers=None,max_bytes=None):
    h=http_rules()
    attempts=max(1,int(h.get("retry_attempts",2)))
    backoff=max(0.0,float(h.get("retry_backoff_seconds",0.75)))
    jitter=max(0.0,float(h.get("retry_jitter_seconds",0.25)))
    retry_status={int(x) for x in h.get("retry_statuses",[429,500,502,503,504])}
    last=None
    for attempt in range(attempts):
        METRICS["requests"]+=1
        try:
            resp=session.get(url,timeout=timeout,headers=headers or {},stream=bool(max_bytes))
            if resp.status_code in retry_status and attempt<attempts-1:
                METRICS["retries"]+=1; bump("retry_statuses",resp.status_code)
                delay=retry_after(resp)
                if delay is None: delay=backoff*(2**attempt)+random.random()*jitter
                logging.warning("Transient HTTP %s for %s; retrying in %.2fs.",resp.status_code,url,delay)
                resp.close(); time.sleep(delay); continue
            resp.raise_for_status()
            if max_bytes:
                chunks=[]; size=0
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk: continue
                    size+=len(chunk)
                    if size>max_bytes: raise ValueError(f"Response exceeded max_bytes={max_bytes}")
                    chunks.append(chunk)
                resp._content=b"".join(chunks)
            return resp
        except (requests.Timeout,requests.ConnectionError) as exc:
            last=exc
            if attempt<attempts-1:
                METRICS["retries"]+=1; bump("retry_exceptions",exc.__class__.__name__)
                delay=backoff*(2**attempt)+random.random()*jitter
                logging.warning("Transient fetch error for %s: %s; retrying in %.2fs.",url,exc,delay)
                time.sleep(delay); continue
            METRICS["failures"]+=1; raise
        except Exception as exc:
            last=exc; METRICS["failures"]+=1; raise
    if last: raise last
    raise RuntimeError(f"fetch failed without exception: {url}")

def write_health(latest:dict[str,Any], errors:list[Any], status:str, coverage_confidence:str):
    ts = latest.get("generated_at") or monitor.now_iso()
    error_payload = [asdict(e) for e in errors]
    health = {
        "generated_at": ts,
        "status": status,
        "mode": "hardened_monitor",
        "frontend_schema": "sections/counts compatible",
        "coverage_confidence": coverage_confidence,
        "counts": latest.get("counts", {}),
        "source_errors": error_payload,
        "http_fetch_metrics": "briefings/http_fetch_metrics.json",
    }
    atomic_json(monitor.BRIEFINGS_DIR/"health.json", health)
    atomic_json(DOCS_DIR/"health.json", health)
    md = [
        "# Senna Pipeline Health",
        "",
        f"_Generated: {ts}_",
        "",
        f"Status: `{status}`",
        "",
        "## Hardened Monitor",
        "",
        "- Normaler Monitor schreibt sichtbaren Feed.",
        "- Emergency RSS writer ist nur noch Fallback, nicht Hauptleitung.",
        f"- coverage confidence: `{coverage_confidence}`",
        f"- findings: `{(latest.get('counts') or {}).get('new_relevant_findings', 0)}`",
        f"- source errors: `{len(error_payload)}`",
        "",
        "---",
        "END OF DOCUMENT",
        "",
    ]
    atomic_text(monitor.BRIEFINGS_DIR/"health.md","\n".join(md))
    atomic_text(DOCS_DIR/"health.md","\n".join(md))

def write_outputs(new_findings,errors,rules):
    monitor.BRIEFINGS_DIR.mkdir(parents=True,exist_ok=True); monitor.DATA_DIR.mkdir(parents=True,exist_ok=True); DOCS_DIR.mkdir(parents=True,exist_ok=True)
    merged=monitor.merge_todays_findings(new_findings)
    latest_md=monitor.render_briefing_md(new_findings,errors,rules)
    atomic_text(monitor.BRIEFINGS_DIR/"latest.md",latest_md)
    atomic_text(DOCS_DIR/"latest.md",latest_md)
    high,medium,observe=monitor.priority_sections(new_findings,rules)
    status="normal" if not errors else "warning"
    coverage_confidence="normal" if not errors else "limited"
    scoring=rules.get("scoring") or {}
    latest={
        "generated_at":monitor.now_iso(),
        "run_id":monitor.now_iso(),
        "date":monitor.today_str(),
        "status":status,
        "mode":"hardened_monitor",
        "scope":"configured_public_sources_only",
        "coverage":{
            "coverage_confidence":coverage_confidence,
            "active_sensor_groups":{"configured_public_sources_only":len(new_findings)},
            "principles":[
                "Normaler Hardened-Monitor ist sichtbare Hauptleitung.",
                "Emergency RSS writer ist Fallback, nicht Lagebild.",
                "Einzelne Quellenfehler begrenzen Coverage, brechen aber nicht den Feed."
            ],
        },
        "counts":{"new_relevant_findings":len(new_findings),"today_file_total":len(merged),"high":len(high),"medium":len(medium),"observe":len(observe),"source_errors":len(errors)},
        "sections":{"high":[asdict(f) for f in high],"medium":[asdict(f) for f in medium],"observe":[asdict(f) for f in observe]},
        "findings":[asdict(f) for f in sorted(new_findings,key=lambda f:f.relevance_score,reverse=True)],
        "source_errors":[asdict(e) for e in errors],
        "quality_gate":{
            "thresholds":{
                "high":int(scoring.get("high_threshold",18)),
                "medium":int(scoring.get("medium_threshold",8)),
                "observe":int(scoring.get("observe_threshold",1)),
            },
            "mode":"hardened_monitor",
            "note":"Normal scoring and source isolation active.",
        },
    }
    atomic_json(monitor.BRIEFINGS_DIR/"latest.json",latest)
    atomic_json(DOCS_DIR/"latest.json",latest)
    write_health(latest, errors, status, coverage_confidence)

def write_metrics():
    payload=dict(METRICS); payload["finished_at"]=utc()
    try:
        atomic_json(monitor.STATE_DIR/"http_fetch_metrics.json",payload)
        atomic_json(monitor.BRIEFINGS_DIR/"http_fetch_metrics.json",payload)
    except Exception as exc:
        logging.warning("Could not write HTTP metrics: %s",exc)

def main():
    monitor.request_get=request_get
    monitor.write_json=atomic_json
    monitor.write_outputs=write_outputs
    atexit.register(write_metrics)
    return int(monitor.main())

if __name__=="__main__":
    raise SystemExit(main())
