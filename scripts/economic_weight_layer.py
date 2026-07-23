#!/usr/bin/env python3
"""Shadow learning layer for lifetime monetary event weight.

The script intentionally does not alter the existing resonance ranking.
It reads current event clusters, creates/updates durable economic event
records, preserves forecasts made at first sight, and writes an audit report.

Inputs:
    briefings/daily.json
    config/economic_weight.yaml

Outputs:
    data/economic_events.jsonl
    briefings/economic_weight.json
    briefings/economic_weight.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "briefings" / "daily.json"
DEFAULT_CONFIG = ROOT / "config" / "economic_weight.yaml"
DEFAULT_LEDGER = ROOT / "data" / "economic_events.jsonl"
DEFAULT_JSON_REPORT = ROOT / "briefings" / "economic_weight.json"
DEFAULT_MD_REPORT = ROOT / "briefings" / "economic_weight.md"


EVENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("vulnerability", ("cve-", "vulnerability", "security advisory", "schwachstelle")),
    ("exploit", ("actively exploited", "exploitation", "zero-day", "0-day", "ransomware")),
    ("outage", ("outage", "downtime", "service disruption", "ausfall")),
    ("regulation", ("regulation", "directive", "law", "act", "policy", "verordnung", "gesetz")),
    ("acquisition", ("acquisition", "acquire", "merger", "übernahme")),
    ("funding", ("funding", "series a", "series b", "investment round", "finanzierungsrunde")),
    ("natural_disaster", ("earthquake", "tsunami", "flood", "wildfire", "erdbeben", "überschwemmung")),
    ("conflict", ("war", "missile", "invasion", "sanctions", "krieg", "sanktionen")),
    ("platform_change", ("api change", "terms of service", "platform policy", "deprecation")),
    ("product_release", ("release", "launch", "announces", "introduced", "veröffentlicht")),
    ("research", ("study", "research", "paper", "benchmark", "studie")),
]

CHANNEL_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("production", ("factory", "manufacturing", "production", "plant", "fabrik")),
    ("revenue", ("revenue", "sales", "customers", "umsatz")),
    ("market_valuation", ("shares", "stock", "market cap", "valuation", "aktie", "bewertung")),
    ("credit", ("bond", "credit", "debt", "loan", "anleihe", "kredit")),
    ("insurance", ("insurance", "insured", "claims", "versicherung")),
    ("compliance", ("compliance", "regulation", "audit", "penalty", "bußgeld")),
    ("infrastructure", ("infrastructure", "grid", "port", "datacenter", "cable", "netz", "hafen")),
    ("labor", ("workers", "employees", "layoffs", "arbeitsplätze", "beschäftigte")),
    ("trade", ("trade", "export", "import", "tariff", "handel", "zoll")),
    ("public_budget", ("government spending", "public budget", "subsidy", "staatshaushalt")),
    ("investment", ("investment", "funding", "capex", "venture", "investition")),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def canonical_text(cluster: dict[str, Any]) -> str:
    parts: list[str] = [str(cluster.get("title", "")), str(cluster.get("key", ""))]
    parts.extend(str(x) for x in cluster.get("watchgraph_modules", []) or [])
    parts.extend(str(x) for x in cluster.get("sources", []) or [])
    return " ".join(parts).lower()


def classify(text: str, patterns: Iterable[tuple[str, tuple[str, ...]]], fallback: str) -> list[str]:
    found = [name for name, terms in patterns if any(term in text for term in terms)]
    return found or [fallback]


def stable_event_id(cluster: dict[str, Any]) -> str:
    raw_key = str(cluster.get("key") or "").strip()
    urls = sorted(str(x).strip() for x in cluster.get("urls", []) or [] if str(x).strip())
    identity = raw_key or "|".join(urls) or str(cluster.get("title", "unknown"))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"evt_{digest}"


def confidence_from_cluster(cluster: dict[str, Any]) -> float:
    independent_hint = len(set(cluster.get("sources", []) or []))
    credibility = float(cluster.get("credibility_total", 0.0) or 0.0)
    confirmed = bool(cluster.get("cross_source_confirmed", False))
    confidence = 0.18 + min(independent_hint, 5) * 0.08 + min(credibility, 5.0) * 0.05
    if confirmed:
        confidence += 0.18
    return round(max(0.05, min(confidence, 0.95)), 3)


def prior_for(event_classes: list[str], config: dict[str, Any]) -> dict[str, float]:
    priors = config.get("priors", {})
    selected = dict(priors.get("default", {"p10": 1e5, "p50": 1e7, "p90": 1e9}))
    by_class = priors.get("by_event_class", {})
    candidates = [by_class[c] for c in event_classes if c in by_class]
    if candidates:
        # For multi-class events, use the largest median prior. This is a
        # conservative shadow forecast and remains visible for later auditing.
        selected = max(candidates, key=lambda item: float(item.get("p50", 0)))
    return {k: float(selected[k]) for k in ("p10", "p50", "p90")}


def signal_multiplier(cluster: dict[str, Any]) -> float:
    """Small bounded adjustment from already observed propagation signals.

    Existing scores are not treated as truth. They only adjust the broad prior
    within a deliberately narrow range so the ledger can later test whether
    those signals were actually predictive.
    """
    source_count = max(1, len(set(cluster.get("sources", []) or [])))
    momentum = max(0.0, float(cluster.get("momentum_delta", 0.0) or 0.0))
    score = max(0.0, float(cluster.get("max_score", 0.0) or 0.0))
    confirmed = 1.0 if cluster.get("cross_source_confirmed") else 0.0
    raw = 1.0 + min(source_count - 1, 4) * 0.08 + min(momentum, 5) * 0.04
    raw += min(score, 25) * 0.008 + confirmed * 0.12
    return round(min(raw, 1.85), 3)


def build_observation(cluster: dict[str, Any], config: dict[str, Any], observed_at: str) -> dict[str, Any]:
    text = canonical_text(cluster)
    event_classes = classify(text, EVENT_PATTERNS, "unknown")
    channels = classify(text, CHANNEL_PATTERNS, "unknown")
    prior = prior_for(event_classes, config)
    multiplier = signal_multiplier(cluster)
    forecast = {k: round(v * multiplier, 2) for k, v in prior.items()}
    return {
        "event_id": stable_event_id(cluster),
        "event_key": cluster.get("key"),
        "title": cluster.get("title", "Untitled event"),
        "first_seen_at": observed_at,
        "last_seen_at": observed_at,
        "status": "active",
        "features": {
            "event_classes": event_classes,
            "capital_channels": channels,
            "regions": [],
            "watchgraph_modules": cluster.get("watchgraph_modules", []) or [],
            "source_classes": cluster.get("source_classes", []) or [],
            "cross_source_confirmed": bool(cluster.get("cross_source_confirmed", False)),
        },
        "initial_signal": {
            "source_count": len(set(cluster.get("sources", []) or [])),
            "finding_count": int(cluster.get("finding_count", 0) or 0),
            "max_score": float(cluster.get("max_score", 0.0) or 0.0),
            "network_score": float(cluster.get("network_score", 0.0) or 0.0),
            "momentum_delta": float(cluster.get("momentum_delta", 0.0) or 0.0),
        },
        "forecast": {
            "lifetime_monetary_weight_usd": forecast,
            "ranking_log10_p50": round(math.log10(max(1.0, forecast["p50"])), 4),
            "confidence": confidence_from_cluster(cluster),
            "method": "class_prior_x_bounded_signal_multiplier_v1",
        },
        "observations": [{
            "observed_at": observed_at,
            "source_count": len(set(cluster.get("sources", []) or [])),
            "finding_count": int(cluster.get("finding_count", 0) or 0),
            "momentum_delta": float(cluster.get("momentum_delta", 0.0) or 0.0),
            "network_score": float(cluster.get("network_score", 0.0) or 0.0),
        }],
        "monetary_evidence": [],
        "outcome": {
            "gross_attributed_usd": None,
            "net_attributed_usd": None,
            "stagnation_reached": False,
            "last_material_delta_at": None,
        },
    }


def read_ledger(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[record["event_id"]] = record
    return records


def update_record(record: dict[str, Any], cluster: dict[str, Any], observed_at: str) -> None:
    record["last_seen_at"] = observed_at
    record["status"] = "active"
    observation = {
        "observed_at": observed_at,
        "source_count": len(set(cluster.get("sources", []) or [])),
        "finding_count": int(cluster.get("finding_count", 0) or 0),
        "momentum_delta": float(cluster.get("momentum_delta", 0.0) or 0.0),
        "network_score": float(cluster.get("network_score", 0.0) or 0.0),
    }
    observations = record.setdefault("observations", [])
    if not observations or observations[-1] != observation:
        observations.append(observation)


def write_ledger(path: Path, records: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(records[k], ensure_ascii=False, sort_keys=True) for k in sorted(records)]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def report_rows(records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records.values():
        forecast = record["forecast"]
        rows.append({
            "event_id": record["event_id"],
            "title": record["title"],
            "event_classes": record["features"]["event_classes"],
            "capital_channels": record["features"]["capital_channels"],
            "p10_usd": forecast["lifetime_monetary_weight_usd"]["p10"],
            "p50_usd": forecast["lifetime_monetary_weight_usd"]["p50"],
            "p90_usd": forecast["lifetime_monetary_weight_usd"]["p90"],
            "confidence": forecast["confidence"],
            "first_seen_at": record["first_seen_at"],
            "last_seen_at": record["last_seen_at"],
            "status": record["status"],
        })
    return sorted(rows, key=lambda row: row["p50_usd"], reverse=True)


def money(value: float) -> str:
    units = ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K"))
    for divisor, suffix in units:
        if abs(value) >= divisor:
            return f"${value / divisor:.2f}{suffix}"
    return f"${value:,.0f}"


def write_reports(json_path: Path, md_path: Path, rows: list[dict[str, Any]], generated_at: str) -> None:
    payload = {
        "version": 1,
        "generated_at": generated_at,
        "mode": "shadow",
        "target": "deduplicated_causally_attributable_lifetime_monetary_weight_usd",
        "events": rows,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Economic Weight Shadow Report",
        "",
        f"Generated: `{generated_at}`",
        "",
        "> Forecasts are broad priors for calibration. They do not change the live ranking.",
        "",
        "| Event | Class | P10 | P50 | P90 | Confidence |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows[:25]:
        title = re.sub(r"\s+", " ", row["title"]).replace("|", r"\|")
        classes = ", ".join(row["event_classes"])
        lines.append(
            f"| {title} | {classes} | {money(row['p10_usd'])} | "
            f"{money(row['p50_usd'])} | {money(row['p90_usd'])} | "
            f"{row['confidence']:.2f} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- P50 is the current median forecast of total lifetime monetary weight.",
        "- P10/P90 expose uncertainty; wide ranges are intentional at this stage.",
        "- The ledger preserves the first forecast so later outcomes can audit it.",
        "- Monetary evidence and causal attribution remain explicit, manual/derived fields.",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--md-report", type=Path, default=DEFAULT_MD_REPORT)
    args = parser.parse_args()

    config = load_yaml(args.config)
    payload = load_json(args.input)
    clusters = payload.get("current_clusters", [])
    observed_at = payload.get("generated_at") or utc_now()
    records = read_ledger(args.ledger)

    seen_ids: set[str] = set()
    for cluster in clusters:
        event_id = stable_event_id(cluster)
        seen_ids.add(event_id)
        if event_id in records:
            update_record(records[event_id], cluster, observed_at)
        else:
            records[event_id] = build_observation(cluster, config, observed_at)

    for event_id, record in records.items():
        if event_id not in seen_ids and record.get("status") == "active":
            record["status"] = "dormant"

    write_ledger(args.ledger, records)
    rows = report_rows(records)
    write_reports(args.json_report, args.md_report, rows, utc_now())
    print(f"Economic weight layer: {len(seen_ids)} current, {len(records)} total events.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
