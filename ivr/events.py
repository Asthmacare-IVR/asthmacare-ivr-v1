"""IVR Runtime events — ISSUE #5 PR-2A.

Plain data only, no behaviour — mirroring the pattern already used by
`queue_engine/events.py` (`QueueEvent`) and `telephony/domain.py`
(`TelephonyEvent`): an immutable dataclass tagged with an enum
discriminator.

Two independent vocabularies live here, deliberately kept separate:

* `RuntimeEvent` / `RuntimeEventType` — everything `ivr.runtime.IVRRuntime`
  itself observes or produces while driving one call through
  `ivr.workflow.DefaultIVRWorkflow`. This is *runtime*-level vocabulary:
  it is neither `telephony.domain.EventType` (the modem/adapter's own
  event vocabulary, which has no concept of "invalid input" or "retry")
  nor `ivr.models.IVRState` (the workflow's own state vocabulary, which
  has no concept of "the caller hung up"). The runtime translates
  between the two — see `ivr/runtime.py` for exactly when each member
  fires.
* `QueueRegistrationRequested` — the single, deliberately minimal signal
  emitted when a call reaches `ivr.models.IVRState.QUEUE_REGISTRATION`.
  Per ISSUE #5 PR-2A scope, the runtime never imports `queue_engine` and
  never registers anything itself; this event is as far as PR-2A goes.
  PR-2B is expected to consume it and call into `queue_engine` through
  its own existing public interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RuntimeEventType(str, Enum):
    """Runtime-level lifecycle events for a single IVR call.

    See module docstring for how these relate to (and differ from)
    `telephony.domain.EventType` and `ivr.models.IVRState`.
    """

    CALL_STARTED = "call_started"
    WELCOME = "welcome"
    PATIENT_IDENTIFICATION = "patient_identification"
    INVALID_INPUT = "invalid_input"
    RETRY = "retry"
    TIMEOUT = "timeout"
    CALL_COMPLETED = "call_completed"
    CALL_FAILED = "call_failed"
    HANGUP = "hangup"


@dataclass(frozen=True)
class RuntimeEvent:
    """Immutable record of one runtime-level event for one call.

    `metadata` is an open bag for context specific to `event_type` (e.g.
    a `reason` string for CALL_FAILED, or `attempt`/`max_attempts` for
    RETRY) without growing this dataclass's shape — the same
    extensibility convention `queue_engine.events.QueueEvent.metadata`
    already uses.
    """

    event_type: RuntimeEventType
    call_id: str
    phone_number: str
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class QueueRegistrationRequested:
    """Emitted once, when a call's workflow reaches QUEUE_REGISTRATION.

    Deliberately minimal (ISSUE #5 PR-2A scope: "emit an internal
    runtime event... Nothing more."). Carries only what a future
    consumer (PR-2B) needs to correlate this request back to a call and
    actually perform registration through `queue_engine`'s own public
    interface — `ivr.runtime.IVRRuntime` never imports `queue_engine`
    and never constructs a `queue_engine` object.
    """

    patient_id: str
    call_id: str
    phone_number: str
    timestamp: datetime = field(default_factory=_utcnow)
