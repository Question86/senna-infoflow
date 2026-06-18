# Keeper Zenner Findings Cheatsheet

STATUS: ACTIVE
UPDATED: 2026-06-18
REPO: Question86/senna-infoflow

## Legend

- OBSERVE: worth watching, no immediate action
- RESEARCH: deeper research needed
- PROTOTYPE: controlled testing worth doing
- ACTIONABLE: can drive a near-term AXI0M task
- HOLD: remember, but do not act yet

---

## F-2026-06-18-001 — openwong2kim/wmux

Status: PROTOTYPE
Theme: Agent Ops / local operator workspace
Source: GitHub
URL: https://github.com/openwong2kim/wmux
Initial score: 23
Classification: SIGNAL, single source

### What it is

Windows terminal/workspace tool aimed at running and controlling multiple AI coding agents side by side, including Claude Code, Codex, Gemini CLI and browser/MCP-style workflows.

### Why it matters

If multiple agents work at once, humans need an operator console.

This matches Yps' direction: information is not enough; action needs control surfaces, sessions, approvals, logs, and human override.

### First research

Known:

- Public GitHub repo.
- Focus: Windows-native multi-agent terminal/workspace.
- Mentions split panes, browser automation, MCP-style control and multiple AI coding agents.
- Early-stage signal, not mature enterprise infrastructure.

Probable:

- The winner may not be wmux, but the pattern is real.
- Agent workspaces are becoming a separate tooling category.

### Chance for Yps / AXI0M

Potential AXI0M angle:

Agent Ops: controlling multiple AI coding agents without losing auditability, safety, or human command.

Useful as a test subject for agent workspace UX, command/session logging, risky-command boundaries, browser automation controls, and local operator workflow.

### Risk

Do not install on a primary machine without review.
Do not test with real credentials, tokens, production repos, or private client data.
Single GitHub source; needs independent confirmation.

### Watch triggers

- star/fork growth accelerates
- independent discussion appears on HN, Reddit, blogs, newsletters
- release cadence stabilizes
- security model becomes clearer
- similar tools cluster around the same pattern

### Next action

Set to observation and optionally test in a Windows VM with dummy credentials and throwaway repositories.

### What not to do

Do not present it as market proof.
Do not connect real accounts.
Do not treat the repo as safe because the concept is useful.

---

## F-2026-06-18-002 — Budibase/budibase

Status: RESEARCH
Theme: Agent Ops / workflow-action layer
Source: GitHub
URL: https://github.com/Budibase/budibase
Initial score: 23
Classification: SIGNAL, single source

### What it is

Open-source operations platform for apps, automations, and agents. It matters here as a possible reference point for turning agent output into controlled business workflows.

### Why it matters

Budibase sits on the other side of the stack from wmux.

- wmux: local operator workspace for agents.
- Budibase: business workflow/action layer for agents, apps, approvals, and automations.

Together they sketch:

Sensor -> Lagebild -> Workflow -> Approval -> Reaction -> Audit

### First research

Known:

- Public GitHub project with large footprint.
- Positions itself around operations, automations, apps, and agents.
- Relevant to self-hosting, internal tooling, and process automation.

Probable:

- Budibase-style systems may become the action layer for business AI.
- Even if AXI0M does not use Budibase, its pattern is strategically relevant.

### Chance for Yps / AXI0M

Potential AXI0M angle:

From monitoring to controlled reaction: AI-assisted workflows with approvals, audit, and human authority.

Could inform the Senna Action Console roadmap: event intake, evidence capture, scenario analysis, review status, reaction draft, approval gate, audit trail.

### Risk

Do not attach real customer data or production systems too early.
Check license and deployment implications before reuse.
Workflow platforms can accidentally give agents too much authority.
Business-action tooling needs explicit approval gates.

### Watch triggers

- Budibase agent features gain traction
- similar open-source workflow-agent tools cluster
- integration patterns emerge for GitHub, Slack, Jira, email, CRM
- governance / audit / approval features become central

### Next action

Keep as reference architecture. Design an AXI0M/Senna workflow schema before choosing any platform.

### What not to do

Do not make Budibase "the solution" before testing.
Do not wire it into external actions without approval gates.
Do not treat agent workflow automation as harmless because it looks like admin UI.

---

## Synthesized pattern

The opportunity is not "more agents".

The opportunity is:

Agents need legible command structures.

That is where Yps' Senna Infoflow and Action Console can become more than monitoring.

END OF DOCUMENT
