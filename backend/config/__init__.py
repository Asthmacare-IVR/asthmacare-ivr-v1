"""AsthmaCare IVR Platform — backend/ (grouping package).

Introduced by the R006 repository restructuring as a grouping package for
`api/`, `config/`, `dashboard/`, `assets/`, `scripts/`, and `logs/` (see
backend/README.md and PROJECT_RESTRUCTURE_REPORT.md). This file was added
by the Backend API Foundation task (GitHub Issue #1) so that
`backend.api.app` imports as a regular package, consistent with every
sibling top-level package (`database/`, `telephony/`, `queue_engine/`),
which already has its own `__init__.py`.
"""
