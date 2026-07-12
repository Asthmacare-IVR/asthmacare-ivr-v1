# Business Rules — AsthmaCare IVR Platform

**Status:** Phase 4 — Frozen for Pilot v1.0 (business behavior specification only; no implementation)
**Related documents:** `docs/SYSTEM_ARCHITECTURE.md` (Phase 3), `docs/DATABASE_DESIGN.md`
(Phase 3.1), `docs/DECISION_LOG.md`

---

## 1. Purpose

This document specifies the business behavior of the AsthmaCare IVR
Platform's patient queue management — independent of any technology used
to implement it. It answers *what the system must do* from a clinical
operations standpoint, not *how* it is coded, stored, or transmitted.

This document is the domain authority for Phase 8 (Queue Engine) and
informs the exact shape of the Repository Interfaces left open in
`docs/DATABASE_DESIGN.md` §10, and the Telephony Interface contract left
open in `docs/SYSTEM_ARCHITECTURE.md` §3.3.

---

## 2. Scope

In scope: the business behavior governing a single patient's journey
through the queue at Professor Dr. B. K. Bose Asthma Care Center during
the Pilot v1.0 telephony-based (SIM900A) queue system — registration,
queue placement, being called, consultation, and all exit paths
(completion, cancellation, no-show).

Out of scope: anything not directly governing patient queue behavior,
including clinical/medical decision-making (diagnosis, treatment),
billing, staff scheduling, and multi-doctor/multi-branch orchestration
(see §13).

---

## 3. Guiding Principles

- **Single source of truth for domain behavior.** This document, not code
  comments or ad hoc implementation choices, defines correct system
  behavior. Phase 8 implementation must conform to it; discrepancies are
  resolved by amending this document via ADR, not by silently diverging in
  code.
- **Technology-agnostic.** Every rule here must hold regardless of whether
  the telephony layer is SIM900A or a future Cloud IVR adapter, and
  regardless of whether storage is SQLite or a future PostgreSQL
  repository — consistent with the Dependency Inversion boundaries already
  frozen in `docs/SYSTEM_ARCHITECTURE.md` and `docs/DATABASE_DESIGN.md`.
- **Fail safe toward the patient.** Where a rule is ambiguous between
  "protect clinic throughput" and "protect the patient's access to care,"
  default to the patient — e.g., prefer retrying a failed call over
  silently dropping a queue entry.
- **Determinism.** Given the same sequence of events, the queue must
  reach the same state. This is required for the system to be testable
  against a mock repository and mock telephony adapter, per the testing
  strategies already committed to in `docs/SYSTEM_ARCHITECTURE.md` §4 and
  `docs/DATABASE_DESIGN.md` §9.
- **Auditability.** Every state transition in the Patient Lifecycle (§4)
  and Queue State Machine (§10) must be attributable to a specific,
  identifiable cause (patient action, staff action, system timeout). This
  principle does not mandate a specific audit log implementation here —
  that is a Phase 5/8 concern — but no rule in this document may be
  satisfied by an untraceable state change.

---

## 4. Patient Lifecycle

The lifecycle below describes the business meaning of each stage a patient
passes through. Precise state names and transition rules are formalized
in §10 (Queue State Machine); this section describes intent and business
meaning.

### 4.1 Registration
A patient (or, per current pilot scope, the caller acting as the patient)
initiates contact via the telephony channel. Registration captures the
minimum information needed to identify the patient and place them in the
queue. Registration does not, by itself, guarantee a queue position — it
must pass Validation first.

### 4.2 Validation
The system checks that the registration is usable: the caller can be
identified or newly enrolled, and the request does not violate a Business
Constraint (§11) — for example, an existing active queue entry for the
same patient (see Duplicate Prevention, §5.6). A registration that fails
Validation does not proceed to Queue Entry; the caller is informed of the
reason via the same channel used to register.

### 4.3 Appointment
Where the patient has a pre-arranged appointment (see §6, Appointment
Rules), the system associates the queue entry with that appointment. Where
no appointment exists, the patient is treated as a walk-in/on-call
registrant subject to the same queue rules, unless a specific business
rule reserves appointment-holders priority (§5.2).

### 4.4 Queue Entry
A validated registration becomes a queue entry: an addressable position in
the day's queue, per the Queue Numbering rule (§5.5). From this point, the
patient's position in the queue is meaningful and trackable.

### 4.5 Waiting
The patient's queue entry exists but has not yet been called. The
patient's position may change only per the rules in §5 (Queue Rules) —
never arbitrarily.

### 4.6 Calling
The system attempts to reach the patient (e.g., an outbound call or
notification) to invite them to consultation. Calling is itself a
sub-process governed by §7 (Call Retry Rules) and §8 (Missed Call
Handling); it is not assumed to succeed on the first attempt.

### 4.7 Consultation
The patient is being seen by the doctor. A queue entry enters this stage
only after a successful Calling stage; a patient cannot move directly from
Waiting to Consultation.

### 4.8 Completion
The consultation has concluded normally. This is a terminal state for the
queue entry — the patient exits the queue with no remaining obligation.

### 4.9 Cancellation
The patient (or staff, on the patient's behalf) withdraws the queue entry
before it reaches Consultation. Cancellation is a terminal state and may
occur from Queue Entry, Waiting, or Calling — but not from Consultation
(see §10; a consultation in progress does not "cancel," it may only
complete).

### 4.10 No-show
The patient fails to respond after the Call Retry Rules (§7) are
exhausted. No-show is a terminal state distinct from Cancellation — it
carries different business meaning (the patient did not affirmatively
withdraw) and may be relevant to future clinic reporting or patient
history features (§14), even though such features are out of scope for
v1.0.

---

## 5. Queue Rules

### 5.1 FIFO Default
In the absence of any priority or emergency condition (§5.2, §5.3), queue
entries are called in strict first-in-first-out order, ordered by Queue
Entry time (§4.4).

### 5.2 Priority Handling
Certain patient categories (to be enumerated by clinical/operational
policy — not fixed in this document, since that is a clinical operations
decision, not an architectural one) may be granted a higher position than
strict FIFO would assign. Priority handling must be expressible as a
modification to queue *position*, not a bypass of the queue itself — a
prioritized patient still occupies a queue entry and is still subject to
all other rules in this document.

### 5.3 Emergency Override
An emergency case may be inserted at the front of the queue, ahead of all
existing entries, including prioritized ones. Emergency Override is
distinct from Priority Handling (§5.2): it is an exceptional, immediate
reordering rather than a standing position rule. The specific clinical
criteria that qualify as an emergency are outside the scope of this
document (clinical policy, not platform architecture) — the platform must
simply support the capability.

### 5.4 Retry Policy
A queue entry that reaches the Calling stage (§4.6) without success
re-enters Waiting rather than being discarded, subject to the limits in
§7 (Call Retry Rules). The Retry Policy governs *queue-position* behavior
on retry (e.g., whether a retried entry keeps its original position or is
moved) — the mechanics of the call attempt itself belong to §7.

### 5.5 Queue Numbering
Every queue entry receives a queue number, unique within its queue-day.
Queue numbers are assigned at Queue Entry (§4.4) and are monotonically
increasing within a given day — they are never reused, reassigned, or
decremented, even if an earlier entry is cancelled. This guarantees a
queue number always unambiguously identifies one, and only one, queue
entry.

### 5.6 Duplicate Prevention
A patient may not hold more than one active (non-terminal) queue entry at
the same time. An attempt to register while an active entry already
exists must fail Validation (§4.2) rather than create a second entry.
"Active" excludes queue entries in Completion, Cancellation, or No-show —
a patient may register again after a prior entry has reached a terminal
state.

---

## 6. Appointment Rules

- An appointment reserves a patient's intent to be seen but does not, by
  itself, create a queue entry — Queue Entry (§4.4) is a separate,
  explicit event triggered by patient contact on or near the appointment
  time.
- An appointment does not guarantee a fixed queue position; it may confer
  priority per §5.2, subject to clinical/operational policy, but is still
  subject to Emergency Override (§5.3).
- A missed appointment (the patient neither calls in nor is otherwise
  registered) does not, by itself, constitute a No-show (§4.10) — No-show
  applies specifically to a queue entry that reached Calling and exhausted
  retries. A missed appointment with no corresponding queue entry is a
  distinct business event, outside the Queue State Machine (§10), and its
  handling (e.g., automatic follow-up) is a Future Extension Point (§14).

---

## 7. Call Retry Rules

- A Calling attempt (§4.6) that does not result in the patient being
  reached is a **failed attempt**, not an immediate No-show.
- The system retries a failed attempt up to a defined maximum number of
  attempts. The exact number is an operational/clinical tuning parameter,
  not fixed by this architecture document — it must be treated as
  configurable (see `docs/SYSTEM_ARCHITECTURE.md` dependency rules: this
  is a `config/` concern, not a Queue Engine or Telephony concern).
- Retries are spaced by a minimum interval to avoid immediately
  re-attempting a call the patient could not answer in time. The exact
  interval is likewise a configurable operational parameter.
- Retry attempts do not themselves change queue position beyond what §5.4
  (Retry Policy) specifies.
- Exhausting all retry attempts without success transitions the queue
  entry to No-show (§4.10, §8).

---

## 8. Missed Call Handling

- A single missed (unanswered) call attempt is not, by itself, a
  terminal event — it is one failed attempt under the Call Retry Rules
  (§7).
- Only the exhaustion of all permitted retry attempts (§7) constitutes a
  missed call resulting in No-show.
- A patient who calls back into the system after a missed attempt, but
  before retries are exhausted, must be able to re-enter the Calling
  stage — a missed call must not permanently lock a patient out of being
  reached.
- A patient who calls back after No-show has already been reached is
  treated as a new Registration (§4.1), subject to Duplicate Prevention
  (§5.6), which by definition permits it since No-show is a terminal
  state.

---

## 9. SMS Notification Rules

- The platform notifies patients via SMS at business-meaningful
  transitions: at minimum, upon successful Queue Entry (confirming queue
  number) and upon transition into Calling (inviting the patient to
  respond).
- SMS notification is a business-level event trigger only. This document
  does not specify message content, delivery mechanics, or retry behavior
  for the SMS itself — those are Telephony Adapter implementation
  concerns (Phase 7), sent through the Telephony Interface contract left
  open in `docs/SYSTEM_ARCHITECTURE.md` §3.3, and must not be assumed
  synchronous or guaranteed to succeed.
- Failure to deliver an SMS notification does not, by itself, alter a
  queue entry's state (e.g., does not cause No-show). Only the Call Retry
  Rules (§7) govern No-show.

---

## 10. Queue State Machine

```
                        ┌──────────────┐
                        │  Registered   │
                        └──────┬───────┘
                               │ passes Validation (§4.2)
                               ▼
                        ┌──────────────┐
              ┌────────▶│    Queued     │◀────────┐
              │         └──────┬───────┘          │
              │                │ Calling begins    │ retry
              │                ▼                   │ (§7 not yet
              │         ┌──────────────┐           │  exhausted)
              │         │   Calling     │───────────┘
   Cancel     │         └──────┬───────┘
  (§4.9)      │                │ patient reached
              │                ▼
              │         ┌──────────────┐
              │         │ Consultation  │
              │         └──────┬───────┘
              │                │ consultation ends
              │                ▼
              │         ┌──────────────┐
              │         │  Completed    │  (terminal)
              │         └──────────────┘
              │
              │         ┌──────────────┐
              └────────▶│  Cancelled    │  (terminal)
                        └──────────────┘

                        ┌──────────────┐
   Calling ──(retries exhausted)──────▶│   No-show     │  (terminal)
                        └──────────────┘
```

**Transition rules:**
- `Registered → Queued`: only via successful Validation (§4.2); a failed
  Validation does not produce a queue entry at all (no state node exists
  for "rejected registration" — it is not a queue entry).
- `Queued → Calling`: triggered when the entry reaches the front of the
  queue per §5 (FIFO, Priority, or Emergency Override ordering).
- `Calling → Queued`: a failed attempt under retry (§7), while attempts
  remain.
- `Calling → Consultation`: the patient is successfully reached.
- `Calling → No-show`: retries exhausted (§7, §8).
- `Consultation → Completed`: normal conclusion (§4.8). This is the only
  transition out of Consultation — a consultation in progress cannot be
  cancelled or reverted to an earlier state.
- `Queued → Cancelled`, `Calling → Cancelled`: patient/staff-initiated
  withdrawal (§4.9), permitted from any non-terminal, pre-Consultation
  state.
- `Completed`, `Cancelled`, `No-show` are terminal: no outbound
  transitions exist from any of them. A patient in a terminal state may
  only re-enter the system via a fresh `Registered` event (§8, §5.6).

---

## 11. Business Constraints

- A queue entry must always belong to exactly one patient identity — the
  platform does not support shared or anonymous queue entries in v1.0.
- A queue number, once assigned, is immutable in value (§5.5) even as the
  entry's state changes.
- Only one queue entry per patient may be in a non-terminal state at any
  time (§5.6).
- Emergency Override (§5.3) may reorder the queue but must never remove or
  overwrite another patient's queue entry.
- Consultation (§4.7) may only be entered from Calling — never directly
  from Queued, Registered, or any other state (§10).
- The clinic's operating hours and daily patient capacity bound how many
  Registration events can succeed on a given day; the exact capacity
  figure is an operational parameter, not fixed here.

---

## 12. Business Invariants

Properties that must hold at every point in time, regardless of the
sequence of events that led there:

- **Queue number uniqueness:** no two queue entries on the same day share
  a queue number.
- **Single active entry per patient:** at most one non-terminal queue
  entry exists per patient identity at any instant (§5.6, §11).
- **Monotonic queue numbering:** queue numbers assigned later in a day are
  always greater than those assigned earlier (§5.5) — never reused.
- **No orphan Consultation:** a queue entry can never be observed in
  Consultation without having passed through Calling immediately prior
  (§10).
- **Terminal finality:** a queue entry observed in Completed, Cancelled,
  or No-show never subsequently changes state (§10).
- **Traceable transitions:** every state transition has an identifiable
  triggering cause (§3, Auditability).

---

## 13. Out-of-Scope

Explicitly excluded from this document and from Pilot v1.0 business
behavior, consistent with the frozen roadmap's out-of-scope list
(`ROADMAP.md`) and prior ADRs:

- Multi-doctor or multi-branch queue orchestration (single doctor / single
  center only, per current baseline).
- Clinical decision-making of any kind (diagnosis, treatment planning,
  triage severity scoring).
- Billing, payment, or insurance processing.
- Patient medical history or EHR integration.
- Any AI-assisted triage or scheduling (explicitly out of scope per
  `ROADMAP.md`).
- Video/telemedicine consultation — the platform governs queue management
  only, not the consultation medium itself.
- Staff scheduling or doctor availability management beyond what's
  implied by "operating hours" (§11).

---

## 14. Future Extension Points

Identified during this analysis as plausible future needs, but not
designed, approved, or scheduled:

- Automatic follow-up for a missed appointment with no corresponding
  queue entry (§6).
- Patient history / repeat-visit awareness (e.g., recognizing a returning
  patient across days) — currently each day's queue is implicitly
  self-contained; cross-day patient identity continuity is not defined
  here.
- Formal, codified priority-category taxonomy (§5.2) — this document
  intentionally leaves the *criteria* for priority and emergency status to
  clinical policy, not platform architecture; a future phase may need to
  formalize this if it becomes systematized.
- Multi-doctor/multi-branch queue partitioning (aligned with the project's
  long-term vision in `README.md`, but out of scope for v1.0).
- No-show pattern reporting (e.g., flagging patients with repeated
  no-shows) — would require the cross-day identity continuity noted
  above.

---

## 15. Architecture Notes

- **Placement of Business Rules logic.** The frozen six-layer pipeline in
  `docs/SYSTEM_ARCHITECTURE.md` §2 depicts Business Rules as a distinct
  conceptual stage between Queue Engine and Database. The approved
  top-level folder structure (`docs/DECISION_LOG.md`, ADR-002) does not
  currently define a separate top-level `business_rules/` package;
  `queue_engine/` is documented as covering "Queue Engine, appointment
  workflow, queue algorithms, business orchestration." Whether the rules
  in this document are implemented as a distinct internal submodule of
  `queue_engine/`, or otherwise organized, is an implementation-structure
  decision deferred to Phase 8 and must be proposed via ADR before
  implementation begins — this document does not resolve it.
- **Relationship to the Repository Interface (`docs/DATABASE_DESIGN.md`).**
  The domain data implied by this document (patient identity, queue entry,
  queue number, state, timestamps for auditability per §3) is the input
  Phase 5 needs to finally define the Repository Interface method
  signatures left open in `docs/DATABASE_DESIGN.md` §6 and §10. This
  document supplies that missing domain knowledge; it does not itself
  specify repository methods.
- **Relationship to the Telephony Interface (`docs/SYSTEM_ARCHITECTURE.md`).**
  The Calling (§4.6), Call Retry (§7), and SMS Notification (§9) rules
  describe *when* and *why* telephony actions occur, not *how*. The actual
  `TelephonyInterface` method signatures remain deferred to Phase 7 per
  `docs/SYSTEM_ARCHITECTURE.md` §3.3; this document constrains what those
  methods must ultimately be capable of expressing (e.g., "attempt to
  reach a patient," "send a queue-position SMS") without naming them.
- **No contradiction with frozen documents.** This document introduces no
  new top-level modules, no changes to the dependency rules in
  `docs/SYSTEM_ARCHITECTURE.md` §4 or `docs/DATABASE_DESIGN.md` §5, and no
  changes to the Repository or Telephony Interface patterns already
  frozen. It operates entirely at the domain/business level those
  documents deliberately left open.
