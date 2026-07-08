#!/usr/bin/env python3
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
B = R / "briefings"; M = R / "memory"; D = R / "docs"

IDENTITY = ["axi0m", "user yps", "question86", "senna-infoflow"]
AI = ["openai", "claude", "llm", "agent", "robot", "nvidia", "mcp", "codex", "artificial intelligence"]
SECURITY = ["cve", "vulnerability", "schwachstelle", "security", "ransomware", "exploit", "patch"]
OFFICIAL = ["cert-eu", "cert-bund", "bsi", "cisa", "jvn", "microsoft", "google cloud", "palo alto", "ivanti"]
OFFICIAL_HIGH = [
    "actively exploited", "active exploitation", "known exploited", "cisa kev", "unauthenticated rce",
    "remote code execution", "arbitrary code execution", "beliebigen code", "codeausführung",
    "cvss 10", "cvss 9.9", "cvss 9.8", "domain controller", "netlogon", "firewall", "vpn",
    "ivanti", "pan-os", "exchange", "sharepoint", "citrix", "fortinet", "palo alto",
    "auth bypass", "privilege escalation", "container breakout", "root privileges",
]
EXPLOITED_NOW = ["actively exploited", "active exploitation", "known exploited", "cisa kev", "aktive angriffe", "ausgenutzt in the wild", "exploited in the wild"]

def load(p, d):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
    except Exception:
        return d

def dump(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def text(row):
    return " ".join(str(row.get(k) or "") for k in ("title", "summary", "source", "url", "comparative_read", "senna_line")).casefold()

def anyhit(t, terms):
    return any(x in t for x in terms)

def add(row, msg):
    why = row.setdefault("why", [])
    if msg not in why:
        why.append(msg)

def harden_row(row):
    t = text(row)
    identity = anyhit(t, IDENTITY)
    ai = anyhit(t, AI) or "ai" in (row.get("topics") or [])
    sec = anyhit(t, SECURITY) or "security" in (row.get("topics") or [])
    official = anyhit(t, OFFICIAL)
    official_high = sec and official and anyhit(t, OFFICIAL_HIGH)
    exploited_now = anyhit(t, EXPLOITED_NOW)
    source_count = int(row.get("source_count") or 0)
    age = float(row.get("age_days") or 0)
    band = row.get("dynamic_band")
    raw = row.get("raw_band")
    score = float(row.get("dynamics_score") or 0)

    if "axiom" in (row.get("topics") or []) and not identity:
        row["topics"] = [x for x in (row.get("topics") or []) if x != "axiom"]
        add(row, "identity recheck: no AXI0M/User-Yps phrase hit")

    if ai and not sec and not identity and source_count <= 1:
        row["single_source_ai_capped"] = True
        score = min(score, 19.9 if age > 14 else 24.9)
        if band in ("krass", "extreme"):
            band = "watch" if age > 14 else "strong"
        add(row, "single-source AI cap enforced after phrase recheck")

    # Official generic security stays visible, but generic single-source advisories are not automatically krass.
    if sec and official and not official_high and source_count <= 1:
        if band in ("krass", "extreme"):
            band = "strong"
            score = min(score, 24.9)
            add(row, "official security but no high-signal phrase: capped at strong")

    # Stale official security needs current exploitation, KEV/in-the-wild wording, or new resonance to stay krass.
    if age > 30 and source_count <= 1 and not identity and not exploited_now:
        if band in ("krass", "extreme"):
            band = "watch"
            score = min(score, 19.9)
            add(row, "stale single-source cap after 30d: no current exploitation phrase")

    # Krass/Extreme gate after phrase recheck.
    can_krass = source_count >= 2 or identity or official_high
    can_extreme = identity or (source_count >= 2 and (official_high or exploited_now))
    if band == "extreme" and not can_extreme:
        band = "strong"
        score = min(score, 24.9)
        add(row, "extreme gate recheck: insufficient independent/current evidence")
    if band == "krass" and not can_krass:
        band = "strong"
        score = min(score, 24.9)
        add(row, "krass gate recheck: needs multi-source, identity, or official high-signal phrase")

    row["dynamic_band"] = band
    row["dynamics_score"] = round(max(0, score), 2)
    row["security_high_signal"] = bool(official_high)
    if band == "krass":
        row["comparative_read"] = "Die Dynamik ist verglichen ziemlich krass; nicht automatisch wahrer, aber deutlich bewegter als übliches Rauschen."
    elif band == "strong":
        row["comparative_read"] = "Die Dynamik liegt über Normalniveau und verdient aktive Beobachtung."
    elif band == "watch":
        row["comparative_read"] = "Die Dynamik ist sichtbar, aber noch nicht stark genug für Alarm."
    elif band == "quiet":
        row["comparative_read"] = "Die Dynamik wirkt aktuell wie Hintergrundrauschen."
    if row["security_high_signal"] and band in ("strong", "krass", "extreme"):
        row["senna_line"] = "Security zuerst. Exposure prüfen, Patchstand sichern, dann erst über Narrative reden."
    elif ai and not sec:
        row["senna_line"] = "Interessant, aber Einzelquellen-AI darf nicht die Lage dominieren."
    return row

def harden_doc(doc):
    rows = [harden_row(dict(r)) for r in doc.get("top_dynamics", []) if isinstance(r, dict)]
    order = {"krass": 4, "extreme": 4, "strong": 3, "watch": 2, "quiet": 1}
    rows.sort(key=lambda r: (order.get(r.get("dynamic_band"), 0), bool(r.get("security_high_signal")), float(r.get("dynamics_score") or 0), int(r.get("source_count") or 0)), reverse=True)
    doc["top_dynamics"] = rows
    counts = {}
    for r in rows:
        counts[r["dynamic_band"]] = counts.get(r["dynamic_band"], 0) + 1
    doc.setdefault("counts", {})["bands_after_gate_recheck"] = counts
    top = rows[0] if rows else None
    if top:
        doc["situation_read"] = f"Stärkste Dynamik nach Gate-Recheck: “{top['title']}” — {top['comparative_read']} Band={top['dynamic_band']}, score={top['dynamics_score']}."
    return doc

def main():
    for p in [B/"intelligence_handoff.json", D/"intelligence_handoff.json", M/"dynamics.json"]:
        doc = load(p, {})
        if isinstance(doc, dict) and isinstance(doc.get("top_dynamics"), list):
            dump(p, harden_doc(doc))
    # Rebuild markdown from briefing json
    h = load(B/"intelligence_handoff.json", {})
    if isinstance(h, dict):
        lines = ["# Senna Intelligence Handoff", "", f"_Generated: {h.get('generated_at')}_", "", "## Lageurteil", "", h.get("situation_read",""), "", "## Top Dynamics", ""]
        for r in h.get("top_dynamics", [])[:12]:
            lines += [f"### {r.get('title')}", "", f"- Band: `{r.get('dynamic_band')}` (raw `{r.get('raw_band')}`)", f"- Dynamics score: `{r.get('dynamics_score')}`", f"- Published: `{r.get('published_at') or 'unknown'}` / age_days `{r.get('age_days')}`", f"- Vergleich: {r.get('comparative_read')}", f"- Senna: {r.get('senna_line')}", f"- Warum: {', '.join(r.get('why') or [])}", f"- Quelle: {r.get('url') or r.get('source') or 'unbekannt'}", ""]
        out = "\n".join(lines + ["END OF DOCUMENT", ""])
        dump(M/"real_memory_candidates.json", load(M/"real_memory_candidates.json", {}))
        (B/"intelligence_handoff.md").write_text(out, encoding="utf-8")
        (D/"intelligence_handoff.md").write_text(out, encoding="utf-8")
    print("Hardened intelligence output gates after phrase recheck.")

if __name__ == "__main__":
    main()
