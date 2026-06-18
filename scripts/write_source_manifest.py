#!/usr/bin/env python3
"""Write active source manifest after workflow overlays are merged."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
BRIEFINGS = ROOT / "briefings"


def read_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return default if data is None else data
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


def host(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower()
    except Exception:
        return ""


def infer_lane(source: dict[str, Any]) -> str:
    sid = str(source.get("id") or "").lower()
    sclass = str(source.get("source_class") or "").lower()
    name = str(source.get("name") or "").lower()
    url = str(source.get("url") or "").lower()

    if any(x in sid for x in ["fed_", "ecb_", "bis_", "oecd_", "gdelt_macro", "gdelt_politics"]) or sclass in {
        "central_bank",
        "central_bank_network",
        "policy_institution",
        "global_media_monitor",
    }:
        return "macro_policy"
    if any(x in sid for x in ["usgs", "gdacs", "geofon", "noaa", "reddit_", "telegram", "election", "prediction", "kalshi"]):
        return "hot"
    if "github" in sid or "github" in name or "github" in url:
        return "platform_dev"
    if any(x in url for x in ["snyk.io", "portswigger.net"]):
        return "vendor_security"
    return "base"


def main() -> int:
    cfg = read_yaml(CONFIG / "sources.yaml", {})
    sources = [s for s in cfg.get("sources", []) if isinstance(s, dict)]
    active = [s for s in sources if s.get("enabled", True) is not False]

    items = []
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    type_counts = Counter()
    lane_counts = Counter()

    for source in active:
        lane = infer_lane(source)
        stype = str(source.get("type") or "unknown")
        record = {
            "id": source.get("id"),
            "name": source.get("name") or source.get("id"),
            "type": stype,
            "lane": lane,
            "source_class": source.get("source_class") or source.get("class"),
            "host": host(str(source.get("url") or "")),
            "max_items": source.get("max_items"),
        }
        items.append(record)
        by_lane[lane].append(record)
        type_counts[stype] += 1
        lane_counts[lane] += 1

    manifest = {
        "schema_version": 1,
        "scope": "configured public sources after runtime overlay merge",
        "source_files": ["config/sources.yaml", "config/hot_sources.yaml", "config/macro_sources.yaml"],
        "cadence": {"hot": "every 5 minutes", "macro_policy": "every 15 minutes or manual dispatch"},
        "counts": {
            "active_sources": len(active),
            "by_type": dict(sorted(type_counts.items())),
            "by_lane": dict(sorted(lane_counts.items())),
        },
        "sources": sorted(items, key=lambda x: (str(x["lane"]), str(x["id"]))),
    }
    write_json(BRIEFINGS / "source_manifest.json", manifest)

    lines = [
        "# Senna Source Manifest",
        "",
        "Scope: configured public sources after runtime overlay merge.",
        "",
        "## Counts",
        "",
        f"- Active sources: `{len(active)}`",
    ]
    for lane, count in sorted(lane_counts.items()):
        lines.append(f"- {lane}: `{count}`")
    lines += ["", "## Sources by lane", ""]
    for lane in sorted(by_lane):
        lines += [f"### {lane}", ""]
        for source in sorted(by_lane[lane], key=lambda x: str(x["id"])):
            cls = source.get("source_class") or "-"
            lines.append(f"- `{source.get('id')}` — {source.get('name')} / `{source.get('type')}` / class `{cls}` / host `{source.get('host') or '-'}`")
        lines.append("")
    write_text(BRIEFINGS / "source_manifest.md", "\n".join(lines).rstrip() + "\n")
    print(f"Wrote source manifest with {len(active)} active sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
