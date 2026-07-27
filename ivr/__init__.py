"""IVR Domain — ISSUE #5 PR-1.

Pure IVR call-flow domain: state machine and workflow only. Independent
of telephony/adapters, queue_engine, backend/api, and database (only the
standard library and modules within this package are imported — see
docs/IVR_STATE_MACHINE.md).
"""

from __future__ import annotations

from ivr.exceptions import (
    InvalidPatientInput,
    InvalidTransitionError,
    IVRError,
    WorkflowFinishedError,
)
from ivr.interface import IVRWorkflow
from ivr.models import DTMFResult, IVRContext, IVRState
from ivr.state_machine import IVRStateMachine
from ivr.workflow import DefaultIVRWorkflow

__all__ = [
    "IVRError",
    "InvalidPatientInput",
    "InvalidTransitionError",
    "WorkflowFinishedError",
    "IVRWorkflow",
    "DTMFResult",
    "IVRContext",
    "IVRState",
    "IVRStateMachine",
    "DefaultIVRWorkflow",
]
