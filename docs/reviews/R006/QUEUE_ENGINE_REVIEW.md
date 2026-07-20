# R006 — Queue Engine Implementation (Merge Review)

**Status:** Implemented (Pending Hardening)

**Scope:** The approved Queue Engine package (`queue_engine/`), merged into
the live `Asthmacare-IVR` repository as part of this restructuring, plus the
pre-requisite `queue_engine` → `queue_engine/` rename (ADR-006, resolving risk
R-004).

## Delivered

- `queue_engine/engine.py` — `QueueEngine` orchestrator: state transitions,
  event emission, ordering/timeout/retry delegation
- `queue_engine/state_machine.py` — `QueueStateMachine`, validates
  transitions per `QUEUE_RULES.md` §5.3 (ADR-004 applied: `IN_SERVICE` →
  `CANCELLED` removed)
- `queue_engine/ordering.py` — `QueueOrdering`, computed (not stored)
  positions per `QUEUE_RULES.md` §6
- `queue_engine/retry_manager.py` — bounded notification retry tracking
- `queue_engine/timeout_manager.py` — admission/notification/confirmation
  timeout detection
- `queue_engine/events.py` — plain-data `QueueEvent`/`EventType`
- `tests/test_queue_engine_state_machine.py`,
  `tests/test_queue_engine_ordering.py`,
  `tests/test_queue_engine_integration.py`
- `docs/adr/ADR-006-r004-resolution.md` — approved, resolves R-004

## Merge validation performed

Since `pytest` could not be installed in this environment (no network
access), validation was performed the same way as the R005 audit: direct
imports plus a hand-written harness, not the real `pytest` binary. Run
`pip install -r requirements.txt && pytest` yourself for the authoritative
result.

1. **Imports** — every module under `database/`, `telephony/`, and
   `queue_engine/` imports cleanly from the repo root with no circular or
   broken references. ✅
2. **Test collection** — all 13 files under `tests/` (including the three
   Queue Engine test files) import/collect without error under a minimal
   pytest-compatible stub. ✅
3. **Core logic spot-check** — `QueueOrdering.compute_positions`,
   `QueueOrdering.get_position`, and `QueueStateMachine.assert_valid`
   (including its rejection of a transition out of a terminal state)
   were exercised directly against `database.domain.QueueEntry` /
   `QueueState` and behave as documented. ✅
4. **Integration test fixture — confirmed defect.** ❌
   `tests/test_queue_engine_integration.py`'s `uow` fixture calls
   `InMemoryUnitOfWork()` with no arguments and uses the result directly
   (never entering its context manager). Reproduced directly:

   ```
   >>> InMemoryUnitOfWork()
   TypeError: InMemoryUnitOfWork.__init__() missing 1 required positional
   argument: 'store'
   ```

   `InMemoryUnitOfWork.__init__(self, store: InMemoryStore)` requires a
   store, and `.patients` / `.queue_entries` are only assigned inside
   `__enter__`. `tests/conftest.py`'s existing `uow_factory` fixture already
   does this correctly (`InMemoryUnitOfWork(store)` inside a `with` block),
   so the fix is mechanical — but it was **not** applied here, per this
   task's "do not rewrite the Queue Engine" scope. Every test in
   `TestAdmitFlow`, `TestNotifyFlow`, `TestConfirmFlow`, `TestCompleteFlow`,
   `TestCancelFlow`, `TestNoShowFlow`, `TestInvalidTransitions`,
   `TestEvents`, and `TestOrdering` in that file depends on this fixture and
   will fail at setup or on first repository access until it is corrected.

   Logged as **R-005** in `docs/roadmap/RISK_REGISTER.md` and as an
   **R006.1 Hardening** action item (see
   `../MASTER_REVIEW/08_Action_Items.md`).

## Outcome

Core Queue Engine modules (state machine, ordering, retry, timeout, events,
engine orchestration) integrate cleanly with the existing `database.domain`
/ `database.interfaces` contracts and the `queue_engine` → `queue_engine/` rename
is complete and consistent throughout the merged tree. The one integration
test fixture defect above is scoped to test code only — no production
(`queue_engine/*.py`) code is affected — and is deferred to R006.1 Hardening
rather than fixed silently during this restructuring.
