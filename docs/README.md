# docs/

**Responsibility:** Engineering documentation.

**Status:** Reorganized during the R006 (Queue Engine) merge into subject-area
subfolders, per the repository restructuring baseline. Nothing was deleted —
every file that previously lived directly under `docs/` (or at the repo
root) has moved to one of the folders below. See
`PROJECT_RESTRUCTURE_REPORT.md` at the repo root for the full move log.

## Structure

- **`adr/`** — Architecture Decision Records and the master `DECISION_LOG.md`
  (D-001 … D-NNN plus formal `ADR-00N-*.md` files).
- **`architecture/`** — Frozen design contracts: system architecture,
  database design, business rules, queue rules/state machine, repository
  interface, SQLite repository design.
- **`roadmap/`** — `ROADMAP.md` (frozen v1.0), `PROJECT_PROGRESS.md` (phase
  log), `TODO.md`, `RISK_REGISTER.md` (merged/updated), and the new
  `PROJECT_PHASE_STATUS.md` snapshot.
- **`reviews/`** — One folder per review package (`R001`–`R006`), each
  containing that package's review evidence (or an index pointing to where
  the evidence lives, if the deliverable itself is architecture-only), plus
  `MASTER_REVIEW/` — the consolidated baseline across all six packages.

## Original Phase 2 Note (preserved verbatim for history)

> **Assumption (flagged for confirmation, not yet approved as binding):**
> Project meta-documents that already exist at the repository root
> (`README.md`, `CHANGELOG.md`, `ROADMAP.md`, `TODO.md`, `PROJECT_PROGRESS.md`,
> `DECISION_LOG.md`, `RISK_REGISTER.md`) remain at the root, since that's
> their established convention and GitHub renders root-level `README.md`
> automatically. Phase-specific engineering documents not yet created
> (`SYSTEM_ARCHITECTURE.md`, `DATABASE_DESIGN.md`, `BUSINESS_RULES.md`,
> `QUEUE_RULES.md`, `PATIENT_FLOW.md`, `TEST_PLAN.md`, `TEST_REPORT.md`) will
> be created inside `docs/` when their owning phase begins, rather than at
> root. Please confirm or correct this interpretation before Phase 3 creates
> `SYSTEM_ARCHITECTURE.md`.
>
> **Status (Phase 2):** Empty except this placeholder.

**Resolution:** superseded by the R006 repository restructuring. Root now
holds only `README.md` and `CHANGELOG.md`; every other meta-document named
above has moved into `docs/roadmap/` or `docs/adr/` as indexed above.
