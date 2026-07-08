#!/usr/bin/env python3
"""Senna intelligence layer.

Turns the current feed/network state into a compact, model-readable comparative
memory layer: dynamics, anomaly hints, early-signal language, and handoff files.

This is not private memory and not hidden collection. It is repo-local analytical
memory derived only from generated public-source briefings and state files.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
MEMORY = ROOT / "memory"
DOCS = ROOT / "docs"
STATE = ROOT / "state"
DATA = ROOT / "data"


TOPIC_RULES: dict[str, list[str]] = {
    "axiom": ["axi0m", "user yps", "question86", "senna-inflow"],
    "ai": ["ai", "ki", "artificial intelligence", "llm", "model", "agent", "openai", "anthropic", "mcp", "codex"],
    "security": ["security", "cyber", "cve", "vulnerability", "schwachstelle", "exploit", "zero-day", "ransomware", "patch"],
    "github_dev": ["github", "repository", "repo", "open source", "developer", "copilot", "actions", "codeql"],
    "macro": ["inflation", "central bank", "rate", "fed", "ecb", "bis", "yield", "bond", "market"],
    "geopolitics": ["war", "election", "sanction", "government", "policy", "nato", "eu", "protest", "strike"],
    "infrastructure": ["blackout", "outage", "supply chain", "port closure", "pipeline", "rail", "shipping", "energy"],
    "climate_disaster": ["earthquake", "flood", "wildfire", "storm", "drought", "heatwave", "volcano", "tsunami"],
}

HIGH_SIGNAL_TERMS = [
    "actively exploited", "active exploitation", "ausgenutzt", "aktive angriffe",
    "zero-day", "0-day", "emergency", "critical", "kritisch", "ransomware",
    "market halted", "trading suspended", "state of emergency", "evacuation order",
    "pipeline outage", "port closure", "supply chain",
]

EARLY_SIGNAL_TERMS = [
    "outage", "blackout", "port closure", "strike", "protest", "pipeline outage",
    "supply chain", "shortage", "evacuation", "unrest", "wildfire", "flood",
    "drought", "earthquake", "local", "regional",
]

ID4TITY_TERMS = ["axi0m", "user yps", "question86", "senna-inflow"]


def utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def clip.value: Any, limit: int = 260) -> str:
