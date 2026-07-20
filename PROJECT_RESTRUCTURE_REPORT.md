# PROJECT_RESTRUCTURE_REPORT.md

Repository restructuring + Queue Engine (R006) merge report. This was a
**restructuring and merge task only** — no architecture redesign, no
business-rule change, no rewriting of the Queue Engine, no test removal.

## 1. Files moved

| Original path | New path |
|---|---|
| `DECISION_LOG.md` | `docs/adr/DECISION_LOG.md` |
| `docs/ADR-005-phase6-open-decisions.md` | `docs/adr/ADR-005-phase6-open-decisions.md` |
| `docs/BUSINESS_RULES.md` | `docs/architecture/BUSINESS_RULES.md` |
| `docs/DATABASE_DESIGN.md` | `docs/architecture/DATABASE_DESIGN.md` |
| `docs/QUEUE_RULES.md` | `docs/architecture/QUEUE_RULES.md` |
| `docs/QUEUE_STATE_MACHINE.md` | `docs/architecture/QUEUE_STATE_MACHINE.md` |
| `docs/REPOSITORY_INTERFACE.md` | `docs/architecture/REPOSITORY_INTERFACE.md` |
| `docs/SQLITE_REPOSITORY_DESIGN.md` | `docs/architecture/SQLITE_REPOSITORY_DESIGN.md` |
| `docs/SYSTEM_ARCHITECTURE.md` | `docs/architecture/SYSTEM_ARCHITECTURE.md` |
| `docs/PARITY_FIX.md` | `docs/reviews/R005/PARITY_FIX.md` |
| `PROJECT_STATE.md` | `docs/reviews/R005/PROJECT_STATE.md` |
| `ROADMAP.md` | `docs/roadmap/ROADMAP.md` |
| `PROJECT_PROGRESS.md` | `docs/roadmap/PROJECT_PROGRESS.md` |
| `TODO.md` | `docs/roadmap/TODO.md` |
| `api/` (incl. `__init__.py`, `README.md`) | `backend/api/` |
| `config/` (incl. `__init__.py`, `README.md`) | `backend/config/` |
| `dashboard/README.md` | `backend/dashboard/README.md` |
| `assets/README.md` | `backend/assets/README.md` |
| `scripts/README.md` | `backend/scripts/README.md` |
| `logs/README.md` | `backend/logs/README.md` |
| `queue_engine` (placeholder: `README.md`, `__init__.py`) | **removed**, superseded by `queue_engine/` (see §3 — approved rename, not a data-preserving move, since `queue_engine` held no runtime logic) |

`database/`, `telephony/`, `tests/`, `pyproject.toml`, `requirements.txt`,
`.gitignore`, `.github/`, `.vscode/` were relocated into the new root
unchanged (same relative structure, same file contents).

## 2. Files renamed

| Original | Renamed to | Authorization |
|---|---|---|
| `queue_engine` (directory) | `queue_engine/` (directory) | ADR-006 (`docs/adr/ADR-006-r004-resolution.md`), approved 2026-07-20, resolving risk R-004 |

No other file or module was renamed.

## 3. Files merged

| Merge | Result |
|---|---|
| `queue_engine_package.zip`'s `queue_engine/` module into the main repo | `queue_engine/` now sits at the repo root, replacing the empty `queue_engine` placeholder per the approved ADR-006 rename |
| `queue_engine_package.zip`'s `tests/test_queue_engine_*.py` (3 files) into the main repo's `tests/` | Now alongside all existing tests in the single top-level `tests/` folder (target structure specifies one `tests/` folder, not a per-module one) |
| `RISK_REGISTER.md` (original) + `RISK_REGISTER_updated.md` (from Queue Engine package) | `docs/roadmap/RISK_REGISTER.md` — R-004 marked resolved (struck through, not deleted), resolution detail added, new risk R-005 logged (see §7 below) |
| `queue_engine_package.zip`'s `docs/ADR-006-r004-resolution.md` | `docs/adr/ADR-006-r004-resolution.md` (moved in, not merged with another file — no prior ADR-006 existed) |

## 4. Files preserved (content unchanged, only relocated or left in place)

- All files under `database/`, `telephony/`, `tests/` (except the 3 new
  Queue Engine test files added, see §3) — byte-for-byte unchanged.
- `pyproject.toml`, `requirements.txt`, `.gitignore`, `.vscode/*`,
  `.github/README.md` — unchanged, unmoved.
- `ROADMAP.md` — moved to `docs/roadmap/ROADMAP.md` but its content was
  **not edited**, even though it is known to be stale (see Open Issue I-6);
  a supplementary `docs/roadmap/PROJECT_PHASE_STATUS.md` was added instead
  of touching the frozen original.
- All 7 architecture documents, `DECISION_LOG.md`, `ADR-005-*.md`,
  `PARITY_FIX.md`, `PROJECT_STATE.md`, `PROJECT_PROGRESS.md`, `TODO.md` —
  content unchanged, only relocated.
- `queue_engine/*.py` (all 6 modules) and `queue_engine/README.md` — content
  unchanged from the delivered package, only relocated to the repo root.

## 5. Files duplicated

None. Every document above was **moved** (single copy retained at its new
location), not copied-and-left-behind. `docs/reviews/R001`–`R004` contain
new index/README files (not duplicates) that link to the single authoritative
copy of each underlying document rather than duplicating its content.

## 6. Files removed

- Only the two placeholder files under the old `queue_engine` (`README.md`,
  `__init__.py`) were removed, and only because they are fully superseded by
  the approved `queue_engine/` rename (ADR-006) — their content (structure-
  only placeholders, no runtime logic) is preserved in spirit in
  `queue_engine/README.md` and `queue_engine/__init__.py`, which explicitly
  reference the rename and R-004 resolution.
- Build/cache artifacts (`__pycache__/`, `*.pyc`, `.pytest_cache/`,
  `.ruff_cache/`) and the `.venv/` virtual environment directory were
  excluded from the delivered ZIP. These are regenerable local-environment
  artifacts, not source or documentation, and including `.venv/` in
  particular would have added ~50MB of vendored third-party packages
  (pip, black, pytest, etc.) with no restructuring value. `.git/` history
  was likewise excluded from the ZIP for the same reason (regenerable,
  environment-specific, not part of the documentation/code deliverable);
  the project's git tags (`v0.1.0`, `v0.4.0`, `v0.5.0`, `v0.5.1`, `v0.5.2`)
  referenced in `CHANGELOG.md` come from the original repository's history
  and should be preserved there.

## 7. Broken links fixed / import changes

- **No import changes were required.** Verified by direct search that no
  existing code imported `api`, `config`, `dashboard`, `assets`, `scripts`,
  or `logs` as top-level packages before they were grouped under `backend/`
  — the move is import-safe as-is. If any future code does
  `from config import ...`, it must be updated to
  `from backend.config import ...`.
- `queue_engine/*.py` already imported `database.domain` /
  `database.interfaces` and its own sibling modules via
  `from queue_engine.x import y` in the delivered package — fully
  compatible with `queue_engine/` living at the repo root; no changes
  needed.
- Internal doc cross-references were updated only inside the **new** files
  this restructuring created (docs/README.md, review indexes, README.md,
  CHANGELOG.md) to point at the new `docs/adr/`, `docs/architecture/`,
  `docs/roadmap/`, `docs/reviews/` paths. No cross-references inside the
  **original, preserved** documents were edited.

## 8. Validation results

Performed with a hand-written harness (no network access to install
`pytest` in this environment — consistent with how the R005 audit was
validated):

| Check | Result |
|---|---|
| All `database/`, `telephony/`, `queue_engine/` modules import cleanly from repo root | ✅ Pass |
| All 13 files under `tests/` import/collect cleanly | ✅ Pass |
| `QueueOrdering.compute_positions` / `get_position` against `database.domain.QueueEntry` | ✅ Pass |
| `QueueStateMachine.assert_valid` — valid transition and terminal-state rejection | ✅ Pass |
| `tests/test_queue_engine_integration.py::uow` fixture | ❌ **Fails** — `InMemoryUnitOfWork()` called without required `store` argument; confirmed via direct reproduction (`TypeError: InMemoryUnitOfWork.__init__() missing 1 required positional argument: 'store'`) |
| No duplicate files (by content/purpose) | ✅ Pass — same-named files across different modules (e.g. `errors.py` in both `database/` and `telephony/`) are distinct, legitimate per-module files |
| No broken paths in new documentation | ✅ Pass — all relative links in newly created docs verified against the final tree |
| `__init__.py` present in every Python package directory | ✅ Pass |

**Full authoritative verification (`pip install -r requirements.txt && pytest`)
has not been performed** in any sandbox to date — see Action Item #1 in
`docs/reviews/MASTER_REVIEW/08_Action_Items.md`.

## 9. Warnings

1. `tests/test_queue_engine_integration.py` will fail at fixture setup until
   the `uow` fixture is corrected (see §8, and Action Item #2). This is a
   pre-existing defect in the delivered Queue Engine test package, not
   something introduced by this restructuring, and it was deliberately
   **not** fixed here per the "do not rewrite the Queue Engine" scope of
   this task.
2. `docs/roadmap/ROADMAP.md` is stale relative to actual project state
   (e.g. it lists Phase 6 as "Not Started" though it is implemented and
   tested). Left unedited per "do not remove/rewrite existing
   documentation"; `docs/roadmap/PROJECT_PHASE_STATUS.md` was added as a
   living supplement instead.
3. The R001–R006 review-package numbering used for `docs/reviews/` is a
   flagged mapping onto the project's own Phase 1–6 numbering (see
   `docs/reviews/MASTER_REVIEW/01_Project_Status.md`), since the project's
   existing documents track phases, not "R00N" review packages, prior to
   this task's own framing of the Queue Engine as "R006". This mapping
   needs Product Owner confirmation, the same way the original Phase 2
   docs-placement assumption did.
4. An unresolved architectural fork from a prior session — an alternate
   `repository_interface.py` contract that was described but never
   uploaded — remains open. This restructuring did not attempt to resolve
   it, since doing so is out of scope for a repository-restructuring task.

## 10. Recommendations

See `docs/reviews/MASTER_REVIEW/08_Action_Items.md` for the full,
prioritized list. Top priority: fix the Queue Engine integration test
fixture (Action Item #2) and run the real `pytest` suite in a networked
environment (Action Item #1) before proceeding to R006.1 Hardening or R007
(Telephony Adapter).
