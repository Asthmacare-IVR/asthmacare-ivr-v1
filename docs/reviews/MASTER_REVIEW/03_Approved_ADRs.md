# 03 — Approved ADRs

Full text lives in `docs/adr/`. Summary:

| Decision | Location | Status | Summary |
|---|---|---|---|
| D-001 | `docs/adr/DECISION_LOG.md` | Resolved | pip + `requirements.txt` for dependency management; `pyproject.toml` for tooling config only |
| D-002 | `docs/adr/DECISION_LOG.md` | Resolved (Phase 1–5), open recommendation logged | Native Windows 11 for Phase 1–5; WSL2 recommended-not-approved, revisit before Phase 6/12 |
| ADR-001 | Referenced in `docs/roadmap/PROJECT_PROGRESS.md` / CHANGELOG | Applied | Telephony Interface clarified as internal contract, not a pipeline stage; PostgreSQL noted as future migration target only |
| ADR-002 | Referenced throughout `docs/adr/DECISION_LOG.md`, `CHANGELOG.md` | Applied | Approved top-level folder structure (Phase 2) |
| ADR-003 | Referenced in `docs/reviews/R003/README.md` | Applied | Database Design decisions (Phase 3.1) |
| ADR-004 | Referenced in `queue_engine/state_machine.py`, `docs/architecture/QUEUE_RULES.md` | Applied | Removed `IN_SERVICE → CANCELLED` transition; also resolved Architecture Gate Review finding C-1 (Authority Hierarchy) |
| ADR-005 | `docs/adr/ADR-005-phase6-open-decisions.md` | Approved | Formally closes `SQLITE_REPOSITORY_DESIGN.md` §15 Open Decisions OD-1..OD-4 |
| ADR-006 | `docs/adr/ADR-006-r004-resolution.md` | Approved | Renames `queue_engine` → `queue_engine/`, resolving risk R-004 (stdlib `queue` shadowing); pre-requisite for Queue Engine implementation |

No ADR was altered, superseded silently, or reinterpreted during this
restructuring — all six above are carried forward unchanged.
