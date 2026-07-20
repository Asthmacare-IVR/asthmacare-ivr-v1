# Changelog

All notable changes to the AsthmaCare IVR Platform are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/), versioning follows
[Semantic Versioning](https://semver.org/).

## [Unreleased] - R006: Queue Engine Merge & Repository Restructuring

### Added
- `queue_engine/` — Queue Engine core implementation merged in from the
  approved R006 package: `engine.py` (orchestration), `state_machine.py`
  (transition validation, ADR-004 applied), `ordering.py` (computed
  position), `retry_manager.py`, `timeout_manager.py`, `events.py`
- `tests/test_queue_engine_state_machine.py`,
  `tests/test_queue_engine_ordering.py`,
  `tests/test_queue_engine_integration.py`
- `docs/adr/ADR-006-r004-resolution.md` — approves and documents the
  `queue/` → `queue_engine/` rename, resolving risk R-004
- Reorganized repository layout: `docs/{adr,architecture,roadmap,reviews}/`
  subfolders; `backend/` grouping `api/, config/, dashboard/, assets/,
  scripts/, logs/`; `docs/reviews/R001`–`R006` plus `MASTER_REVIEW/`
- `docs/roadmap/PROJECT_PHASE_STATUS.md` — living phase-status snapshot
- `PROJECT_RESTRUCTURE_REPORT.md` — full move/merge accounting for this
  reorganization

### Changed
- Top-level `queue/` package **renamed** to `queue_engine/` (ADR-006,
  approved) — resolves risk R-004 (shadowing the Python standard library
  `queue` module). All imports referencing `queue` (local package) now
  reference `queue_engine`.
- `RISK_REGISTER.md` merged/updated: R-004 marked **RESOLVED**; new risk
  R-005 logged (see "Fixed/Known Issues" below); relocated to
  `docs/roadmap/RISK_REGISTER.md`.
- `api/, config/, dashboard/, assets/, scripts/, logs/` relocated under a
  new `backend/` parent folder (grouping move only — no file content
  changed, no import previously referenced these as top-level packages).
- All documentation relocated from repo root and the flat `docs/` folder
  into `docs/adr/`, `docs/architecture/`, `docs/roadmap/`, and
  `docs/reviews/` — see `PROJECT_RESTRUCTURE_REPORT.md` for the full
  file-by-file move log. `README.md` and `CHANGELOG.md` remain at the
  repository root.

### Known Issues (not fixed in this release — tracked for R006.1)
- `tests/test_queue_engine_integration.py`'s `uow` fixture instantiates
  `InMemoryUnitOfWork()` without its required `store` argument and never
  enters its context manager; every test in that file will fail at setup
  until corrected. Confirmed via direct reproduction during merge
  validation. See `docs/reviews/R006/QUEUE_ENGINE_REVIEW.md` and
  `docs/reviews/MASTER_REVIEW/08_Action_Items.md` (#2).
- No real `pytest` run has been performed on this codebase in any
  environment to date (no network access in the sandboxes used for either
  the R005 or R006 merges); validation has used a hand-written harness. See
  Action Item #1.

### Notes
- This release is a **repository restructuring and Queue Engine merge**,
  not a feature-development or architecture-redesign release. No business
  rule, ADR, architecture decision, or existing test was modified, removed,
  or reinterpreted.

## [0.5.2] - R005: Database Layer Audit & Parity Fix

### Fixed
- `InMemoryPatientRepository.update()` did not enforce phone-number
  uniqueness the way `SqlitePatientRepository.update()` did — a patient
  could be updated to a phone number already held by a different patient
  without raising `ConflictError` in the in-memory implementation. Fixed;
  regression test added. See `docs/reviews/R005/PARITY_FIX.md`.

### Added
- `docs/adr/ADR-005-phase6-open-decisions.md` — formally closes
  `SQLITE_REPOSITORY_DESIGN.md` §15's four Open Decisions (OD-1..OD-4)
- `database/sqlite/migrations.py` — versioned, idempotent migration runner
- `database/sqlite/unit_of_work.py::SqliteRepositories` — standalone,
  non-UnitOfWork repository access path
- `tests/test_sqlite_migrations.py`, `tests/test_sqlite_concurrency.py`,
  `tests/test_sqlite_standalone_repositories.py`,
  `tests/test_queue_entry_repository_error_translation.py`

### Changed
- `database/sqlite/schema.py` — DDL extracted to public `SCHEMA_STATEMENTS`;
  `ensure_schema()` delegates to the migration runner
- `database/sqlite/queue_entry_repository.py` — `update()`'s optimistic-lock
  pre-read now goes through error-translation-wrapped `_execute_read`
  instead of a raw `connection.execute()` call, closing a bug where a
  pre-read failure would leak an untranslated `sqlite3` exception
- `pyproject.toml` — added `pythonpath = ["."]` under
  `[tool.pytest.ini_options]`

### Notes
- Full audit detail, including an unresolved fork regarding an alternate
  `repository_interface.py` contract referenced in a prior session but never
  uploaded: `docs/reviews/R005/PROJECT_STATE.md`.

## [0.5.1] - Phase 5.1: SQLite Repository Design

### Added
- `docs/architecture/SQLITE_REPOSITORY_DESIGN.md` (frozen)
- Repository lifecycle, composition, identity strategy, transaction
  strategy, error translation strategy, pilot concurrency model documented

### Notes
- Architecture Gate Review finding C-1 resolved through ADR-004 (Authority
  Hierarchy clarification); C-2/C-3 (documentation consistency) logged as
  non-blocking.

## [0.5.0] - Phase 5: Repository Interface Design

### Added
- `docs/architecture/REPOSITORY_INTERFACE.md` (frozen) — implementation-
  independent repository contracts, domain-level data contracts, error
  contract, transaction boundary, concurrency expectations, testing strategy

## [0.4.0] - Phase 4 / 4.1: Business Rules & Queue Rules

### Added
- `docs/architecture/BUSINESS_RULES.md` (frozen)
- `docs/architecture/QUEUE_RULES.md` (frozen)
- `docs/architecture/QUEUE_STATE_MACHINE.md` — state machine extracted from
  Queue Rules as the authoritative Queue Engine design reference

## [0.3.0] - Phase 3 / 3.1: System Architecture & Database Design

### Added
- `docs/architecture/SYSTEM_ARCHITECTURE.md` (frozen)
- `docs/architecture/DATABASE_DESIGN.md` (frozen)
- ADR-003 recorded

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
