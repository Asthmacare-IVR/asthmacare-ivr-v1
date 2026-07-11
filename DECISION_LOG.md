# Decision Log

Record of significant engineering decisions, per Change Management process
in Engineering Charter v3.0.

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
(`api/, backend/, config/, dashboard/, database/, docs/, logs/, queue/,
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
api/  telephony/  queue/  database/  dashboard/  config/  docs/  tests/
logs/  assets/  scripts/  .github/  .vscode/
```

### Directory Responsibilities
| Directory | Responsibility |
|---|---|
| `api/` | REST API layer only — HTTP endpoints, validation, serialization. No business logic. |
| `telephony/` | Telephony abstraction: `interface.py` (contract), future `adapters/`, future `mock/`. |
| `queue/` | Core application logic — Queue Engine, appointment workflow, queue algorithms, orchestration. Must never import a concrete telephony adapter. |
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
`queue/` as a top-level package name shadows Python's standard library
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
