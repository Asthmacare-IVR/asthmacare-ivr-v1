# IVR_STATE_MACHINE.md

## Purpose

This document is the authoritative reference for the IVR call-flow state machine implemented in `ivr/`. It covers ISSUE #5, PR-1 only: the IVR domain and its state machine. It does not define telephony playback, DTMF collection, queue engine integration, backend API endpoints, or persistence — those are later PRs (see "Future integration points" below).

This document does not define implementation details beyond the state machine itself.

---

# IVR States

## Active States

* START
* WELCOME
* PATIENT_IDENTIFICATION
* PATIENT_VERIFIED
* QUEUE_REGISTRATION
* CONFIRMATION
* CALL_COMPLETED
* FAILED

## Terminal States

* END

END is immutable and has no outgoing transitions. FAILED is *not* itself terminal — it always resolves to END (a failed call still ends in a graceful hangup, not an alternate dead end).

---

# State Transition Diagram

```
START
  │
  ▼
WELCOME
  │
  ▼
PATIENT_IDENTIFICATION
  │
  ▼
PATIENT_VERIFIED
  │
  ▼
QUEUE_REGISTRATION
  │
  ▼
CONFIRMATION
  │
  ▼
CALL_COMPLETED
  │
  ▼
END
```

Failure branch, available from any active state (START through CALL_COMPLETED):

```
<any active state>
  │
  ▼
FAILED
  │
  ▼
END
```

---

# Allowed Transitions

| From                    | To                      |
| ------------------------ | ------------------------ |
| START                    | WELCOME                  |
| WELCOME                  | PATIENT_IDENTIFICATION   |
| PATIENT_IDENTIFICATION   | PATIENT_VERIFIED         |
| PATIENT_VERIFIED         | QUEUE_REGISTRATION       |
| QUEUE_REGISTRATION       | CONFIRMATION             |
| CONFIRMATION             | CALL_COMPLETED           |
| CALL_COMPLETED           | END                      |
| FAILED                   | END                      |
| *(any active state)*     | FAILED                   |

"Any active state" means every state above except FAILED and END themselves — a call cannot fail twice, and a terminated call cannot fail at all.

---

# Responsibilities

* **`ivr/models.py`** — the vocabulary: `IVRState`, `DTMFResult` enums, and the `IVRContext` dataclass carried between workflow calls. No behaviour.
* **`ivr/state_machine.py`** — `IVRStateMachine`: pure, immutable, side-effect-free transition validation. Given a current state, it can report the allowed next states, validate a proposed transition, and raise `InvalidTransitionError` when a transition is forbidden. It does **not** execute transitions or hold call state — this mirrors the validate-only pattern used by `queue_engine/state_machine.py` for `QueueState`.
* **`ivr/interface.py`** — `IVRWorkflow`: the abstract contract (`start`, `next`, `reset`, `current_state`, `is_finished`) that any caller of a workflow depends on.
* **`ivr/workflow.py`** — `DefaultIVRWorkflow`: the concrete, in-memory implementation of `IVRWorkflow`. Holds an `IVRContext` and delegates every transition decision to `IVRStateMachine`; it never decides transition legality itself. Also exposes `fail(reason)` — an extension point outside the abstract contract, since branching to FAILED is triggered by an external signal (DTMF timeout, invalid input, hangup), not a step in the `start()`/`next()` happy path.
* **`ivr/prompts.py`** — static prompt text constants only. No audio/TTS/playback.
* **`ivr/dtmf.py`** — pure input-validation helpers (`normalize_digits`, `validate_patient_id`, `classify_patient_id_input`) and a placeholder `DTMFCollector` `Protocol` marking where real DTMF collection will plug in. No modem or telephony I/O.
* **`ivr/exceptions.py`** — `IVRError` (base), `InvalidTransitionError`, `InvalidPatientInput`, `WorkflowFinishedError`.

## Design decisions

* **`is_finished()` is true only at `END`.** FAILED is a real, addressable state (so a caller can detect and log a failed call, attach a `failure_reason` to `IVRContext.metadata`), but it is not the workflow's stopping point — `next()` from FAILED still advances to END, the single terminal state. This avoids a second "kind" of terminal state and keeps `IVRStateMachine.TERMINAL_STATES` a single-element set, matching the "one terminal state, immutable" shape used elsewhere in the codebase.
* **`fail()` is not part of `IVRWorkflow`.** The abstract interface specified by ISSUE #5 is exactly `start`, `next`, `reset`, `current_state`, `is_finished` — five methods, no more. Failure is exceptional and externally triggered, so it lives on the concrete `DefaultIVRWorkflow` as an extension a later PR calls, rather than being forced into every future `IVRWorkflow` implementation.
* **No conditional business logic in the state machine.** `IVRStateMachine` only knows the state graph; it has no knowledge of *why* a transition happens (patient input, queue engine response, telephony event). That knowledge belongs to whichever later PR drives the workflow — the same separation `queue_engine/state_machine.py` draws from `QueueEntryRepository`.

---

# Future Integration Points

This PR intentionally stops at a pure, dependency-free state machine. Later PRs are expected to:

1. **Telephony playback** — call `ivr/prompts.py` constants through a TTS/audio layer at each state, driven by a telephony adapter (e.g. `telephony/adapters/sim900a.py`). Not wired here.
2. **DTMF collection** — implement `ivr.dtmf.DTMFCollector` against a real telephony adapter, feed raw input to `classify_patient_id_input` / `validate_patient_id`, and call `DefaultIVRWorkflow.fail(...)` on repeated invalid/timeout results (tracked via `IVRContext.attempts`).
3. **Queue Engine integration** — at `QUEUE_REGISTRATION`, call into `queue_engine` (via its existing public interface) to actually create/admit a queue entry; the IVR workflow itself must remain unaware of `QueueEntryRepository` or `QueueState`.
4. **Backend API endpoints** — expose workflow start/advance/status over `backend/api`, translating IVR states into HTTP responses.
5. **Database changes / repository changes** — persist `IVRContext` (or an audit trail of its transitions) if call history needs to survive process restarts; none of `ivr/` imports `database` today, and that boundary should hold when persistence is added — a repository should be introduced behind `database/interfaces.py`, not imported directly into `ivr/`.
6. **SIM900A logic** — none of this PR touches `telephony/adapters/sim900a.py`; that adapter remains exactly as it is.

None of the above is implemented in this PR. `ivr/` currently imports only the Python standard library and other modules within `ivr/`.
