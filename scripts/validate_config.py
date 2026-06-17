#!/usr/bin/env python3
"""Preflight validation for senna-infoflow configuration."""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
BRIEFINGS = ROOT / "briefings"
STATE = ROOT / "state"

IMPLEMENTED_TYPES = {"rss", "github_search", "reddit_json", "hackernews", "webpage_check", "manual_note"}
PLANNED_DISABLED_TYPES = {"gdelt_doc_api", "reliefweb_api", "json_api", "nvd_api", "firms_api", "fred_api", "socrata_api"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    return value if value is not None else default


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_json(path: Path, payload: Any):
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def add(issues, severity, code, message, source_id=None):
    item = {"severity": severity, "code": code, "message": message}
    if source_id:
        item["source_id"] = source_id
    issues.append(item)


def validate_url(value, issues, source_id):
    url = str(value or "").strip()
    if not url:
        add(issues, "error", "url_missing", "URL is required.", source_id)
        return
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        add(issues, "error", "url_bad_scheme", f"URL scheme must be http/https, got `{parsed.scheme or 'none'}`.", source_id)
        return
    if not parsed.netloc:
        add(issues, "error", "url_missing_host", "URL must include a hostname.", source_id)
        return
    if parsed.username or parsed.password:
        add(issues, "error", "url_credentials", "URL must not contain embedded credentials.", source_id)
    host = parsed.hostname or ""
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        add(issues, "error", "url_unsafe_ip", f"blocked unsafe IP literal: {ip}", source_id)


def validate_manual_path(value, issues, source_id):
    rel = str(value or "").strip()
    if not rel:
        add(issues, "error", "manual_path_missing", "manual_note source requires path.", source_id)
        return
    if rel.startswith("/") or re.match(r"^[a-zA-Z]:[\\/]", rel):
        add(issues, "error", "manual_path_absolute", "manual_note path must be relative to repository root.", source_id)
        return
    target = (ROOT / rel).resolve()
    if ROOT not in target.parents and target != ROOT:
        add(issues, "error", "manual_path_escape", "manual_note path escapes repository root.", source_id)


def validate_source(source, issues, seen_ids, index):
    if not isinstance(source, dict):
        add(issues, "error", "source_not_object", f"Source at index {index} is not an object.")
        return
    source_id = str(source.get("id") or "").strip()
    if not source_id:
        source_id = f"index:{index}"
        add(issues, "error", "source_id_missing", f"Source at index {index} has no id.", source_id)
    elif source_id in seen_ids:
        add(issues, "error", "source_id_duplicate", f"Duplicate source id `{source_id}`.", source_id)
    else:
        seen_ids.add(source_id)
    source_type = str(source.get("type") or "").strip()
    enabled = source.get("enabled", True) is not False
    if not source_type:
        add(issues, "error", "source_type_missing", "Source has no type.", source_id)
        return
    if enabled and source_type not in IMPLEMENTED_TYPES:
        add(issues, "error", "enabled_type_not_implemented", f"Enabled source type `{source_type}` has no implemented adapter.", source_id)
    elif (not enabled) and source_type not in IMPLEMENTED_TYPES and source_type not in PLANNED_DISABLED_TYPES:
        add(issues, "warning", "disabled_type_unknown", f"Disabled source type `{source_type}` is neither implemented nor known as planned.", source_id)
    if source.get("max_items") is not None:
        try:
            max_items = int(source.get("max_items"))
            if max_items < 1 or max_items > 100:
                add(issues, "warning", "source_max_items_suspicious", "max_items should usually be between 1 and 100.", source_id)
        except Exception:
            add(issues, "error", "source_max_items_invalid", "max_items must be an integer.", source_id)
    if source_type in {"rss", "webpage_check"}:
        validate_url(source.get("url"), issues, source_id)
    elif source_type == "github_search":
        mode = str(source.get("mode") or "issues").strip().lower()
        if mode not in {"issues", "repositories", "repos", "code"}:
            add(issues, "error", "github_mode_invalid", f"Unsupported github_search mode `{mode}`.", source_id)
        if not str(source.get("query") or "").strip():
            add(issues, "error", "github_query_missing", "github_search source requires query.", source_id)
    elif source_type == "reddit_json":
        if not str(source.get("subreddit") or "").strip():
            add(issues, "error", "reddit_subreddit_missing", "reddit_json source requires subreddit.", source_id)
    elif source_type == "hackernews":
        if not str(source.get("query") or "").strip():
            add(issues, "error", "hackernews_query_missing", "hackernews source requires query.", source_id)
    elif source_type == "manual_note":
        validate_manual_path(source.get("path"), issues, source_id)
    elif source.get("url"):
        validate_url(source.get("url"), issues, source_id)
    keywords = source.get("keywords")
    if keywords is not None:
        if not isinstance(keywords, list):
            add(issues, "error", "source_keywords_not_list", "keywords must be a list.", source_id)
        elif any(not str(x).strip() for x in keywords):
            add(issues, "warning", "source_keywords_blank", "keywords contains blank item(s).", source_id)


def validate_rules(rules, issues):
    if not isinstance(rules, dict):
        add(issues, "error", "rules_not_object", "config/rules.yaml must be an object.")
        return
    scoring = rules.get("scoring") or {}
    if not isinstance(scoring, dict):
        add(issues, "error", "scoring_not_object", "rules.scoring must be an object.")
        return
    try:
        high = int(scoring.get("high_threshold", 24))
        medium = int(scoring.get("medium_threshold", 12))
        observe = int(scoring.get("observe_threshold", 1))
        max_score = int(scoring.get("max_score", 100))
        if not (0 <= observe <= medium <= high <= max_score):
            add(issues, "error", "threshold_order_invalid", "Expected 0 <= observe_threshold <= medium_threshold <= high_threshold <= max_score.")
    except Exception:
        add(issues, "error", "threshold_invalid", "Scoring thresholds must be integers.")
    http = rules.get("http") or {}
    if isinstance(http, dict):
        try:
            timeout = int(http.get("timeout_seconds", 15))
            if timeout < 3 or timeout > 90:
                add(issues, "warning", "timeout_suspicious", "http.timeout_seconds should usually be between 3 and 90.")
        except Exception:
            add(issues, "error", "timeout_invalid", "http.timeout_seconds must be an integer.")


def validate_keywords(config, issues):
    if not isinstance(config, dict):
        add(issues, "error", "keywords_not_object", "config/keywords.yaml must be an object.")
        return
    keywords = config.get("keywords") or []
    if not isinstance(keywords, list):
        add(issues, "error", "keywords_not_list", "keywords must be a list.")
        return
    seen = set()
    for index, item in enumerate(keywords):
        if not isinstance(item, dict):
            add(issues, "error", "keyword_not_object", f"Keyword item at index {index} is not an object.")
            continue
        term = str(item.get("term") or "").strip()
        if not term:
            add(issues, "error", "keyword_term_missing", f"Keyword item at index {index} has no term.")
            continue
        key = term.casefold()
        if key in seen:
            add(issues, "warning", "keyword_duplicate", f"Duplicate keyword term `{term}`.")
        seen.add(key)
        try:
            weight = float(item.get("weight", 1))
            if weight <= 0 or weight > 50:
                add(issues, "warning", "keyword_weight_suspicious", f"Keyword `{term}` has suspicious weight {weight}.")
        except Exception:
            add(issues, "error", "keyword_weight_invalid", f"Keyword `{term}` has invalid weight.")


def write_report(issues, source_count):
    errors = sum(1 for x in issues if x["severity"] == "error")
    warnings = sum(1 for x in issues if x["severity"] == "warning")
    status = "error" if errors else "warning" if warnings else "ok"
    payload = {"schema_version": 1, "doc_type": "senna.config_validation", "generated_at": utc_now(), "status": status, "counts": {"sources": source_count, "errors": errors, "warnings": warnings}, "issues": issues}
    write_json(STATE / "config_validation.json", payload)
    write_json(BRIEFINGS / "config_validation.json", payload)
    lines = ["# Senna Config Validation", "", f"_Generated: {payload['generated_at']}_", "", f"Status: `{status}`", "", "## Counts", "", f"- sources: `{source_count}`", f"- errors: `{errors}`", f"- warnings: `{warnings}`", "", "## Issues", ""]
    if not issues:
        lines.append("- Keine Config-Probleme erkannt.")
    else:
        for issue in issues:
            sid = f" `{issue.get('source_id')}`" if issue.get("source_id") else ""
            lines.append(f"- **{issue['severity']}** `{issue['code']}`{sid} — {issue['message']}")
    lines.extend(["", "---", "", "END OF DOCUMENT", ""])
    atomic_write_text(BRIEFINGS / "config_validation.md", "\n".join(lines))


def main():
    sources_config = read_yaml(CONFIG / "sources.yaml", {})
    rules = read_yaml(CONFIG / "rules.yaml", {})
    keywords = read_yaml(CONFIG / "keywords.yaml", {})
    issues = []
    if not isinstance(sources_config, dict):
        add(issues, "error", "sources_not_object", "config/sources.yaml must be an object.")
        sources = []
    else:
        sources = sources_config.get("sources") or []
        if not isinstance(sources, list):
            add(issues, "error", "sources_not_list", "sources must be a list.")
            sources = []
    seen_ids = set()
    for index, source in enumerate(sources):
        validate_source(source, issues, seen_ids, index)
    validate_rules(rules, issues)
    validate_keywords(keywords, issues)
    write_report(issues, len(sources))
    errors = [x in issues if x["severity"] == "error"]
    errors = [x for x in issues if x["severity"] == "error"]
    if errors:
        print(f"Config validation failed with {len(errors)} error(s).")
        for item in errors[:20]:
            sid = f" [{item.get('source_id')}]" if item.get("source_id") else ""
            print(f"- {item['code']}{sid}: {item['message']}")
        return 2
    warnings = [x for x in issues if x["severity"] == "warning"]
    print(f"Config validation ok: sources={len(sources)}, warnings={len(warnings)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
