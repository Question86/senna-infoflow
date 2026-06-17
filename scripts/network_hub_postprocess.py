#!/usr/bin/env python3
"""Network Hub layer: momentum, source credibility, and cross-source fusion."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
STATE = ROOT / "state"
DATA = ROOT / "data"
MAX_HISTORY = 30


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def text_of(item: dict) -> str:
    return " ".join(str(x or "") for x in [
        item.get("title"),
        item.get("summary"),
        item.get("url"),
        item.get("source"),
        " ".join(item.get("matched_keywords") or []),
        " ".join(item.get("watchgraph_modules") or []),
    ]).lower()


def key_for(item: dict) -> str:
    text = text_of(item)
    title = norm(str(item.get("title") or "")).lower()
    url = str(item.get("url") or "")

    cve = re.search(r"\bcve-\d{4}-\d{4,7}\b", text, re.I)
    if cve:
        return "cve:" + cve.group(0).upper()

    if any(x in text for x in ["earthquake", "shakemap", "pager", "gdacs"]):
        mag = re.search(r"\b(?:magnitude|mag|m)\s*[: ]?\s*(\d+(?:\.\d+)?)\b", text)
        mag_text = "unknown"
        if mag:
            try:
                mag_text = f"{float(mag.group(1)):.1f}"
            except ValueError:
                mag_text = mag.group(1)
        loc = ""
        for candidate in [
            "central mid-atlantic ridge",
            "mid-atlantic ridge",
            "japan",
            "taiwan",
            "chile",
            "alaska",
            "california",
            "turkey",
            "indonesia",
            "philippines",
        ]:
            if candidate in text:
                loc = candidate
                break
        if not loc:
            loc_match = re.search(r"\b(?:in|near|at)\s+([a-z][a-z0-9 -]{4,60})", title)
            loc = norm(loc_match.group(1))[:60] if loc_match else title[:60]
        return f"earthquake:{loc}:{mag_text}"

    storm = re.search(r"\b(?:tropical storm|hurricane|cyclone|typhoon)\s+([a-z][a-z0-9-]{2,30})\b", text)
    if storm:
        return "storm:" + storm.group(1).lower()

    parsed = urlparse(url)
    if parsed.netloc.endswith("github.com") and parsed.path.count("/") >= 2:
        return "github_repo:" + "/".join(parsed.path.strip("/").split("/")[:2]).lower()

    domain = re.search(r"\b[a-z0-9.-]+\.(?:de|com|org|net|io|gov|int|eu)\b", text, re.I)
    if domain and domain.group(0).lower() not in {"github.com", "www.gdacs.org"}:
        return "domain:" + domain.group(0).lower().strip(".")

    words = [w for w in re.findall(r"[a-z0-9]{3,}", title) if w not in {"the", "and", "for", "with", "from", "into", "how", "new"}]
    return "title:" + "-".join(words[:8]) if words else "url:" + url.lower()


def source_class(item: dict) -> str:
    text = f"{item.get('source','')} {item.get('source_type','')} {item.get('url','')}".lower()
    if any(x in text for x in ["usgs", "gdacs", "noaa", "nhc", "cisa", "nvd", "reliefweb", "tsunami.gov", "gfz", "geofon"]):
        return "tier1_official"
    if any(x in text for x in ["reuters", "associated press", "ap news", "bloomberg", "financial times", "wsj"]):
        return "tier2_major_news"
    if any(x in text for x in ["portswigger", "snyk", "heise", "bleepingcomputer", "github blog", "openai"]):
        return "tier3_specialist"
    if any(x in text for x in ["reddit", "hacker news", "telegram", "bluesky", "twitter", "x.com"]):
        return "tier4_platform_social"
    if str(item.get("source_type") or "") == "github_search":
        return "tier5_generic_repo"
    return "tier3_specialist"


def weight(cls: str) -> float:
    return {
        "tier1_official": 1.35,
        "tier2_major_news": 1.20,
        "tier3_specialist": 1.05,
        "tier4_platform_social": 0.75,
        "tier5_generic_repo": 0.55,
    }.get(cls, 1.0)


def update_velocity(groups: dict[str, list[dict]], generated_at: str) -> dict:
    prev = read_json(STATE / "velocity.json", {"version": 1, "entities": {}})
    old_entities = prev.get("entities") if isinstance(prev, dict) else {}
    old_entities = old_entities if isinstance(old_entities, dict) else {}
    entities = {}

    for key, items in groups.items():
        old = old_entities.get(key, {}) if isinstance(old_entities.get(key), dict) else {}
        last = int(old.get("last_run_count") or 0)
        count = len(items)
        hist = list(old.get("history") or [])
        hist.append({"at": generated_at, "count": count})
        entities[key] = {
            "title": norm(str(items[0].get("title") or key)),
            "first_seen_at": old.get("first_seen_at") or generated_at,
            "last_seen_at": generated_at,
            "previous_run_count": last,
            "last_run_count": count,
            "momentum_delta": count - last,
            "momentum_status": "increasing" if count > last else "falling" if count < last else "stable",
            "history": hist[-MAX_HISTORY:],
            "sources": sorted({str(i.get("source") or "") for i in items if i.get("source")}),
        }

    for key, old in old_entities.items():
        if key in entities or not isinstance(old, dict):
            continue
        last = int(old.get("last_run_count") or 0)
        hist = list(old.get("history") or [])
        hist.append({"at": generated_at, "count": 0})
        old = dict(old)
        old["previous_run_count"] = last
        old["last_run_count"] = 0
        old["momentum_delta"] = -last if last else 0
        old["momentum_status"] = "falling" if last else "quiet"
        old["history"] = hist[-MAX_HISTORY:]
        entities[key] = old

    state = {"version": 1, "generated_at": generated_at, "entities": entities}
    write_json(STATE / "velocity.json", state)
    return state


def build_network(findings: list[dict], velocity: dict, generated_at: str) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in findings:
        if isinstance(item, dict):
            groups[key_for(item)].append(item)

    entities = (velocity.get("entities") or {}) if isinstance(velocity, dict) else {}
    clusters = []
    for key, items in groups.items():
        scores = [int(i.get("relevance_score") or 0) for i in items]
        sources = sorted({str(i.get("source") or "") for i in items if i.get("source")})
        classes = sorted({source_class(i) for i in items})
        cred = round(sum(weight(source_class(i)) for i in items), 2)
        vel = entities.get(key, {}) if isinstance(entities, dict) else {}
        delta = int(vel.get("momentum_delta") or 0)
        cross = len(sources) >= 2 or len(classes) >= 2
        max_score = max(scores) if scores else 0
        network_score = max_score + 2 * max(0, len(sources) - 1) + 3 * max(0, delta) + 2 * cred
        if cross:
            network_score += 4
        if cross and "tier1_official" in classes:
            network_score += 3

        top = sorted(items, key=lambda x: int(x.get("relevance_score") or 0), reverse=True)[0]
        modules = []
        for item in items:
            for module in item.get("watchgraph_modules") or []:
                if module not in modules:
                    modules.append(module)
        urls = []
        for item in items:
            url = str(item.get("url") or "")
            if url and url not in urls:
                urls.append(url)

        hot = network_score >= 24 or (cross and max_score >= 12) or delta >= 2
        clusters.append({
            "key": key,
            "title": norm(str(top.get("title") or key)),
            "sources": sources,
            "source_classes": classes,
            "urls": urls[:6],
            "finding_count": len(items),
            "max_score": max_score,
            "credibility_total": cred,
            "cross_source_confirmed": cross,
            "momentum_delta": delta,
            "momentum_status": str(vel.get("momentum_status") or "stable"),
            "network_score": round(network_score, 2),
            "hot": hot,
            "watchgraph_modules": modules,
            "recommended_action": (
                "HOT: cross-source confirmed. Quelle sichern, Kontext prüfen, bei Relevanz aktiv alarmieren."
                if hot else str(top.get("recommended_action") or "Beobachten.")
            ),
        })

    clusters.sort(key=lambda c: (c["network_score"], c["max_score"], c["finding_count"]), reverse=True)
    return {
        "generated_at": generated_at,
        "source": "briefings/latest.json",
        "counts": {
            "findings": len(findings),
            "clusters": len(clusters),
            "cross_source_confrmed": sum(1 for c in clusters if c["cross_source_confirmed"]),
            "hot": sum(1 for c in clusters if c["hot"]),
        },
        "clusters": clusters,
    }


def write_breaking(network: dict) -> None:
    lines = ["# Senna Breaking", "", f"_Generiert: {network['generated_at']}_", ""]
    hot = [c for c in network["clusters"] if c["hot"]][:3]
    if not hot:
        lines += ["Keine Breaking-Signale. Keine laute Sirene.", ""]
    for c in hot:
        lines += [
            f"## {c['title']}",
            "",
            f"- Network Score: {c['network_score']}",
            f"- Max Monitor Score: {c['max_score']}",
            f"- Quellen: {', '.join(c['sources']) or 'unbekannt'}",
            f"- Klassen: {', '.join(c['source_classes']) or 'unbekannt'}",
            f"- Cross-source bestätigt: {'ja' if c['cross_source_confirmed'] else 'nein'}",
            f"- Momentum: {c['momentum_status']} ({c['momentum_delta']:+d})",
            f"- Watchgraph: {', '.join(c['watchgraph_modules']) or 'keine'}",
            f"- Erste Quelle: {c['urls'][0] if c['urls'] else 'keine'}",
            f"- Handlung: {c['recommended_action']}",
            "",
        ]
    (BRIEFINGS / "breaking.md").write_text("\n".join(lines), encoding="utf-8")


def update_baseline(network: dict) -> None:
    baseline = read_json(STATE / "baseline.json", {"version": 1, "entities": {}})
    entities = baseline.get("entities") if isinstance(baseline, dict) else {}
    entities = entities if isinstance(entities, dict) else {}
    for c in network["clusters"]:
        old = entities.get(c["key"], {}) if isinstance(entities.get(c["key"]), dict) else {}
        scores = list(old.get("network_scores") or [])
        scores.append(c["network_score"])
        scores = scores[-MAX_HISTORY:]
        avg = sum(scores) / len(scores) if scores else 0
        entities[c["key"]] = {
            "title": c["title"],
            "updated_at": network["generated_at"],
            "network_scores": scores,
            "rolling_average": round(avg, 2),
            "rolling_peak": round(max(scores), 2) if scores else 0,
            "last_score": c["network_score"],
            "z_hint": round(c["network_score"] - avg, 2),
        }
    write_json(STATE / "baseline.json", {"version": 1, "generated_at": network["generated_at"], "entities": entities})


def main() -> int:
    generated_at = now()
    latest = read_json(BRIEFINGS / "latest.json", {})
    findings = latest.get("findings") if isinstance(latest, dict) else []
    findings = findings if isinstance(findings, list) else []

    groups = defaultdict(list)
    for item in findings:
        if isinstance(item, dict):
            groups[key_for(item)].append(item)

    velocity = update_velocity(groups, generated_at)
    network = build_network(findings, velocity, generated_at)
    write_json(BRIEFINGS / "network.json", network)
    write_breaking(network)
    update_baseline(network)

    today_file = read_json(DATA / today() / "findings.json", [])
    write_json(BRIEFINGS / "daily.json", {
        "generated_at": generated_at,
        "today_file_total": len(today_file) if isinstance(today_file, list) else 0,
        "current_clusters": network["clusters"][:20],
    })

    print(
        f"Network hub postprocess complete: {network['counts']['findings']} findings, "
        f"{network['counts']['clusters']} clusters, {network['counts']['hot']} hot."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
