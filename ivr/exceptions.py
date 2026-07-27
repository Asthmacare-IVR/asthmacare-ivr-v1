"""IVR domain exceptions.

Kept deliberately small and flat — the IVR package has no persistence or
telephony concerns in this PR, so there is nothing here beyond the state
machine and input-validation vocabulary needed by `state_machine.py`,
`workflow.py`, and `dtmf.py`.
"""

from __future__ import annotations


class IVRError(Exception):
    """Base class for all IVR domain errors."""


class InvalidTransitionError(IVRError):
    """Raised when a requested IVR state transition is not permitted."""


class InvalidPatientInput(IVRError):  # noqa: N818 — name fixed by ISSUE #5 spec
    """Raised when patient-supplied input (e.g. patient-ID digits) fails
    validation. Defined here for the domain vocabulary; nothing in this
    PR raises it yet — DTMF collection (a later PR) is expected to,
    once real input reaches `dtmf.validate_patient_id`.
    """


class WorkflowFinishedError(IVRError):
    """Raised when an operation is attempted on a workflow that has
    already reached its terminal state (IVRState.END).
    """
