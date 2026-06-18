# Agent Ops Watchlist

STATUS: ACTIVE
UPDATED: 2026-06-18
REPO: Question86/senna-inflow
OWNER_CONTEXT: Yps / AXI0M / Senna Infoflow

---

## Watch theme

Agent Ops is the emerging practice of making AI agents usable in real work without losing control.

Core question:

How does Yps keep agency, auditability, and reaction control while using increasingly autonomous tools?

## Current model

Datenstrom -> Lagebild -> Handlungsmappe -> Recherche -> Szenarien -> Freigabe -> Reaktion -> Audit

## Current findings

### openwong2kim/wmux

Layer: operator workspace
Status: PROTOTYPE

Watch because:

- shows the need for multi-agent command surfaces
- links coding agents, terminals, browser automation, and MCP-style operations
- relevant to local control of AI work

Primary risk:

- too much local capability too early
- unclear maturity
- unsafe if tested with real credentials

Recommended observation:

- watch repo growth
- test only in VM
- compare with similar tools
- extract UX/control lessons for Senna Action Console

### Budibase/budibase

Layer: workflow-action system
Status: RESEARCH

Watch because:

- shows how agents may be embedded into internal operations
- connects apps, automations, data and approvals
- useful as reference for action-layer design

Primary risk:

- workflow automation can create real-world effects
- licensing/deployment must be checked
- approval gates must be explicit

Recommended observation:

- track agent features
- compare with n8n, Dify, Langflow and internal tool builders
- use as pattern source, not default dependency

## AXIM0 opportunity

Agent Ops for small teams:
How to move from AI experiments to controlled workflows,
without handing the keys to the machine.

Possible modules:

- signal intake
- evidence capture
- scenario generation
- response drafting
- human approval
- action audit
- rollback / postmortem

## What to remember

The strategic pattern is stronger than either individual repo.

wmux asks: How do I control many agents?
Budibase asks: How do I route agent work through business processes?

Senna should answer:

With evidence, scenarios, approval, and audit.

---

END OF DOCUMENT
