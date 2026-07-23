#!/usr/bin/env python3
"""Aggregate monetary evidence into economic event outcomes.

Evidence is read from data/economic_evidence.jsonl. Each line must contain:
event_id, observed_at, component, gross_usd, attribution_probability,
overlap_group, source_url. net_usd is optional.

Deduplication rule:
- evidence in the same (event_id, overlap_group, component) bucket is not summed;
- the largest causally attributed gross magnitude is retained;
- net follows the retained gross record;
- different components and overlap groups are additive.

The script updates data/economic_events.jsonl in place and writes
briefings/economic_outcomes.json and briefings/economic_outcomes.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "economic_events.jsonl"
DEFAULT_EVIDENCE = ROOT / "data" / "economic_evidence.jsonl"
DEFAULT_JSON = ROOT / "briefings" / "economic_outcomes.json"
DEFAULT_MD = ROOT / "briefings" / "economic_outcomes.md"
DEFAULT_CONFIG = ROOT / "config" / "economic_weight.yaml"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def validate(evidence: dict[str, Any]) -> None:
    required = (
        "event_id",
        "observed_at",
        "component",
        "gross_usd",
        "attribution_probability",
        "overlap_group",
        "source_url",
    )
    missing = [key for key in required if key not in evidence]
    if missing:
        raise ValueError(f"missing fields: {missing}")
    if float(evidence["gross_usd"]) < 0:
        raise ValueError("gross_usd must be >= 0")
    probability = float(evidence["attribution_probability"])
    if not 0 <= probability <= 1:
        raise ValueError("attribution_probability must be in [0,1]")


def attributed(evidence: dict[str, Any]) -> tuple[float, float | None]:
    probability = float(evidence["attribution_probability"])
    gross = float(evidence["gross_usd"]) * probability
    net = (
        None
        if evidence.get("net_usd") is None
        else float(evidence["net_usd"]) * probability
    )
    return gross, net


def aggregate_event(evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[
        tuple[str, str],
        tuple[float, float | None, dict[str, Any]],
    ] = {}

    for evidence in evidence_rows:
        validate(evidence)
        gross, net = attributed(evidence)
        key = (str(evidence["overlap_group"]), str(evidence["component"]))
        current = buckets.get(key)
        if current is None or gross > current[0]:
            buckets[key] = (gross, net, evidence)

    gross_total = sum(value[0] for value in buckets.values())
    nets = [value[1] for value in buckets.values() if value[1] is not None]
    net_total = sum(nets) if nets else None
    last_material_delta = max(
        (str(value[2]["observed_at"]) for value in buckets.values()),
        default=None,
    )

    return {
        "gross_attributed_usd": round(gross_total, 2),
        "net_attributed_usd": None if net_total is None else round(net_total, 2),
        "last_material_delta_at": last_material_delta,
        "deduplicated_buckets": len(buckets),
        "evidence_count": len(evidence_rows),
    }


def stagnation_reached(
    record: dict[str, Any],
    config: dict[str, Any],
    current_time: datetime,
) -> bool:
    last = record.get("outcome", {}).get("last_material_delta_at")
    if not last:
        return False

    stagnation = config.get("stagnation", {})
    rule = stagnation.get("default", {})
    overrides = stagnation.get("event_overrides", {})
    for event_class in record.get("features", {}).get("event_classes", []):
        if event_class in overrides:
            rule = overrides[event_class]
            break

    window_days = int(rule.get("rolling_window_days", 30))
    consecutive_windows = int(rule.get("consecutive_windows", 3))
    last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    return (current_time - last_dt).days >= window_days * consecutive_windows


def money(value: float | None) -> str:
    if value is None:
        return "—"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= divisor:
            return f"${value / divisor:.2f}{suffix}"
    return f"${value:,.0f}"


def write_reports(
    json_path: Path,
    md_path: Path,
    rows: list[dict[str, Any]],
) -> None:
    generated_at = now()
    payload = {
        "version": 1,
        "generated_at": generated_at,
        "events": sorted(
            rows,
            key=lambda row: row["gross_attributed_usd"] or 0,
            reverse=True,
        ),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Economic Outcomes",
        "",
        f"Generated: `{generated_at}`",
        "",
        "| Event | Gross attributed | Net attributed | Evidence | Buckets | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in payload["events"][:25]:
        title = str(row["title"]).replace("|", r"\|")
        lines.append(
            f"| {title} | {money(row['gross_attributed_usd'])} | "
            f"{money(row['net_attributed_usd'])} | {row['evidence_count']} | "
            f"{row['deduplicated_buckets']} | {row['status']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-report", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    records = read_jsonl(args.ledger)
    evidence_rows = read_jsonl(args.evidence)

    by_event: dict[str, list[dict[str, Any]]] = {}
    for evidence in evidence_rows:
        validate(evidence)
        by_event.setdefault(str(evidence["event_id"]), []).append(evidence)

    current_time = datetime.now(timezone.utc)
    report_rows: list[dict[str, Any]] = []

    for record in records:
        event_evidence = by_event.get(record["event_id"], [])
        record["monetary_evidence"] = event_evidence
        outcome = record.setdefault("outcome", {})
        outcome.update(aggregate_event(event_evidence))
        outcome["stagnation_reached"] = stagnation_reached(
            record,
            config,
            current_time,
        )
        if outcome["stagnation_reached"]:
            record["status"] = "stagnant"

        report_rows.append(
            {
                "event_id": record["event_id"],
                "title": record.get("title", ""),
                **outcome,
                "status": record.get("status"),
            }
        )

    write_jsonl(args.ledger, records)
    write_reports(args.json_report, args.md_report, report_rows)
    print(
        f"Updated outcomes for {len(records)} events using "
        f"{len(evidence_rows)} evidence rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
