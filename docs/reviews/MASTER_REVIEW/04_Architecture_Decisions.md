# 04 — Architecture Decisions (Design Rules in Force)

These are the standing design rules the codebase must continue to satisfy,
consolidated from `docs/architecture/*` and `docs/adr/*` for quick reference
during future reviews. This is a summary index, not a replacement for the
source documents.

1. **Repository pattern isolates persistence.** `queue_engine/` never
   imports a concrete repository (`database.sqlite.*`, `database.memory.*`)
   — only `database.interfaces` / `database.domain`
   (`docs/architecture/DATABASE_DESIGN.md`, `docs/architecture/
   REPOSITORY_INTERFACE.md`).
2. **Telephony is abstracted behind an interface.** No concrete adapter
   (SIM900A, Cloud IVR) may be imported from `queue_engine/`
   (`docs/architecture/SYSTEM_ARCHITECTURE.md`).
3. **Business Rules vs. Queue Rules authority hierarchy** — see
   `02_Architecture_Baseline.md`.
4. **Domain objects are immutable** (frozen dataclasses); updates are
   expressed via `dataclasses.replace`, never in-place mutation
   (`database/domain.py`, `docs/architecture/REPOSITORY_INTERFACE.md` §6).
5. **Closed error vocabulary** — five categories (NotFound, Conflict,
   ValidationFailure, Unavailable, Unknown), with full SQLite-to-domain
   translation coverage (`database/errors.py`,
   `database/sqlite/error_translation.py`).
6. **Queue position is computed, not stored**
   (`docs/architecture/QUEUE_RULES.md` §6.3, `queue_engine/ordering.py`).
7. **Terminal queue states are immutable** — no outgoing transitions from
   `COMPLETED`, `NO_SHOW`, `CANCELLED`, `EXPIRED`
   (`database/domain.py::TERMINAL_QUEUE_STATES`,
   `queue_engine/state_machine.py`).
8. **Every state transition emits exactly one event**
   (`docs/architecture/QUEUE_RULES.md` §9 Invariant 7,
   `queue_engine/events.py`).
9. **Single-writer concurrency model for the SQLite pilot** — documented
   and verified under real multi-threaded contention
   (`docs/architecture/SQLITE_REPOSITORY_DESIGN.md`,
   `tests/test_sqlite_concurrency.py`).
10. **Package naming must not shadow the Python standard library** —
    established retroactively via ADR-006 after R-004 was raised; applies
    going forward to any new top-level package.
