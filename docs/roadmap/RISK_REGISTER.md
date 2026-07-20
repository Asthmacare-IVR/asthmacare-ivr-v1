# Risk Register

Merged register: original `RISK_REGISTER.md` (Phase 1–2 baseline) plus the
`RISK_REGISTER_updated.md` delivered with the Queue Engine (R006) package,
which resolved R-004. No entries have been removed; R-004's original row is
preserved (struck through) alongside its resolution for audit continuity.

| ID | Risk | Phase Introduced | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|---|---|
| R-001 | Windows-native serial handling (pyserial) may behave differently than on Linux/Pi, causing rework at Phase 6 or 12 | 1 | Medium | Medium | Keep Telephony Adapter interface narrow and OS-agnostic; revisit WSL2 decision (D-002) before Phase 6 | Open |
| R-002 | SQLite file could be accidentally committed to Git, exposing patient data | 1 | Low | High | `.gitignore` excludes `*.db` / `*.sqlite3`; enforce in code review | Mitigated |
| R-003 | Hardware delivery delay (SIM900A, Pi) stalls Phases 6/12 | 1 | Medium | Medium | Software phases (2–5, 7–11 partially) sequenced to not depend on hardware arrival | Monitored |
| ~~R-004~~ | ~~Top-level `queue_engine` directory/package shadows Python's standard library `queue` module, risking import shadowing bugs (affects asyncio, concurrent.futures, and any library doing `import queue`)~~ | ~~2~~ | ~~Medium~~ | ~~Medium-High~~ | ~~Resolved by ADR-006: renamed to `queue_engine/`~~ | **RESOLVED** — see ADR-006 |

## R-004 Resolution Details

- **ADR:** ADR-006 (`docs/adr/ADR-006-r004-resolution.md`)
- **Action:** Renamed `queue_engine` → `queue_engine/`
- **Date:** 2026-07-20
- **Impact:** Unblocks Phase 8/9 (Queue Engine implementation)
- **Verification:** All imports updated; test suite passes for engine, ordering,
  and state-machine modules. See `docs/reviews/R006/QUEUE_ENGINE_REVIEW.md`
  for one open test-fixture defect found during merge validation
  (`tests/test_queue_engine_integration.py`), tracked as an R006.1 hardening
  item — it does not affect R-004 itself.

## New Risk Logged at R006 Merge

| ID | Risk | Phase Introduced | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|---|---|
| R-005 | `tests/test_queue_engine_integration.py`'s `uow` fixture instantiates `InMemoryUnitOfWork()` with no arguments and never enters its context manager, but `InMemoryUnitOfWork.__init__` requires a `store: InMemoryStore` argument and only populates `.patients` / `.queue_entries` inside `__enter__`. As delivered, the integration test file will raise `TypeError` at fixture setup / `AttributeError` on first repository access. | 6 (R006 merge) | High (deterministic) | Low (test-only; no production code path affected) | Fix the fixture to construct `InMemoryStore()` then `InMemoryUnitOfWork(store)` and use it inside a `with` block (or call `__enter__`/`__exit__` explicitly), matching the pattern already used in `tests/conftest.py::uow_factory`. Left unmodified in this merge per "do not rewrite the Queue Engine" scope; tracked for R006.1 Hardening. | Open |

See `docs/reviews/MASTER_REVIEW/07_Open_Issues.md` for the consolidated open-issues view.
