# queue/

**Responsibility:** Core application logic — the heart of the application.

- Queue Engine
- Appointment workflow
- Queue algorithms
- Business orchestration

**Dependency rule:** `queue/` may depend on `telephony/interface.py` and
`database/`. It must **never** import a concrete telephony adapter (e.g.
SIM900A) — only the abstract interface. This is what keeps the Queue Engine
telephony-agnostic per the frozen architecture.

**Status (Phase 2):** Structure only. Queue Engine logic is implemented in
Phase 8.

**⚠️ Naming note (tracked in RISK_REGISTER.md):** This directory name shadows
Python's standard library `queue` module. This is flagged for review before
Phase 8 implementation begins — see Decision Log for the pending
recommendation.
