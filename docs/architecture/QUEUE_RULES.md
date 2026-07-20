# Queue Rules

**Document Phase:** 4.1
**Baseline:** Git tag `v0.4.0` (approved architecture baseline)
**Status:** Frozen upon Chief Architect approval
**Depends on:** `SYSTEM_ARCHITECTURE.md` (Phase 3), `BUSINESS_RULES.md` (Phase 4)
**Governs:** `queue_engine` module (Queue Engine) — architecture only, no implementation

---

## 1. Purpose and Scope

This document defines the architectural behavior of the **Queue Engine**: the
states a patient may occupy while queued, the transitions permitted between
those states, the ordering discipline applied to the queue, and the timeout,
retry, and error-handling behavior the Queue Engine must exhibit at a
structural level.

This document does **not**:

- Define specific numeric thresholds, durations, or scoring formulas for
  prioritization (owned by `BUSINESS_RULES.md`).
- Define persistence schema, table structure, or storage mechanics (owned by
  `DATABASE_DESIGN.md`).
- Define REST endpoints, request/response contracts, or API error codes
  (owned by the future `api/` design documentation, Phase 10).
- Define telephony message formats, SIM900A AT-command behavior, or IVR/SMS
  wording (owned by `telephony/` and `PATIENT_FLOW.md`).
- Contain Python code, SQL, pseudocode, or UI layout.

Where this document says a decision is "delegated to Business Rules," it
means the Queue Engine invokes that decision as an external policy input
without knowing or encoding the policy itself. This preserves the
single-responsibility boundary established in ADR-002.

---

## 2. Relationship to SYSTEM_ARCHITECTURE.md and BUSINESS_RULES.md

The Queue Engine sits between the Telephony Interface (contract) and
Business Rules in the frozen six-layer pipeline:

```
Patient → Telephony Adapter → Queue Engine → Business Rules → Database → REST API → Admin Dashboard
```

Two dependency directions govern this document:

1. **Queue Engine → Telephony Interface (Contract).** The Queue Engine
   consumes patient-initiated events (e.g., "join," "cancel," "confirm
   presence") only through the Telephony Interface contract defined in
   `SYSTEM_ARCHITECTURE.md`. It never depends on a concrete adapter
   (SIM900A, future Cloud IVR/SIP, or Mock). This is the same rule recorded
   in ADR-002 and is reaffirmed, not re-litigated, here.

2. **Queue Engine → Business Rules.** The Queue Engine owns *mechanism*
   (state, order, timing enforcement). `BUSINESS_RULES.md` owns *policy*
   (who gets priority, how long a slot is held, what counts as a no-show,
   what triggers escalation). Wherever this document requires a policy
   value or decision, it names the decision point and states that
   `BUSINESS_RULES.md` supplies the answer — it does not restate or
   duplicate that answer.

This document assumes `SYSTEM_ARCHITECTURE.md` and `BUSINESS_RULES.md` as
already frozen inputs and is constrained to remain consistent with both. Any
conflict discovered between this document and either predecessor must be
resolved by ADR before this document is considered frozen.

**Resolution (ADR-004):** The state machine in Section 5 is the Queue
Engine's internal operational realization of the domain-level lifecycle
defined in `BUSINESS_RULES.md` §10. The two are related by refinement, per
the canonical mapping in ADR-004 (`DECISION_LOG.md`), and are not in
conflict at the level of state naming or granularity. One substantive
conflict was identified and corrected by ADR-004: the `IN_SERVICE →
CANCELLED` ("Service abandoned/interrupted") transition previously in
Section 5.3 contradicted `BUSINESS_RULES.md` §4.9/§10, which permit no
outbound transition from Consultation other than normal completion. That
transition has been removed; see Section 5.3.

---

## 3. Queue Engine Responsibility Boundary

The Queue Engine is responsible for:

- Holding the authoritative in-memory/session representation of "who is
  currently in the queue and in what state."
- Enforcing valid state transitions (Section 5) and rejecting invalid ones.
- Enforcing ordering discipline (Section 6) at the moment ordering is
  queried, not by continuously re-sorting a stored list.
- Detecting timeout conditions (Section 8) and raising them as events for
  Business Rules to interpret.
- Emitting queue-state-change events consumed downstream by Database
  (for persistence) and, transitively, by API and Dashboard.
- Never persisting data directly (Database's responsibility) and never
  interpreting telephony payloads directly (Telephony Adapter's
  responsibility, translated through the Telephony Interface).

The Queue Engine is explicitly **not** responsible for:

- Deciding *why* one patient outranks another (Business Rules).
- Deciding *what* a no-show consequence is (Business Rules).
- Deciding *how* a state change is stored or recovered after a crash
  (Database).
- Deciding *how* a state change is announced to a patient (Telephony
  Adapter, via Telephony Interface).

---

## 4. Patient Lifecycle Overview

A patient's presence in the system is modeled as a single lifecycle that
passes through the queue at most once per visit episode. A "visit episode"
begins at intake and ends at a terminal state (Section 5.3). Re-entry after
a terminal state constitutes a new episode, not a re-opened one.

At the architectural level, the lifecycle has three regions:

1. **Pre-Queue** — patient has contacted the system but has not yet been
   admitted to the ordered queue (e.g., identity/registration steps owned
   by Business Rules and upstream layers).
2. **In-Queue** — patient occupies one of the queue states defined in
   Section 5.2, and is subject to ordering (Section 6), timeout (Section 8),
   and retry (Section 7) behavior.
3. **Post-Queue** — patient has reached a terminal state and is retained
   only as a historical record (Database), no longer subject to queue
   mechanics.

The Queue Engine owns only the In-Queue region. Pre-Queue and Post-Queue
boundaries are named here for completeness but are governed elsewhere.

### 4.1 Duplicate Request Rule

A patient must never have more than one active (non-terminal) queue entry
within the same visit episode. This constraint is a direct consequence of
the single-lifecycle-per-episode principle stated above. The mechanism used
to determine whether two incoming requests belong to the same patient is
intentionally **not defined here**; duplicate detection strategy is
implementation-defined and will be specified during Phase 5 (Repository
Interface Design).

---

## 5. Queue States and Transitions

### 5.1 State Machine Principles

- The queue is modeled as a **finite state machine per patient entry**,
  not a single global state. Each patient entry has its own current state.
- Transitions are **event-driven**: a transition occurs only in response to
  a named event (Telephony Interface event, Business Rules decision, or
  internally raised timeout event). There is no implicit or time-based
  transition that bypasses an explicit event.
- Transitions are **one-directional per event**: a single event resolves to
  exactly one next state. Ambiguous events (an event that could plausibly
  resolve to more than one state) are not permitted in the contract; they
  must be disambiguated at the Telephony Interface or Business Rules layer
  before reaching the Queue Engine.
- Every state transition must be observable as an emitted event, so that
  Database, API, and Dashboard remain eventually consistent with the Queue
  Engine's authoritative state.

### 5.2 Defined States

| State | Description |
|---|---|
| `REQUESTED` | Patient has asked to join the queue; not yet validated against Business Rules admission policy. |
| `ADMITTED` | Business Rules has approved entry; patient now holds an ordered position in the queue. |
| `WAITING` | Steady-state member of the ordered queue, awaiting call-forward. |
| `NOTIFIED` | Patient has been signaled (via Telephony Adapter) that their turn is approaching or has arrived; awaiting confirmation. |
| `CONFIRMED` | Patient has acknowledged presence/readiness in response to notification. |
| `IN_SERVICE` | Patient has been handed off to the consultation/appointment process; queue involvement is suspended, not ended. |
| `COMPLETED` | Terminal. Patient's visit episode concluded normally. |
| `NO_SHOW` | Terminal. Patient failed to confirm or present within the window defined by Business Rules. |
| `CANCELLED` | Terminal. Patient or operator withdrew the request before service. |
| `EXPIRED` | Terminal. Request was withdrawn by the system due to a timeout condition not classified as a no-show (e.g., abandoned at `REQUESTED` before admission). |

### 5.3 Transition Table

| From | Event | To | Notes |
|---|---|---|---|
| — | Join request received | `REQUESTED` | Entry point. |
| `REQUESTED` | Business Rules admission approved | `ADMITTED` | Admission criteria are a Business Rules concern. |
| `REQUESTED` | Business Rules admission denied | *(rejected, no entry created)* | No queue state is created; handled entirely outside the Queue Engine. |
| `REQUESTED` | Timeout (no admission decision within window) | `EXPIRED` | See Section 8. |
| `ADMITTED` | Position assigned | `WAITING` | Automatic, immediately following admission. |
| `WAITING` | Call-forward triggered by ordering | `NOTIFIED` | See Section 6. |
| `NOTIFIED` | Patient confirms | `CONFIRMED` | |
| `NOTIFIED` | Timeout (no confirmation) | `NO_SHOW` | Consequence policy is a Business Rules concern; state change is a Queue Engine concern. |
| `NOTIFIED` | Patient cancels | `CANCELLED` | |
| `CONFIRMED` | Handoff to service | `IN_SERVICE` | |
| `CONFIRMED` | Timeout (no handoff within window) | `NO_SHOW` | Guards against a confirmed-but-never-arrived case. |
| `WAITING` | Patient cancels | `CANCELLED` | Cancellation permitted at any point before `IN_SERVICE`. |
| `IN_SERVICE` | Service concluded | `COMPLETED` | Per `BUSINESS_RULES.md` §4.9/§10 (ADR-004), `IN_SERVICE` has no other outbound transition — a consultation in progress cannot be cancelled or reverted to an earlier state. |

No other transitions are valid. A transition request that does not match a
row in this table must be rejected by the Queue Engine and raised as an
error event, not silently ignored or coerced into a nearby state.

### 5.4 Terminal State Invariant

Once a patient entry reaches `COMPLETED`, `NO_SHOW`, `CANCELLED`, or
`EXPIRED`, it is immutable. No further transition, reordering, or
notification may target that entry. A new visit episode requires a new
`REQUESTED` entry (Section 4).

---

## 6. Ordering Rules

### 6.1 Ordering Scope

Ordering applies only to entries in `WAITING` and, transiently, `NOTIFIED`
state (a notified patient still occupies its ordering position until it
resolves to `CONFIRMED`, `NO_SHOW`, or `CANCELLED`). Entries in `REQUESTED`,
`ADMITTED` (pre-position-assignment), `IN_SERVICE`, or any terminal state
are outside the ordering computation.

### 6.2 Ordering Discipline

- The default ordering discipline is **first-in-first-out (FIFO)** by the
  timestamp of entry into `WAITING`.
- FIFO order may be **overridden by Business Rules** (e.g., clinical
  urgency, appointment-type priority, elderly/child precedence). The Queue
  Engine does not encode what qualifies for override — it exposes an
  ordering-input hook that Business Rules populates, and the Queue Engine
  is responsible only for applying whatever ordered result it receives
  consistently and deterministically.
- Ordering must be **deterministic and stable**: given the same set of
  entries and the same Business Rules input, the computed order must not
  vary between evaluations. Ties not resolved by Business Rules fall back
  to FIFO by entry timestamp, then by a stable secondary key (entry
  identifier) to guarantee a single deterministic order.
- Re-ordering as a result of a Business Rules override must not silently
  reset or lose a patient's original entry timestamp; the original
  timestamp remains part of the entry's record for audit and fallback
  comparison purposes.

### 6.3 Position Is Computed, Not Stored as Truth

A patient's queue position is a **derived value**, computed at query time
from the set of `WAITING`/`NOTIFIED` entries and the current ordering
input. It is not the authoritative state of the entry — state (Section 5)
is authoritative; position is a projection of state plus ordering policy.
This distinction matters for consistency after any reordering event: no
stored "position number" needs to be rewritten across many entries when one
entry changes state.

### 6.4 Queue Capacity

The Queue Engine does not define queue capacity. Maximum queue size,
admission limits, overflow policy, and waiting-list policies are Business
Rules decisions. The Queue Engine only enforces ordering and state
mechanics (Sections 5–6) over the accepted queue entries it receives; it
does not itself decide whether a new entry may be accepted.

---

## 7. Retry Policy

Retry, at the architecture level, concerns the Queue Engine's handling of
**communication uncertainty** with the patient through the Telephony
Interface — not business consequence, which remains a Business Rules
concern.

- A `NOTIFIED` entry that does not resolve is eligible for a bounded number
  of **re-notification attempts** before the timeout in Section 8 is
  allowed to fire. The number of attempts and spacing between them is a
  Business Rules–supplied parameter; the Queue Engine only enforces that
  attempts are counted, bounded, and exhausted before a timeout transition
  is permitted.
- Each retry attempt is a distinct, auditable event, not a silent repeat.
  The Queue Engine must be able to report how many notification attempts
  were made for any entry.
- Retries never extend or reset a patient's underlying ordering timestamp
  (Section 6.2) and never change queue state on their own; a retry either
  succeeds (patient responds, causing a normal transition) or is exhausted
  (contributing toward, but not itself triggering, a timeout transition).
- Retry is defined only for the `NOTIFIED` state. No other state in Section
  5.2 has a retry concept; failure to transition out of any other state is
  handled purely through the timeout mechanism (Section 8).
- If the Telephony Interface itself reports a delivery failure (as opposed
  to patient non-response), that failure is treated as a failed attempt
  under this same retry accounting — the Queue Engine does not distinguish
  "patient didn't answer" from "message didn't arrive" at the state-machine
  level. Both consume a retry attempt.

---

## 8. Timeout Handling

- Every non-terminal state that has an associated timeout (`REQUESTED`,
  `NOTIFIED`, `CONFIRMED`, per the transition table in Section 5.3) is
  governed by a **maximum dwell duration** supplied by Business Rules. The
  Queue Engine enforces the boundary; it does not define the duration
  value.
- Timeout detection is the Queue Engine's responsibility to raise as an
  event once the dwell duration is exceeded and any applicable retries
  (Section 7) are exhausted. Interpretation of that event's consequence
  (e.g., what a `NO_SHOW` means for a patient's future queue priority) is
  a Business Rules concern applied after the state transition, not a
  precondition for it.
- Timeout evaluation must be **idempotent**: repeated evaluation of an
  already-timed-out entry must not produce duplicate transition events.
- Timeout evaluation must not depend on continuous polling as the only
  possible mechanism; the architecture permits either an event-scheduling
  approach or a polling approach at implementation time, provided the
  dwell-duration guarantee in this section holds. This document does not
  mandate an implementation mechanism, consistent with Section 1 scope.

---

## 9. Invariants

The following must hold true at all times and are considered architectural
guarantees of the Queue Engine, independent of implementation:

1. **Single active state.** A patient entry occupies exactly one state
   (Section 5.2) at any instant; no entry is ever simultaneously in two
   states.
2. **Terminal immutability.** No entry in a terminal state (Section 5.4)
   is ever mutated or re-ordered.
3. **Monotonic entry timestamp.** A patient entry's original entry
   timestamp, once set, is never altered by reordering, retries, or
   renotification.
4. **No orphaned notifications.** Every `NOTIFIED` entry must resolve to
   exactly one of `CONFIRMED`, `NO_SHOW`, or `CANCELLED` — it cannot remain
   indefinitely in `NOTIFIED`.
5. **Deterministic order.** For a fixed set of `WAITING`/`NOTIFIED` entries
   and a fixed Business Rules ordering input, the computed order is unique
   and reproducible (Section 6.2).
6. **No direct adapter dependency.** The Queue Engine never references a
   concrete telephony adapter type; all patient-facing communication is
   expressed only through the Telephony Interface contract (reaffirming
   ADR-002).
7. **State changes are events.** Every transition in Section 5.3 produces
   exactly one emitted state-change event; there is no transition that
   occurs without a corresponding, observable event.
8. **Policy separation.** No prioritization weight, timeout duration, retry
   count, or no-show consequence is hard-coded within the Queue Engine's
   own definition; all such values are Business Rules inputs (Section 2).

**Note on historical retention.** The Queue Engine never deletes
historical state-transition events; it emits them (Invariant 7) but does
not itself manage their retention. Historical retention, archival policy,
and storage lifecycle are Database responsibilities, consistent with the
Queue Engine's non-persistence boundary (Section 3).

---

## 10. Edge Cases

| Edge Case | Architectural Handling |
|---|---|
| Patient cancels while `NOTIFIED`, immediately after a retry was dispatched but before the patient receives it | The `CANCELLED` transition wins; any in-flight retry that later resolves must be a no-op against a terminal entry (Invariant 2). |
| Business Rules ordering input changes while a patient is `NOTIFIED` | The `NOTIFIED` entry's ordering position may be recomputed for other `WAITING` entries, but the `NOTIFIED` entry itself is not re-targeted or double-notified as a result. |
| Two entries would compute to the same order under FIFO and Business Rules input is silent on a tiebreaker | Resolved by the deterministic fallback in Section 6.2 (timestamp, then entry identifier). |
| Telephony Interface reports success for a notification, but the patient later claims non-receipt | Outside Queue Engine authority; the Queue Engine's record of the event stands, and dispute resolution is an operational/Business Rules process, not a queue-state concern. |
| Patient re-contacts the system while a prior entry for the same patient is still non-terminal | Treated as an event against the existing entry, not a new `REQUESTED` entry; the Queue Engine must not permit two concurrent non-terminal entries for the same patient within one visit episode. |
| `IN_SERVICE` entry needs to return to the queue (e.g., service interrupted, patient must wait again) | Not modeled as a transition back into `WAITING`. Per Section 5.3 (ADR-004), `IN_SERVICE` resolves only to `COMPLETED`; a genuine re-wait is a new visit episode (Section 4), preserving invariant 2 and avoiding an ordering re-entry ambiguity. Interrupted-consultation handling is not yet defined by `BUSINESS_RULES.md` and is logged there as a Future Extension Point. |
| Queue Engine receives an event for an entry identifier it has no record of | Rejected as an error event (Section 5.3); the Queue Engine never fabricates a state for an unknown entry. |
| All retries for a `NOTIFIED` entry are exhausted at the exact instant the patient confirms | Confirmation, if it reaches the Queue Engine before the timeout event is raised, takes precedence; once the timeout event has been raised and the transition to `NO_SHOW` has occurred, the entry is terminal and a later-arriving confirmation is a no-op (Invariant 2). |

---

## 11. Extension Points

Consistent with the frozen architecture's telephony-replaceability goal,
the Queue Engine defines two extension points relevant to future phases,
without themselves being implementation:

- **Ordering input source.** Business Rules may supply increasingly complex
  prioritization logic over time (e.g., clinical triage scoring) without
  requiring any change to the state machine (Section 5) or the ordering
  application mechanism (Section 6), only the ordering input.
- **Notification channel plurality.** The Telephony Interface may in future
  represent more than one concrete channel (SIM900A IVR/SMS today; Cloud
  IVR/SIP later). The Queue Engine's `NOTIFIED`/retry model (Sections 5, 7)
  is channel-agnostic by design and requires no change when additional
  adapters are introduced.

---

## 12. Change Control

This document is frozen upon Chief Architect approval, consistent with the
Engineering Charter v3.0 change-management process applied to
`SYSTEM_ARCHITECTURE.md` and `BUSINESS_RULES.md`. Any change to the state
set (Section 5.2), transition table (Section 5.3), ordering discipline
(Section 6), or invariants (Section 9) requires a corresponding ADR in
`DECISION_LOG.md` before implementation may proceed in Phase 8 (Queue
Engine).

This document must be read together with the open item in `RISK_REGISTER.md`
(R-004: `queue_engine` package name shadowing Python's standard library `queue`
module). R-004 is a naming/implementation risk and does not affect any rule
defined in this document; it must nonetheless be resolved by ADR before
Phase 8 implementation begins, per its logged mitigation.
