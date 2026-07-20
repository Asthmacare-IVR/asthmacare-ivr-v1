# R004 — Business Rules & Queue Rules

**Status:** Completed (Frozen)

**Scope:** Phase 4 (Business Rules) and Phase 4.1 (Queue Rules), including
the Queue State Machine extraction.

## Delivered

- `docs/architecture/BUSINESS_RULES.md` — business behavior, independent of
  implementation
- `docs/architecture/QUEUE_RULES.md` — Queue Engine operational states,
  scheduling, ordering, notifications, transitions, execution mechanics
- `docs/architecture/QUEUE_STATE_MACHINE.md` — state machine extracted from
  `QUEUE_RULES.md` as the authoritative Queue Engine design reference
- Authority Hierarchy established (`../../adr/DECISION_LOG.md` preamble):
  Business Rules is authoritative for policy; Queue Rules is authoritative
  for execution mechanics; the Queue Engine implements but never redefines
  Business Rules

## Evidence

- `../../architecture/BUSINESS_RULES.md`
- `../../architecture/QUEUE_RULES.md`
- `../../architecture/QUEUE_STATE_MACHINE.md`
- `../../roadmap/PROJECT_PROGRESS.md` — "Phase 4" section

## Outcome

Frozen, architecture status "Approved", implementation status "Not Started"
at time of freeze — implementation later delivered as R005 (Repository/
Database layer) and R006 (Queue Engine). No open findings recorded.
