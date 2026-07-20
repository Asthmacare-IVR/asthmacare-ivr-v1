# Repository Interface Design

**Document Type:** Architecture Contract
**Phase:** 5 — Repository Interface Design
**Baseline:** v0.4.0 (Approved Architecture Baseline)

---

## 1. Purpose

This document defines the **Repository Interface** — the architectural contract
through which the Queue Engine and Business Rules layers access persisted data,
without depending on any concrete storage technology.

`DATABASE_DESIGN.md` establishes the Repository Pattern conceptually, as the
boundary between domain logic and storage. This document completes that
concept into a binding architectural contract: it defines *what* a repository
must guarantee, not *how* any repository fulfills that guarantee.

This mirrors the precedent already set for telephony in ADR-001
(`DECISION_LOG.md`): the Queue Engine depends on the **Telephony Interface**,
never on the SIM900A Adapter directly. The Repository Interface applies the
identical Dependency Inversion discipline to the persistence boundary. No new
architectural pattern is introduced — this document is the data-layer
counterpart of a decision already ratified for the telephony layer.

Concrete repository implementations (SQLite for the pilot, PostgreSQL for a
future production migration) are implementation details that satisfy this
contract. They do not define it, and their internal design is explicitly out
of scope for this document.

---

## 2. Architectural Position

Per the frozen six-layer pipeline in `README.md` and the dependency rule in
ADR-002:

```
Dashboard → API → Queue → Database
```

The Repository Interface sits at the lower boundary of the Queue layer,
occupying the same structural role toward `database/` that
`telephony/interface.py` occupies toward `telephony/`:

```
Queue Engine  →  Repository Interface (Contract)  ←  SQLite Repository (pilot)
                                                    ←  PostgreSQL Repository (future)
                                                    ←  Mock/In-Memory Repository (testing)
```

The Queue Engine and Business Rules layers depend only on the Repository
Interface. They hold no reference, import, or awareness of any concrete
repository. Concrete repositories depend on the interface; the interface does
not depend on them. This is the same inversion already established for
telephony and is treated as a single, consistent architectural rule applied
uniformly across both external boundaries of the system (telephony inbound,
persistence outbound).

The `database/` directory (per ADR-002's directory responsibilities) is the
sole location permitted to contain code that satisfies this contract.
`api/`, `queue/`, and `dashboard/` must never import a concrete repository
implementation.

---

## 3. Repository Responsibilities

A repository is responsible for:

- Translating between domain-level data (patients, queue entries, visits,
  appointments — as defined conceptually in `DATABASE_DESIGN.md`) and
  whatever persistent form the underlying storage technology requires.
- Guaranteeing that data handed back to the Queue Engine is complete and
  internally consistent according to the domain model, regardless of how the
  underlying storage represents it.
- Enforcing storage-level integrity (uniqueness, referential integrity)
  required to protect the domain model from corruption.
- Surfacing failures as Error Contracts (Section 7), never as
  storage-specific failure types.

A repository is explicitly **not** responsible for:

- Queue ordering, prioritization, or eligibility logic — this remains the
  responsibility of the Queue Engine and `QUEUE_RULES.md`.
- Business validation (e.g., appointment eligibility, patient
  classification) — this remains the responsibility of `BUSINESS_RULES.md`.
- Presentation, formatting, or serialization for external consumption — this
  remains the responsibility of the API layer.
- Telephony or communication concerns of any kind.

A repository's authority ends at the boundary of accurate, reliable data
storage and retrieval. It has no opinion about why data is being read or
written, only that the operation is carried out faithfully.

---

## 4. Repository Boundaries

Each repository is scoped to a single domain aggregate, consistent with the
entities defined in `DATABASE_DESIGN.md` (e.g., a Patient Repository, a Queue
Entry Repository, a Visit Repository). A repository must not:

- Reach across aggregate boundaries to directly manipulate data owned by
  another repository. Cross-aggregate coordination is the responsibility of
  the calling layer (Queue Engine / Business Rules), not the repository.
- Contain conditional logic that depends on business state (e.g., "only
  return this record if the queue is open"). Such logic belongs above the
  boundary.
- Expose storage-specific constructs (connection handles, query builders,
  cursors, schema identifiers) through its contract surface.
- Assume a single-process, single-machine deployment. The contract must
  remain valid whether the concrete implementation is a local embedded
  database (pilot) or a networked database server (future).

A repository's boundary is intentionally narrow: it is a faithful,
opinion-free custodian of one aggregate's data.

---

## 5. Repository Contracts (Conceptual Operations)

The following operation categories define the shape of the contract each
repository must fulfill. These are conceptual capabilities, not method
signatures, and apply uniformly to each aggregate-scoped repository
(Patient, Queue Entry, Visit, and any aggregate introduced by
`DATABASE_DESIGN.md`):

- **Identify** — retrieve a single record by its domain identity.
- **Enumerate** — retrieve a collection of records matching a domain-level
  criterion (e.g., all queue entries for a given day), without exposing how
  that criterion is evaluated internally.
- **Persist (Create)** — record a new domain entity as a durable record.
- **Persist (Update)** — record a change to an existing domain entity's
  state.
- **Remove** — retire or delete a record, consistent with whatever retention
  posture is defined by `DATABASE_DESIGN.md` and applicable data-handling
  policy.
- **Existence Check** — confirm whether a record satisfying a domain
  condition is present, without requiring the full record to be retrieved.

Each operation is defined purely in terms of domain concepts (patient,
queue position, visit) and domain identity. No operation may be defined in
terms of tables, rows, columns, files, connections, or query languages of
any kind.

---

## 6. Domain-Level Data Contracts

Repositories exchange **domain objects** with the Queue Engine, not storage
records. A domain object is a conceptual, technology-neutral representation
of an entity as defined in `DATABASE_DESIGN.md` — for example, a Patient or
a Queue Entry — described only by its meaningful attributes and identity.

The data contract guarantees:

- **Identity stability** — a domain object's identity, once assigned, never
  changes and never depends on storage-internal details (e.g., a database
  row's physical location).
- **Completeness** — a domain object returned by a repository contains every
  attribute the Queue Engine and Business Rules layers are entitled to rely
  on, as defined by `DATABASE_DESIGN.md`.
- **Immutability of intent** — a domain object passed to a repository for
  persistence represents a complete, intended state; the repository does not
  infer or fill in missing meaning.
- **No leakage of storage shape** — nothing about how the underlying
  technology stores an attribute (type width, encoding, indexing) is
  observable through the domain object.

This document does not enumerate the specific attributes of each domain
object — that enumeration belongs to `DATABASE_DESIGN.md` and must not be
duplicated here. This section constrains only the *form* the contract must
take, not its specific content.

---

## 7. Error Contracts

Repositories must translate all storage-level failures into a small,
stable set of domain-meaningful error categories before they cross the
Repository Interface boundary. The Queue Engine must never observe a
storage-specific exception, error code, or failure type.

Required error categories:

- **Not Found** — the requested record does not exist.
- **Conflict** — the operation cannot be completed because it would violate
  a uniqueness or state constraint (e.g., duplicate identity).
- **Validation Failure** — the data presented for persistence does not
  satisfy the structural requirements of the domain object (distinct from
  business-rule validation, which occurs above this boundary).
- **Unavailable** — the underlying storage cannot currently be reached or is
  not currently able to service the request.
- **Unknown/Unexpected** — a catch-all category for failures that do not fit
  the above, preserved so that the Queue Engine can respond safely rather
  than crash on an unrecognized condition.

The specific mechanism for representing these categories (exceptions, result
types, or otherwise) is a language- and implementation-level decision
deferred to Phase 5.1, and is intentionally not fixed here.

---

## 8. Transaction Boundary

The Repository Interface must expose a way for the calling layer (Queue
Engine or Business Rules) to group multiple repository operations into a
single unit of work, so that either all included changes are durably
applied or none are.

Principles governing the transaction boundary:

- **Ownership resides above the repository.** A single repository operation
  is implicitly transactional with respect to itself, but multi-step
  workflows that span more than one operation — potentially across more
  than one aggregate — must be explicitly bounded by the calling layer, not
  silently assumed by any individual repository.
- **The boundary is a domain concept, not a storage concept.** The contract
  describes a unit of work in terms of "these changes succeed or fail
  together," never in terms of storage-specific transaction mechanics.
- **No partial visibility.** No caller may observe an intermediate,
  partially-applied state of a unit of work in progress.
- **No nested ambiguity.** The contract does not require support for nested
  units of work; if a future implementation needs this, it must be
  addressed through a dedicated ADR rather than assumed.

The precise API shape of this boundary is deferred to Phase 5.1, consistent
with this document's conceptual-only scope.

---

## 9. Concurrency Expectations

The pilot deployment (single SIM900A adapter, single Raspberry Pi, per
`ROADMAP.md` Phases 6 and 12) implies modest concurrency, but the contract
itself must not assume this permanently, since PostgreSQL is a documented
future migration target (ADR-001, Decision 2).

The Repository Interface contract requires:

- **Safe concurrent reads.** Multiple callers may enumerate or identify
  records concurrently without corrupting state or observing one another's
  in-progress writes.
- **Conflict visibility, not silent loss.** If two callers attempt
  conflicting writes to the same domain object, the contract must surface a
  Conflict error (Section 7) rather than silently allowing one write to
  overwrite the other unnoticed.
- **No assumption of a single writer.** Although the pilot's operational
  profile is low-concurrency, the contract must not be designed in a way
  that presumes only one process will ever write to the store, since this
  would need to be re-architected rather than merely re-implemented at
  migration time.
- **No ordering guarantee beyond the domain's own rules.** Any ordering
  guarantees required for queue correctness are the responsibility of
  `QUEUE_RULES.md` and the Queue Engine, not the repository. The repository
  guarantees only that its own operations are individually consistent.

---

## 10. Future Repository Implementations (SQLite / PostgreSQL)

This document defines the contract that any concrete repository must
satisfy. Two concrete implementations are anticipated by the frozen
roadmap and technology stack:

- **SQLite Repository (Phase 5.1, pilot target)** — the sole implementation
  target for v1.0, per the frozen technology stack and ADR-001, Decision 2.
- **PostgreSQL Repository (future, out of scope for v1.0)** — documented as
  the future production migration target only (ADR-001, Decision 2). Its
  existence must not influence the pilot's implementation, and it is
  designed only if and when a future ADR authorizes that work.

Because both implementations satisfy the same Repository Interface, the
Queue Engine, Business Rules, and API layers require **no modification**
when migrating from SQLite to PostgreSQL. This is the explicit architectural
payoff of this document and the reason the contract is finalized before any
concrete repository is written.

No implementation detail of either repository (schema, connection
management, query construction, driver selection) belongs in this document.

---

## 11. Testing Strategy

The Repository Interface enables the Queue Engine and Business Rules layers
to be tested in complete isolation from any real storage technology, using
a Mock/In-Memory Repository that satisfies the same contract.

Testing strategy principles:

- **Contract tests, not implementation tests.** A shared suite of tests
  should be defined against the Repository Interface itself, and run
  against every concrete implementation (Mock, SQLite, and eventually
  PostgreSQL) to confirm each satisfies the identical contract.
- **Queue Engine tests depend only on the Mock Repository.** Tests of queue
  behavior (`QUEUE_RULES.md`) and business behavior
  (`BUSINESS_RULES.md`) must never depend on a real database, keeping them
  fast and deterministic.
- **Repository tests are storage-specific and separate.** Tests confirming
  that the SQLite Repository correctly satisfies the contract belong to
  Phase 5.1 and are scoped to persistence behavior only, not domain logic.
- **Error Contract coverage.** Each concrete repository's test suite must
  demonstrate that every Error Contract category (Section 7) is reachable
  and correctly surfaced, not only the success path.

This section defines only the strategy; concrete test cases are produced
alongside each repository implementation, not in this document.

---

## 12. Open Decisions

The following are explicitly deferred and must be resolved by a dedicated
ADR before Phase 5.1 begins or, where noted, before the relevant later
phase:

1. **Mechanism for surfacing Error Contracts** — the concrete representation
   (e.g., exception hierarchy vs. explicit result values) is unresolved and
   deferred to Phase 5.1.
2. **Mechanism for the Transaction Boundary (Section 8)** — the concrete API
   shape for grouping operations into a unit of work is unresolved and
   deferred to Phase 5.1.
3. **Resolution of R-004** — the `queue/` top-level package name shadows
   Python's standard library `queue` module (`RISK_REGISTER.md`). This must
   be resolved before Phase 8 (Queue Engine implementation) and may affect
   how the Queue Engine imports the Repository Interface; tracked
   separately and not resolved by this document.
4. **Retention and deletion posture** — whether "Remove" (Section 5) implies
   physical deletion, soft deletion, or archival is not fixed here and
   depends on data-handling requirements not yet ratified.
5. **Placement of the interface definition itself** — whether the Repository
   Interface contract is defined inside `database/` or a shared/common
   location accessible to both `queue/` and `database/` without violating
   the ADR-002 dependency rule is unresolved and must be settled at the
   start of Phase 5.1.

---

## Status

**Status:** Phase 5 — Repository Interface Design

**Implementation:** Not Started

**Depends On:**
- SYSTEM_ARCHITECTURE.md
- DATABASE_DESIGN.md
- BUSINESS_RULES.md
- QUEUE_RULES.md

**Next Phase:** Phase 5.1 — SQLite Repository Design
