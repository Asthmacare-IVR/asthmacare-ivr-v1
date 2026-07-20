# PROJECT_STATE.md — AsthmaCare IVR Platform

**Generated:** 2026-07-15 (post-audit merge)
**Scope of this audit:** `database/` (Repository Interface, SQLite Repository,
In-Memory/Mock Repository) — Phases 5, 5.1, and 6.

---

## 1. What this audit did

Three uploads were provided: `Projects.zip` (the live `Asthmacare-IVR` git
repo plus phase archives), `files__3_.zip` (two nested zips —
`asthmacare_database_phase6_audited.zip` and `changed_files.zip` — from a
prior session), and `New_Text_Document.txt` (a prior session's exported
transcript).

Steps taken:

1. Extracted and diffed `changed_files.zip` against
   `asthmacare_database_phase6_audited.zip` — **identical**, confirming the
   "audited" zip is the complete, current state of that prior session's work
   (not a stale pre-change snapshot).
2. Diffed the "audited" zip against this conversation's own earlier Phase 6
   deliverable — only 7 files differ (see §3); everything else is
   byte-identical.
3. Read every changed/new file in full.
4. Ran the full existing contract-test logic and new migration/concurrency/
   standalone-repository/error-translation-regression logic via a manual
   Python harness (**pytest itself is not installable in this sandbox — no
   network access** — so a hand-written equivalent harness was used instead;
   see §7 Known Issues). All checks passed against both SQLite and in-memory
   implementations.
5. Verified every module under `database/` imports cleanly with no circular
   or broken imports, both standalone and from the live repo root.
6. Merged the audited `database/`, `tests/`, and `docs/ADR-005-*.md` into the
   live `Asthmacare-IVR` repo, replacing only the Phase 2 placeholder stub
   `database/__init__.py` — no other existing file (docs, config/, api/,
   queue_engine, telephony/, dashboard/) was modified except `pyproject.toml`
   (one line added, see §3).
7. Re-ran every check from the project root to confirm the merge introduced
   no regressions.

---

## 2. ⚠️ Unresolved fork — read this before continuing (see §8 for full detail)

The prior session's transcript describes being handed an actual
**`repository_interface.py` Python file** (not the markdown
`docs/REPOSITORY_INTERFACE.md`) that defines a **materially different**
contract: `QueueEntryState` (not `QueueState`), `PatientDraft`/
`QueueEntryDraft` value objects, a `QueueEntryTransitionRepository`,
`update_state()`/`increment_notification_attempts()`/
`get_active_entry_for_patient()`/`list_by_state()` methods, a
`RepositoryFactory` Protocol, and **repository-generated** identifiers
(contradicting this codebase's caller-supplied-UUID design, and — by the
transcript's own account — contradicting its *own* docstring against
`ADR-005`'s OD-4).

**That `repository_interface.py` file was not included in this upload.**
Only `docs/REPOSITORY_INTERFACE.md` (the markdown architecture doc) is
present, and the merged, tested implementation conforms to *that* document
correctly and completely.

I have **not** attempted to reconstruct or guess at the unseen Python spec
from the transcript's paraphrase — doing so risks building against a
self-contradictory, secondhand description of a file I cannot verify.
**If you want that alternate contract adopted, re-upload
`repository_interface.py` itself** and it can be diffed properly against the
current implementation. Until then, the current, tested, merged code is the
authoritative baseline.

---

## 3. Files changed vs. this conversation's earlier Phase 6 delivery

| File | Change |
|---|---|
| `database/sqlite/__init__.py` | Exports `SqliteRepositories` alongside existing names |
| `database/sqlite/factory.py` | `SqliteRepositoryProvider` gains `.repositories()` — standalone, non-UnitOfWork access path |
| `database/sqlite/unit_of_work.py` | Adds `SqliteRepositories` class (see above) |
| `database/sqlite/queue_entry_repository.py` | `update()`'s optimistic-lock pre-read now goes through `_execute_read` (error-translation-wrapped) instead of a raw `connection.execute()` call — closes a bug where a pre-read failure would leak an untranslated `sqlite3` exception |
| `database/sqlite/schema.py` | DDL extracted to public `SCHEMA_STATEMENTS`; `ensure_schema()` now delegates to the new migration runner |
| `database/sqlite/migrations.py` | **New.** Versioned, idempotent migration runner + `schema_migrations` tracking table |
| `docs/ADR-005-phase6-open-decisions.md` | **New.** Formally closes `SQLITE_REPOSITORY_DESIGN.md` §15's four Open Decisions (OD-1..OD-4) after the fact |
| `tests/test_sqlite_migrations.py` | **New** — migration idempotency/versioning coverage |
| `tests/test_sqlite_concurrency.py` | **New** — multi-threaded writer race coverage |
| `tests/test_sqlite_standalone_repositories.py` | **New** — coverage for the `.repositories()` path |
| `tests/test_queue_entry_repository_error_translation.py` | **New** — regression test for the `update()` fix above |
| `pyproject.toml` (standalone project copy) | version bump only |
| `pyproject.toml` (live repo, this merge) | added `pythonpath = ["."]` under `[tool.pytest.ini_options]` — required so `tests/` can `import database.*` when pytest is run from the repo root (the live repo didn't previously need this since `database/` had no importable code) |

Everything else (domain model, error hierarchy, abstract interfaces,
mapping, error translation, base repository, patient/visit repositories,
in-memory repository + unit of work, and the original contract/unit-of-work
tests) is **byte-identical** to this conversation's earlier delivery — no
unnecessary rewriting occurred.

---

## 4. Current architecture (as merged)

```
Asthmacare-IVR/
├── docs/                          Frozen architecture contracts (Phases 3–5.1) + ADR-005
├── database/
│   ├── domain.py                  Patient, QueueEntry, QueueState, Visit, VisitType
│   ├── errors.py                  RepositoryError hierarchy (NotFound/Conflict/ValidationFailure/Unavailable/Unknown)
│   ├── interfaces.py               Abstract PatientRepository / QueueEntryRepository / VisitRepository / UnitOfWork
│   ├── sqlite/                     Concrete SQLite Repository Interface implementation
│   │   ├── connection.py           Connection lifecycle, TransactionContext, write lock
│   │   ├── schema.py                DDL (SCHEMA_STATEMENTS) — delegates to migrations
│   │   ├── migrations.py            Versioned, idempotent schema application
│   │   ├── mapping.py               row <-> domain object translation
│   │   ├── error_translation.py     sqlite3.* -> database.errors.* translation
│   │   ├── base_repository.py       Shared write/read plumbing (commit-per-call vs. deferred-to-UoW)
│   │   ├── patient_repository.py, queue_entry_repository.py, visit_repository.py
│   │   ├── unit_of_work.py          SqliteUnitOfWork (transaction boundary) + SqliteRepositories (standalone access)
│   │   └── factory.py               SqliteConfig, SqliteRepositoryProvider — the only construction entry point
│   └── memory/                     Mock/In-Memory Repository (same interfaces, same invariants, for Queue Engine tests)
├── tests/                          Contract tests (run against both implementations) + UoW, migration, concurrency, error-translation tests
├── api/, config/, dashboard/, queue_engine, telephony/   Phase 2 placeholders — unchanged, out of scope for this audit
└── pyproject.toml, requirements.txt   pytest 8.3.3 already pinned; pythonpath fix applied
```

Dependency direction matches `DATABASE_DESIGN.md` §5 and
`SYSTEM_ARCHITECTURE.md` §4: `database.sqlite` and `database.memory` are
leaves; only `database.interfaces`/`database.domain`/`database.errors` are
meant to be imported by anything above the Database boundary (`queue_engine`,
`api/` — not yet implemented).

---

## 5. Completed work

- [x] Domain model (Patient, QueueEntry w/ QUEUE_RULES.md's 10 states, Visit)
- [x] Closed error vocabulary (5 categories) with full SQLite translation coverage, including a regression fix for a previously-untranslated read path
- [x] Abstract Repository Interfaces + Unit of Work contract
- [x] SQLite concrete repositories for all three aggregates
- [x] Versioned, idempotent SQLite schema migrations
- [x] Transaction boundary (`SqliteUnitOfWork`) with atomicity/rollback verified under both normal exit and exception propagation
- [x] Standalone (non-UnitOfWork) single-operation access path (`SqliteRepositories`)
- [x] Single-writer concurrency serialization, verified under real multi-threaded contention (no lost/corrupted writes; exactly-one-winner on a genuine race)
- [x] Storage-level backstops for two Business Rules invariants (single active queue entry per patient; queue-number uniqueness per day)
- [x] In-Memory/Mock Repository implementing identical contracts/invariants, with snapshot-based rollback
- [x] Contract test suite shared across both implementations
- [x] ADR-005 formally closing SQLITE_REPOSITORY_DESIGN.md §15's four Open Decisions
- [x] Merged into the live repo without disturbing any existing file except the two noted above

---

## 6. Remaining work (unchanged from before this audit — none of it was in scope)

- [ ] Phase 7 — Telephony Adapter (blocked on SIM900A hardware delivery)
- [ ] Phase 8 — Queue Engine (must resolve R-004 — `queue_engine` package shadows stdlib `queue` — before starting; see RISK_REGISTER.md)
- [ ] Phase 9 — Business Rules implementation (currently only documented in `docs/BUSINESS_RULES.md`, not coded)
- [ ] Phase 10 — Admin Dashboard
- [ ] Phase 11 — REST API
- [ ] Phase 12 — Raspberry Pi Deployment (blocked on hardware purchase)
- [ ] Phase 13 — Testing & QA (integration tests spanning Queue Engine → real SQLite, per `DATABASE_DESIGN.md` §9, are explicitly deferred to this phase)
- [ ] A `config/` module that actually calls `database.sqlite.factory.build_unit_of_work(...)` — right now nothing outside `tests/` constructs a `SqliteRepositoryProvider`
- [ ] Contract-test parity check against a future `PostgreSQLRepository`, if/when that migration begins (out of scope for v1.0 per `DATABASE_DESIGN.md` §7)

---

## 7. Known issues

1. **Cannot run `pytest` itself in this sandbox.** No network access here to
   `pip install pytest`, so every check in this audit (and in the original
   Phase 6 delivery) was verified with a hand-written Python harness that
   exercises the same scenarios, not with the actual `pytest` binary.
   `requirements.txt` already pins `pytest==8.3.3`; **run
   `pip install -r requirements.txt && pytest` yourself** to get the real,
   authoritative test run — this has not happened yet on this codebase.
2. **The `repository_interface.py` fork is unresolved** — see §2. No code
   change was made in response to it since the file itself wasn't provided.
3. **R-004 (`queue_engine` shadows stdlib `queue`) is still open** — pre-existing,
   not introduced or affected by this audit, but blocks Phase 8 per
   `RISK_REGISTER.md`.
4. **Optimistic-locking pre-read in `SqliteQueueEntryRepository.update()`**
   has a small window between its `SELECT` and its conditional `UPDATE`
   where a concurrent writer could interleave outside of an explicit
   `SqliteUnitOfWork`'s write-lock hold (the single-writer lock is held for
   the whole block only when a `SqliteUnitOfWork` is used; the standalone
   `SqliteRepositories.update()` path re-acquires the lock only for the
   `UPDATE` statement itself, not the preceding read). The conditional
   `WHERE state = :expected_current_state` clause still prevents a *silent*
   lost update (it raises `ConflictError` instead), so no invariant is
   violated — but under standalone (non-UoW) use, two racing `update()`
   calls could both correctly detect terminal state via the same
   pre-read snapshot before either writes. This is a documented, acceptable
   pilot-scope simplification (single-process, low write volume), not a bug,
   but is worth a comment/ADR if write concurrency increases.
5. **No `config/` wiring exists yet** — `SqliteConfig`/`build_unit_of_work`
   are fully implemented and tested but nothing outside `tests/` calls them.
   This is expected (Phase 8/9 territory) but is the actual reason the
   Database layer, while complete, has zero real callers today.

---

## 8. Full detail on the repository_interface.py fork (for future continuation)

The prior session's transcript (`New_Text_Document.txt`) shows it was given
an uploaded `repository_interface.py` file in *that* conversation and, after
initially flagging "a fundamental architectural mismatch" against the
markdown-doc-conformant implementation, concluded (per its own words) that
the Python file was authoritative because it was "more recent, more
carefully reasoned, and directly cites specific open decisions with explicit
rationale" — despite also noting, in the same breath, that the file
internally contradicts `ADR-005`'s OD-4 (repository-generated vs.
caller-supplied identity). The transcript contains what appear to be partial
or full rewritten modules (e.g., `InMemoryQueueEntryTransitionRepository`)
reflecting that alternate contract, starting roughly two-thirds of the way
through the document.

**None of that rewritten code was included as an actual file in this
upload** — only the transcript's prose/quoted fragments are present, and no
corresponding zip of the rewrite was attached. Reconstructing a full,
consistent implementation from a paraphrased transcript, for a spec file
that (a) isn't available to verify against and (b) was reported as
internally self-contradictory even by the session that was rewriting toward
it, would mean guessing at a moving target rather than implementing a
reviewed contract.

**Recommendation for whoever continues this:** if `repository_interface.py`
is meant to supersede `docs/REPOSITORY_INTERFACE.md`, re-upload that exact
file plus a decision on which of `QueueState`/`QueueEntryState`,
caller-supplied/repository-generated identity, and flat/`interfaces/`
sub-package layout is correct — ideally as a new ADR superseding ADR-005 —
before any further database-layer code changes are made. Until that
happens, treat the merged code in this delivery as the current baseline.

---

## 9. Readiness score

**Database layer (Phases 5 / 5.1 / 6): 90/100**
— fully implemented, tested (via manual harness; real `pytest` run still
pending), migrated, concurrency-verified, and merged cleanly into the live
repo with zero regressions. Points withheld for: the unresolved
`repository_interface.py` fork (§2/§8), the lack of a real `pytest` run in
this environment, and the small standalone-path race window noted in §7.4.

**Overall project (all phases): 22/100**
— only Phases 1–6 have any implementation; Phases 7–14 remain entirely
unstarted per `ROADMAP.md`, several blocked on hardware delivery.
