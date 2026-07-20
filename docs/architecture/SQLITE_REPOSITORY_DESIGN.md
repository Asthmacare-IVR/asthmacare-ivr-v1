# SQLite Repository Design

**Phase:** 5.1
**Milestone:** v0.5.0
**Applies to:** Database Layer — SQLite Repository (pilot)

> **Baseline note:** This document is written for full consistency with the
> approved and frozen `SYSTEM_ARCHITECTURE.md`, `DATABASE_DESIGN.md`,
> `BUSINESS_RULES.md`, `QUEUE_RULES.md`, and `REPOSITORY_INTERFACE.md`. Those
> documents are not reproduced or redefined here — this document assumes
> their contents as the architectural baseline and only describes how the
> SQLite implementation will satisfy them.

---

## 1. Purpose

This document describes the architectural design of the SQLite implementation
of the Repository Interface. It exists to establish *how* the pilot's data
access layer will be structured, isolated, and governed — without specifying
*how it will be coded*. It is a design contract for the implementation work
scheduled in Phase 6, not the implementation itself.

## 2. Scope

In scope:
- The architectural shape of a `SQLiteRepository` component that fulfills the
  Repository Interface
- How this component is composed, initialized, and retired
- How it maps interface-level operations to SQLite-backed storage concepts
- How it handles identity, transactions, errors, and concurrency at a design
  level
- How it stays swappable for a future PostgreSQL-backed repository

Out of scope:
- Any Python, SQL, ORM, or query-level detail
- Any REST/API-facing contract (owned by `api/`, governed separately)
- Any change to the Repository Interface itself
- Any change to Queue Engine or Business Rules behavior

## 3. Architectural Position

The SQLite Repository is a **concrete adapter** that sits behind the
Repository Interface, in the same architectural role that the SIM900A
Adapter occupies behind the Telephony Interface (per ADR-001). It lives
inside the `database/` boundary defined in ADR-002 and participates in the
frozen dependency rule:

```
Dashboard
→ API
→ Queue Engine
→ Repository Interface
→ SQLite Repository
```

The Queue Engine and Business Rules depend only on the Repository Interface,
never on the SQLite Repository directly. This preserves the same Dependency
Inversion boundary already established for telephony, applied symmetrically
to persistence. The SQLite Repository is a leaf node in the dependency
graph: it may depend on SQLite as a storage mechanism, but nothing above the
Database boundary may depend on SQLite.

## 4. Repository Composition

The SQLite Repository is composed, not monolithic. Architecturally it is
made up of:

- A **connection/session boundary**, responsible for owning access to the
  underlying storage engine and for nothing else
- A set of **entity-focused repository units**, each corresponding to a
  repository responsibility defined in `DATABASE_DESIGN.md`, each
  implementing the relevant slice of the Repository Interface for that
  responsibility
- A **shared mapping layer**, responsible for translating between the
  domain-facing shapes defined by the Repository Interface and the
  storage-facing shapes defined by `DATABASE_DESIGN.md`
- A **shared error-translation layer**, responsible for converting
  storage-level failures into the interface-level error vocabulary

No repository unit accesses another repository unit's storage concerns
directly. Coordination across repository units, where required, is an
interface-level concern (e.g. unit-of-work / transaction scope), not an
inter-repository dependency.

## 5. Repository Lifecycle

The SQLite Repository has a well-defined lifecycle, independent of any
individual request:

1. **Construction** — the repository is assembled with its configuration
   (see Section 12) but does not yet hold an open resource.
2. **Activation** — a storage-engine session/connection is acquired,
   scoped to the lifetime the application layer grants it (e.g.
   application-lifetime for the pilot, request-scoped if later required).
3. **Operation** — the repository services calls arriving through the
   Repository Interface for the duration of activation.
4. **Deactivation/Disposal** — the session/connection is released
   deterministically, whether the application shuts down normally or an
   unrecoverable storage error occurs.

This lifecycle is owned entirely within `database/`. Nothing above the
Database boundary is aware of activation or disposal; callers only ever see
the Repository Interface.

## 6. SQLite Responsibilities

SQLite, within this design, is responsible only for:

- Durable storage of the pilot's relational data, per the schema defined in
  `DATABASE_DESIGN.md`
- Enforcing storage-level integrity constraints (uniqueness, referential
  integrity) as a backstop to, not a replacement for, Business Rules
- Providing the transactional primitives the Repository uses to guarantee
  atomicity of multi-step writes

SQLite is explicitly **not** responsible for, and must never be the location
of:

- Queue ordering or scheduling logic (owned by `QUEUE_RULES.md` / Queue
  Engine)
- Eligibility, validation, or workflow rules (owned by `BUSINESS_RULES.md`)
- Any decision that changes the meaning of patient or queue data — the
  Repository stores and retrieves; it does not decide

This restatement is intentional: it is the same non-negotiable boundary
already established for the Telephony Adapter with respect to Queue Engine,
applied to the Database Adapter with respect to Business Rules.

## 7. Interface Mapping Strategy

Each operation exposed by the Repository Interface maps to exactly one
coherent unit of work inside the SQLite Repository. The mapping strategy
follows three principles:

- **One interface operation, one storage transaction.** No interface
  operation spans multiple independently-committed storage transactions.
- **No interface operation is storage-shaped.** The Repository Interface's
  vocabulary (defined in `REPOSITORY_INTERFACE.md`) is preserved exactly;
  the SQLite Repository adapts its internal storage model to the interface,
  not the reverse.
- **No leakage of storage concepts upward.** Table names, row identifiers in
  their storage form, or SQLite-specific constructs never appear in values
  returned across the Repository Interface boundary. Only the domain shapes
  defined in `DATABASE_DESIGN.md`/`REPOSITORY_INTERFACE.md` cross that
  boundary.

## 8. Identity Strategy

Entity identity is defined at the interface/domain level and is treated as
authoritative. The SQLite Repository's internal storage identity (however
`DATABASE_DESIGN.md` defines it) is an implementation detail of persistence,
not a substitute for domain identity.

The design principle is: domain identity is assigned and owned according to
`DATABASE_DESIGN.md`'s identity model; the SQLite Repository's role is to
persist and reliably resolve that identity, not to originate a competing
notion of identity that leaks into Queue Engine or Business Rules.

Where the identity model calls for identifiers to be generated at write time,
generation happens inside the Database boundary, before the identifier is
handed back across the Repository Interface — callers never construct or
guess identifiers themselves.

Repository-generated identities, once assigned, must remain stable for the
lifetime of the entity and across future storage migrations.

## 9. Transaction Strategy

Transaction boundaries are owned by the SQLite Repository, not by callers.
The design principles are:

- **Atomicity per interface operation**, as stated in Section 7.
- **No open-ended transactions.** A transaction's lifetime is bounded by a
  single Repository Interface call (or, where the interface explicitly
  defines a unit-of-work concept, by that unit of work) — it is never left
  open across unrelated calls.
- **Isolation from Queue Engine timing.** The Queue Engine's ordering and
  scheduling semantics (`QUEUE_RULES.md`) are logically independent of
  storage transaction boundaries; the Repository does not assume anything
  about Queue Engine call ordering, and the Queue Engine does not assume
  anything about SQLite's internal locking behavior.
- **Fail-closed semantics.** If a transaction cannot be committed in full,
  no partial effect is observable through the Repository Interface.

## 10. Error Translation Strategy

Storage-level failures are never surfaced to callers in their native form.
The SQLite Repository's error-translation layer (Section 4) is responsible
for mapping every storage-level failure mode into the error vocabulary
already defined by `REPOSITORY_INTERFACE.md`.

Design principles:

- **Closed vocabulary.** Callers only ever observe the finite set of error
  conditions the Repository Interface defines (e.g. not-found, conflict,
  constraint-violation, unavailable) — never a storage-engine-specific
  failure type.
- **No silent downgrade.** A failure is never swallowed or converted into a
  successful-looking result; ambiguous storage states are translated to the
  most conservative applicable interface error.
- **No business meaning added at translation time.** The translation layer
  reports *that* a storage-level condition occurred; it does not decide what
  that condition *means* for a patient or a queue — that judgment remains
  with Business Rules and Queue Engine, consistent with Section 6.

## 11. Concurrency Model

The pilot's concurrency model is deliberately conservative, matching the
pilot's single-instance deployment target (Raspberry Pi, Phase 12) and
SQLite's own concurrency characteristics:

- The SQLite Repository assumes a **single-writer** environment for the
  pilot. Concurrent readers are accommodated; concurrent writers are
  serialized at the Database boundary rather than pushed upward as a caller
  concern.
- Serialization is a Database-boundary responsibility. Queue Engine issues
  Repository Interface calls without needing to reason about locking,
  retries, or write contention — that reasoning is fully contained within
  `database/`.
- This model is explicitly scoped to the pilot. It is not assumed to hold
  once a multi-instance or networked-database deployment (Section 13) is
  introduced; concurrency assumptions are revisited at that time, not
  retrofitted silently.

The Queue Engine must never implement retry logic for storage contention;
retry behavior, if required, belongs entirely within the Database boundary.

## 12. Configuration

The SQLite Repository is configured, not hard-wired, consistent with the
`config/` boundary defined in ADR-002. Configuration concerns include:

- Location/identity of the SQLite storage file, following the pilot
  constraint (SQLite, per `DATABASE_DESIGN.md` and ADR-001) that this is the
  only implementation target for the pilot
- Lifecycle parameters (Section 5), such as whether activation is
  application-scoped or request-scoped
- Any operational parameters `DATABASE_DESIGN.md` reserves for the storage
  engine (e.g. durability/synchronization posture)

Configuration values are supplied to the Repository at construction time by
`config/`; the Repository does not read its own configuration from the
environment directly. This keeps the Database boundary consistent with how
every other adapter in the system is configured.

## 13. Future PostgreSQL Compatibility

Per ADR-001, PostgreSQL is a documented future production migration target
and must not influence pilot implementation decisions. This design supports
that future without anticipating it prematurely:

- Because Queue Engine and Business Rules depend only on the Repository
  Interface (Section 3), a future PostgreSQL Repository is a second concrete
  adapter behind the same interface — not a rewrite of anything above the
  Database boundary.
- The mapping (Section 7), identity (Section 8), transaction (Section 9),
  and error-translation (Section 10) *strategies* are written engine-
  agnostically on purpose, so that a PostgreSQL implementation can follow the
  same strategies with different mechanics.
- The concurrency model (Section 11) is explicitly flagged as
  pilot-specific and SQLite-specific; a PostgreSQL adapter is expected to
  define its own concurrency model rather than inherit this one.
- No PostgreSQL-specific facility, extension, or assumption is introduced at
  this phase. This section records compatibility intent only, per ADR-001 —
  it authorizes no implementation work.

## 14. Testing Strategy

Testing of the SQLite Repository is scoped at the architecture level as
follows:

- **Interface-conformance testing.** The primary test obligation is that the
  SQLite Repository satisfies the Repository Interface's observable
  contract — the same test suite shape should be reusable, unchanged,
  against any future concrete repository (including a future PostgreSQL
  repository), per Section 13.
- **Isolation testing.** Tests must confirm that Queue Engine and Business
  Rules can be exercised against a substitute/in-memory repository without
  requiring SQLite, verifying the Dependency Inversion boundary in Section 3
  is real and not merely documented.
- **Failure-mode testing.** Tests must confirm the error-translation layer
  (Section 10) maps storage failures onto the correct interface-level error
  vocabulary, not onto engine-specific exceptions.
- Concrete test tooling, fixtures, and file organization are Phase 6
  implementation concerns and are intentionally not specified here.

All future repository implementations (SQLite and PostgreSQL) must satisfy
the same contract test suite before being considered compliant.

## 15. Open Decisions

The following are flagged for resolution before or during Phase 6 and are
not settled by this document:

- **OD-1:** Exact lifecycle scope for Section 5 (application-scoped vs.
  request-scoped activation) — depends on final shape of the FastAPI request
  lifecycle, not yet implemented.
- **OD-2:** Whether unit-of-work spanning multiple Repository Interface
  calls is required by any Business Rule not yet exercised in
  `BUSINESS_RULES.md`, which would affect Section 9.
- **OD-3:** Interaction between R-004 (top-level `queue/` package shadowing
  stdlib `queue`, per `RISK_REGISTER.md`) and any Database-layer module
  naming — to be confirmed clear of collision before Phase 6 begins.
- **OD-4:** Whether `DATABASE_DESIGN.md`'s identity model requires
  Repository-generated identifiers (Section 8) or accepts caller-supplied
  identifiers for any entity — should be reconfirmed directly against
  `DATABASE_DESIGN.md` before implementation.

These are design questions, not implementation bugs; none of them block
freezing this document, but all must be closed before Phase 6 implementation
begins.

## 16. Architecture Diagram

```
                        Dashboard
                            |
                            v
                           API
                            |
                            v
                       Queue Engine
                            |
                            v
                      Business Rules
                            |
                            v
                  Repository Interface  (contract; database/)
                            ^
                            |
                    +-------+--------+
                    |                |
             SQLite Repository   (future) PostgreSQL Repository
             (Phase 5.1 design)      (out of scope, v1.0)
                    |
                    v
             SQLite Storage Engine
```

Queue Engine and Business Rules depend only on the Repository Interface.
The SQLite Repository is one interchangeable implementation behind it,
mirroring the Telephony Interface / SIM900A Adapter relationship
established in ADR-001.

## 17. Sequence Diagram

Representative flow for a single Repository Interface call originating in
Business Rules (no method names implied; this illustrates control flow
only):

```
Business Rules        Repository Interface      SQLite Repository        SQLite Engine
     |                        |                        |                      |
     |--- request (domain shape) -------------------->|                      |
     |                        |                        |--- open txn ------->|
     |                        |                        |--- map request ---->|
     |                        |                        |    to storage ops   |
     |                        |                        |--- execute -------->|
     |                        |                        |<-- storage result --|
     |                        |                        |--- commit txn ----->|
     |                        |                        |<-- ack -------------|
     |                        |                        |--- map result ------|
     |                        |                        |    to domain shape  |
     |<-- response (domain shape) --------------------|                      |
     |                        |                        |                      |

Failure path (storage-level failure):
     |--- request ----------------------------------->|                      |
     |                        |                        |--- execute -------->|
     |                        |                        |<-- storage failure -|
     |                        |                        |--- rollback txn --->|
     |                        |                        |--- translate error -|
     |                        |                        |    (Section 10)     |
     |<-- interface-level error ------------------------|                    |
```

Business Rules never observes SQLite directly, in either the success or
failure path — every observable outcome is expressed in the Repository
Interface's own vocabulary.

## 18. Freeze Status

Status:
Phase 5.1 — SQLite Repository Design

Architecture Status:
Frozen

Implementation:
Not Started

Next Phase:
Phase 6 — SQLite Repository Implementation
