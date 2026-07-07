#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEFINGS = ROOT / "briefings"
MEMORY = ROOT / "memory"
DOCS = ROOT / "docs"

TOPIC_RULES = {
    "ai": ["ai", "artificial intelligence", "llm", "model", "agent", "openai", "anthropic"],
    "security": ["security", "cve", "vulnerability", "exploit", "zero-day", "ransomware", "patch"],
    "github": ["github", "repository", "repo", "open source", "pull request"],
    "economy": ["economy", "market", "inflation", "bank", "rate", "central bank"],
    "geopolitics": ["war", "election", "sanction", "government", "policy", "nato", "eu"],
    "axiom": ["axi0m", "yps", "question86"],
}

def utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def clip(value, limit=180):
    text = "" if value is None else " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

def findings(feed):
    items = feed.get("findings") if isinstance(feed, dict) else []
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]

def classify(item):
    blob = " ".join(str(item.get(k) or "") for k in ("title", "source", "source_type", "summary", "url")).lower()
    hits = [topic for topic, words in TOPIC_RULES.items() if any(word in blob for word in words)]
    return hits or ["general"]

def main():
    latest = load_json(BRIEFINGS / "latest.json", {})
    items = findings(latest)
    generated_at = (latest.get("generated_at") if isinstance(latest, dict) else None) or utc()

    topic_counts = {}
    top_by_topic = {}

    for item in items:
        for topic in classify(item):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
            top_by_topic.setdefault(topic, []).append({
                "title": clip(item.get("title")),
                "source": clip(item.get("source"), 90),
                "published_at": item.get("published_at"),
                "relevance_score": item.get("relevance_score"),
                "url": item.get("url"),
            })

    for topic, values in top_by_topic.items():
        values.sort(
            key=lambda x: (float(x.get("relevance_score") or 0), str(x.get("published_at") or "")),
            reverse=True,
        )
        top_by_topic[topic] = values[:10]

    index = {
        "schema_version": 1,
        "doc_type": "senna.memory.index",
        "generated_at": generated_at,
        "purpose": "Compact semantic memory index for LLM-native first-pass access.",
        "source": "briefings/latest.json",
        "counts": {"source_items": len(items), "topics": len(topic_counts)},
        "topic_counts": dict(sorted(topic_counts.items(), key=lambda x: (-x[1], x[0]))),
        "files": {"topics": "memory/topics.json", "index_md": "memory/index.md"},
        "read_order": [
            "briefings/chat_handoff.json",
            "memory/index.json",
            "memory/topics.json",
            "briefings/latest.json only if deeper inspection is required",
        ],
    }

    topics = {
        "schema_version": 1,
        "doc_type": "senna.memory.topics",
        "generated_at": generated_at,
        "topics": top_by_topic,
    }

    write_json(MEMORY / "index.json", index)
    write_json(MEMORY / "topics.json", topics)

    lines = [
        "# Senna Memory Index",
        "",
        f"_Generated: {generated_at}_",
        "",
        "## Topic Counts",
        "",
    ]
    for topic, count in index["topic_counts"].items():
        lines.append(f"- {topic}: `{count}`")
    lines += ["", "## Read Order", ""]
    for path in index["read_order"]:
        lines.append(f"- `{path}`")
    lines += ["", "END OF DOCUMENT", ""]

    MEMORY.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    (MEMORY / "index.md").write_text("\n".join(lines), encoding="utf-8")
    (DOCS / "memory_index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote memory index from {len(items)} finding(s).")

if __name__ == "__main__":
    main()
