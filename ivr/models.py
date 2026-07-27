"""IVR domain models — enums and data carriers only.

No behaviour lives here. `IVRState` and `DTMFResult` are the vocabulary
the rest of the package (state_machine, workflow, dtmf) is built from;
`IVRContext` is the plain data a workflow instance carries between calls
to `IVRWorkflow` methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IVRState(Enum):
    """States of the IVR call flow (see docs/IVR_STATE_MACHINE.md).

    The happy path is linear: START → WELCOME → PATIENT_IDENTIFICATION →
    PATIENT_VERIFIED → QUEUE_REGISTRATION → CONFIRMATION →
    CALL_COMPLETED → END. FAILED is the single failure branch, reachable
    from any non-terminal state and itself resolving to END.
    """

    START = "START"
    WELCOME = "WELCOME"
    PATIENT_IDENTIFICATION = "PATIENT_IDENTIFICATION"
    PATIENT_VERIFIED = "PATIENT_VERIFIED"
    QUEUE_REGISTRATION = "QUEUE_REGISTRATION"
    CONFIRMATION = "CONFIRMATION"
    CALL_COMPLETED = "CALL_COMPLETED"
    FAILED = "FAILED"
    END = "END"


class DTMFResult(Enum):
    """Classification of a single DTMF input attempt.

    Defined now so `dtmf.py`'s validation helpers and the future DTMF
    collection PR share one vocabulary. No modem/telephony concern here.
    """

    UNKNOWN = "UNKNOWN"
    TIMEOUT = "TIMEOUT"
    INVALID = "INVALID"
    VALID = "VALID"


@dataclass
class IVRContext:
    """The data a single IVR call carries across workflow steps.

    Deliberately narrow, per ISSUE #5 PR-1 scope: identity of the call
    and patient, a retry counter, the workflow's current state, and an
    open `metadata` bag for whatever a later PR needs to attach (e.g. a
    failure reason) without changing this shape.
    """

    call_id: str
    phone_number: str
    patient_id: str | None = None
    attempts: int = 0
    current_state: IVRState = IVRState.START
    metadata: dict[str, Any] = field(default_factory=dict)
