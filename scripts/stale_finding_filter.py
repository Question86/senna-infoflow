#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
STATE = ROOT / "state"

DEFAULT_MAX_AGE_DAYS = 45
ARCHIVE_MAX_SCORE = 2
STALE_DROP_SCORE = 0

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

DATE_KEYS = (
    "published_at",
    "published",
    "updated_at",
    "updated",
    "date",
    "created_at",
)

def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)

def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    Path(tmp).replace(path)

def parse_dt(value) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        dt = parsedate_to_datetime(str(value))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def date_from_text(text: str) -> datetime | None:
    text = unquote(str(text or ""))

    # URLs like /2025/06/food-security-update-june-13-2025/
    m = re.search(r"/(20\d{2})[/-](0?[1-9]|1[0-2])(?:[/-](0?[1-9]|[12]\d|3[01]))?/", text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass

    # Titles/slugs like June 13 2025 or june-13-2025
    m = re.search(
        r"\b("
        + "|".join(MONTHS.keys())
        + r")[\s_-]+(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?[\s,_-]+(20\d{2})\b",
        text,
        flags=re.I,
    )
    if m:
        month = MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3))
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass

    # ISO-ish fragments anywhere
    m = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            pass

    return None

def item_date(item: dict) -> tuple[datetime | None, str]:
    for key in DATE_KEYS:
        dt = parse_dt(item.get(key))
        if dt:
            return dt, key

    combined = " ".join(str(item.get(k) or "") for k in ("url", "title", "summary"))
    dt = date_from_text(combined)
    if dt:
        return dt, "extracted_from_url_or_text"

    return None, "missing"

def score(item: dict) -> int:
    try:
        return int(item.get("relevance_score") or 0)
    except Exception:
        return 0

def note(item: dict, msg: str) -> None:
    notes = item.setdefault("quality_notes", [])
    if msg not in notes:
        notes.append(msg)

def rebuild_sections(latest: dict) -> None:
    q = latest.get("quality_gate") or {}
    thresholds = (q.get("thresholds") or {}) if isinstance(q, dict) else {}
    high = int(thresholds.get("high", 24))
    medium = int(thresholds.get("medium", 14))
    observe = int(thresholds.get("observe", 3))

    findings = [f for f in latest.get("findings", []) if isinstance(f, dict)]
    findings.sort(key=lambda f: (score(f), str(f.get("published_at") or ""), str(f.get("title") or "")), reverse=True)

    latest["sections"] = {
        "high": [f for f in findings if score(f) >= high],
        "medium": [f for f in findings if medium <= score(f) < high],
        "observe": [f for f in findings if observe <= score(f) < medium],
    }
    latest.setdefault("counts", {}).update({
        "new_relevant_findings": len(findings),
        "today_file_total": len(findings),
        "high": len(latest["sections"]["high"]),
        "medium": len(latest["sections"]["medium"]),
        "observe": len(latest["sections"]["observe"]),
    })
    latest["findings"] = findings

def main() -> int:
    path = BRIEFINGS / "latest.json"
    if not path.exists():
        print("No briefings/latest.json found.")
        return 0

    latest = json.loads(path.read_text(encoding="utf-8"))
    ts = now_utc()
    max_age_days = int(((latest.get("quality_gate") or {}).get("freshness") or {}).get("max_age_days", DEFAULT_MAX_AGE_DAYS))

    kept = []
    stale = []

    for item in latest.get("findings", []):
        if not isinstance(item, dict):
            continue
        dt, source = item_date(item)
        item["freshness_date_source"] = source

        if not dt:
            # Unknown date should not be allowed to dominate the briefing.
            if score(item) > ARCHIVE_MAX_SCORE:
                old = score(item)
                item["relevance_score"] = ARCHIVE_MAX_SCORE
                note(item, f"freshness unknown; score capped from {old} to {ARCHIVE_MAX_SCORE}")
            kept.append(item)
            continue

        age_days = (ts - dt.astimezone(timezone.utc)).days
        item["freshness_age_days"] = age_days

        if age_days > max_age_days:
            old = score(item)
            item["stale"] = True
            item["relevance_score"] = min(old, STALE_DROP_SCORE)
            note(item, f"stale finding: age {age_days}d exceeds max_age_days={max_age_days}; score capped from {old} to {item['relevance_score']}")
            stale.append(item)
        else:
            kept.append(item)

    latest["findings"] = kept + stale
    latest["stale_filter"] = {
        "schema_version": 1,
        "generated_at": ts.isoformat().replace("+00:00", "Z"),
        "max_age_days": max_age_days,
        "stale_count": len(stale),
        "unknown_date_capped": sum(1 for f in latest["findings"] if "freshness unknown" in " ".join(f.get("quality_notes", []))),
        "policy": "Items older than max_age_days are retained for audit but demoted to score 0 so they cannot lead current briefings.",
    }

    rebuild_sections(latest)

    audit = {
        "schema_version": 1,
        "generated_at": ts.isoformat().replace("+00:00", "Z"),
        "max_age_days": max_age_days,
        "stale_count": len(stale),
        "stale": [
            {
                "title": f.get("title"),
                "url": f.get("url"),
                "source": f.get("source"),
                "freshness_age_days": f.get("freshness_age_days"),
                "freshness_date_source": f.get("freshness_date_source"),
                "relevance_score": f.get("relevance_score"),
            }
            for f in stale[:100]
        ],
    }

    atomic_json(path, latest)
    atomic_json(BRIEFINGS / "stale_audit.json", audit)
    atomic_json(STATE / "stale_audit.json", audit)
    print(f"stale filter complete: stale={len(stale)}, max_age_days={max_age_days}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
