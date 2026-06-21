#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = [
    ("base", ROOT / "config" / "sources.yaml"),
    ("hot", ROOT / "config" / "hot_sources.yaml"),
    ("macro_policy", ROOT / "config" / "macro_sources.yaml"),
]
RUNTIME_MAX_ITEMS_CAP = 6
ENSO_TOPIC_ID = "enso_el_nino_2026_global_climate_stress"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def source_id(src: dict) -> str:
    return str(src.get("id") or src.get("name") or "").strip()


def is_enabled(src: dict, defaults: dict) -> bool:
    return src.get("enabled", defaults.get("enabled", True)) is not False


def source_host(src: dict) -> str:
    url = str(src.get("url") or src.get("html_url") or "").strip()
    if not url:
        return ""
    return urlparse(url).netloc


def ensure_enso_watch_topic() -> bool:
    path = ROOT / "inbox" / "manual_notes.md"
    if not path.exists():
        return False

    text = path.read_text(encoding="utf-8")
    if ENSO_TOPIC_ID in text:
        return False

    block = """
- [observe] id: enso_el_nino_2026_global_climate_stress
  Titel: ENSO / El Niño 2026 — globale Klima-, Ernte-, Energie- und Infrastruktur-Stressachse
  Status: active
  Region: Global, Tropical Pacific, Australia, Indonesia, South Asia, Horn of Africa, Americas, Pacific Islands
  Quelle: Gesprächsnotiz User Yps, 2026-06-21; offizielle ENSO-Lagequellen NOAA CPC, WMO, Australian BoM
  Warum: El Niño 2026 ist kein einzelnes Wetterereignis, sondern ein globaler Risikomultiplikator: Temperaturrekorde, Dürre, Starkregen, Monsunabweichungen, Feuerwetter, Korallenbleiche, Agrarpreise, Wasserstress, Energiebedarf, Versicherungen, Migration und Lieferketten können über Monate gekoppelt reagieren. Für AXI0M ist es eine Klima-/Infrastruktur-/Public-Risk-Lane, nicht Wetterrauschen.
  Beobachten: NOAA CPC ENSO Diagnostics Discussion, WMO El Niño/La Niña Update, Australian BoM ENSO Tracker, ECMWF/IRI seasonal outlooks, sea surface temperature anomalies, Niño 3.4/RONI, Southern Oscillation Index, trade winds, subsurface Pacific heat content, Indian Ocean Dipole, monsoon outlooks, heatwaves, drought/flood anomalies, wildfire risk, coral bleaching, crop stress, food price signals, hydropower/water levels, insurance losses, humanitarian early warnings.
  Trigger: El Niño, El Nino, El Ninjo, ENSO, La Niña, La Nina, Niño 3.4, Nino 3.4, RONI, ONI, Southern Oscillation Index, SOI, trade winds, tropical Pacific, sea surface temperature, SST anomaly, WMO El Niño, NOAA CPC ENSO, BoM ENSO, IRI ENSO, ECMWF seasonal, Indian Ocean Dipole, monsoon, drought, heatwave, wildfire, bushfire, coral bleaching, crop failure, food prices, hydropower, water stress, flood, Horn of Africa, Australia drought, Indonesia drought, South Asia monsoon, Pacific Islands, Americas rainfall
  Update-Regel: Hochziehen bei NOAA/WMO/BoM Advisory- oder Watch-Änderung, Niño-3.4/RONI >= +0.5 über mehrere Monate, Prognose auf stark/sehr stark, bestätigter Dürre-/Monsun-/Feuer-/Ernte-/Energie-/Wasserstress in mehreren Regionen, Food-Price- oder Versicherungsresonanz, oder direktem Bezug zu Yps/AXI0M-Reisen, Kunden, Infrastruktur, Hosting, Lieferketten oder Content-Chancen. Als MEDIUM führen, wenn aktuelle offizielle ENSO-Lage plus mindestens eine regionale Primärquelle innerhalb von 14 Tagen zusammenfallen.
  Nicht tun: Nicht jedes lokale Wetterereignis El Niño zuschreiben. Keine "Super-El-Niño"/Godzilla-Rhetorik als offizielle Klassifikation behandeln. Keine Klimapanik und keine Klimaverharmlosung. ENSO ist Multiplikator, nicht alleinige Ursache.
"""
    marker = "\n## Eingehende Hinweise"
    if marker in text:
        text = text.replace(marker, "\n" + block + marker, 1)
    else:
        text = text.rstrip() + "\n\n" + block
    path.write_text(text, encoding="utf-8")
    return True


def build_runtime_sources() -> tuple[dict, list[dict], list[dict]]:
    base_doc = load_yaml(CONFIGS[0][1])
    defaults = dict(base_doc.get("defaults") or {"enabled": True, "max_items": 5})

    merged: dict[str, dict] = {}
    order: list[str] = []

    for lane, path in CONFIGS:
        doc = load_yaml(path)
        for raw in doc.get("sources") or []:
            if not isinstance(raw, dict):
                continue
            sid = source_id(raw)
            if not sid:
                continue

            item = dict(raw)
            item["lane"] = str(item.get("lane") or lane)
            item["runtime_source_file"] = str(path.relative_to(ROOT))

            if item.get("type") != "manual_note" and item.get("max_items") is not None:
                try:
                    item["max_items"] = max(1, min(int(item["max_items"]), RUNTIME_MAX_ITEMS_CAP))
                except Exception:
                    item["max_items"] = RUNTIME_MAX_ITEMS_CAP

            if sid not in merged:
                order.append(sid)
                merged[sid] = item
            else:
                # Hot/macro overlays are allowed to refine existing base entries.
                merged[sid].update(item)

    sources = [merged[sid] for sid in order]
    active = [src for src in sources if is_enabled(src, defaults)]

    runtime_doc = dict(base_doc)
    runtime_meta = dict(runtime_doc.get("meta") or {})
    runtime_meta["runtime_overlay_merge"] = {
        "enabled": True,
        "generated_at": utc_now(),
        "source_files": [str(path.relative_to(ROOT)) for _, path in CONFIGS],
        "policy": "Visible broad feed merges base + hot + macro overlays at runtime. config/sources.yaml is rewritten only inside the Action workspace.",
        "runtime_max_items_cap": RUNTIME_MAX_ITEMS_CAP,
    }
    runtime_doc["meta"] = runtime_meta
    runtime_doc["defaults"] = defaults
    runtime_doc["sources"] = sources

    (ROOT / "config" / "sources.yaml").write_text(
        yaml.safe_dump(runtime_doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return defaults, sources, active


def write_source_manifest(defaults: dict, sources: list[dict], active: list[dict]) -> dict:
    by_type = Counter(str(src.get("type") or "unknown") for src in active)
    by_lane = Counter(str(src.get("lane") or "unknown") for src in active)
    by_class = Counter(str(src.get("source_class") or "-") for src in active)

    manifest_sources = []
    for src in active:
        manifest_sources.append(
            {
                "id": source_id(src),
                "name": str(src.get("name") or source_id(src)),
                "type": str(src.get("type") or "unknown"),
                "lane": str(src.get("lane") or "unknown"),
                "source_class": src.get("source_class") or src.get("class"),
                "host": source_host(src),
                "max_items": src.get("max_items"),
                "runtime_source_file": src.get("runtime_source_file"),
            }
        )

    manifest = {
        "schema_version": 2,
        "generated_at": utc_now(),
        "scope": "actual runtime sources after base + hot + macro overlay merge",
        "source_files": [str(path.relative_to(ROOT)) for _, path in CONFIGS],
        "runtime_policy": {
            "visible_feed": "broad runtime merge",
            "runtime_max_items_cap": RUNTIME_MAX_ITEMS_CAP,
            "disabled_sources_are_excluded": True,
            "notes": [
                "This manifest is generated from the Action workspace before the monitor runs.",
                "It is the truth source for what the current run is allowed to fetch.",
                "docs/index.html is not modified by this script.",
            ],
        },
        "counts": {
            "configured_sources": len(sources),
            "active_sources": len(active),
            "by_type": dict(sorted(by_type.items())),
            "by_lane": dict(sorted(by_lane.items())),
            "by_class": dict(sorted(by_class.items())),
        },
        "sources": manifest_sources,
    }

    briefings = ROOT / "briefings"
    briefings.mkdir(exist_ok=True)
    (briefings / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Senna Source Manifest",
        "",
        f"_Generated: {manifest['generated_at']}_",
        "",
        "Scope: actual runtime sources after base + hot + macro overlay merge.",
        "",
        "## Counts",
        "",
        f"- Configured sources: `{len(sources)}`",
        f"- Active sources: `{len(active)}`",
        "",
        "### By lane",
        "",
    ]
    for lane, count in sorted(by_lane.items()):
        md.append(f"- {lane}: `{count}`")
    md.extend(["", "### By type", ""])
    for typ, count in sorted(by_type.items()):
        md.append(f"- {typ}: `{count}`")
    md.extend(["", "## Sources by lane", ""])
    for lane in sorted(by_lane):
        md.extend([f"### {lane}", ""])
        for src in manifest_sources:
            if src["lane"] != lane:
                continue
            md.append(
                f"- `{src['id']}` — {src['name']} / `{src['type']}` / "
                f"class `{src.get('source_class') or '-'}` / host `{src.get('host') or '-'}` / "
                f"from `{src.get('runtime_source_file')}`"
            )
        md.append("")
    (briefings / "source_manifest.md").write_text("\n".join(md), encoding="utf-8")
    return manifest


def main() -> int:
    ens_added = ensure_enso_watch_topic()
    defaults, sources, active = build_runtime_sources()
    manifest = write_source_manifest(defaults, sources, active)

    print(json.dumps(
        {
            "enso_watch_topic_added": ens_added,
            "configured_sources": len(sources),
            "active_sources": len(active),
            "by_lane": manifest["counts"]["by_lane"],
            "by_type": manifest["counts"]["by_type"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
