# Economic Lifetime-Weight Layer

## Objective

The layer estimates the deduplicated, causally attributable total monetary weight touched by an event over its full lifetime, until the incremental weight has effectively stagnated.

This is an economic-strategic metric. It is not an emotional severity score and does not attempt to measure moral importance.

## Current mode

`shadow`

The layer does not change the live resonance ranking. It records what Infoflow believed at first sight so later outcomes can be compared honestly against the initial forecast.

## Files

- `config/economic_weight.yaml` — priors, event classes, capital channels and stagnation rules
- `scripts/economic_weight_layer.py` — event ledger and report generation
- `schemas/economic_event.schema.json` — event/evidence/outcome contract
- `tests/test_economic_weight_layer.py` — unit tests
- `.github/workflows/economic-weight.yml` — independent post-monitor workflow
- `data/economic_events.jsonl` — durable event ledger
- `briefings/economic_weight.json` — machine-readable forecast report
- `briefings/economic_weight.md` — compact audit report

## Invariants

1. The initial P10/P50/P90 forecast is not rewritten by later observations.
2. Existing ranking scores are bounded propagation hints, not ground truth.
3. Monetary evidence, causal attribution and overlap groups remain explicit.
4. No weight changes are auto-applied during the shadow period.
5. Generated reports are committed only after tests pass.

## Next layer

The next implementation should enrich `monetary_evidence`, deduplicate overlap groups, calculate attributed gross/net outcomes, detect stagnation by event class and produce forecast calibration statistics in log-dollar space.
