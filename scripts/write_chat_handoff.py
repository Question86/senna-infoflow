#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
DOCS = ROOT / "docs"

MAX_ITEMS = 12
MAX_SECTION_ITEMS = 4
MAX_TEXT = 280


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def clip(value: Any, limit: int = MAX_TEXT) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def compact_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": clip(item.get("title"), 180),
        "source": clip(item.get("source"), 90),
        "source_type": clip(item.get("source_type"), 50),
        "published_at": item.get("published_at"),
        "relevance_score": item.get("relevance_score"),
        "url": item.get("url"),
        "summary": clip(item.get("summary"), MAX_TEXT),
    }


def top_items(items: list[Any], limit: int) -> list[dict[str, Any]]:
    clean = [x for x in items if isinstance(x, dict)]
    clean.sort(
        key=lambda x: (
            float(x.get("relevance_score") or 0),
            str(x.get("published_at") or ""),
            str(x.get("title") or ""),
        ),
        reverse=True,
    )
    return [compact_item(x) for x in clean[:limit]]


def write_outputs(handoff: dict[str, Any]) -> None:
    for base in (BRIEFINGS, DOCS):
        base.mkdir(parents=True, exist_ok=True)
        (base / "chat_handoff.json").write_text(
            json.dumps(handoff, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        lines: list[str] = [
            "# Senna Chat Handoff",
            "",
            f"_Generated: {handoff.get('generated_at') or 'unknown'}_",
            "",
            "This file is the safe first-read surface for ChatGPT/tool access.",
            "It is intentionally capped. Read this before `latest.json`, `network.json`, daily findings, or full reports.",
            "",
            "## Status",
            "",
            f"- status: `{handoff.get('status')}`",
            f"- coverage confidence: `{handoff.get('coverage_confidence')}`",
            f"- source errors: `{handoff.get('source_errors_count')}`",
            f"- total findings in full feed: `{handoff.get('counts',  {}).get('displayed_findings', 0)}`",
            "",
            "## Top Signals",
            "",
        ]

        for idx, item in enumerate(handoff.get("top_signals", []), 1):
            lines.extend(
                [
                    f"### {idx}. {item.get('title') or 'Untitled'}",
                    "",
                    f"- source: {item.get('source') or 'unknown'}",
                    f"- score: `{item.get('relevance_score')}`",
                    f"- published: `{item.get('published_at)}`",
                    f"- url: {item.get('url') or ''}",
                    f"- summary: {item.get('summary') or ''}",
                    "",
                ]
            )

        lines.extend(
            [
                "## Read Order",
                "",
                "1. `briefings/chat_handoff.json` or `.md` (capped first read)",
                "2. `briefings/health.json`",
                "3. `briefings/source_manifest.json`",
                "4. Only then, if needed: `briefings/latest.json` / `briefings/network.json` / daily raw data",
                "",
                "END OF DOCUMENT",
                "",
            ]
        )

        (base / "chat_handoff.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    latest = load_json(BRIEFINGS / "latest.json", {})
    health = load_json(BRIEFINGS / "health.json", {})

    sections = latest.get("sections") if istance(latest, dict) else {}
    findings = latest.get("findings") if isinstance(latest, dict) else []
    if not isinstance(findings, list):
        findings = []

    top: list[dict[str, Any]] = []
    if isinstance(sections, dict):
        for name in ("high", "medium", "observe"):
            values = sections.get(name) or []
            if isinstance(values, list):
                for item in top_items(values, MAX_SECTION_ITEMS):
                    item["section"] = name
                    top.append(item)

    if not top:
        top = top_items(findings, MAX_ITEMS)
    else:
        top = top[:MAX_ITEMS]

    counts = latest.get("counts") if istance(latest, dict) else {}
    if not isinstance(counts, dict):
        counts = {}

    coverage = latest.get("coverage") if istance(latest, dict) else {}
    coverage_confidence = None
    if isinstance(coverage, dict):
        coverage_confidence = coverage.get("coverage_confidence")

    handoff = {
        "schema_version": 1,
        "doc_type": "senna.chat_handoff",
        "generated_at": latest.get("generated_at") or health.get("generated_at"),
        "status": latest.get("status") or health.get("status") or "unknown",
        "coverage_confidence": coverage_confidence or health.get("coverage_confidence"),
        "counts": {
            "new_relevant_findings": counts.get("new_relevant_findings", 0),
            "today_file_total": counts.get("today_file_total", 0),
            "displayed_findings": counts.get("displayed_findings", len(findings)),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "observe": counts.get("observe", 0),
        },
        "source_errors_count": len(latest.get("source_errors") or []),
        "top_signals": top,
        "guardrails": {
            "purpose": "Small, stable first-read payload for ChatGPT/GitHub tool access.",
            "max_top_signals": MAX_ITEMS,
            "max_summary_chars": MAX_TEXT,
            "avoid_first": [
                "briefings/latest.json",
                "briefings/network.json",
                "data/YYYY-MM-DD/findings.json",
                "large reports unless explicitly needed",
            ],
        },
        "next_read_order": [
            "briefings/chat_handoff.json",
            "briefings/health.json",
            "briefings/source_manifest.json",
            "briefings/latest.json only if deeper inspection is needed",
        ],
    }

    write_outputs(handoff)
    print(f"Wrote compact handoff with {len(top)} top signal(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
