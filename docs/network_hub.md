# Senna Modern Network Hub

This file translates the external feedback into an operational roadmap for `senna-infoflow`.

The core diagnosis is simple: the monitor must stop being a periodic keyword counter and become a time-aware network. The system needs cadence, velocity, cross-source correlation, credibility weighting, and multiple outputs.

## Tiers

### Tier 1 — Fundamental weaknesses

Critical items:

1. 6h cadence is too slow for viral/security/disaster signals.
2. Static keyword scoring has no momentum memory.
3. Social velocity is missing or too weak.
4. Sources are isolated; no cross-source entity correlation.

### Tier 2 — Signal quality

High-priority improvements:

1. Semantic relatedness for high-score candidates.
2. Rolling baseline and anomaly scoring.
3. GitHub Trending or equivalent tech-pulse sensor.
4. Legal public-channel monitoring where allowed.
5. Source credibility weighting.

### Tier 3 — AXI0M business intelligence

Medium-priority expansion:

1. Research preprints for signal detection, GPU reproducibility, CUDA, provenance.
2. Patent watch.
3. Competitor tracking via local/private config.
4. Finance and market-cross-signal mapping.

### Tier 4 — Output, action, intelligence

High-priority operational layer:

1. `seen.json` remains dedupe; add momentum/baseline state.
2. Critical hits should create an actionable alert, ideally a GitHub issue.
3. Optional LLM synthesis for high-score candidates.
4. Split outputs into `breaking.md`, `daily.md`, `weekly.md`.
5. Add geopolitics/disaster sensors beyond mainstream RSS.

### Tier 5 — Advanced ideas

Lower priority, useful later:

1. Multimedia signals: podcasts, YouTube Data API where allowed.
2. Multilingual Asian tech scan with credibility gates and allowed translation APIs.

## Implementation order

1. Finish `monitor.py` Watchgraph scoring patch.
2. Add momentum state files.
3. Add cross-source entity join.
4. Add source credibility weights.
5. Add alert issue creation.
6. Add multi-output renderer.
7. Add adapters in small, tested steps.

## Boundary

No scraping against terms, no private channels, no credential bypass, no secrets in config.

Social is smoke. GitHub repo descriptions are smoke. Official sources and cross-source velocity are signal.
