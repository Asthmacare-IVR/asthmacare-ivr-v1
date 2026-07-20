# 01 — Project Status

**As of:** 2026-07-20 (R006 repository restructuring / Queue Engine merge)

## Review-package ↔ project-phase mapping (flagged assumption)

The project's own phase tracking (`docs/roadmap/ROADMAP.md`,
`docs/roadmap/PROJECT_PROGRESS.md`) uses decimal phase numbers (1, 2, 3,
3.1, 4, 4.1, 5, 5.1, 6, 7 …). The restructuring brief for this merge instead
asked for six review packages, `R001`–`R006`, and named the incoming Queue
Engine package "the approved R006 implementation". To reconcile the two
without inventing new phases or renumbering the frozen roadmap, this
restructuring maps them as follows — **flagged here for confirmation, same
as the project's own convention** (see the original `docs/README.md` Phase 2
note, preserved in the reorganized `docs/README.md`):

| Review | Phase(s) covered | Status |
|---|---|---|
| R001 | Phase 1 — Development Environment | Completed |
| R002 | Phase 2 — Project Foundation | Completed |
| R003 | Phase 3 / 3.1 — System Architecture, Database Design | Completed |
| R004 | Phase 4 / 4.1 — Business Rules, Queue Rules | Completed |
| R005 | Phase 5 / 5.1 / 6 — Repository Interface, SQLite Repository Design & Implementation | Approved / Implemented |
| R006 | Queue Engine (this merge) | Implemented (Pending Hardening) |

See `docs/roadmap/PROJECT_PHASE_STATUS.md` for the current phase-by-phase
snapshot in the roadmap's own numbering.

## Headline status

- **Implemented and merged:** Development environment, folder structure,
  frozen architecture/business-rule documentation, the full database
  (Repository Interface) layer with SQLite + in-memory implementations, and
  now the Queue Engine core (state machine, ordering, retry, timeout,
  events, orchestration).
- **Not yet started:** Telephony Adapter concrete implementation (blocked on
  SIM900A hardware delivery), Business Rules runtime enforcement wiring,
  Admin Dashboard, REST API, Raspberry Pi deployment, formal Testing & QA
  phase.
- **Open item carried into this merge:** one test-fixture defect in the
  delivered Queue Engine test package (see `02_Architecture_Baseline.md` and
  `07_Open_Issues.md`).

## Repository restructuring summary

This merge also reorganized the repository layout (moving documentation into
`docs/{adr,architecture,roadmap,reviews}/`, grouping placeholder modules
under `backend/`, and renaming `queue_engine` → `queue_engine/` per ADR-006) without
altering any business logic, architecture decision, or existing test. Full
detail: `PROJECT_RESTRUCTURE_REPORT.md` at the repository root.
