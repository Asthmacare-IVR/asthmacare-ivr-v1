# 06 — AI Review Comparison

This project has now been reviewed by AI assistance across at least three
distinct sessions. This note compares them so a human reviewer can see where
they agree, where they diverge, and what remains unresolved.

## Session A — prior Phase 6 database delivery + audit (`docs/reviews/R005/PROJECT_STATE.md`)

- Merged an "audited" database-layer zip against a live repo, diffed it
  against an earlier in-session delivery (7 files differed), and re-verified
  everything with a hand-written harness (no `pytest` available in that
  sandbox either).
- Flagged an **unresolved fork**: a prior session's transcript described an
  alternate `repository_interface.py` contract (different state-enum name,
  repository-generated identity, extra methods) that was never actually
  uploaded as a file. Session A explicitly declined to reconstruct it from
  a secondhand, self-contradictory paraphrase, and treated the
  markdown-doc-conformant implementation as authoritative until the real
  file is provided.
- Self-scored the database layer 90/100, overall project 22/100.

## Session B — this restructuring / Queue Engine merge

- Did not re-open the Session A fork; no new information about
  `repository_interface.py` was provided in this task, so it remains
  unresolved exactly as Session A left it (see `07_Open_Issues.md`).
- Independently verified imports and core `queue_engine/` logic (state
  machine, ordering) against the *existing, merged* `database.domain`
  contract — confirmed compatible with zero changes needed.
- Found a **new** defect not present in Session A's scope: the Queue
  Engine's own delivered integration test fixture
  (`tests/test_queue_engine_integration.py::uow`) does not match the
  `InMemoryUnitOfWork` constructor contract that Session A's delivered
  `tests/conftest.py::uow_factory` fixture already uses correctly. This is
  new because Session A never touched `queue_engine/` — it did not exist
  yet at that point.
- Did not attempt to fix the defect (see `PROJECT_RESTRUCTURE_REPORT.md` —
  "do not rewrite the Queue Engine" was in scope for this task); logged it
  instead.

## Points of agreement

- Both sessions independently reached for a manual verification harness in
  the absence of network-installable `pytest`, and both flag that the real
  test suite still needs to be run in a networked environment before either
  delivery is called fully verified.
- Both sessions treat "don't guess at unseen or unapproved specs" as a hard
  rule rather than filling gaps with assumptions.

## Open discrepancy carried forward

The `repository_interface.py` fork from Session A is still open. If it is
meant to supersede `docs/architecture/REPOSITORY_INTERFACE.md`, the actual
file (plus a decision on `QueueState` vs. `QueueEntryState`, identity
strategy, and package layout) needs to be supplied and reviewed as its own
ADR before further `database/` changes — this restructuring did not resolve
it because doing so is out of scope for a repository-restructuring task.
