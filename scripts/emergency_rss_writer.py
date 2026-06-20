#!/usr/bin/env python3
from __future__ import annotations

import email.utils
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

USER_AGENT = "senna-infoflow-emergency/1.3"

SOURCES = [
    ("openai_news_rss", "OpenAI News RSS", "https://openai.com/news/rss.xml", ["OpenAI", "ChatGPT", "AI", "agents", "automation", "safety", "privacy"], "agentic_ai"),
    ("github_blog_atom", "GitHub Blog", "https://github.blog/feed/", ["GitHub", "Copilot", "CodeQL", "Dependabot", "security", "automation", "AI"], "agentic_devtools"),
    ("github_changelog_atom", "GitHub Changelog", "https://github.blog/changelog/feed/", ["GitHub", "Copilot", "Actions", "security", "AI", "MCP"], "agentic_devtools"),
    ("hatena_hotentry_it", "Hatena Hotentry IT", "https://b.hatena.ne.jp/hotentry/it.rss", ["Japan", "developer", "AI", "security", "GitHub", "MCP", "Codex", "agent", "ENPIRE"], "apac_signal"),
    ("e27_asia_startups_feed", "e27 Asia Startup and Tech", "https://e27.co/feed/", ["Southeast Asia", "startup", "founder", "AI", "funding", "Singapore", "Indonesia", "Vietnam", "Thailand", "Philippines"], "apac_signal"),
    ("jpcert_english_alerts", "JPCERT English Alerts", "https://www.jpcert.or.jp/english/rss/jpcert-en.rdf", ["JPCERT", "Japan", "security", "CVE", "vulnerability", "incident", "advisory", "malware", "ransomware"], "security"),
    ("twcert_security_news", "TWCERT Security News", "https://www.twcert.org.tw/tw/rss-104-1.xml", ["TWCERT", "Taiwan", "security", "CVE", "vulnerability", "incident", "phishing", "ransomware", "patch"], "security"),
    ("heise_security_atom", "heise Security Alerts", "https://www.heise.de/security/rss/alert-news-atom.xml", ["security", "CVE", "vulnerability", "Datenschutz", "Open Source", "Supply Chain Security"], "security"),
]


def strip_html(text: str | None) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def child_text(el: ET.Element, names: list[str]) -> str:
    for child in list(el):
        if local_name(child.tag) in names and child.text:
            return child.text.strip()
    for name in names:
        found = el.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def child_link(el: ET.Element) -> str:
    txt = child_text(el, ["link"])
    if txt:
        return txt.strip()
    for child in list(el):
        if local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return ""


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return email.utils.parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return None


def classify_priority(entry: dict) -> tuple[str, int]:
    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
    high_terms = ["critical", "kritisch", "actively exploited", "rce", "remote code", "zero-day", "0-day", "breach", "leak", "outage", "ransomware", "cve-"]
    medium_terms = ["security", "vulnerability", "patch", "copilot", "agent", "mcp", "ai", "openai", "github", "jpcert", "twcert", "enpire", "robot"]
    if any(t in text for t in high_terms):
        return "medium", 12
    if any(t in text for t in medium_terms):
        return "observe", 7
    return "observe", 5


def fetch_source(source_id: str, name: str, url: str, keywords: list[str], bucket: str, ts: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read(600000)
    root = ET.fromstring(data)
    items = root.findall(".//item")
    if not items:
        items = [el for el in root.iter() if local_name(el.tag) == "entry"]

    entries: list[dict] = []
    for item in items[:6]:
        title = strip_html(child_text(item, ["title"]))[:220]
        if not title:
            continue
        link = child_link(item)
        summary = strip_html(child_text(item, ["description", "summary", "content"]))[:420]
        published = parse_date(child_text(item, ["pubDate", "published", "updated", "date"]))
        entry = {
            "source_id": source_id,
            "source": name,
            "source_type": "rss",
            "bucket": bucket,
            "title": title,
            "url": link,
            "summary": summary,
            "published_at": published,
            "observed_at": ts,
            "risk_or_opportunity": "Beobachtung",
            "why_it_matters": summary or "Minimaler Notfeed-Treffer; nach Normalisierung gegenprüfen.",
            "recommendation": "Bei Relevanz direkt gegen Primärquelle prüfen; Emergency Mode ist bewusst dünn.",
            "keywords": keywords,
        }
        priority, score = classify_priority(entry)
        entry["priority"] = priority
        entry["relevance_score"] = score
        entries.append(entry)
    return entries


def render_markdown(latest: dict) -> str:
    sections = latest["sections"]
    lines: list[str] = [
        "# Senna Briefing", "",
        f"_Generiert: {latest['generated_at']}_", "",
        "## Emergency Feed Mode", "",
        "Der normale Hardened-Monitor läuft als Canary nebenher. Diese sichtbare Ausgabe bleibt absichtlich stabil und frontend-kompatibel, bis der normale Pfad wieder zuverlässig ist.", "",
        f"- Coverage confidence: `{latest['coverage']['coverage_confidence']}`",
        f"- Findings: `{latest['counts']['new_relevant_findings']}`",
        f"- Source errors: `{latest['counts']['source_errors']}`", "",
        "## Kurzlage", "",
        f"{latest['counts']['new_relevant_findings']} Treffer aus minimalem Kernfeed. Keine Score-Behauptung über Weltlage; nur Notversorgung bis zur Slow-Lane-Reparatur.", "",
    ]
    for label in ["high", "medium", "observe"]:
        lines.extend([f"## {label.upper()}", ""])
        items = sections.get(label) or []
        if not items:
            lines.append("- Keine.")
        for f in items:
            lines.append(f"- **{f['title']}** — {f['source']} — Score {f['relevance_score']}")
            if f.get("url"):
                lines.append(f"  - Quelle: {f['url']}")
            lines.append(f"  - Zeit: `{f.get('published_at') or 'unknown'}`")
            if f.get("summary"):
                lines.append(f"  - Kurz: {f['summary']}")
        lines.append("")
    lines.append("## Source Errors")
    if latest.get("source_errors"):
        for e in latest["source_errors"]:
            lines.append(f"- `{e['source_id']}` — {e['error']}")
    else:
        lines.append("- Keine.")
    lines.extend(["", "---", "END OF DOCUMENT", ""])
    return "\n".join(lines)


def main() -> int:
    ts = datetime.now(timezone.utc).isoformat()
    findings: list[dict] = []
    errors: list[dict] = []

    for sid, name, url, keywords, bucket in SOURCES:
        try:
            findings.extend(fetch_source(sid, name, url, keywords, bucket, ts))
        except Exception as exc:
            errors.append({"source_id": sid, "source": name, "url": url, "error": repr(exc), "observed_at": ts})
        time.sleep(0.1)

    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for f in findings:
        key = (str(f.get("title", "")).lower(), str(f.get("url", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    findings = deduped[:35]

    sections = {"high": [], "medium": [], "observe": []}
    for f in findings:
        sections.setdefault(f.get("priority", "observe"), []).append(f)

    counts = {
        "today_file_total": len(findings),
        "high": len(sections["high"]),
        "medium": len(sections["medium"]),
        "observe": len(sections["observe"]),
        "new_relevant_findings": len(findings),
        "source_errors": len(errors),
    }
    active_groups: dict[str, int] = {}
    for f in findings:
        bucket = f.get("bucket") or f.get("source_type") or "other"
        active_groups[bucket] = active_groups.get(bucket, 0) + 1

    latest = {
        "generated_at": ts,
        "run_id": ts,
        "status": "emergency",
        "mode": "emergency_minimal_rss_writer",
        "coverage": {
            "coverage_confidence": "low",
            "active_sensor_groups": active_groups,
            "principles": [
                "Emergency Mode: Feed-Kadenz vor Vollabdeckung.",
                "Keine Weltlage aus Minimalfeed ableiten.",
                "Direkte Primärquellen bei relevanten Treffern gegenprüfen.",
                "Hardened-Monitor läuft als Canary, bis Slow-Lane und Timeouts repariert sind.",
            ],
        },
        "counts": counts,
        "sections": sections,
        "findings": findings,
        "source_errors": errors,
        "quality_gate": {
            "thresholds": {"high": 18, "medium": 14, "observe": 3},
            "mode": "bypassed_emergency_writer",
            "note": "Normal quality gate bypassed to preserve visible feed cadence.",
        },
        "under_observation": {
            "topics": [
                {
                    "id": "feed_recovery_emergency_mode",
                    "title": "Feed Recovery Emergency Mode",
                    "status": "active",
                    "window_hits": {},
                    "notes": "Normaler Hardened-Monitor läuft als Canary; Emergency-RSS-Writer hält sichtbare Updates am Leben.",
                },
                {
                    "id": "physical_autoresearch_agentic_runtime",
                    "title": "ENPIRE / Physical Autoresearch und agentische Runtime-Verbesserung",
                    "status": "active",
                    "window_hits": {},
                    "notes": "Beobachtet Physical-Autoresearch, Verification/Reset/Budget/Audit-Harness und agentische Runtime-Pipelines.",
                },
            ]
        },
    }

    for dirname in ["briefings", "docs", "state", "reports", "data"]:
        Path(dirname).mkdir(exist_ok=True)

    payload = json.dumps(latest, ensure_ascii=False, indent=2) + "\n"
    Path("briefings/latest.json").write_text(payload, encoding="utf-8")
    Path("docs/latest.json").write_text(payload, encoding="utf-8")
    Path("briefings/latest.md").write_text(render_markdown(latest), encoding="utf-8")

    health = {
        "generated_at": ts,
        "status": "emergency",
        "mode": "emergency_minimal_rss_writer",
        "frontend_schema": "sections/counts compatible",
        "findings": len(findings),
        "source_errors": errors,
        "normal_canary": "see reports/canary/status.json if present",
    }
    health_payload = json.dumps(health, ensure_ascii=False, indent=2) + "\n"
    Path("briefings/health.json").write_text(health_payload, encoding="utf-8")
    Path("docs/health.json").write_text(health_payload, encoding="utf-8")
    Path("briefings/health.md").write_text(
        "\n".join([
            "# Senna Pipeline Health", "",
            f"_Generated: {ts}_", "",
            "Status: `emergency`", "",
            "## Emergency Mode", "",
            "- Minimal RSS writer active for visible dashboard cadence.",
            "- Hardened monitor runs separately as canary when workflow permits.",
            "- Frontend-compatible `sections/counts` schema active.",
            f"- findings: `{len(findings)}`",
            f"- source errors: `{len(errors)}`",
            "",
            "---",
            "END OF DOCUMENT",
            "",
        ]),
        encoding="utf-8",
    )
    print(f"Emergency frontend-compatible briefing written with {len(findings)} findings and {len(errors)} source errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
