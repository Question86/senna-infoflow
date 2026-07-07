#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
DOCS = ROOT / "docs"

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def clip(value, limit=260):
    text = "" if value is None else " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

def compact(item):
    return {
        "title": clip(item.get("title"), 180),
        "source": clip(item.get("source"), 90),
        "source_type": item.get("source_type"),
        "published_at": item.get("published_at"),
        "relevance_score": item.get("relevance_score"),
        "url": item.get("url"),
        "summary": clip(item.get("summary")),
    }

def top_items(latest):
    out = []
    sections = latest.get("sections") if isinstance(latest, dict) else {}
    if isinstance(sections, dict):
        for section in ("high", "medium", "observe"):
            values = [x for x in (sections.get(section) or []) if isinstance(x, dict)]
            values.sort(key=lambda x: (float(x.get("relevance_score") or 0), str(x.get("published_at") or "")), reverse=True)
            for item in values[:4]:
                row = compact(item)
                row["section"] = section
                out.append(row)
    if not out:
        findings = [x for x in (latest.get("findings") or []) if isinstance(x, dict)]
        findings.sort(key=lambda x: float(x.get("relevance_score") or 0), reverse=True)
        out = [compact(x) for x in findings[:12]]
    return out[:12]

def main():
    latest = load_json(BRIEFINGS / "latest.json", {})
    health = load_json(BRIEFINGS / "health.json", {})
    counts = latest.get("counts") if isinstance(latest, dict) else {}
    if not isinstance(counts, dict):
        counts = {}
    coverage = latest.get("coverage") if isinstance(latest, dict) else {}
    if not isinstance(coverage, dict):
        coverage = {}
    handoff = {
        "schema_version": 1,
        "doc_type": "senna.chat_handoff",
        "generated_at": latest.get("generated_at") or health.get("generated_at"),
        "status": latest.get("status") or health.get("status") or "unknown",
        "coverage_confidence": coverage.get("coverage_confidence") or health.get("coverage_confidence"),
        "counts": {
            "new_relevant_findings": counts.get("new_relevant_findings", 0),
            "today_file_total": counts.get("today_file_total", 0),
            "displayed_findings": counts.get("displayed_findings", 0),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "observe": counts.get("observe", 0),
        },
        "source_errors_count": len(latest.get("source_errors") or []),
        "top_signals": top_items(latest),
        "next_read_order": [
            "briefings/chat_handoff.json",
            "memory/index.json",
            "briefings/health.json",
            "briefings/latest.json only if deeper inspection is needed",
        ],
    }
    for base in (BRIEFINGS, DOCS):
        base.mkdir(parents=True, exist_ok=True)
        (base / "chat_handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = ["# Senna Chat Handoff", "", f"_Generated: {handoff.get('generated_at')}_", "", "## Status",
                 f"- status: `{handoff.get('status')}`", f"- findings: `{handoff['counts'].get('displayed_findings')}`", "", "## Top Signals"]
        for i, item in enumerate(handoff["top_signals"], 1):
            lines += ["", f"### {i}. {item.get('title') or 'Untitled'}", f"- source: {item.get('source') or 'unknown'}",
                      f"- score: `{item.get('relevance_score')}`", f"- published: `{item.get('published_at')}`",
                      f"- url: {item.get('url') or ''}", f"- summary: {item.get('summary') or ''}"]
        lines += ["", "END OF DOCUMENT", ""]
        (base / "chat_handoff.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote compact ChatGPT handoff with {len(handoff['top_signals'])} top signal(s).")

if __name__ == "__main__":
    main()
