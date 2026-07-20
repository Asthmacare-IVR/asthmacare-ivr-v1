# Project Phase Status

**Snapshot as of:** 2026-07-20 (R006 Queue Engine merge / repository
restructuring)

This is a living status snapshot, supplementary to the frozen
`docs/roadmap/ROADMAP.md` (v1.0), which is left unedited per this
restructuring's "do not remove/rewrite existing documentation" scope. Where
the two disagree, this file reflects the actual current state; `ROADMAP.md`
reflects the originally approved phase plan and gating.

| Phase | Name | Roadmap (frozen) status | Actual status |
|---|---|---|---|
| 1 | Development Environment | Complete | Completed |
| 2 | Project Foundation | Complete | Completed (folders since regrouped under `backend/`, see restructure report) |
| 3 | System Architecture | Complete | Completed |
| 3.1 | Database Design | Complete | Completed |
| 4 | Business Rules | Complete | Completed |
| 4.1 | Queue Rules | Complete | Completed |
| 5 | Repository Interface | Complete | Completed |
| 5.1 | SQLite Repository Design | Complete | Completed |
| 6 | SQLite Repository Implementation | Not Started | **Implemented** (audited, merged — `docs/reviews/R005/`) |
| 7 | SIM900A Hardware | Blocked (hardware not delivered) | Blocked (unchanged) |
| 8 | Telephony Adapter | Not Started | Not Started (unchanged) |
| 9 | Queue Engine | Not Started | **Implemented, pending hardening** (`docs/reviews/R006/`) |
| 10 | Admin Dashboard | Not Started | Not Started |
| 11 | REST API | Not Started | Not Started |
| 12 | Raspberry Pi Deployment | Blocked (hardware not purchased) | Blocked (unchanged) |
| 13 | Testing & QA | Not Started | Not Started (a real `pytest` run is still outstanding — see Open Issue I-2) |
| 14 | Pilot Release (v1.0.0) | Not Started | Not Started |

## Review-package view (R001–R006)

- R001 — Completed
- R002 — Completed
- R003 — Completed
- R004 — Completed
- R005 — Approved
- R006 — Implemented (Pending Hardening)

**Next:**
- R006.1 — Hardening (fix Queue Engine integration test fixture, run real
  `pytest`, add SQLite-backed Queue Engine integration coverage)
- R007 — Service Layer / Telephony Adapter

See `docs/reviews/MASTER_REVIEW/09_Next_Phases.md` for the full forward plan
and `docs/reviews/MASTER_REVIEW/07_Open_Issues.md` /
`08_Action_Items.md` for what is blocking each step.
