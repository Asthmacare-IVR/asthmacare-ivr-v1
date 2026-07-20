# System Architecture

**Status:** Phase 3 — Frozen for Pilot v1.0 (per Engineering Charter v3.0 baseline)
**Related decisions:** ADR-001 (Telephony Interface clarification), ADR-002
(folder structure), ADR-003 (queue_engine rename, doc split)

---

## 1. Purpose

This document is the authoritative technical description of how the
AsthmaCare IVR Platform is structured internally. Where `README.md` gives a
simplified six-layer overview for newcomers, this document gives the
precise contracts, dependency rules, and rationale an implementer needs.

---

## 2. Runtime Pipeline (Frozen, unchanged from README)

```
Patient
    │
    ▼
Telephony Adapter
    │
    ▼
Queue Engine
    │
    ▼
Business Rules
    │
    ▼
Database
    │
    ▼
REST API
    │
    ▼
Admin Dashboard
```

This is the *conceptual* data/event flow a patient interaction follows. It
is **not** a literal function-call chain — e.g., the REST API and Admin
Dashboard are also entry points for staff, not just downstream of a call.
The diagram communicates primary direction of flow, not exhaustive control
flow.

---

## 3. The Telephony Interface Pattern (Dependency Inversion)

### 3.1 Problem

The Queue Engine must function identically regardless of whether patient
interaction arrives via SIM900A GSM hardware (pilot) or, in a future
version, Cloud IVR / SIP / Asterisk. If the Queue Engine imports and calls
SIM900A-specific code directly, replacing the telephony layer later means
rewriting the Queue Engine — which violates the frozen architectural
requirement (README: "Queue Engine must remain independent of the
Telephony Adapter").

### 3.2 Solution — Dependency Inversion Principle (DIP)

Instead of the Queue Engine depending on a concrete adapter, both the Queue
Engine and every concrete adapter depend on a shared abstraction: the
**Telephony Interface**.

```
                    ┌───────────────────┐
                    │   Queue Engine     │
                    │  (queue/)          │
                    └─────────┬──────────┘
                              │ depends on (calls methods on)
                              ▼
                    ┌───────────────────────────┐
                    │  Telephony Interface       │
                    │  (telephony/interface.py)  │
                    │  — abstract contract —     │
                    └─────────────▲───────────────┘
                                  │ implements
              ┌───────────────────┼───────────────────┬──────────────┐
              │                   │                   │              │
     ┌────────┴────────┐ ┌────────┴────────┐ ┌────────┴───────┐ ┌────┴─────┐
     │ SIM900A Adapter  │ │ Cloud IVR Adapter│ │  SIP Adapter   │ │  Mock    │
     │   (Phase 7)      │ │    (future,      │ │   (future,     │ │ Adapter  │
     │                  │ │  out of v1.0)    │ │  out of v1.0)  │ │ (testing)│
     └──────────────────┘ └──────────────────┘ └────────────────┘ └──────────┘
```

**Key point:** the arrow between Queue Engine and Telephony Interface points
*from* Queue Engine *to* the interface — the Queue Engine owns the contract
it needs, and adapters conform to it. This is the inversion: normally you'd
expect the "lower level" telephony code to define the interface, but here
the "higher level" business logic (Queue Engine) defines what it needs, and
telephony implementations must satisfy that need.

### 3.3 UML — Class Diagram (conceptual, pre-implementation)

```
┌────────────────────────────────┐
│      <<abstract>>               │
│      TelephonyInterface         │
├──────────────────────────────────┤
│ + send_sms(to, message) : bool  │
│ + receive_call() : CallEvent    │
│ + send_dtmf_prompt(...) : None  │
│ + hangup(call_id) : None        │
└──────────────────────────────────┘
              △
              │ implements
   ┌──────────┴───────────┐
   │                       │
┌──┴──────────────┐   ┌────┴─────────────┐
│ SIM900AAdapter   │   │  MockAdapter     │
│  (Phase 7)       │   │  (test double)   │
└──────────────────┘   └──────────────────┘
```

**Note:** The exact method signatures above are illustrative only — they
are **not yet approved or implemented**. The real contract is designed at
the start of Phase 7 (Telephony Adapter), once SIM900A hardware has
arrived and its actual AT-command capabilities are known. Defining the
interface too early, before hardware constraints are known, risks
designing an abstraction that doesn't fit reality — a known anti-pattern
(speculative generality). `telephony/interface.py` therefore remains
empty until Phase 7, per ADR-002.

### 3.4 Why this satisfies "Queue Engine must never import a concrete adapter"

Because `queue/` only ever imports `telephony.interface`, never
`telephony.adapters.sim900a` (or any future adapter module). At Phase 8,
this will be enforced by:
- Code review (manual)
- Optionally, a static-analysis rule or `pytest` architecture test that
  fails the build if `queue/` imports anything under
  `telephony/adapters/` — a decision to be proposed at Phase 8 planning
  time, not implemented here.

---

## 4. Module Dependency Rules (Frozen, per ADR-002)

```
Dashboard → API → Queue Engine → Database
Queue Engine → Telephony Interface ← Telephony Adapter → Telephony Interface
```

| Module | May depend on | Must never depend on |
|---|---|---|
| `dashboard/` | `api/` (via HTTP only, not direct import) | `queue/`, `database/`, `telephony/` directly |
| `api/` | `queue/` | `telephony/` directly, `database/` directly (goes through `queue/`) |
| `queue/` | `telephony/interface.py`, `database/` | Any concrete `telephony/adapters/*` module |
| `database/` | (nothing internal) | `queue/`, `api/`, `telephony/` |
| `telephony/interface.py` | (nothing internal) | Everything — it is the innermost contract |
| `telephony/adapters/*` (future) | `telephony/interface.py` | `queue/`, `api/`, `database/` |
| `config/` | (nothing internal) | Business logic of any kind |

**Rationale:** This is a standard layered/hexagonal architecture. Each
module can be tested in isolation; `queue/` can be fully tested
against a `MockAdapter` with zero hardware, which matters given SIM900A
hardware delivery is currently blocked (see `docs/RISK_REGISTER.md`, R-003).

---

## 5. Why Not a Simpler Design?

Per Decision Management principles, documenting why we didn't take a
simpler path:

**Alternative considered:** Queue Engine directly imports and calls SIM900A
serial functions.
**Rejected because:** Migrating to Cloud IVR later would require rewriting
`queue/`, which the frozen baseline explicitly forbids ("without
changes to the queue engine, business rules, database, or API").

**Alternative considered:** A generic "Telephony Service" class instead of
an abstract interface + adapters.
**Rejected because:** A single concrete class with `if hardware == "sim900a"`
branching inside it accumulates conditional complexity as more telephony
backends are added (Cloud IVR, SIP, Asterisk are explicitly on the
long-term roadmap, even though out of scope for v1.0). The interface +
adapter pattern keeps each backend's logic isolated and independently
testable.

---

## 6. Open Items for Later Phases

- **Phase 7:** Define the real `TelephonyInterface` method signatures once
  SIM900A AT-command behavior is confirmed against actual hardware.
- **Phase 8:** Decide whether to add an automated architecture-boundary
  test (e.g. import-linter or a custom pytest check) enforcing the
  dependency rules in Section 4. Will be proposed via ADR before
  implementation.
- **Phase 5:** `database/` repository interface design (analogous DIP
  question for SQLite → future PostgreSQL) is addressed in
  `docs/DATABASE_DESIGN.md`, not here.
