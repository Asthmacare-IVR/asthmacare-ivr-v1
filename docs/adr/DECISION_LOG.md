# Decision Log

Record of significant engineering decisions, per Change Management process
in Engineering Charter v3.0.

### Authority Hierarchy

To avoid ambiguity between business policy and queue execution, the following
architectural authority hierarchy is established:

1. **BUSINESS_RULES.md** is the authoritative source for patient lifecycle,
   eligibility, workflow policy, and business meaning.

2. **QUEUE_RULES.md** is the authoritative source for internal Queue Engine
   operational states, scheduling, ordering, notifications, transitions, and
   execution mechanics.

3. The Queue Engine SHALL implement Business Rules but SHALL NOT redefine,
   extend, or override business policy.

4. Business Rules SHALL NOT define Queue Engine operational mechanics or
   internal execution states.

5. If future documentation appears inconsistent, the Authority Hierarchy established in this ADR shall takes precedence
   until the affected document has been updated and synchronized.

This hierarchy establishes a clear separation between policy and execution,
preserving the layered architecture and preventing future ownership conflicts.
---

## D-001: Dependency Management — pip + requirements.txt vs poetry/pyproject.toml

**Date:** Phase 1
**Status:** Resolved (Approved via Project Baseline v1.0)
**Decision:** Use `venv` + `requirements.txt` for dependency management.
`pyproject.toml` is used only for tool configuration (Black/Ruff/isort/pytest),
not dependency resolution.
**Rationale:** Simpler onboarding for a small team; sufficient for pilot scale.
**Revisit trigger:** If multi-environment dependency conflicts appear (e.g.
Raspberry Pi requiring different pinned versions than Windows dev), reconsider
poetry for lockfile-based resolution.

---

## D-002: Development Platform — Native Windows 11 vs WSL2

**Date:** Phase 1
**Status:** Resolved (Approved via Project Baseline v1.0)
**Decision:** Develop natively on Windows 11 for Phase 1–5 (no hardware/serial
dependency yet).
**Recommendation on record (not approved, logged for future review):** WSL2
(Ubuntu) reduces Windows-to-Linux porting friction for serial (SIM900A) and
Raspberry Pi deployment phases. Revisit before Phase 6 (SIM900A Hardware) and
Phase 12 (Raspberry Pi Deployment), where native Windows may introduce
serial-port and path-handling differences not present on Linux.
**Rationale for deferring:** Baseline explicitly specifies Windows 11 as the
development platform; no hardware work is happening yet that would expose the
risk.

---

## ADR-001: Telephony Interface Clarification, PostgreSQL Documentation, Folder Structure, README Scope

**Date:** Phase 1 (post-completion, pre-Phase 2)
**Status:** Approved by Chief Architect
**Raised by:** Senior Engineering Partner, in response to a revised README proposal

### Decision 1 — Telephony Interface
**Question:** A proposed README depicted "Telephony Interface" as a distinct
box between "Telephony Adapter" and "Queue Engine" in the runtime pipeline.
**Resolution:** Approved with clarification. The Telephony Interface is **not**
a runtime pipeline stage. It is an architectural contract (abstract
interface/Dependency Inversion boundary) that the Queue Engine depends on, and
which concrete adapters (SIM900A, future Cloud IVR/SIP/Asterisk/Mock) implement.
**Effect on frozen architecture:** None. The six-layer pipeline in README.md
is unchanged:
```
Patient → Telephony Adapter → Queue Engine → Business Rules → Database → REST API → Admin Dashboard
```
Internally (documented fully in `SYSTEM_ARCHITECTURE.md` at Phase 3, with
UML/class diagrams):
```
Queue Engine → Telephony Interface (Contract) ← SIM900A Adapter
                                               ← Cloud IVR Adapter (future)
                                               ← SIP Adapter (future)
                                               ← Asterisk Adapter (future)
                                               ← Mock Adapter (testing)
```

### Decision 2 — Future PostgreSQL
**Resolution:** Approved. PostgreSQL may be documented as the planned
production migration target only. It must not influence any pilot
implementation decisions. Current and only implementation target for the
pilot remains SQLite.

### Decision 3 — Folder Structure
**Resolution:** Approved in principle as the initial Phase 2 proposal
(`api/, backend/, config/, dashboard/, database/, docs/, logs/, queue_engine,
telephony/, tests/, assets/, scripts/, .github/, .vscode/`). Names may be
refined during Phase 2 implementation, but: no unnecessary directories, no
architectural boundary changes, no added complexity. Must stay
beginner-friendly.

### Decision 4 — README Scope
**Resolution:** README.md stays lightweight: project overview, quick setup,
architecture summary (six-layer diagram only), roadmap summary, links to
detailed docs. Detailed engineering discussion (interface patterns, DI,
class diagrams) belongs in `SYSTEM_ARCHITECTURE.md`, `DATABASE_DESIGN.md`,
`BUSINESS_RULES.md`, `QUEUE_RULES.md` — created at their respective phases.

### Decision 5 — Architecture Freeze (reaffirmed)
No additional layers, frameworks, services, or technologies may be introduced
without a corresponding ADR.

### Action Items
1. ✅ Update `README.md` to reflect Decisions 1, 2, 4 (six-layer pipeline
   retained; PostgreSQL noted as future-only; interface detail deferred to
   Phase 3).
2. ✅ Record this decision as ADR-001 (this entry).
3. Proceed with Phase 2 per frozen roadmap — approved.
4. Wait for explicit approval before beginning Phase 3.

---

## ADR-002: Remove backend/ Directory and Adopt Single-Responsibility Top-Level Structure

**Date:** Phase 2
**Status:** Approved by Chief Architect
**Raised by:** Senior Engineering Partner — ambiguity between `api/` and
`backend/` overlap in the proposed folder structure.

### Decision
The top-level `backend/` directory is removed. Approved structure:
```
api/  telephony/  queue_engine  database/  dashboard/  config/  docs/  tests/
logs/  assets/  scripts/  .github/  .vscode/
```

### Directory Responsibilities
| Directory | Responsibility |
|---|---|
| `api/` | REST API layer only — HTTP endpoints, validation, serialization. No business logic. |
| `telephony/` | Telephony abstraction: `interface.py` (contract), future `adapters/`, future `mock/`. |
| `queue_engine` | Core application logic — Queue Engine, appointment workflow, queue algorithms, orchestration. Must never import a concrete telephony adapter. |
| `database/` | SQLite access (pilot), future PostgreSQL migration, repository layer, migrations, seed scripts. |
| `dashboard/` | Admin dashboard UI templates and static assets. No business logic. |
| `config/` | Environment variables, logging configuration, application settings. |
| `docs/` | Engineering documentation (phase-specific docs; see assumption logged in `docs/README.md`). |
| `tests/` | Unit, integration (future), system (future) tests. |
| `logs/` | Runtime log files. Git-ignored except placeholder. |
| `assets/` | Images, icons, audio prompts / voice recordings. |
| `scripts/` | Development, build, and maintenance scripts — not part of application runtime. |

### Dependency Rule (approved)
```
Dashboard → API → Queue → Database
Queue → Telephony Interface ← Telephony Adapter → Telephony Interface
```
The Queue module must **never** import a concrete SIM900A (or any other
concrete telephony) adapter — only `telephony/interface.py`.

### Phase 2 Scope (approved)
Folder creation, placeholder README files, empty `interface.py`, `__init__.py`
where appropriate. **No runtime logic. No SIM900A code. No FastAPI
application code.** Structure only.

### Risk identified during implementation
`queue_engine` as a top-level package name shadows Python's standard library
`queue` module. Logged as R-004 in `RISK_REGISTER.md`. Must be resolved
(rename, or src-layout namespacing) via a dedicated ADR before Phase 8 –
Queue Engine implementation begins. Not blocking Phase 2 (structure only,
no imports exercised yet).

### Open question raised (pending confirmation, not blocking)
Whether phase-specific documents (`SYSTEM_ARCHITECTURE.md`,
`DATABASE_DESIGN.md`, `BUSINESS_RULES.md`, `QUEUE_RULES.md`,
`PATIENT_FLOW.md`, `TEST_PLAN.md`, `TEST_REPORT.md`) should be created
inside `docs/` (assumed) or at repository root (existing convention for
README/CHANGELOG/ROADMAP/TODO/DECISION_LOG/RISK_REGISTER/PROJECT_PROGRESS).
Assumption stated in `docs/README.md`; will follow it unless corrected
before Phase 3.

---

## ADR-003: Data Access Layer Architecture (Repository / DAO Pattern)

**Date:** Phase 3.1
**Status:** Approved by Chief Architect
**Raised by:** Senior Engineering Partner — data persistence architecture for Pilot v1.0 and future database migration.

### Context

The Queue Engine requires persistent storage while remaining independent of
the underlying database implementation.

Pilot v1.0 targets SQLite only.

Future versions may migrate to PostgreSQL.

The Engineering Charter requires that replacing the database must not require
changes to the Queue Engine, Business Rules, REST API, or Dashboard.

### Decision

The project adopts the **Repository / DAO Pattern**.

The Queue Engine depends only on abstract Repository Interface(s).

Concrete repository implementations encapsulate all storage-specific logic.

SQLite will be implemented during Phase 5.

Future PostgreSQL support will be provided by implementing the same repository
contracts.

### Rationale

- Aligns with the Dependency Inversion Principle already adopted for the
  Telephony Interface (ADR-001).
- Keeps business logic independent from storage technology.
- Allows Queue Engine testing with fake/mock repositories.
- Isolates future SQLite → PostgreSQL migration to repository
  implementations only.
- Maintains a consistent architectural style across external dependencies.

### Consequences

**Positive**

- Storage independence.
- Improved testability.
- Better separation of concerns.
- Reduced migration cost.
- Consistent architecture across telephony and persistence layers.

**Trade-offs**

- Additional abstraction layer.
- Slightly increased implementation effort.
- Repository contracts must avoid leaking storage-specific concepts.

### Action Items

1. Phase 4 defines Business Rules.
2. Phase 5 designs Repository Interface(s).
3. Phase 5 implements SQLiteRepository.
4. Future PostgreSQL support remains out of scope for Pilot v1.0.

### Related Documents

- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/DATABASE_DESIGN.md`

---

## ADR-004: Queue State Machine Canonical Definition

**Date:** Architecture Gate Review remediation (pre-Phase 6 Implementation)
**Status:** Approved by Chief Architect
**Raised by:** Architecture Gate Review — Critical Finding C-1 (`BUSINESS_RULES.md`
and `QUEUE_RULES.md` define apparently different Queue State Machines)
If future documentation appears inconsistent, the Authority Hierarchy established in this ADR shall take precedence until the affected documentation has been updated and synchronized.

### Context

`BUSINESS_RULES.md` §10 defines a six-state domain-level lifecycle
(`Registered → Queued → Calling → Consultation → {Completed | Cancelled |
No-show}`). `QUEUE_RULES.md` §5.2–5.3 defines a ten-state Queue-Engine
operational state machine (`REQUESTED → ADMITTED → WAITING → NOTIFIED →
CONFIRMED → IN_SERVICE → {COMPLETED | NO_SHOW | CANCELLED | EXPIRED}`).
`QUEUE_RULES.md` §2 states that any conflict with `BUSINESS_RULES.md` must
be resolved by ADR before `QUEUE_RULES.md` may remain Frozen. No such ADR
existed; the Architecture Gate Review logged this as Critical Finding C-1
and blocked Phase 6 implementation on its resolution.

Analysis found two distinct issues bundled inside C-1:

1. **Apparent conflict that is in fact a difference in abstraction level.**
   Most of the discrepancy is explained by `QUEUE_RULES.md` refining each
   `BUSINESS_RULES.md` stage into one or more mechanism-level states
   (e.g., `Calling` → `NOTIFIED` + `CONFIRMED`), plus two engine-internal
   states (`REQUESTED`, `EXPIRED`) that exist before a business-meaningful
   Queue Entry (`BUSINESS_RULES.md` §4.4) is created at all. This is not a
   contradiction; it is the expected relationship between a domain-level
   lifecycle and its implementation.
2. **One genuine substantive conflict.** `QUEUE_RULES.md` §5.3 permitted a
   `IN_SERVICE → CANCELLED` ("Service abandoned/interrupted") transition.
   `BUSINESS_RULES.md` §4.9 and §10 explicitly forbid this: cancellation is
   permitted only from Queue Entry, Waiting, or Calling — "a consultation
   in progress does not 'cancel,' it may only complete." This is a true
   rule conflict, not a granularity difference, and required a canonical
   choice.

### Decision

1. **`BUSINESS_RULES.md` §10 remains canonical for domain-level business
   behavior** — the business-meaningful patient lifecycle and every
   constraint on which transitions are permitted. It is not amended in
   content by this ADR.
2. **`QUEUE_RULES.md` §5.2–5.3 remains canonical for the Queue Engine's
   internal operational mechanism** — state naming, retry/notification
   granularity, and ordering behavior — as a refinement of, not a
   replacement for, the lifecycle in `BUSINESS_RULES.md` §10.
3. **The canonical mapping between the two** is fixed as follows and must
   not be duplicated or restated elsewhere; both documents reference this
   table by pointing to this ADR:

   | `BUSINESS_RULES.md` Stage (§4 / §10) | `QUEUE_RULES.md` State(s) (§5.2) | Notes |
   |---|---|---|
   | *(pre-Registration; no queue entry exists)* | `REQUESTED` | No Business Rules equivalent — consistent with §4.2 ("a registration that fails Validation does not proceed to Queue Entry"). |
   | Registered (§4.1) → passes Validation (§4.2) | `ADMITTED` | The moment Validation succeeds is the moment `REQUESTED → ADMITTED` occurs. |
   | Queued (§4.4) / Waiting (§4.5) | `WAITING` | Direct equivalence. `ADMITTED → WAITING` is an automatic sub-step with no independent business meaning. |
   | Calling (§4.6) | `NOTIFIED` → `CONFIRMED` | `QUEUE_RULES.md` refines the single business stage "Calling" into signaled (`NOTIFIED`) and acknowledged (`CONFIRMED`) sub-states. No new business meaning is introduced. |
   | Consultation (§4.7) | `IN_SERVICE` | Direct equivalence. |
   | Completion (§4.8) | `COMPLETED` | Direct equivalence. |
   | Cancellation (§4.9) | `CANCELLED` | Direct equivalence. Reachable only from `WAITING`, `NOTIFIED`, or `CONFIRMED` — never from `IN_SERVICE` (see Decision 4). |
   | No-show (§4.10) | `NO_SHOW` | Direct equivalence. |
   | *(no Business Rules equivalent — abandoned prior to admission)* | `EXPIRED` | An engine-internal outcome for a `REQUESTED` entry that times out before an admission decision; no Queue Entry ever existed, so it carries no business-lifecycle meaning distinct from "registration did not result in a queue entry." |

4. **The `IN_SERVICE → CANCELLED` ("Service abandoned/interrupted")
   transition in `QUEUE_RULES.md` §5.3 is removed.** `BUSINESS_RULES.md`
   is canonical for this conflict per its own stated domain authority
   (§1, §3): "this document, not code comments or ad hoc implementation
   choices, defines correct system behavior." `IN_SERVICE` (Consultation)
   now has exactly one outbound transition: `COMPLETED`.
5. **No new state, transition, or business rule is introduced.** Handling
   of an interrupted/abandoned consultation is out of scope for Pilot
   v1.0 and is logged as a Future Extension Point in `BUSINESS_RULES.md`
   §14, to be addressed by a future business rule (and, if needed, a
   corresponding `QUEUE_RULES.md` amendment) before the Queue Engine can
   support it.

### Rationale

- Preserves the ownership split already frozen in `QUEUE_RULES.md` §2:
  Business Rules owns *policy* (what is permitted), Queue Engine owns
  *mechanism* (state, order, timing). Treating the two state machines as
  layered rather than competing keeps both documents true to that split.
- Resolves the conflict using the authority `BUSINESS_RULES.md` already
  claims for itself (§3, Guiding Principles: "Single source of truth for
  domain behavior"), rather than inventing a new tie-breaking rule.
- Requires no redesign: no state is renamed, no new state is added, and
  the only content change is the removal of one transition that was
  already inconsistent with a frozen constraint.
- Fixes the root cause of `QUEUE_RULES.md`'s self-declared freeze
  violation (§2: "any conflict... must be resolved by ADR before this
  document is considered frozen") rather than merely re-asserting Frozen
  status without addressing it.
- Avoids duplicating the mapping table in both source documents, which
  would reintroduce the same class of silent-drift risk that produced
  C-1 in the first place; both documents point to this ADR as the single
  source of truth for the mapping.

### Consequences

**Positive**

- `BUSINESS_RULES.md` and `QUEUE_RULES.md` are now mutually consistent;
  Critical Finding C-1 is closed.
- The Queue Engine (Phase 6/9) has one authoritative operational state
  machine, one authoritative business lifecycle, and one authoritative
  mapping between them.
- Dependency Inversion, the Repository Pattern, Business Rules ownership,
  Queue Engine ownership, the SQLite design, and future PostgreSQL
  compatibility are all unaffected — none of the frozen documents
  governing those areas were touched.

**Trade-offs**

- `QUEUE_RULES.md` loses its only modeled path for an interrupted
  consultation. This is intentional (Decision 5) and is tracked as an
  open gap in `BUSINESS_RULES.md` §14, not silently dropped.
- Both `BUSINESS_RULES.md` and `QUEUE_RULES.md` now carry a normative
  dependency on this ADR for the state mapping; any future change to
  either state machine must update this ADR in the same change, or the
  same class of drift (C-1) can recur.

### Migration Notes

1. **No code migration required** — no implementation exists yet
   (Phase 6/9 not started); this ADR only corrects architecture documents
   before implementation begins.
2. **Document edits applied by this ADR:**
   - `BUSINESS_RULES.md` §10 — added an abstraction-level clarification
     note; added new §10.1 ("Relationship to QUEUE_RULES.md"); added one
     Future Extension Point bullet to §14. No state, transition, or rule
     changed.
   - `QUEUE_RULES.md` §2 — added a resolution note pointing to this ADR.
     §5.3 — removed the `IN_SERVICE → CANCELLED` ("Service
     abandoned/interrupted") row and updated the `IN_SERVICE → COMPLETED`
     row's notes. §10 (Edge Cases) — updated the row describing
     `IN_SERVICE` re-wait handling to reflect the single remaining
     outbound transition.
   - `DECISION_LOG.md` — this entry (ADR-004) added.
3. **No change** to `SYSTEM_ARCHITECTURE.md`, `DATABASE_DESIGN.md`,
   `REPOSITORY_INTERFACE.md`, `SQLITE_REPOSITORY_DESIGN.md`, `ROADMAP.md`,
   `PROJECT_PROGRESS.md`, or `README.md`. This ADR is scoped exclusively
   to closing Critical Finding C-1.
4. **Verification before Phase 6:** confirm no other document (e.g. a
   future `PATIENT_FLOW.md` at Phase 4 per `README.md`'s documentation
   index) restates either state machine independently; any future
   restatement must cite this ADR rather than re-deriving the mapping.

### Related Documents

- `docs/BUSINESS_RULES.md`
- `docs/QUEUE_RULES.md`

---
