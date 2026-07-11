# dashboard/

**Responsibility:** Admin dashboard.

UI templates and static assets related to the dashboard only. No business
logic — the dashboard consumes data via `api/`.

**Dependency rule:** `dashboard/` depends on `api/` only (at the HTTP
boundary, not via direct Python import).

**Status (Phase 2):** Structure only. Templates and dashboard views are
implemented in Phase 9 – Admin Dashboard.
