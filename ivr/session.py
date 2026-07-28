"""IVR call session — ISSUE #5 PR-2A.

`IVRSession` is `ivr.runtime.IVRRuntime`'s per-call bookkeeping: the
pairing of a call's telephony identity with its
`ivr.interface.IVRWorkflow` instance and the runtime's own housekeeping
fields (retry count, last activity, current prompt, finished flag). It
holds no orchestration logic of its own beyond two small, self-contained
helpers — sequencing lives in `ivr.runtime.IVRRuntime`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ivr.interface import IVRWorkflow


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class IVRSession:
    """One active (or just-finished) call's IVR state.

    Field set per ISSUE #5 PR-2A ("SESSION MODEL"): `call_id`,
    `phone_number`, `workflow`, `current_prompt`, `retry_count`,
    `last_activity`, `finished`.

    `patient_id` is one addition beyond that list: the runtime needs
    somewhere to hold the digits collected during PATIENT_IDENTIFICATION
    so it can populate `ivr.events.QueueRegistrationRequested.patient_id`
    once the workflow reaches QUEUE_REGISTRATION.
    `ivr.interface.IVRWorkflow`'s abstract contract (`start`, `next`,
    `reset`, `current_state`, `is_finished`) has no setter for this, and
    adding one would mean widening a frozen five-method interface for a
    PR-2A-only concern (see docs/IVR_STATE_MACHINE.md, "Design
    decisions"). Session-level storage avoids that without touching
    `ivr/interface.py`.
    """

    call_id: str
    phone_number: str
    workflow: IVRWorkflow
    current_prompt: str | None = None
    retry_count: int = 0
    last_activity: datetime = field(default_factory=_utcnow)
    finished: bool = False
    patient_id: str | None = None

    def touch(self) -> None:
        """Record activity now. Called on every inbound event/DTMF attempt."""
        self.last_activity = _utcnow()

    def mark_finished(self) -> None:
        """Mark the session as concluded (successfully or not) and touch it."""
        self.finished = True
        self.touch()
