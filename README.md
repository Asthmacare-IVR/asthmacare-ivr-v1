# AsthmaCare IVR Platform

Automated patient queue management platform for Professor Dr. B. K. Bose Asthma Care
Center, Bangladesh. Pilot phase uses a SIM900A GSM module for IVR/SMS; architecture is
designed so the telephony layer can be replaced later without changes to the queue
engine, business rules, database, or API.

## Project Status

**Current Phase:** Phase 1 – Development Environment
**Version:** v0.1.0
**Status:** In progress

See `PROJECT_PROGRESS.md` for full phase-by-phase status and `ROADMAP.md` for the
complete plan.

## Architecture (Frozen v1.0)

```
Patient
    |
    v
Telephony Adapter
    |
    v
Queue Engine
    |
    v
Business Rules
    |
    v
Database
    |
    v
REST API
    |
    v
Admin Dashboard
```

The Queue Engine is architecturally independent of the Telephony Adapter. This
allows the SIM900A adapter used in the pilot to be replaced by a Cloud IVR / SIP
adapter in a future version without modifying the queue engine, business rules,
database, or API layers.

The mechanism enforcing this independence (an internal Telephony Interface
contract, not a runtime pipeline stage) is documented in `SYSTEM_ARCHITECTURE.md`
(created in Phase 3) — see ADR-001 in `DECISION_LOG.md` for the decision record.

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

## Development Environment Setup (Phase 1)

Prerequisites: Windows 11, Python 3.11, Git.

```powershell
# 1. Clone the repository
git clone <repo-url>
cd asthmacare-ivr-platform

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify environment
pytest
```

Expected result: 2 tests pass (`tests/test_environment.py`).

## Code Quality

Before every commit:

```powershell
black .
isort .
ruff check .
```

VS Code is configured (`.vscode/settings.json`) to format on save automatically,
provided the recommended extensions (`.vscode/extensions.json`) are installed.

## Documentation Index

| Document | Purpose |
|---|---|
| README.md | Project overview, setup |
| CHANGELOG.md | Version history |
| PROJECT_PROGRESS.md | Phase-by-phase status |
| ROADMAP.md | Full frozen roadmap |
| TODO.md | Active task list |
| DECISION_LOG.md | Record of engineering decisions |
| RISK_REGISTER.md | Tracked risks and mitigations |

Additional documents (`SYSTEM_ARCHITECTURE.md`, `DATABASE_DESIGN.md`,
`BUSINESS_RULES.md`, `QUEUE_RULES.md`, `PATIENT_FLOW.md`, `TEST_PLAN.md`,
`TEST_REPORT.md`) are created at the phase in which they first have real content
(Phase 3, 5, 4, 4, 4, 11, 11 respectively).

## Out of Scope for v1.0

Cloud IVR, SIP, Asterisk/FreePBX, and AI integration are explicitly out of scope
for this pilot release, per the frozen project baseline.
