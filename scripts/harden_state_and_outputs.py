#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
STATE = ROOT / "state"
INBOX = ROOT / "inbox"

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            h.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

def norm_field(name):
    key = re.sub(r"\s+", " ", name.strip().lower().replace("_", " "))
    return {
        "titel": "title", "title": "title",
        "status": "status", "region": "region", "tags": "tags",
        "quelle": "source", "source": "source",
        "kontext": "context", "context": "context",
        "warum": "why", "why": "why",
        "beobachten": "watch", "watch": "watch",
        "trigger": "triggers", "triggers": "triggers",
        "update-regel": "update_rule", "update regel": "update_rule", "update": "update_rule",
        "nicht tun": "do_not", "nicht_tun": "do_not",
        "cadence": "cadence", "takt": "cadence",
    }.get(key, re.sub(r"[^a-z0-9_]+", "_", key).strip("_") or "note")

def parse_observation_topics():
    path = INBOX / "manual_notes.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    in_lane = False
    topics, cur, cur_field = [], None, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^\s*##\s+Unter Beobachtung\s*$", line, re.I):
            in_lane = True
            continue
        if in_lane and re.match(r"^\s*##\s+", line):
            break
        if not in_lane:
            continue
        m = re.match(r"^\s*-\s*\[observe\]\s*(?:id\s*:\s*)?([A-Za-z0-9_.:-]+)\s*$", line, re.I)
        if m:
            if cur:
                topics.append(cur)
            cur = {"id": m.group(1), "status": "active"}
            cur_field = None
            continue
        if cur is None:
            continue
        f = re.match(r"^\s{2,}([^:]{2,40}):\s*(.*)$", line)
        if f:
            cur_field = norm_field(f.group(1))
            cur[cur_field] = f.group(2).strip()
            continue
        if cur_field and line.strip():
            cur[cur_field] = (str(cur.get(cur_field, "")).rstrip() + " " + line.strip()).strip()
    if cur:
        topics.append(cur)
    out, seen = [], set()
    for t in topics:
        tid = str(t.get("id") or "").strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        t.setdefault("title", tid.replace("_", " ").title())
        t.setdefault("status", "active")
        t.setdefault("cadence", "routine")
        t.setdefault("source", "inbox/manual_notes.md")
        t.setdefault("watch", "")
        t.setdefault("triggers", "")
        out.append(t)
    return out

def terms(text):
    out, seen = [], set()
    for raw in re.split(r"[,;/|]|\s+OR\s+", text or "", flags=re.I):
        term = raw.strip().strip("`'\"").lower()
        if len(term) < 3 or term in {"and", "oder", "und", "the", "mit", "for"} or term in seen:
            continue
        seen.add(term); out.append(term)
    return out[:40]

def attach_current_hits(topics, latest):
    findings = latest.get("findings") if isinstance(latest, dict) else []
    if not isinstance(findings, list):
        findings = []
    for t in topics:
        trigger_text = " ".join(str(t.get(k) or "") for k in ("id","title","region","tags","triggers","watch"))
        ts = terms(trigger_text)
        hits = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            hay = " ".join(str(f.get(k) or "") for k in ("title","summary","source","url","matched_keywords","relevance_reason")).lower()
            if any(x in hay for x in ts):
                hits.append({"title": f.get("title"), "source": f.get("source"), "score": f.get("relevance_score"), "url": f.get("url")})
        t["current_feed_signal_count"] = len(hits)
        t["current_feed_signal_examples"] = hits[:3]

def render_lane(topics, generated_at):
    lines = [
        "## Unter Beobachtung", "",
        "Diese Lane ist absichtlich feed-unabhängig. Sie hält Themen sichtbar, auch wenn die Presse gerade woanders hinglotzt.",
        "", f"_Aktualisiert: {generated_at}_", ""
    ]
    if not topics:
        lines.append("- Keine aktiven Beobachtungsthemen eingetragen.")
        return "\n".join(lines).rstrip() + "\n"
    for t in topics:
        lines.append(f"- **{t.get('title') or t.get('id')}** — `{t.get('id')}` / `{t.get('status','active')}` / `{t.get('cadence','routine')}`")
        for label, key in (("Warum","why"),("Beobachten","watch"),("Trigger","triggers"),("Update-Regel","update_rule"),("Nicht tun","do_not")):
            if t.get(key):
                lines.append(f"  - {label}: {t[key]}")
        lines.append(f"  - Aktueller Feed-Signalabgleich: `{int(t.get('current_feed_signal_count') or 0)}` Treffer")
    return "\n".join(lines).rstrip() + "\n"

def main():
    ts = now_iso()
    latest_path = BRIEFINGS / "latest.json"
    latest = read_json(latest_path, {})
    topics = parse_observation_topics()
    attach_current_hits(topics, latest if isinstance(latest, dict) else {})
    payload = {
        "schema_version": 1,
        "doc_type": "senna.under_observation_lane",
        "generated_at": ts,
        "source": "inbox/manual_notes.md",
        "purpose": "persistent routine watch topics independent of current feed attention",
        "count": len(topics),
        "topics": topics,
    }
    if isinstance(latest, dict):
        latest["under_observation"] = payload
        write_json(latest_path, latest)

    md_path = BRIEFINGS / "latest.md"
    base = md_path.read_text(encoding="utf-8") if md_path.exists() else "# Senna Briefing\n"
    base = re.split(r"\n## Unter Beobachtung\n", base, maxsplit=1)[0].rstrip()
    write_text(md_path, base + "\n\n" + render_lane(topics, ts))

    health = read_json(BRIEFINGS / "health.json", {})
    if not isinstance(health, dict):
        health = {}
    health.update({
        "generated_at": ts,
        "status": health.get("status", "ok"),
        "under_observation_topics": len(topics),
        "under_observation_source": "inbox/manual_notes.md",
    })
    write_json(BRIEFINGS / "health.json", health)
    write_json(STATE / "health.json", health)

    print(f"under observation lane updated: topics={len(topics)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
