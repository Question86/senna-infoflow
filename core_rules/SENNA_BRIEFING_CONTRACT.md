# SENNA BRIEFING CONTRACT

MODE: RUNTIME RULE
STATUS: ACTIVE
CREATED: 2026-06-17
TASK: Define what Y`s means when asking for a briefing, update, layer summary, or situation summary.

---

## CORE RULE

When Yps asks for:

- `briefing`
- `update`
- `zesammenfassung`
- `lage`
- `situation`
- `was gibt es neues?`
- or comparable language

Senna must interpret the request as a request for a summary based on the `senna-infoflow` GitHub pipeline artifacts.

## PRIMARY SOURCES

Use these repository artifacts first:

```text
briefings/latest.json
briefings/network.json
briefings/daily.json
briefings/breaking.md
briefings/trends.json
reports/latest_atom.md
reports/atoms/<date>/*
data/<date>/runs/*
state/*
```

## NO WILD ONLINE SEARCH 

Do not perform a general web search for a briefing/update request unless Yps explicitly asks for:

- web search
- online verification
- external sources
- current news beyond the infoflow report
- a fresh internet check

## IF THE INFOFLOW IS EMPTY OR STALE

If the pipeline artifacts are empty, stale, or missing, Senna must say that clearly and treat it as a pipeline observation, not as a reason to invent a lobal briefing.

## STYLE

Briefings should be:

- short
- direct
- evidence-based
- prioritized
- clear about source, time, score, magnitude, trend, and uncertainty

## END OF DOCUMENT
