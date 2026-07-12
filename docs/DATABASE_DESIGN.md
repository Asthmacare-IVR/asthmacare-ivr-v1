# Database Design — Data Access Architecture

**Status:** Phase 3.1 — Frozen for Pilot v1.0 (architecture only; no implementation)
**Related decisions:** ADR-004 (Data Access Layer Architecture)
**Related documents:** `docs/SYSTEM_ARCHITECTURE.md` (Phase 3), `docs/DECISION_LOG.md`

---

## 1. Purpose

This document defines how the Queue Engine (and, indirectly, the REST API)
accesses persisted data, without ever knowing which database technology is
actually storing it. It exists to satisfy a specific, frozen requirement:

> Replacing SQLite (pilot) with PostgreSQL (future production target) must
> not require changes to the Queue Engine, Business Rules, REST API, or
> Dashboard.

This is the data-layer counterpart to the Telephony Interface pattern
already frozen in `docs/SYSTEM_ARCHITECTURE.md` §3 — the same Dependency
Inversion technique applied to persistence instead of telephony.

This document covers **architecture only**. No Python classes, no SQL, no
schema, no table definitions, no CRUD methods. Those belong to Phase 5
(Database Design — Implementation), which will build directly on top of the
contracts frozen here.

---

## 2. Database Layer Overview

The `database/` module (see `docs/SYSTEM_ARCHITECTURE.md` §4 for its
position in the overall dependency graph) is internally split into two
conceptual halves:

1. **Repository Interfaces** — abstract contracts describing *what* data
   operations the Queue Engine needs (e.g. "find the next patient in
   queue"), without saying *how* they're performed.
2. **Concrete Repositories** — implementations of those contracts against a
   specific storage technology (SQLite for the pilot; PostgreSQL for a
   future production deployment).

The Queue Engine only ever talks to (1). It never imports, references, or
has any awareness of (2).

---

## 3. Repository Pattern — Why DAO / Repository Is Chosen

### Problem
The Queue Engine needs to read and write patient/queue data. If it calls
SQLite directly (e.g. `sqlite3.connect(...)`, raw SQL strings inline in
business logic), two problems follow:

- **Coupling:** Business logic and storage logic become entangled. A change
  to how data is stored (e.g. adding an index, changing a column type)
  risks touching code that has nothing to do with persistence.
- **Migration cost:** The frozen requirement to move to PostgreSQL later
  without touching the Queue Engine becomes impossible if the Queue Engine
  contains SQLite-specific code (connection handling, SQLite-flavored SQL,
  `sqlite3`-specific error types).

### Options Considered

| Option | Description |
|---|---|
| A. Direct SQLite calls in Queue Engine | Simplest to write initially |
| B. Active Record pattern (model objects that save themselves) | Common in some frameworks (e.g. Django ORM) |
| C. Repository / DAO pattern (this decision) | Queue Engine depends only on an abstract repository interface; concrete repositories implement it |
| D. Full ORM (e.g. SQLAlchemy) with Queue Engine using ORM models directly | Reduces boilerplate but couples business logic to ORM's query API |

### Decision
**Option C — Repository / DAO pattern**, mirroring the Telephony Interface
pattern already frozen for the telephony layer.

### Rationale
- **Consistency:** The project already committed to Dependency Inversion for
  telephony (ADR-001, `docs/SYSTEM_ARCHITECTURE.md` §3). Applying the same
  pattern to persistence keeps the codebase's architectural style uniform —
  one mental model for "how do we swap an external dependency," not two.
- **Testability:** The Queue Engine can be tested against an in-memory fake
  repository with zero real database involved, matching how it will be
  tested against a `MockAdapter` for telephony (see
  `docs/SYSTEM_ARCHITECTURE.md` §4 rationale).
- **Migration isolation:** SQLite → PostgreSQL becomes "write a new
  concrete repository," not "rewrite the Queue Engine."
- **Rejects Option A:** Directly violates the frozen non-negotiable
  requirement.
- **Rejects Option B (Active Record):** Model objects that know how to
  persist themselves re-couple business data and storage mechanics — the
  same coupling problem as Option A, just spread across model classes
  instead of centralized in the Queue Engine.
- **Rejects Option D (ORM-in-business-logic):** An ORM's query builder
  (e.g. SQLAlchemy `Session.query(...)`) is itself a storage-technology
  detail. If the Queue Engine calls it directly, swapping databases can
  still require query-level changes (dialect differences, session
  lifecycle). Wrapping the ORM *inside* a concrete repository (i.e., using
  an ORM as an implementation detail of Option C) remains open for Phase 5
  and is **not precluded** by this decision — see §10 Open Decisions.

### Trade-offs
- More upfront structure (an interface plus at least one implementation)
  than directly calling SQLite — acceptable given the pilot has already
  accepted equivalent overhead for telephony.
- Repository interfaces must be designed carefully enough to not leak
  SQLite-specific concepts (e.g. rowids, SQLite-specific error codes) into
  their method signatures, or the abstraction leaks and migration cost
  returns. This is a design discipline concern for Phase 5, not solved by
  the pattern alone.

### Future Impact
Phase 5 implements `SQLiteRepository` classes conforming to the interfaces
frozen here. A future (out-of-scope-for-v1.0) migration phase implements
`PostgreSQLRepository` classes conforming to the same interfaces — no
change to `queue_engine/`, `api/`, or business rules.

---

## 4. Architecture Diagram

```
                    ┌───────────────────┐
                    │   Queue Engine     │
                    │  (queue_engine/)   │
                    └─────────┬──────────┘
                              │ depends on (calls methods on)
                              ▼
                ┌─────────────────────────────┐
                │  Repository Interface(s)     │
                │  (database/ — abstract)      │
                │  — contract, no SQL —        │
                └─────────────▲─────────────────┘
                              │ implements
              ┌───────────────┼────────────────┐
              │                                │
   ┌──────────┴───────────┐         ┌──────────┴────────────┐
   │  SQLiteRepository     │         │  PostgreSQLRepository  │
   │  (Pilot — Phase 5)    │         │  (future, out of v1.0) │
   └────────────────────────┘         └─────────────────────────┘
```

This mirrors `docs/SYSTEM_ARCHITECTURE.md` §3.3 exactly — same shape,
different domain (persistence instead of telephony). This symmetry is
intentional (see §3 Rationale above).

---

## 5. Dependency Rules

| Module | May depend on | Must never depend on |
|---|---|---|
| `queue_engine/` | Repository Interface(s) in `database/` | `SQLiteRepository`, any concrete repository, `sqlite3` module directly, any SQL string |
| `api/` | `queue_engine/` (goes through Queue Engine, not around it) | `database/` directly |
| Repository Interface (`database/`, abstract) | (nothing internal) | Any concrete repository, any storage-specific library |
| `SQLiteRepository` (Phase 5) | Repository Interface it implements, `sqlite3` (or chosen driver) | `queue_engine/`, `api/`, `telephony/` |
| `PostgreSQLRepository` (future) | Same Repository Interface, PostgreSQL driver | `queue_engine/`, `api/`, `telephony/` |

**Forbidden, explicitly:** `queue_engine/` importing `sqlite3`, importing a
concrete repository class, or containing any raw SQL string. This is the
data-layer equivalent of the telephony rule "Queue Engine must never import
a concrete adapter" (`docs/SYSTEM_ARCHITECTURE.md` §3.4), and will be
subject to the same future code-review / architecture-test enforcement
question raised there (see §10).

---

## 6. Repository Interfaces (Concept Only — No Implementation)

At the concept level, the Queue Engine will need repository interfaces
covering at minimum:

- A **Patient/Queue Repository** — concept: retrieving, adding, and
  updating queue entries, without specifying method signatures, return
  types, or storage representation.
- Possibly a separate **Appointment Repository** if Business Rules (Phase
  4) distinguish "queue position" from "appointment record" as separate
  concerns — **this split is not decided here** and is deferred to Phase 4
  (Business Rules must exist first to know what data the Queue Engine
  actually needs to persist).

**Explicitly out of scope for this document:** method names, parameter
types, return types, exception types, or how many interfaces there will be.
Designing these prematurely — before Business Rules (Phase 4) defines what
data the domain actually contains — risks the same speculative-generality
problem already flagged for the Telephony Interface in
`docs/SYSTEM_ARCHITECTURE.md` §3.3. The interfaces are designed at the
start of Phase 5, informed by Phase 4's output.

---

## 7. Future PostgreSQL Migration

Because the Queue Engine depends only on the Repository Interface (§4, §5),
migrating from SQLite to PostgreSQL in a future release consists of:

1. Implementing a new `PostgreSQLRepository` class conforming to the same
   Repository Interface(s) defined in Phase 5.
2. Changing a single configuration point (in `config/`, per
   `docs/SYSTEM_ARCHITECTURE.md` §4) that selects which concrete repository
   is instantiated at startup — a dependency-injection wiring concern, not
   a Queue Engine concern.
3. Running a data migration (SQLite → PostgreSQL data transfer) — an
   operational task, not an architectural one, and out of scope for this
   document.

No change to `queue_engine/`, `api/`, business rules, or `dashboard/` is
required. This is the direct payoff of the Repository pattern chosen in §3,
and mirrors how Cloud IVR/SIP adapters would be added later without
touching the Queue Engine (`docs/SYSTEM_ARCHITECTURE.md` §3).

**Reaffirmed constraint (per ADR-001):** PostgreSQL remains a documented
future target only. It must not influence any Pilot v1.0 implementation
decision. This document describes *how* the migration would work
architecturally — it does not schedule or begin that migration.

---

## 8. Sequence Diagram

```
Patient Request
      │
      ▼
┌─────────────┐
│ Queue Engine │
└──────┬───────┘
       │ calls Repository Interface method
       │ (e.g. "get next in queue" — concept only)
       ▼
┌───────────────────────┐
│ Repository Interface    │
│ (abstract contract)     │
└──────────┬───────────────┘
           │ dispatched to concrete implementation
           ▼
┌────────────────────┐
│ SQLiteRepository     │
│ (Phase 5)            │
└──────────┬─────────────┘
           │ executes query against
           ▼
┌────────────┐
│   SQLite    │
│  (pilot DB) │
└──────┬──────┘
       │ raw result
       ▼
┌────────────────────┐
│ SQLiteRepository     │
│ (maps raw result to  │
│  domain-level data)  │
└──────────┬─────────────┘
           │ returns domain-level result
           ▼
┌───────────────┐
│ Repository       │
│ Interface         │
└──────────┬─────────┘
           │ returns domain-level result
           ▼
┌──────────────┐
│ Queue Engine  │
└──────┬────────┘
       │
       ▼
    Result
```

**Key point:** the Queue Engine receives domain-level data (whatever shape
Phase 4/5 define), never raw SQLite rows, SQL error objects, or connection
handles. The mapping from raw storage format to domain data happens inside
the concrete repository, not the interface and not the Queue Engine.

---

## 9. Testing Strategy

- **Repository mocking:** The Queue Engine's own tests (Phase 8) will use
  an in-memory fake/mock repository conforming to the Repository Interface
  — analogous to the `MockAdapter` already planned for telephony
  (`docs/SYSTEM_ARCHITECTURE.md` §3.3, §4). This lets Queue Engine logic be
  tested with zero real database dependency.
- **Unit testing (Phase 5):** `SQLiteRepository` is tested in isolation
  against a real (test) SQLite database, verifying it correctly implements
  the Repository Interface contract.
- **Future integration testing:** End-to-end tests exercising Queue Engine
  → Repository Interface → real `SQLiteRepository` → real SQLite file,
  planned for Phase 11 (Testing & QA), not implemented here.
- **Contract testing (proposed, not yet approved):** A shared test suite
  that both `SQLiteRepository` and any future `PostgreSQLRepository` must
  pass, guaranteeing behavioral equivalence across implementations. Raised
  here as a recommendation for Phase 5 planning, not decided now.

---

## 10. Open Decisions (Postponed to Later Phases)

| Item | Deferred to | Reason |
|---|---|---|
| Exact Repository Interface method signatures | Phase 5 | Depends on Business Rules (Phase 4) defining actual domain data |
| Number of repository interfaces (single vs. split by entity) | Phase 5 | Same — depends on Phase 4 output |
| Whether to use an ORM (e.g. SQLAlchemy) inside `SQLiteRepository`, or raw `sqlite3` | Phase 5 | Implementation detail; either choice satisfies this architecture as long as it stays behind the Repository Interface |
| Automated architecture-boundary enforcement (e.g. import-linter check preventing `queue_engine/` from importing `sqlite3`) | Phase 5 or 8 | Same open question already raised for telephony boundary enforcement in `docs/SYSTEM_ARCHITECTURE.md` §6 — will be proposed together via a single tooling ADR rather than decided piecemeal |
| Contract test suite shared across repository implementations | Phase 5 | Recommendation only; needs explicit approval before adoption |
| Whether Appointment data and Queue-position data are one repository or two | Phase 4/5 boundary | Depends on Business Rules output |
