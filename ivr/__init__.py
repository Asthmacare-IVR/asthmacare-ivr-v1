"""IVR Domain — ISSUE #5 PR-1, plus the IVR Runtime (PR-2A).

`ivr.exceptions`, `ivr.interface`, `ivr.models`, `ivr.state_machine`,
`ivr.workflow`, `ivr.prompts`, and `ivr.dtmf` remain the pure IVR
call-flow domain: independent of telephony/adapters, queue_engine,
backend/api, and database. This package's top-level `__all__` below
imports only from those pure modules and the standard library, so
`import ivr` alone still carries no telephony dependency — see
docs/IVR_STATE_MACHINE.md.

`ivr.runtime` (`IVRRuntime`) and its supporting modules
(`ivr.session`, `ivr.player`, `ivr.dtmf_runtime`, `ivr.events`) are the
ISSUE #5 PR-2A runtime layer that connects the above to
`telephony.interface.TelephonyInterface`. They depend on
`telephony.interface` / `telephony.domain` / `telephony.errors` per
PR-2A's architecture rules, and are imported explicitly from their own
submodules (e.g. `from ivr.runtime import IVRRuntime`) rather than
re-exported here, so that dependency stays opt-in.
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
