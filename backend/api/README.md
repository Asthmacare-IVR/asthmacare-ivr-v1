# api/

**Responsibility:** REST API layer only.

Contains HTTP endpoints, request validation, and response serialization.
No business logic lives here — it delegates to the `queue/` and `database/`
layers.

**Dependency rule:** `api/` may depend on `queue/`. It must never be depended
upon by `queue/`, `database/`, or `telephony/`.

**Status (Phase 2):** Structure only. FastAPI application code is implemented
in Phase 10 – REST API.
