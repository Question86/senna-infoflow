#!/usr/bin/env python3
from __future__ import annotations

import atexit
import json
import logging
import os
import random
import time
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import monitor

DOCS_DIR = monitor.ROOT / "docs"

METRICS = {
    "schema_version": 1,
    "doc_type": "senna.http_fetch_metrics",
    "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "requests": 0,
    "retries": 0,
    "failures": 0,
    "retry_statuses": {},
    "retry_exceptions": {},
}


def utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_rules() -> dict[str, Any]:
    rules = monitor.load_yaml(monitor.CONFIG_DIR / "rules.yaml", {})
    return (rules.get("http") or {}) if isinstance(rules, dict) else {}


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_json(path: Path, data: Any) -> None:
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def retry_after(resp: requests.Response) -> float | None:
    try:
        return max(0.0, min(float(resp.headers.get("Retry-After", "")), 60.0))
    except Exception:
        return None


def bump(bucket: str, key: Any) -> None:
    METRICS[bucket][str(key)] = int(METRICS[bucket].get(str(key), 0)) + 1


def request_get(
    session: requests.Session,
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
) -> requests.Response:
    http = http_rules()
    attempts = max(1, int(http.get("retry_attempts", 2)))
    backoff = max(0.0, float(http.get("retry_backoff_seconds", 0.75)))
    jitter = max(0.0, float(http.get("retry_jitter_seconds", 0.25)))
    retry_statuses = {int(x) for x in http.get("retry_statuses", [429, 500, 502, 503, 504])}
    last: BaseException | None = None

    for attempt in range(attempts):
        METRICS["requests"] += 1
        try:
            resp = session.get(
                url,
                timeout=timeout,
                headers=headers or {},
                stream=bool(max_bytes),
            )
            if resp.status_code in retry_statuses and attempt < attempts - 1:
                METRICS["retries"] += 1
                bump("retry_statuses", resp.status_code)
                delay = retry_after(resp)
                if delay is None:
                    delay = backoff * (2**attempt) + random.random() * jitter
                logging.warning("Transient HTTP %s for %s; retrying in %.2fs.", resp.status_code, url, delay)
                resp.close()
                time.sleep(delay)
                continue

            resp.raise_for_status()

            if max_bytes:
                chunks: list[bytes] = []
                size = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"Response exceeded max_bytes={max_bytes}")
                    chunks.append(chunk)
                resp._content = b"".join(chunks)

            return resp

        except (requests.Timeout, requests.ConnectionError) as exc:
            last = exc
            if attempt < attempts - 1:
                METRICS["retries"] += 1
                bump("retry_exceptions", exc.__class__.__name__)
                delay = backoff * (2**attempt) + random.random() * jitter
                logging.warning("Transient fetch error for %s: %s; retrying in %.2fs.", url, exc, delay)
                time.sleep(delay)
                continue
            METRICS["failures"] += 1
            raise
        except Exception as exc:
            last = exc
            METRICS["failures"] += 1
            raise

    if last:
        raise last
    raise RuntimeError(f"fetch failed without exception: {url}")


_FINDING_FIELDS = {field.name for field in fields(monitor.Finding)}


def finding_from_dict(item: dict[str, Any]) -> monitor.Finding:
    base = {
        "title": "",
        "url": "",
        "source": "",
        "source_type": "unknown",
        "published_at": None,
        "fetched_at": monitor.now_iso(),
        "summary": "",
    }
    base.update({k: item.get(k) for k in _FINDING_FIELDS if k in item})
    return monitor.Finding(**{k: base[k] for k in _FINDING_FIELDS if k in base})


def write_health(latest: dict[str, Any], errors: list[monitor.SourceError], status: str, coverage_confidence: str) -> None:
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
    atomic_json(monitor.BRIEFINGS_DIR / "health.json", health)
    atomic_json(DOCS_DIR / "health.json", health)
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
        "- Emergency RSS writer ist nur Fallback, nicht Lagebild.",
        f"- coverage confidence: `{coverage_confidence}`",
        f"- findings displayed: `{(latest.get('counts') or {}).get('displayed_findings', 0)}`",
        f"- new findings this run: `{(latest.get('counts') or {}).get('new_relevant_findings', 0)}`",
        f"- source errors: `{len(error_payload)}`",
        "",
        "---",
        "END OF DOCUMENT",
        "",
    ]
    atomic_text(monitor.BRIEFINGS_DIR / "health.md", "\n".join(md))
    atomic_text(DOCS_DIR / "health.md", "\n".join(md))


def write_outputs(new_findings: list[monitor.Finding], errors: list[monitor.SourceError], rules: dict[str, Any]) -> None:
    monitor.BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    monitor.DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    merged_today = monitor.merge_todays_findings(new_findings)
    display_findings = [finding_from_dict(item) for item in merged_today if isinstance(item, dict)]

    # Dashboard is a Lagebild, not a delta viewer. New findings remain counted,
    # but visible sections render the current UTC-day pool.
    latest_md = monitor.render_briefing_md(display_findings, errors, rules)
    atomic_text(monitor.BRIEFINGS_DIR / "latest.md", latest_md)
    atomic_text(DOCS_DIR / "latest.md", latest_md)

    high, medium, observe = monitor.priority_sections(display_findings, rules)
    sorted_display = sorted(
        display_findings,
        key=lambda f: (f.relevance_score, f.published_at or "", f.title),
        reverse=True,
    )

    status = "normal" if not errors else "warning"
    coverage_confidence = "normal" if not errors else "limited"
    scoring = rules.get("scoring") or {}

    latest = {
        "generated_at": monitor.now_iso(),
        "run_id": monitor.now_iso(),
        "date": monitor.today_str(),
        "status": status,
        "mode": "hardened_monitor",
        "scope": "configured_public_sources_only",
        "coverage": {
            "coverage_confidence": coverage_confidence,
            "active_sensor_groups": {
                "configured_public_sources_only": len(display_findings),
            },
            "principles": [
                "Normaler Hardened-Monitor ist sichtbare Hauptleitung.",
                "Dashboard zeigt Tageslage aus data/YYYY-MM-DD/findings.json, nicht nur Run-Delta.",
                "Emergency RSS writer ist Fallback, nicht Lagebild.",
                "Einzelne Quellenfehler begrenzen Coverage, brechen aber nicht den Feed.",
            ],
        },
        "counts": {
            "new_relevant_findings": len(new_findings),
            "today_file_total": len(display_findings),
            "displayed_findings": len(sorted_display),
            "high": len(high),
            "medium": len(medium),
            "observe": len(observe),
            "source_errors": len(errors),
        },
        "sections": {
            "high": [asdict(f) for f in high],
            "medium": [asdict(f) for f in medium],
            "observe": [asdict(f) for f in observe],
        },
        "findings": [asdict(f) for f in sorted_display],
        "new_findings": [asdict(f) for f in sorted(new_findings, key=lambda f: f.relevance_score, reverse=True)],
        "source_errors": [asdict(e) for e in errors],
        "quality_gate": {
            "thresholds": {
                "high": int(scoring.get("high_threshold", 18)),
                "medium": int(scoring.get("medium_threshold", 8)),
                "observe": int(scoring.get("observe_threshold", 1)),
            },
            "mode": "hardened_monitor",
            "note": "Normal scoring active. Visible dashboard renders current-day pool; new_findings is the run delta.",
        },
    }

    atomic_json(monitor.BRIEFINGS_DIR / "latest.json", latest)
    atomic_json(DOCS_DIR / "latest.json", latest)
    write_health(latest, errors, status, coverage_confidence)


def write_metrics() -> None:
    payload = dict(METRICS)
    payload["finished_at"] = utc()
    try:
        atomic_json(monitor.STATE_DIR / "http_fetch_metrics.json", payload)
        atomic_json(monitor.BRIEFINGS_DIR / "http_fetch_metrics.json", payload)
    except Exception as exc:
        logging.warning("Could not write HTTP metrics: %s", exc)


def main() -> int:
    monitor.request_get = request_get
    monitor.write_json = atomic_json
    monitor.write_outputs = write_outputs
    atexit.register(write_metrics)
    return int(monitor.main())


if __name__ == "__main__":
    raise SystemExit(main())
