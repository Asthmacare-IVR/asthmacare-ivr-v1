# 08 — Action Items

| # | Action | Owner | Priority | Linked issue |
|---|---|---|---|---|
| 1 | Run `pip install -r requirements.txt && pytest` in a real, networked environment and record the authoritative pass/fail result | Dev team | High | I-2 |
| 2 | Fix `tests/test_queue_engine_integration.py`'s `uow` fixture: construct `InMemoryStore()` then `InMemoryUnitOfWork(store)` and use it inside a `with` block (mirroring `tests/conftest.py::uow_factory`) | Dev team | High | I-3 |
| 3 | Re-run the full test suite after action #2 to confirm the Queue Engine integration suite passes end-to-end | Dev team | High | I-3 |
| 4 | Decide the `repository_interface.py` fork: either produce the actual file for review (plus a superseding ADR), or formally close I-1 as "no such file exists, current implementation stands" | Product Owner / Chief Architect | Medium | I-1 |
| 5 | Wire `backend/config/` to actually call `database.sqlite.factory.build_unit_of_work(...)` as part of upcoming Phase 8/9 work | Dev team | Medium | I-5 |
| 6 | Approve or correct the R001–R006 ↔ Phase-number mapping flagged in `01_Project_Status.md`, the same way Phase 2's docs-placement assumption was previously confirmed | Product Owner | Medium | — |
| 7 | When convenient, refresh `docs/roadmap/ROADMAP.md` itself (currently frozen/stale) — or formally adopt `docs/roadmap/PROJECT_PHASE_STATUS.md` as the living status document and mark `ROADMAP.md` as the historical v1.0 baseline only | Product Owner | Low | I-6 |
| 8 | Begin R006.1 Hardening once action items #2–#3 are complete: broaden Queue Engine test coverage to include SQLite-backed integration (not just in-memory), per `DATABASE_DESIGN.md` §9's deferred integration-test scope | Dev team | Medium | — |
| 9 | Proceed to R007 (Telephony Adapter / Service Layer) only after R006.1 Hardening closes, consistent with the roadmap's phase-gate practice used at every prior review | Dev team / Product Owner | Medium | — |
