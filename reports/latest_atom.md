---
{"doc_type": "senna.report_atom", "schema_version": 1, "mode": "ATOMIC_REPORT", "status": "GENERATED", "run_id": "2026-06-17T20-44-39Z", "generated_at": "2026-06-17T20:44:39Z", "refs": ["[ref:data/2026-06-17/runs/run_2026-06-17T20-44-39Z.json#root|v:2026-06-17T20-44-39Z|tags:snapshot,json|src:senna-infoflow]", "[ref:data/timeseries/2026-06-17/topic_rank_samples.jsonl#root|v:dynamic|tags:timeseries,jsonl|src:senna-infoflow]"]}
---

# REPORT_ATOM 2026-06-17T20-44-39Z

## IDENTITY
- run_id: `2026-06-17T20-44-39Z`
- cadence_minutes: `5`

## CANONICAL_REFS
- [ref:data/2026-06-17/runs/run_2026-06-17T20-44-39Z.json#root|v:2026-06-17T20-44-39Z|tags:snapshot,json|src:senna-infoflow]
- [ref:data/timeseries/2026-06-17/topic_rank_samples.jsonl#root|v:dynamic|tags:timeseries,jsonl|src:senna-infoflow]

## FINDING_ATOMS
### F001 - Introducing LifeSciBench
- topic_key: `title:introducing-lifescibench`
- score: `14`
- source: `OpenAI News RSS`

### F002 - Read remote repository content with GitHub CLI
- topic_key: `title:read-remote-repository-content-with-github-cli`
- score: `10`
- source: `GitHub Changelog Atom`

## TOPIC_SAMPLES
```json
[
  {
    "sample_id": "2026-06-17T20-44-39Z:title:introducing-lifescibench",
    "sample_index": 5939096,
    "timestamp_utc": "2026-06-17T20:44:39Z",
    "run_id": "2026-06-17T20-44-39Z",
    "topic_key": "title:introducing-lifescibench",
    "topic_label": "Introducing LifeSciBench",
    "network_score": 14.0,
    "mention_count": 1,
    "source_count": 1,
    "sources": [
      "OpenAI News RSS"
    ],
    "score_delta_5m": 14.0,
    "trend_wucht": 16.0,
    "status": "emerging",
    "urls": [
      "https://openai.com/index/introducing-life-sci-bench"
    ]
  },
  {
    "sample_id": "2026-06-17T20-44-39Z:title:read-remote-repository-content-with-github-cli",
    "sample_index": 5939096,
    "timestamp_utc": "2026-06-17T20:44:39Z",
    "run_id": "2026-06-17T20-44-39Z",
    "topic_key": "title:read-remote-repository-content-with-github-cli",
    "topic_label": "Read remote repository content with GitHub CLI",
    "network_score": 10.0,
    "mention_count": 1,
    "source_count": 1,
    "sources": [
      "GitHub Changelog Atom"
    ],
    "score_delta_5m": 10.0,
    "trend_wucht": 12.0,
    "status": "emerging",
    "urls": [
      "https://github.blog/changelog/2026-06-17-read-remote-repository-content-with-github-cli"
    ]
  }
]
```

END OF DOCUMENT
