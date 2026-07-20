# QUEUE_STATE_MACHINE.md

## Purpose

This document extracts the Queue State Machine from QUEUE_RULES.md and serves as the authoritative reference for Queue Engine design.

This document does not define implementation details.

---

# Queue States

## Active States

* REQUESTED
* ADMITTED
* WAITING
* NOTIFIED
* CONFIRMED
* IN_SERVICE

## Terminal States

* COMPLETED
* NO_SHOW
* CANCELLED
* EXPIRED

Terminal states are immutable and have no outgoing transitions.

---

# State Transition Diagram

REQUESTED
│
├── Admission Approved
│
▼
ADMITTED
│
▼
WAITING
│
▼
NOTIFIED
│
├── Patient Confirms
│   ▼
│   CONFIRMED
│   │
│   ▼
│   IN_SERVICE
│   │
│   ▼
│   COMPLETED
│
├── Patient Cancels
│   ▼
│   CANCELLED
│
└── Notification Timeout
▼
NO_SHOW

REQUESTED
│
└── Admission Timeout
▼
EXPIRED

---

# Allowed Transitions

| From       | To         |
| ---------- | ---------- |
| REQUESTED  | ADMITTED   |
| REQUESTED  | EXPIRED    |
| ADMITTED   | WAITING    |
| WAITING    | NOTIFIED   |
| NOTIFIED   | CONFIRMED  |
| NOTIFIED   | CANCELLED  |
| NOTIFIED   | NO_SHOW    |
| CONFIRMED  | IN_SERVICE |
| IN_SERVICE | COMPLETED  |

---

# Transition Triggers

| Trigger | Transition |
|----------|------------|
| Admission Approved | REQUESTED → ADMITTED |
| Admission Timeout | REQUESTED → EXPIRED |
| Notification Sent | WAITING → NOTIFIED |
| Patient Confirmed | NOTIFIED → CONFIRMED |
| Patient Cancelled | NOTIFIED → CANCELLED |
| Notification Timeout | NOTIFIED → NO_SHOW |
| Service Started | CONFIRMED → IN_SERVICE |
| Service Completed | IN_SERVICE → COMPLETED |

# Forbidden Transitions

Any transition not explicitly listed in Allowed Transitions is forbidden.

Examples:

* COMPLETED → WAITING
* NO_SHOW → CONFIRMED
* CANCELLED → NOTIFIED
* EXPIRED → ADMITTED

---

# Terminal State Rules

COMPLETED, NO_SHOW, CANCELLED, and EXPIRED are terminal.

Once entered:

* No further state transitions are allowed.
* Queue position is permanently closed.
* Queue Engine must reject transition attempts.

---

# Patient Confirmation Rule

A patient confirmation event may move a queue entry from:

NOTIFIED → CONFIRMED

The source of confirmation is intentionally undefined at this stage.

Possible future sources:

* SMS reply
* Phone keypad response
* Operator action
* Dashboard action

The Queue Engine only consumes a confirmation event and must not depend on telephony implementation details.

---

# Patient Cancellation Rule

A cancellation event may move a queue entry from:

NOTIFIED → CANCELLED

The Queue Engine consumes cancellation events but does not define how they are collected.

---

# Queue Engine Responsibility

The Queue Engine is responsible for:

* State validation
* Transition validation
* Transition execution
* Terminal-state enforcement

The Queue Engine is not responsible for:

* SMS transport
* Phone calls
* Modem communication
* SIM900A interaction
* AT commands

Those responsibilities belong to the Telephony layer.

---

# Future Design Notes

The following concerns are intentionally deferred:

* Retry scheduling
* Notification retry policies
* Escalation workflows
* DTMF interpretation
* Telephony-specific event translation

These items will be defined in later phases if required.
