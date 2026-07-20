# ADR-005: Phase 6 Resolution of SQLITE_REPOSITORY_DESIGN.md §15 Open Decisions

**Status:** Accepted
**Phase:** 6 — SQLite Repository Implementation
**Context documents:** `SQLITE_REPOSITORY_DESIGN.md` §15, `REPOSITORY_INTERFACE.md` §12

---

## Context

`SQLITE_REPOSITORY_DESIGN.md` §15 flagged four Open Decisions and stated
they "must be closed before Phase 6 implementation begins." The Phase 6
implementation (this codebase) made concrete choices for all four while
writing the code, but no ADR was recorded at the time to close them
formally. This ADR records those resolutions after the fact, as required
by `QUEUE_RULES.md` §12's change-control precedent and
`SQLITE_REPOSITORY_DESIGN.md`'s own instruction — it does not change any
behavior; it documents behavior the implementation already has.

## Decisions

### OD-1 — Lifecycle scope (application-scoped vs. request-scoped activation)

**Resolved:** Application-scoped. `SqliteConnectionManager` owns one
long-lived connection for the process lifetime, opened once at
`activate()` and closed once at `dispose()`. `database/sqlite/connection.py`
already documents this choice inline; this ADR promotes it from an inline
comment to a recorded decision.

**Rationale:** Matches the pilot's single-process Raspberry Pi deployment
target (`ROADMAP.md` Phase 12) and the single-writer concurrency model
(`SQLITE_REPOSITORY_DESIGN.md` §11). Request-scoped activation would add
per-request connection overhead with no corresponding benefit until a
multi-process deployment is actually adopted — which `SQLITE_REPOSITORY_DESIGN.md`
§13 explicitly treats as a future, not current, concern.

**Revisit when:** the deployment target changes from a single Raspberry
Pi process to something request-scoped connections would materially
benefit (e.g. a multi-worker WSGI/ASGI deployment).

### OD-2 — Unit-of-work spanning multiple Repository Interface calls

**Resolved:** Supported, but not currently required by any ratified
Business Rule. `SqliteUnitOfWork` and `InMemoryUnitOfWork` both implement
the full multi-call transaction boundary (`REPOSITORY_INTERFACE.md` §8),
and `database/sqlite/unit_of_work.py::SqliteRepositories` additionally
provides a standalone, no-explicit-boundary path for the common case of a
single operation — so callers are never forced into a `with uow:` block
they don't need, and the capability exists for callers that do.

**Rationale:** Building the mechanism now (during Phase 6, when it is a
cheap, well-scoped addition) rather than retrofitting it once a
multi-call Business Rule actually appears keeps `queue_engine`/Business Rules
implementation (Phase 8/9) from being blocked on a database-layer change.
No currently-frozen Business Rule requires atomicity across more than one
aggregate write; `tests/test_unit_of_work.py` exercises the mechanism
directly (patient + queue entry created together) to prove it out ahead
of need.

**Revisit when:** a Business Rules revision requires two or more
aggregate writes to be atomic together (e.g., "creating a Visit and its
first Queue Entry must succeed or fail together").

### OD-3 — R-004 (`queue_engine` stdlib shadowing) interaction with Database-layer naming

**Resolved:** No collision. This codebase's top-level package is
`database`, not `queue`; no module inside `database/` or `database/sqlite/`
is named `queue`, `queue.py`, or shadows any standard-library module name.
`RISK_REGISTER.md` R-004 concerns the *separate*, not-yet-implemented
`queue_engine` package (Phase 8/9) and is unaffected by, and does not affect,
this Phase 6 deliverable.

**Rationale:** Verified by direct inspection of every module name under
`database/` (see file listing in the accompanying audit report).

### OD-4 — Repository-generated vs. caller-supplied identifiers

**Resolved:** Caller-supplied. `Patient.patient_id`, `QueueEntry.entry_id`,
and `Visit.visit_id` are all assigned by the calling layer before the
domain object reaches a repository's `add()` method; no repository
implementation (SQLite or in-memory) generates or mutates an identity
value. `queue_entries.queue_number` is the one repository-computed value
in the domain model (via `next_queue_number()`), and it is a distinct
concept from entity identity (`BUSINESS_RULES.md` §5.5) — it is a
sequential business number, not a storage identity, so `SQLITE_REPOSITORY_DESIGN.md`
§8's identity-stability guarantee applies to `entry_id`, not to
`queue_number`.

**Rationale:** `SQLITE_REPOSITORY_DESIGN.md` §8 states identity is "assigned
and owned according to `DATABASE_DESIGN.md`'s identity model," and leaves
open only *whether* generation happens caller-side or repository-side.
Caller-supplied UUIDs (as used throughout `tests/conftest.py`'s domain
object factories) keep identity generation out of the Database boundary
entirely, which is the simpler of the two options and imposes no
constraint on how a future `queue_engine`/Business Rules layer chooses to
generate identifiers (UUID4, ULID, or otherwise) — that choice remains
entirely theirs, with no repository-side coupling.

**Revisit when:** a future requirement needs storage-guaranteed identity
uniqueness independent of caller behavior (e.g., multiple untrusted
callers). The pilot's single-process, single-writer deployment does not
currently need this.

## Consequences

- All four Open Decisions flagged in `SQLITE_REPOSITORY_DESIGN.md` §15
  are now closed and traceable to a decision record, satisfying that
  document's own precondition for Phase 6 implementation.
- No code change results from this ADR — it documents decisions the
  Phase 6 implementation already embodies.
- Future changes to any of OD-1 through OD-4's resolutions must update
  this ADR in the same change, consistent with the precedent set by
  ADR-004.

## Related Documents

- `SQLITE_REPOSITORY_DESIGN.md` §15
- `REPOSITORY_INTERFACE.md` §12
- `RISK_REGISTER.md` R-004
