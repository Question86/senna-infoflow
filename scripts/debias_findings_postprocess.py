#!/usr/bin/env python3
"""Post-monitor score debiasing.

Conservative repairs:
- fixes keyword false positives such as repo matching report.aspx
- prevents single-source vendor/self-project feeds from ranking like broad news
- keeps small initial signals visible, but labels them as small-initial instead of world-scale
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import re

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"

SCORE_IN_SEGMENT_RE = re.compile(r"\(\+([0-9.]+)\)")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def host_of(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower()
    except Exception:
        return ""


def is_github_item(item: dict[str, Any]) -> bool:
    host = host_of(str(item.get("url") or ""))
    source = str(item.get("source") or "").lower()
    stype = str(item.get("source_type") or "").lower()
    return stype == "github_search" or host.endswith("github.com") or "github" in source


def remove_keyword(item: dict[str, Any], keyword: str) -> None:
    kws = item.get("matched_keywords")
    if isinstance(kws, list):
        item["matched_keywords"] = [x for x in kws if str(x).casefold() != keyword.casefold()]


def subtract_reason_segment(item: dict[str, Any], label: str) -> float:
    reason = str(item.get("relevance_reason") or "")
    total = 0.0
    parts = []
    for raw in [p.strip() for p in reason.split(";") if p.strip()]:
        if raw.startswith(label + " ("):
            m = SCORE_IN_SEGMENT_RE.search(raw)
            if m:
                try:
                    total += float(m.group(1))
                except Exception:
                    pass
            continue
        parts.append(raw)
    item["relevance_reason"] = "; ".join(parts) if parts else "Adjusted: no remaining configured keyword reason."
    return total


def has_high_signal(item: dict[str, Any]) -> bool:
    text = " ".join(str(x or "") for x in [
        item.get("title"),
        item.get("summary"),
        item.get("relevance_reason"),
        " ".join(item.get("matched_keywords") or []),
        " ".join(item.get("watchgraph_modules") or []),
    ]).lower()
    terms = [
        "actively exploited", "exploited in the wild", "cisa kev", "zero-day", "zero day",
        "emergency patch", "market halted", "trading suspended", "state of emergency",
        "evacuation order", "central bank emergency", "rate decision", "pipeline outage",
        "port closure", "export ban",
    ]
    return any(term in text for term in terms)


def classify_source_bias(item: dict[str, Any]) -> str:
    host = host_of(str(item.get("url") or ""))
    source = str(item.get("source") or "").lower()
    stype = str(item.get("source_type") or "").lower()

    if "snyk.io" in host or "snyk" in source or "portswigger.net" in host or "portswigger" in source:
        return "vendor_self_feed"
    if stype == "github_search":
        return "single_platform_github"
    if "electionbettingodds.com" in host or "kalshi" in source or "polymarket" in source:
        return "market_odds_proxy"
    if "gdeltproject.org" in host or "gdelt" in source:
        return "broad_media_sensor"
    if any(x in host for x in ["federalreserve.gov", "ecb.europa.eu", "bis.org", "oecd.org"]):
        return "institutional_macro"
    return "normal"


def apply_caps(item: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    score = int(item.get("relevance_score") or 0)
    bias = classify_source_bias(item)
    high = has_high_signal(item)
    item["source_bias_class"] = bias

    if bias == "vendor_self_feed" and not high:
        cap = 9
        if score > cap:
            item["relevance_score"] = cap
            notes.append(f"vendor/self feed capped to {cap} unless independently high-signal")
    elif bias == "single_platform_github" and not high:
        cap = 10
        if score > cap:
            item["relevance_score"] = cap
            notes.append(f"single-platform GitHub signal capped to {cap} without independent resonance")
    elif bias == "market_odds_proxy" and not high:
        cap = 10
        if score > cap:
            item["relevance_score"] = cap
            notes.append(f"odds proxy capped to {cap} without external confirmation")

    if notes:
        reason = str(item.get("relevance_reason") or "")
        item["relevance_reason"] = (reason + "; " if reason else "") + "; ".join(f"debias: {n}" for n in notes)
    return notes


def fix_public_health_who_false_positive(item: dict[str, Any]) -> None:
    source = str(item.get("source") or "").lower()
    title = str(item.get("title") or "").lower()
    reasons = item.get("watchgraph_reasons") or []
    modules = item.get("watchgraph_modules") or []

    if "election" not in source and "election" not in title:
        return
    if "public_health_biosecurity" not in modules:
        return
    if not any(str(r).strip().lower() == "public_health_biosecurity: who" for r in reasons):
        return

    item["watchgraph_modules"] = [m for m in modules if m != "public_health_biosecurity"]
    item["watchgraph_reasons"] = [r for r in reasons if str(r).strip().lower() != "public_health_biosecurity: who"]
    ctx = item.get("market_context") or []
    health_tickers = {"PFE", "MRNA", "BNTX", "GSK", "AZN", "TMO", "DHR"}
    item["market_context"] = [x for x in ctx if str(x) not in health_tickers]
    item["relevance_score"] = max(0, int(item.get("relevance_score") or 0) - 3)
    item["relevance_reason"] = str(item.get("relevance_reason") or "") + "; debias: removed public_health_biosecurity false positive from 'Who will win'"


def debias_item(item: dict[str, Any]) -> dict[str, Any]:
    adjusted = dict(item)

    if not is_github_item(adjusted) and "GitHub" in [str(x) for x in adjusted.get("matched_keywords") or []]:
        removed = subtract_reason_segment(adjusted, "GitHub")
        remove_keyword(adjusted, "GitHub")
        if removed:
            adjusted["relevance_score"] = max(0, int(adjusted.get("relevance_score") or 0) - int(round(removed)))
        adjusted["relevance_reason"] = str(adjusted.get("relevance_reason") or "") + "; debias: removed false GitHub keyword match on non-GitHub source"

    fix_public_health_who_false_positive(adjusted)
    apply_caps(adjusted)
    return adjusted


def sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda x: (
            int(x.get("relevance_score") or 0),
            str(x.get("published_at") or ""),
            str(x.get("title") or ""),
        ),
        reverse=True,
    )


def rebuild_sections(latest: dict[str, Any]) -> None:
    findings = [x for x in latest.get("findings", []) if isinstance(x, dict)]
    high = [x for x in findings if int(x.get("relevance_score") or 0) >= 24]
    medium = [x for x in findings if 12 <= int(x.get("relevance_score") or 0) < 24]
    observe = [x for x in findings if 1 <= int(x.get("relevance_score") or 0) < 12]
    latest["sections"] = {"high": sort_items(high), "medium": sort_items(medium), "observe": sort_items(observe)}
    latest["findings"] = sort_items(findings)
    latest.setdefault("counts", {})
    latest["counts"]["high"] = len(high)
    latest["counts"]["medium"] = len(medium)
    latest["counts"]["observe"] = len(observe)
    latest["counts"]["new_relevant_findings"] = len(findings)


def main() -> int:
    latest_path = BRIEFINGS / "latest.json"
    latest = read_json(latest_path, {})
    if not isinstance(latest, dict):
        print("No latest.json to debias.")
        return 0

    findings = latest.get("findings")
    if not isinstance(findings, list):
        print("No findings to debias.")
        return 0

    latest["findings"] = [debias_item(item) if isinstance(item, dict) else item for item in findings]
    rebuild_sections(latest)
    latest["score_debias"] = {
        "schema_version": 1,
        "enabled": True,
        "principles": [
            "literal keyword false positives are removed",
            "single-source vendor feeds are capped unless high-signal",
            "single-platform GitHub repo findings remain visible but cannot dominate world/policy ranking alone",
            "odds proxies are capped without external confirmation",
        ],
    }
    write_json(latest_path, latest)
    print(f"Debiased {len(latest['findings'])} findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
