#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BRIEFINGS_DIR = ROOT / "briefings"

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

DEFAULT_MAX_AGE_DAYS = 120
MAX_AGE_BY_SOURCE_CLASS = {
    # institutional reports can be slower, but not year-old top hits
    "agriculture_food_security": 120,
    "humanitarian_agency": 120,
    "humanitarian_official_aggregator": 120,
    "rainforest_south_america": 180,
    "medical_research_breakthroughs": 365,
    "medical_approvals_research": 365,
}
ALLOW_ARCHIVE_ROLES = {"archive", "reference", "historical_reference", "long_tail_research"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "unknown", "unbekannt"}:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def dates_from_text(text: str) -> list[datetime]:
    s = text or ""
    out: list[datetime] = []

    # /2025/06/... or -2025-06-13
    for y, m, d in re.findall(r"(?<!\d)(20\d{2})[/-](0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])(?!\d)", s):
        try:
            out.append(datetime(int(y), int(m), int(d), tzinfo=timezone.utc))
        except ValueError:
            pass

    # june-13-2025, june 13 2025
    month_re = "|".join(sorted(MONTHS, key=len, reverse=True))
    for mon, d, y in re.findall(rf"\b({month_re})[-\s_]+0?[1-9]|[12]\d|3[01](?:st|nd|rd|th)?[-\s,_]+(20\d{2})\b", s, flags=re.I):
        try:
            out.append(datetime(int(y), MONTHS[mon.lower()], int(d), tzinfo=timezone.utc))
        except ValueError:
            pass

    # 13-june-2025, 13 june 2025
    for d, mon, y in re.findall(rf"\b(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?[-\s_]+({month_re})[-\s,_]+(20\d{2})\b", s, flags=re.I):
        try:
            out.append(datetime(int(y), MONTHS[mon.lower()], int(d), tzinfo=timezone.utc))
        except ValueError:
            pass

    return out


def evidence_date(item: dict[str, Any]) -> tuple[datetime | None, str]:
    published = parse_dt(item.get("published_at"))
    if published:
        return published, "published_at"

    text = " ".join(str(item.get(k) or "") for k in ("url", "title", "summary"))
    candidates = dates_from_text(text)
    if candidates:
        # Prefer the most recent explicit date found in the item text/URL.
        return max(candidates), "explicit_date_in_url_or_text"

    return None, "unknown"


def max_age_days(item: dict[str, Any]) -> int:
    source_class = str(item.get("source_class") or item.get("class") or "").strip()
    source_role = str(item.get("source_role") or "").strip().lower()
    if source_role in ALLOW_ARCHIVE_ROLES or item.get("allow_stale") is True:
        return 10_000
    return int(MAX_AGE_BY_SOURCE_CLASS.get(source_class, DEFAULT_MAX_AGE_DAYS))


def is_stale(item: dict[str, Any], now: datetime) -> tuple[bool, str]:
    dt, basis = evidence_date(item)
    if not dt:
        return False, "no_date_available"
    age_days = (now - dt).total_seconds() / 86400
    if age_days < -2:
        return True, f"future_date_suspicious:{basis}:{dt.date()}"
    limit = max_age_days(item)
    if age_days > limit:
        return True, f"stale:{basis}:{dt.date()}:age_days={age_days:.1f}:limit={limit}"
    return False, f"fresh_enough:{basis}:{dt.date()}:age_days={age_days:.1f}:limit={limit}"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def filter_itemsitems: list[dict[str, Any]], now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept, removed = [], []
    for item in items:
        if not isinstance(item, dict):
            continue
        stale, reason = is_stale(item, now)
        if stale:
            clone = dict(item)
            clone["stale_filter_reason"] = reason
            removed.append(clone)
        else:
            kept.append(item)
    return kept, removed


def rewrite_latest_json(now: datetime, removed_acc: list[dict[str, Any]]) -> None:
    path = BRIEFINGS_DIR / "latest.json"
    payload = load_json(path, {})
    if not isinstance(payload, dict):
        return

    for section in ("high", "medium", "observe"):
        items = payload.get("sections", {}).get(section)
        if isinstance(items, list):
            kept, removed = filter_items(items, now)
            payload["sections"][section] = kept
            removed_acc.extend(removed)

    findings = payload.get("findings")
    if isinstance(findings, list):
        kept, removed = filter_items(findings, now)
        payload["findings"] = kept
        removed_acc.extend(removed)

    counts = payload.setdefault("counts", {})
    if isinstance(counts, dict):
        counts["stale_removed"] = len(removed_acc)
        sections = payload.get("sections", {})
        if isinstance(sections, dict):
            counts["high"] = len(sections.get("high") or [])
            counts["medium"] = len(sections.get("medium") or [])
            counts["observe"] = len(sections.get("observe") or [])
        counts["new_relevant_findings"] = len(payload.get("findings") or [])
    write_json(path, payload)


def rewrite_today_findings(now: datetime, removed_acc: list[dict[str, Any]]) -> None:
    date_dir = DATA_DIR / now.strftime("%Y-%m-%d")
    path = date_dir / "findings.json"
    items = load_json(path, [])
    if not isinstance(items, list):
        return
    kept, removed = filter_items([x for x in items if isinstance(x, dict)], now)
    removed_acc.extend(removed)
    write_json(path, kept)


def main() -> int:
    now = utcnow()
    removed: list[dict[str, Any]] = []
    rewrite_today_findings(now, removed)
    rewrite_latest_json(now, removed)

    audit = {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "doc_type": "senna.stale_filter",
        "default_max_age_days": DEFAULT_MAX_AGE_DAYS,
        "removed_count": len(removed),
        "removed": removed[:200],
    }
    write_json(BRIEFINGS_DIR / "stale_filter.json", audit)
    if removed:
        print(f"Stale filter removed {len(removed)} item(s).")
        for item in removed[:20]:
            print(f"- {item.get('title')} :: {item.get('stale_filter_reason')} :: {item.get('url')}")
    else:
        print("Stale filter removed no items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
