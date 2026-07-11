# config/

**Responsibility:** Configuration.

- Environment variables
- Logging configuration
- Application settings

**Dependency rule:** `config/` depends on nothing else in this project. It
may be depended upon by any layer that needs settings (`api/`, `queue/`,
`database/`, `telephony/`).

**Status (Phase 2):** Structure only, per ADR-002 ("Do NOT implement any
runtime logic"). Actual settings/env loading is implemented starting Phase 3
onward, as each layer needs it.
