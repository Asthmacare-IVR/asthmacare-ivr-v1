# database/

**Responsibility:** Database layer.

- SQLite access (pilot)
- Future PostgreSQL migration (documented target only — see ADR-001)
- Repository layer
- Migrations
- Seed scripts

**Dependency rule:** `database/` depends on nothing else in this project. It
is depended upon by `queue/` and `api/`.

**Status (Phase 2):** Structure only. Schema and repository implementation
begin in Phase 5 – Database Design.
