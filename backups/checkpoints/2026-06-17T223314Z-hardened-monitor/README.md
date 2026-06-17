# Backup Checkpoint — Senna Infoflow Hardened Monitor

MODE: BACKUP CHECKPOINT
STATUS: CREATED
CREATED_AT: 2026-06-17T22:33:14Z
SOURCE_REPO: Question86/senna-infoflow
SOURCE_BRANCH: main
SOURCE_HEAD_COMMIT: 94a6e08f89a97a9af676cc7c3ec07ed3dba58b19
TRIGGER_RUN: 27724011031

---

## PURPOSE

This checkpoint preserves the current pipeline edge after introducing the hardened monitor wrapper.

It exists so later fast patches can be compared against a known working/intended code state without digging through conversational context.

## DIRECTLY COPIED FILES

- `.github/workflows/monitor.yml`
  - backup: `monitor.workflow.yml`
  - source commit: `94a6e08f89a97a9af676cc7c3ec07ed3dba58b19`

- `scripts/run_monitor_hardened.py`
  - backup: `run_monitor_hardened.py`
  - source commit: `cdf9686c9d9a5cc216903f9bfd9b7f0e1aaa712b`
  - active in workflow since commit: `94a6e08f89a97a9af676cc7c3ec07ed3dba58b19`

## PIPELINE STATE AT CHECKPOINT

Current intended order:

```text
Merge hot-lane sources
→ Validate monitor configuration
→ Run hardened monitor
→ Run network hub postprocess
→ Write canonical report atoms and trend samples
→ Harden state and outputs
→ Commit generated briefings
```

## KNOWN RISK AT CHECKPOINT

Run #17 was still `in_progress` during checkpoint creation.

The likely next fix is not more retry. It is runtime containment:

```text
- cap effective HTTP timeout
- reduce retry attempts
- set GitHub Actions step timeout-minutes
- mark slow sources degraded instead of letting one source dominate cadence
```

## RESTORE NOTES

To restore this checkpoint manually:

```bash
cp backups/checkpoints/2026-06-17T223314Z-hardened-monitor/monitor.workflow.yml .github/workflows/monitor.yml
cp backups/checkpoints/2026-06-17T223314Z-hardened-monitor/run_monitor_hardened.py scripts/run_monitor_hardened.py
```

Then commit and dispatch `monitor.yml`.

---

END OF DOCUMENT
