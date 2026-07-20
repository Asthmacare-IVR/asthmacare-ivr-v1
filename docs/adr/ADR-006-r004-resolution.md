# ADR-006: Resolve R-004 — Rename queue/ to queue_engine/

**Status:** Approved
**Date:** 2026-07-20
**Phase:** 8/9 — Queue Engine Implementation (pre-requisite)
**Raised by:** Development Team

## Context
RISK_REGISTER.md R-004: Top-level `queue/` package shadows Python's 
standard library `queue` module. This blocks Phase 8/9 (Queue Engine 
implementation) because `import queue` resolves to local package instead 
of stdlib, breaking `asyncio`, `concurrent.futures`, and any dependency 
using `import queue`.

## Decision
Rename top-level package: `queue/` → `queue_engine/`

## Rationale
- Minimal surgical change (single directory rename + import updates)
- More descriptive name ("queue engine" vs generic "queue")
- Zero tooling changes required
- Consistent with `database/`, `telephony/` naming
- `src/` layout deferred — revisit if project grows to multi-package

## Consequences
- All imports: `from queue import ...` → `from queue_engine import ...`
- Documentation references updated
- No external API impact (no REST API exists yet)

## Migration Steps
1. Rename directory: `queue/` → `queue_engine/`
2. Update `queue_engine/__init__.py` (was `queue/__init__.py`)
3. Update `queue_engine/README.md`
4. Update all docs referencing `queue/`
5. Verify no `import queue` (stdlib) in current codebase
6. Run test suite: zero regressions

## Closes
- RISK_REGISTER.md R-004 (resolved)
- Blocks Phase 8/9 Queue Engine implementation (unblocked)
