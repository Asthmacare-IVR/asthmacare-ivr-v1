# queue_engine/

**Responsibility:** Core application logic — Queue Engine, appointment 
workflow, queue algorithms, business orchestration.

**Dependency rule:** 
- `queue_engine/` depends on `telephony/interface.py` (contract only)
- `queue_engine/` depends on `database/interfaces.py` (contract only)
- `queue_engine/` must NEVER import from `telephony/adapters/`, 
  `database/sqlite/`, or any concrete implementation

**Status:** Phase 8/9 — Implementation in progress (R-004 resolved per ADR-006)

**Submodules (planned):**
- `state_machine.py` — Queue state transition validation (QUEUE_RULES.md §5)
- `ordering.py` — FIFO + priority queue ordering (QUEUE_RULES.md §6)
- `engine.py` — Main Queue Engine orchestrator
- `events.py` — State change event emission
- `rules/` — Business Rules integration points
