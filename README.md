# AsthmaCare IVR Platform

Automated patient queue management platform for Professor Dr. B. K. Bose Asthma
Care Center, Bangladesh. Pilot phase uses a SIM900A GSM module for IVR/SMS;
architecture is designed so the telephony layer can be replaced later without
changes to the queue engine, business rules, database, or API.

## Project Overview

Patients are admitted into a daily queue, notified when their turn approaches,
and tracked through a fixed set of states (requested → admitted → waiting →
notified → confirmed → in-service → completed, plus the terminal
no-show/cancelled/expired outcomes) until service completion. The platform is
built as independently testable layers — Telephony, Queue Engine, Business
Rules, Database (Repository pattern), REST API, Admin Dashboard — so any one
layer (most notably the telephony hardware) can be replaced without touching
the others.

## Architecture Overview (Frozen v1.0)

```
Patient
    |
    v
Telephony Adapter        (interface only today — telephony/interface.py)
    |
    v
Queue Engine              (queue_engine/ — state machine, ordering, retries, timeouts, events)
    |
    v
Business Rules            (documented in docs/architecture/BUSINESS_RULES.md; runtime wiring not yet started)
    |
    v
Database                  (database/ — Repository Interface, SQLite + in-memory implementations)
    |
    v
REST API                  (backend/api/ — placeholder)
    |
    v
Admin Dashboard            (backend/dashboard/ — placeholder)
```

The Queue Engine is architecturally independent of the Telephony Adapter and
of any concrete database implementation: it depends only on
`database.interfaces` / `database.domain` and `telephony.interface`, never on
a concrete repository (SQLite, in-memory) or a concrete telephony adapter.
This allows the SIM900A adapter used in the pilot to be replaced by a Cloud
IVR / SIP adapter in a future version without modifying the queue engine,
business rules, database, or API layers. See `docs/architecture/
SYSTEM_ARCHITECTURE.md` and ADR-001 (`docs/adr/DECISION_LOG.md`) for the full
decision record.

## Folder Structure

```
AsthmaCare-IVR/
├── docs/
│   ├── adr/            Architecture Decision Records + master Decision Log
│   ├── architecture/    Frozen design contracts (system, database, business
│   │                    rules, queue rules/state machine, repository
│   │                    interface, SQLite repository design)
│   ├── roadmap/         ROADMAP.md, PROJECT_PROGRESS.md, TODO.md,
│   │                    RISK_REGISTER.md, PROJECT_PHASE_STATUS.md
│   └── reviews/
│       ├── R001/ … R006/   Per-review evidence/index (R001–R006)
│       └── MASTER_REVIEW/  Consolidated baseline across all reviews
├── backend/
│   ├── api/             REST API (placeholder — Phase 11)
│   ├── config/          Wiring/configuration (placeholder — Phase 8/9)
│   ├── dashboard/       Admin Dashboard (placeholder — Phase 10)
│   ├── assets/          Static assets (placeholder)
│   ├── scripts/         Operational scripts (placeholder)
│   └── logs/            Runtime log output (placeholder)
├── database/            Repository Interface + SQLite/in-memory implementations
├── queue_engine/        Core orchestration (state machine, ordering, retries,
│                        timeouts, events) — renamed from queue/ per ADR-006
├── telephony/           Abstract Telephony Interface (no concrete adapter yet)
├── tests/               Contract, unit, and integration tests
├── CHANGELOG.md
└── README.md
```

See `PROJECT_RESTRUCTURE_REPORT.md` for exactly what moved during this
reorganization (nothing was deleted or rewritten — only relocated).

## Current Status

**Current review:** R006 — Queue Engine merged (Implemented, Pending
Hardening)
**Version:** see `CHANGELOG.md`

| Layer | Status |
|---|---|
| Development environment, folder structure | Complete |
| System/database/business-rules/queue-rules architecture | Complete (frozen) |
| Database (Repository Interface) implementation | Implemented, tested (manual harness) |
| Queue Engine implementation | Implemented — one known test-fixture defect, see below |
| Telephony Adapter (concrete) | Not started (blocked on SIM900A hardware) |
| Business Rules runtime wiring, Admin Dashboard, REST API | Not started |

Full phase-by-phase detail: `docs/roadmap/PROJECT_PHASE_STATUS.md`.

**Known issue:** `tests/test_queue_engine_integration.py`'s `uow` fixture
does not match the `InMemoryUnitOfWork` constructor contract and will fail at
setup until corrected (tracked as risk R-005 / action item in
`docs/reviews/MASTER_REVIEW/08_Action_Items.md`). All other modules and test
files were verified to import and collect cleanly.

## Technology Stack (Approved)

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Backend | FastAPI |
| Frontend | HTML, Bootstrap, JavaScript |
| Database | SQLite (pilot) — PostgreSQL is the documented future production migration target only; it does not influence pilot implementation (see ADR-001) |
| Testing | pytest |
| Formatting/Linting | Black, Ruff, isort |
| Version Control | Git, GitHub |
| Dependency Management | venv + requirements.txt |

## Build Instructions

Prerequisites: Windows 11 (or any OS with Python 3.11 — see D-002 in
`docs/adr/DECISION_LOG.md` for the platform decision record), Python 3.11,
Git.

```powershell
# 1. Clone the repository
git clone <repo-url>
cd AsthmaCare-IVR

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Testing

```powershell
pytest
```

`pyproject.toml` sets `testpaths = ["tests"]` and `pythonpath = ["."]`, so
`tests/` can `import database.*`, `import queue_engine.*`, and
`import telephony.*` directly from the repo root — no package installation
required.

Expected: all tests under `tests/` pass **except**
`tests/test_queue_engine_integration.py`, which currently fails at fixture
setup (see "Current Status" above) until the fixture fix in
`docs/reviews/MASTER_REVIEW/08_Action_Items.md` (#2) is applied.

Code quality, before every commit:

```powershell
black .
isort .
ruff check .
```

VS Code is configured (`.vscode/settings.json`) to format on save
automatically, provided the recommended extensions
(`.vscode/extensions.json`) are installed.

## Roadmap

See `docs/roadmap/ROADMAP.md` for the frozen v1.0 phase plan and
`docs/roadmap/PROJECT_PHASE_STATUS.md` for the current phase-by-phase
snapshot. Immediate next steps:

1. **R006.1 — Queue Engine Hardening**: fix the integration test fixture,
   run the real `pytest` suite, add SQLite-backed Queue Engine integration
   coverage.
2. **R007 — Telephony Adapter**: blocked on SIM900A hardware delivery.
3. **Business Rules runtime wiring, Admin Dashboard, REST API, Raspberry Pi
   deployment, formal Testing & QA** — see `docs/reviews/MASTER_REVIEW/
   09_Next_Phases.md` for the full sequence and gating.

## Documentation Index

| Document | Location | Purpose |
|---|---|---|
| README.md | repo root | Project overview, setup (this file) |
| CHANGELOG.md | repo root | Version history |
| DECISION_LOG.md + ADR-00N | `docs/adr/` | Engineering decisions |
| Architecture contracts | `docs/architecture/` | Frozen system/database/business/queue design |
| ROADMAP.md, PROJECT_PROGRESS.md, TODO.md, RISK_REGISTER.md, PROJECT_PHASE_STATUS.md | `docs/roadmap/` | Planning, progress, risks |
| Review evidence, R001–R006 | `docs/reviews/` | Per-review record |
| Consolidated baseline | `docs/reviews/MASTER_REVIEW/` | Cross-review summary, open issues, action items, next phases |
| Restructure log | repo root `PROJECT_RESTRUCTURE_REPORT.md` | Exact move/merge accounting for this reorganization |

## Out of Scope for v1.0

Cloud IVR, SIP, Asterisk/FreePBX, and AI integration are explicitly out of
scope for this pilot release, per the frozen project baseline.
