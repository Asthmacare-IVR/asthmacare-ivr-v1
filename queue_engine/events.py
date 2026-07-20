"""
Queue Events — QUEUE_RULES.md §9 Invariant 7.

Every state transition produces exactly one emitted event.
Events are plain data — no behavior, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from database.domain import QueueState


class EventType(Enum):
    STATE_CHANGED = "state_changed"
    PATIENT_NOTIFIED = "patient_notified"
    PATIENT_CONFIRMED = "patient_confirmed"
    SERVICE_STARTED = "service_started"
    SERVICE_COMPLETED = "service_completed"
    ENTRY_CANCELLED = "entry_cancelled"
    NO_SHOW = "no_show"
    ENTRY_EXPIRED = "entry_expired"
    RETRY_ATTEMPTED = "retry_attempted"
    TIMEOUT_OCCURRED = "timeout_occurred"


@dataclass(frozen=True)
class QueueEvent:
    """
    Immutable event emitted on queue state changes.

    QUEUE_RULES.md §9 Invariant 7: every transition produces exactly one event.
    QUEUE_RULES.md §9 Invariant 8: no hard-coded policy in event.
    """
    event_id: str
    event_type: EventType
    entry_id: str
    patient_id: str
    from_state: QueueState
    to_state: QueueState
    timestamp: datetime
    metadata: Optional[dict] = None  # Extensible for future use
