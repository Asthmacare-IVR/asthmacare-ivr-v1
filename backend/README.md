# backend/

**Responsibility:** Groups the application's "outer layer" placeholder
modules — the pieces that will eventually expose or support the Queue
Engine / Database core, but do not yet contain runtime logic.

This folder was introduced by the R006 repository restructuring purely as a
**grouping move**: `api/`, `config/`, `dashboard/`, `assets/`, `scripts/`,
and `logs/` were relocated here unchanged (no file content modified) so that
`database/`, `queue_engine/`, and `telephony/` — the three modules that
currently contain real, tested implementation — sit at the top level
alongside `backend/`, `docs/`, and `tests/`, matching the target structure
for this restructuring.

| Subfolder | Responsibility | Status |
|---|---|---|
| `api/` | REST API surface (Phase 11) | Placeholder — `__init__.py` + README only |
| `config/` | Wiring/configuration, e.g. constructing `database.sqlite.factory.SqliteRepositoryProvider` (Phase 8/9) | Placeholder — not yet wired (see Open Issue I-5) |
| `dashboard/` | Admin Dashboard (Phase 10) | Placeholder |
| `assets/` | Static assets | Placeholder |
| `scripts/` | Operational/maintenance scripts | Placeholder |
| `logs/` | Runtime log output directory | Placeholder |

No import in the codebase referenced `api`, `config`, `dashboard`, `assets`,
`scripts`, or `logs` as top-level packages prior to this move (verified by
search), so this regrouping introduces no import breakage. If any future
code does `from config import ...` or similar, update it to
`from backend.config import ...`.
