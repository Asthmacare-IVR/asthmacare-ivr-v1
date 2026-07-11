# Changelog

All notable changes to the AsthmaCare IVR Platform are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/), versioning follows
[Semantic Versioning](https://semver.org/).

## [Unreleased] - Phase 2: Project Foundation

### Added
- Approved top-level folder structure (ADR-002): `api/, telephony/, queue/,
  database/, dashboard/, config/, docs/, tests/, logs/, assets/, scripts/,
  .github/`
- Directory-responsibility `README.md` in every top-level folder
- `__init__.py` package markers in `api/`, `telephony/`, `queue/`,
  `database/`, `config/`
- Empty `telephony/interface.py` — Telephony Interface contract placeholder
  (no methods yet; structure only per ADR-002)

### Notes
- No runtime logic, no SIM900A code, no FastAPI application code — structure
  only, as scoped by ADR-002.
- R-004 risk logged: `queue/` package name shadows Python stdlib `queue`
  module; must be resolved before Phase 8.

## [0.1.0] - Phase 1: Development Environment

### Added
- Git repository initialized
- Python 3.11 virtual environment (`venv`)
- `requirements.txt` with development tooling: pytest, black, ruff, isort
- `pyproject.toml` with Black/Ruff/isort configuration
- `.gitignore` (excludes venv, `.db`/`.sqlite3` files, secrets, caches)
- VS Code workspace configuration (`.vscode/settings.json`, `.vscode/extensions.json`)
- Smoke test suite (`tests/test_environment.py`) verifying Python version and pytest operation
- `README.md`, `PROJECT_PROGRESS.md`, `ROADMAP.md`, `TODO.md`, `DECISION_LOG.md`,
  `RISK_REGISTER.md` initialized

### Changed
- README.md architecture section clarified: Telephony Interface documented as
  an internal contract (not a pipeline stage); PostgreSQL noted as future
  production migration target only (see ADR-001 in DECISION_LOG.md)

### Notes
- No application code exists at this stage by design. This release establishes
  only the development environment and tooling foundation.
