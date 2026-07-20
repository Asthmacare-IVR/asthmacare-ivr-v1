# 10 — MASTER BASELINE v1.0

This document is the single consolidated baseline for the repository as of
the R006 (Queue Engine) merge and restructuring. It supersedes nothing —
every source document it summarizes remains in place at the paths listed
below.

## Baseline components

| Layer | Status | Authoritative source |
|---|---|---|
| Development environment | Frozen | `docs/reviews/R001/README.md` |
| Folder structure | Frozen (regrouped under `backend/` — see restructuring report) | `docs/reviews/R002/README.md`, ADR-002 |
| System architecture | Frozen | `docs/architecture/SYSTEM_ARCHITECTURE.md` |
| Database design | Frozen | `docs/architecture/DATABASE_DESIGN.md` |
| Business rules | Frozen | `docs/architecture/BUSINESS_RULES.md` |
| Queue rules / state machine | Frozen | `docs/architecture/QUEUE_RULES.md`, `docs/architecture/QUEUE_STATE_MACHINE.md` |
| Repository interface | Frozen | `docs/architecture/REPOSITORY_INTERFACE.md` |
| SQLite repository design | Frozen | `docs/architecture/SQLITE_REPOSITORY_DESIGN.md` |
| Database implementation | Implemented, tested (manual harness), merged | `database/`, `docs/reviews/R005/` |
| Queue Engine implementation | Implemented, merged, one open test defect | `queue_engine/`, `docs/reviews/R006/QUEUE_ENGINE_REVIEW.md` |
| Telephony abstraction | Interface only — no concrete adapter | `telephony/` |
| Admin Dashboard, REST API, Config wiring | Not started (placeholders) | `backend/dashboard/`, `backend/api/`, `backend/config/` |

## Approved decisions in force (see `03_Approved_ADRs.md` for detail)

D-001, D-002, ADR-001 through ADR-006 — all applied, none superseded by this
restructuring.

## Known open items (see `07_Open_Issues.md` for detail)

I-1 (unresolved `repository_interface.py` fork), I-2 (no real `pytest` run
yet performed), I-3 (Queue Engine integration test fixture defect), I-4
(documented standalone-update race window), I-5 (`config/` not wired), I-6
(`ROADMAP.md` stale relative to actual progress).

## What changed to produce this baseline

This restructuring **moved documentation into subject-area folders,
grouped placeholder modules under `backend/`, and merged in the
pre-approved Queue Engine package (including its pre-requisite `queue/` →
`queue_engine/` rename)**. It did not alter any architecture decision,
business rule, test, or piece of application logic. Full move-by-move
accounting: `PROJECT_RESTRUCTURE_REPORT.md` at the repository root.

## Version

This baseline corresponds to `CHANGELOG.md`'s next entry (Queue Engine
merge / repository restructuring) — see the repository root `CHANGELOG.md`
for the exact version tag once assigned by the Product Owner.
