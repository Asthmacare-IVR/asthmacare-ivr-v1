# telephony/

**Responsibility:** Telephony abstraction layer.

Defines the contract (`interface.py`) that the Queue Engine depends on, and
which concrete telephony implementations must satisfy. This is the seam that
allows the SIM900A adapter to be replaced by Cloud IVR / SIP / Asterisk later
without touching `queue_engine`, `database/`, `api/`, or `dashboard/`.

**Planned contents (future phases, not yet created):**
- `adapters/` — concrete implementations (SIM900A in Phase 7; Cloud IVR, SIP,
  Asterisk later, out of scope for v1.0)
- `mock/` — a mock adapter for testing the Queue Engine without hardware

**Dependency rule:** `telephony/interface.py` depends on nothing else in this
project. Concrete adapters depend on `interface.py`. `queue_engine` depends on
`interface.py` only — **never** on a concrete adapter.

**Status (Phase 2):** `interface.py` exists as an empty placeholder only. No
SIM900A implementation exists yet (blocked on hardware — Phase 6).
