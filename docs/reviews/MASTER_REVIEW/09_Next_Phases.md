# 09 — Next Phases

Immediately following this restructuring, in recommended order:

1. **R006.1 — Queue Engine Hardening** (blocking next phase)
   - Fix the `uow` fixture defect in `tests/test_queue_engine_integration.py`
     (Action Item #2).
   - Run the real `pytest` suite (Action Item #1) and confirm zero
     regressions across contract, unit, and integration tests.
   - Add SQLite-backed Queue Engine integration coverage, per
     `docs/architecture/DATABASE_DESIGN.md` §9's deferred scope.

2. **R007 — Telephony Adapter** (Phase 7/8 in `docs/roadmap/ROADMAP.md`)
   - Blocked on SIM900A hardware delivery (`docs/roadmap/RISK_REGISTER.md`
     R-003).
   - Concrete implementation of `telephony/interface.py` — must remain
     swappable per the Telephony Interface abstraction
     (`docs/architecture/SYSTEM_ARCHITECTURE.md`).

3. **R008 — Business Rules Runtime Wiring** (Phase 9 in `ROADMAP.md`)
   - Currently `docs/architecture/BUSINESS_RULES.md` is documentation-only;
     no code enforces it yet outside what `queue_engine/` already implements
     structurally (state machine, ordering, retries, timeouts).
   - Wire `backend/config/` to construct real `SqliteRepositoryProvider`
     instances (Action Item #5).

4. **R009 — Admin Dashboard** (Phase 10) and **R010 — REST API** (Phase 11)
   - Both currently empty placeholders under `backend/dashboard/` and
     `backend/api/`.
   - REST API phase is also where CI workflows in `.github/` were
     previously proposed but not yet approved (`docs/roadmap/TODO.md`).

5. **R011 — Raspberry Pi Deployment** (Phase 12)
   - Blocked on hardware purchase (`docs/roadmap/RISK_REGISTER.md` R-003).
   - Revisit the WSL2-vs-native-Windows development-platform decision
     (D-002, `docs/adr/DECISION_LOG.md`) before this phase, as originally
     flagged.

6. **R012 — Testing & QA** (Phase 13)
   - Full integration tests spanning Queue Engine → real SQLite were
     explicitly deferred to this phase in `docs/architecture/
     DATABASE_DESIGN.md` §9 — do not treat R006.1's SQLite-backed coverage
     as a substitute for the full QA pass.

7. **R013 — Pilot Release v1.0.0** (Phase 14)
   - Gated on all of the above, per the phase-gate practice already in use
     (each phase in `ROADMAP.md` completes only when acceptance criteria are
     explicitly approved by the Product Owner).
