# TODO

## Current Sprint — Phase 2: Project Foundation

- [x] Create approved top-level folder structure (ADR-002)
- [x] Add directory-responsibility README.md to each top-level folder
- [x] Add `__init__.py` to Python package directories (`api/`, `telephony/`,
      `queue/`, `database/`, `config/`)
- [x] Create empty `telephony/interface.py` placeholder (contract, no methods)
- [x] Log queue/ stdlib naming collision as R-004 in RISK_REGISTER.md
- [x] Flag docs/ vs root-level documentation placement assumption
- [ ] Product Owner / Chief Architect confirms docs/ placement assumption
- [ ] Git commit Phase 2 structure
- [ ] Wait for approval before Phase 3

## Completed — Phase 1: Development Environment

- [x] Initialize Git repository
- [x] Create Python virtual environment
- [x] Create `requirements.txt` (pytest, black, ruff, isort)
- [x] Create `pyproject.toml` tooling config
- [x] Create `.gitignore`
- [x] Configure VS Code workspace
- [x] Create smoke test (`tests/test_environment.py`)
- [x] Initialize core documentation set
- [x] Git commit + tag `v0.1.0`
- [x] ADR-001 recorded (Telephony Interface clarification, PostgreSQL note, README scope)

## Blocked

- Phase 6 (SIM900A Hardware): blocked on hardware delivery
- Phase 12 (Raspberry Pi Deployment): blocked on hardware purchase

## Known Bugs

None yet — no application code exists.

## Technical Debt

None yet.

## Future Enhancements (Not in Scope for v1.0)

- WSL2-based development environment (recommended, not approved — see DECISION_LOG.md)
- CI workflows in `.github/` (proposed for Phase 11, not yet approved)
- Cloud IVR / SIP / Asterisk migration
- AI-assisted triage or scheduling
