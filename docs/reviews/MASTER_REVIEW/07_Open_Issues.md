# 07 — Open Issues

Consolidated from all six review packages plus this restructuring pass. No
issue below was introduced by the restructuring itself — all are carried
forward from prior deliveries or newly discovered during validation of what
was delivered.

| ID | Issue | Origin | Severity | Status |
|---|---|---|---|---|
| I-1 | Alternate `repository_interface.py` contract referenced in a prior session's transcript (different state enum name, repository-generated identity, extra methods) was never actually uploaded as a file; current `database/` implementation conforms to `docs/architecture/REPOSITORY_INTERFACE.md` instead | R005 | Medium (architectural ambiguity, not a defect) | Open — needs the real file + a superseding ADR if it is meant to apply |
| I-2 | No real `pytest` run has ever been performed on this codebase (R005 or R006) — every check has used a hand-written harness in a no-network sandbox | R005 / R006 | Medium (verification gap) | Open — run `pip install -r requirements.txt && pytest` in a networked environment |
| I-3 | `tests/test_queue_engine_integration.py`'s `uow` fixture instantiates `InMemoryUnitOfWork()` without the required `store` argument and never enters its context manager; every test in that file depends on it | R006 (this merge) | High for that test file (deterministic failure), Low overall (test-only, no production code affected) | Open — logged as risk R-005 (`docs/roadmap/RISK_REGISTER.md`), not fixed in place per this task's scope |
| I-4 | Standalone (non-`SqliteUnitOfWork`) `update()` path has a small race window between its pre-read and its conditional write under concurrent standalone use (documented, not a silent-lost-update risk since the conditional `WHERE` clause still raises `ConflictError`) | R005 | Low (documented, pilot-scale acceptable) | Open — worth an ADR if write concurrency increases |
| I-5 | `config/` (now `backend/config/`) has no code that actually calls `database.sqlite.factory.build_unit_of_work(...)` — nothing outside `tests/` constructs a `SqliteRepositoryProvider` yet | R005 | Low (expected — Phase 8/9 territory) | Open — tracked as forward work, not a defect |
| I-6 | `ROADMAP.md` (now `docs/roadmap/ROADMAP.md`) is stale relative to actual progress — it lists Phase 6 as "Not Started" though the database layer (R005) is implemented and tested, and does not yet reflect the Queue Engine (R006) at all | R001–R006 (documentation drift) | Low (documentation only) | Open — see `docs/roadmap/PROJECT_PHASE_STATUS.md` for the current snapshot; the frozen `ROADMAP.md` itself was left untouched per "do not remove/rewrite existing documentation" |

## Issues explicitly closed during this restructuring

None — this was a restructuring task, not a remediation task. I-3 was
*discovered*, not fixed, and I-6 was *worked around* with a new
supplementary document rather than editing the frozen original.
