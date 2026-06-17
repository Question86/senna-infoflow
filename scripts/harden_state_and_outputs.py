#!/usr/bin/env python3
"""State and output hygiene for senna-infoflow.

Post-monitor layer:
- prune unbounded state/seen.json
- preserve source errors across runs in state/source_errors.jsonl
- validate expected output documents
- write briefings/health.{json,md}

The goal is less silent rot, not more noise.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
STATE = ROOT / "state"
REPORTS = ROOT / "reports"

DEFAULT_SEEN_RETENTION_DAYS = 90
DEFAULT_SEEN_MAX_ITEMS = 50000
SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        if not text:
            return None
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_seen() -> dict[str, Any]:
    state = read_json(STATE / "seen.json", {"version": 1, "items": {}})
    if isinstance(state, list):
        return {"version": 1, "items": {str(item): {"first_seen_at": None} for item in state}}
    if not isinstance(state, dict):
        return {"version": 1, "items": {}}
    if not isinstance(state.get("items"), dict):
        state["items"] = {}
    state.setdefault("version", 1)
    return state


def prune_seen(now: datetime) -> dict[str, Any]:
    retention_days = int(os.getenv("SENNA_SEEN_RETENTION_DAYS", DEFAULT_SEEN_RETENTION_DAYS))
    max_items = int(os.getenv("SENNA_SEEN_MAX_ITEMS", DEFAULT_SEEN_MAX_ITEMS))
    cutoff = now - timedelta(days=retention_days)

    state = load_seen()
    original_items = state.get("items") or {}
    kept: dict[str, Any] = {}
    removed_expired = 0
    malformed = 0

    sortable: list[tuple[datetime, str, dict[str, Any]]] = []
    for item_id, raw_entry in original_items.items():
        if not isinstance(raw_entry, dict):
            malformed += 1
            continue
        last_seen = parse_dt(raw_entry.get("last_seen_at") or raw_entry.get("first_seen_at"))
        if last_seen is None:
            last_seen = datetime(1970, 1, 1, tzinfo=timezone.utc)
        if last_seen < cutoff:
            removed_expired += 1
            continue
        sortable.append((last_seen, str(item_id), raw_entry))

    sortable.sort(key=lambda x: (x[0], x[1]), reverse=True)
    removed_overflow = max(0, len(sortable) - max_items)
    for _last_seen, item_id, entry in sortable[:max_items]:
        kept[item_id] = entry

    state["items"] = kept
    state["last_pruned_at"] = iso(now)
    state["retention_days"] = retention_days
    state["max_items"] = max_items
    atomic_write_json(STATE / "seen.json", state)

    return {
        "seen_original": len(original_items),
        "seen_kept": len(kept),
        "seen_removed_expired": removed_expired,
        "seen_removed_overflow": removed_overflow,
        "seen_malformed_removed": malformed,
        "retention_days": retention_days,
        "max_items": max_items,
    }


def append_source_errors(now: datetime, latest: dict[str, Any]) -> int:
    errors = latest.get("source_errors") if isinstance(latest, dict) else []
    if not isinstance(errors, list) or not errors:
        return 0

    path = STATE / "source_errors.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[str] = []
    run_generated_at = str(latest.get("generated_at") or iso(now))
    for error in errors:
        if not isinstance(error, dict):
            continue
        row = {
            "recorded_at": iso(now),
            "run_generated_at": run_generated_at,
            "source_id": error.get("source_id"),
            "source_name": error.get("source_name"),
            "source_type": error.get("source_type"),
            "error": error.get("error"),
        }
        rows.append(json.dumps(row, ensure_ascii=False, sort_keys=True))

    if rows:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")
    return len(rows)


def validate_outputs(latest: Any, network: Any, trends: Any, latest_atom: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def issue(severity: str, code: str, message: str) -> None:
        issues.append({"severity": severity, "code": code, "message": message})

    if not isinstance(latest, dict):
        issue("critical", "latest_json_missing", "briefings/latest.json is missing or invalid.")
    else:
        for key in ("generated_at", "counts", "sections", "findings", "source_errors"):
            if key not in latest:
                issue("warning", "latest_json_field_missing", f"latest.json missing field: {key}")
        counts = latest.get("counts") or {}
        if isinstance(counts, dict) and counts.get("source_errors", 0):
            issue("warning", "source_errors_present", f"{counts.get('source_errors')} source error(s) in latest run.")

    if not isinstance(network, dict):
        issue("warning", "network_json_missing", "briefings/network.json is missing or invalid.")
    elif "clusters" not in network and "counts" not in network:
        issue("warning", "network_schema_weak", "network.json has neither clusters nor counts.")

    if not isinstance(trends, dict):
        issue("warning", "trends_json_missing", "briefings/trends.json is missing or invalid.")
    elif "ranked_topics" not in trends:
        issue("warning", "trends_ranked_topics_missing", "trends.json missing ranked_topics.")

    if not latest_atom.strip():
        issue("warning", "latest_atom_missing", "reports/latest_atom.md is missing or empty.")
    else:
        for section in ("## IDENTITY", "## CANONICAL_REFS", "## FINDING_ATOMS", "## TOPIC_SAMPLES"):
            if section not in latest_atom:
                issue("warning", "atom_section_missing", f"latest_atom.md missing section: {section}")

    return issues


def write_health(now: datetime, prune_stats: dict[str, Any], errors_appended: int, issues: list[dict[str, str]]) -> None:
    critical = sum(1 for item in issues if item.get("severity") == "critical")
    warnings = sum(1 for item in issues if item.get("severity") == "warning")
    status = "critical" if critical else "warning" if warnings else "ok"

    health = {
        "schema_version": SCHEMA_VERSION,
        "doc_type": "senna.pipeline_health",
        "generated_at": iso(now),
        "status": status,
        "counts": {
            "critical": critical,
            "warnings": warnings,
            "source_errors_appended": errors_appended,
        },
        "seen_state": prune_stats,
        "issues": issues,
    }
    atomic_write_json(STATE / "health.json", health)
    atomic_write_json(BRIEFINGS / "health.json", health)

    lines = [
        "# Senna Pipeline Health",
        "",
        f"_Generiert: {iso(now)}_",
        "",
        f"Status: `{status}`",
        "",
        "## State Hygiene",
        "",
        f"- seen original: `{prune_stats['seen_original']}`",
        f"- seen kept: `{prune_stats['seen_kept']}`",
        f"- removed expired: `{prune_stats['seen_removed_expired']}`",
        f"- removed overflow: `{prune_stats['seen_removed_overflow']}`",
        f"- malformed removed: `{prune_stats['seen_malformed_removed']}`",
        f"- retention days: `{prune_stats['retention_days']}`",
        "",
        "## Source Error Journal",
        "",
        f"- appended this run: `{errors_appended}`",
        "",
        "## Output Validation",
        "",
    ]

    if not issues:
        lines.append("- Keine Strukturprobleme erkannt.")
    else:
        for item in issues:
            lines.append(f"- **{item['severity']}** `{item['code']}` — {item['message']}")

    lines.extend(["", "---", "", "END OF DOCUMENT", ""])
    atomic_write_text(BRIEFINGS / "health.md", "\n".join(lines))


def main() -> int:
    now = utc_now()
    latest = read_json(BRIEFINGS / "latest.json", {})
    network = read_json(BRIEFINGS / "network.json", {})
    trends = read_json(BRIEFINGS / "trends.json", {})
    latest_atom_path = REPORTS / "latest_atom.md"
    latest_atom = latest_atom_path.read_text(encoding="utf-8") if latest_atom_path.exists() else ""

    prune_stats = prune_seen(now)
    errors_appended = append_source_errors(now, latest if isinstance(latest, dict) else {})
    issues = validate_outputs(latest, network, trends, latest_atom)
    write_health(now, prune_stats, errors_appended, issues)

    status = "critical" if any(i["severity"] == "critical" for i in issues) else "warning" if issues else "ok"
    print(
        "state/output hygiene complete: "
        f"status={status}, seen_kept={prune_stats['seen_kept']}, "
        f"errors_appended={errors_appended}, issues={len(issues)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
