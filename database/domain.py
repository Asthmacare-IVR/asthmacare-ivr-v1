"""
Domain-level data contracts — REPOSITORY_INTERFACE.md §6.

These are technology-neutral representations of the entities named in
DATABASE_DESIGN.md §6 (Patient, Queue Entry) and REPOSITORY_INTERFACE.md §5
(Patient, Queue Entry, Visit). Nothing here is aware of SQLite, rows,
columns, or any storage technology.

Field lists are an implementation-phase decision: DATABASE_DESIGN.md and
REPOSITORY_INTERFACE.md deliberately leave attribute enumeration open
(DATABASE_DESIGN.md §6, REPOSITORY_INTERFACE.md §6) pending Business Rules.
The fields below are derived from what BUSINESS_RULES.md and QUEUE_RULES.md
actually require the domain to track:
  - patient identity (BUSINESS_RULES.md §11)
  - queue number, state, and auditable timestamps (BUSINESS_RULES.md §3
    Auditability, §5.5 Queue Numbering; QUEUE_RULES.md §5.2, §9 Invariant 3)
  - an appointment/visit concept distinct from a queue entry
    (BUSINESS_RULES.md §6 Appointment Rules)

Domain objects are immutable (frozen dataclasses). "Persist (Update)"
(REPOSITORY_INTERFACE.md §5) is expressed by constructing a new, complete
domain object (via `dataclasses.replace`) and handing it to the repository
— consistent with "Immutability of intent" (REPOSITORY_INTERFACE.md §6):
a repository never infers or fills in missing meaning.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class Patient:
    """A single patient identity (BUSINESS_RULES.md §11: a queue entry
    belongs to exactly one patient identity)."""

    patient_id: str
    name: str
    phone_number: str
    created_at: datetime


class QueueState(enum.Enum):
    """
    Queue Engine states — QUEUE_RULES.md §5.2. Reproduced here only as a
    domain-level vocabulary the Repository Interface must be able to
    persist and return faithfully; the Repository has no opinion about
    transition legality (QUEUE_RULES.md §5.3 — that is Queue Engine
    authority, never repository authority, per REPOSITORY_INTERFACE.md §4).
    """

    REQUESTED = "REQUESTED"
    ADMITTED = "ADMITTED"
    WAITING = "WAITING"
    NOTIFIED = "NOTIFIED"
    CONFIRMED = "CONFIRMED"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# QUEUE_RULES.md §5.4: terminal states are immutable once reached.
TERMINAL_QUEUE_STATES = frozenset(
    {QueueState.COMPLETED, QueueState.NO_SHOW, QueueState.CANCELLED, QueueState.EXPIRED}
)


@dataclass(frozen=True)
class QueueEntry:
    """
    A single patient's position in a single day's queue
    (BUSINESS_RULES.md §4.4, §5.5).

    entry_timestamp is the original, monotonic ordering timestamp
    (QUEUE_RULES.md §9 Invariant 3: never altered by reordering, retries,
    or renotification). last_updated_at records the most recent state
    transition for auditability (BUSINESS_RULES.md §3).
    """

    entry_id: str
    patient_id: str
    queue_date: date
    queue_number: int
    state: QueueState
    entry_timestamp: datetime
    last_updated_at: datetime
    notification_attempts: int = 0
    appointment_id: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_QUEUE_STATES


class VisitType(enum.Enum):
    """BUSINESS_RULES.md §6: an appointment-holder vs. a walk-in/on-call
    registrant are both subject to the same queue rules unless a specific
    business rule reserves priority (§5.2)."""

    APPOINTMENT = "APPOINTMENT"
    WALK_IN = "WALK_IN"


@dataclass(frozen=True)
class Visit:
    """
    An appointment/visit record (BUSINESS_RULES.md §6). A Visit reserves a
    patient's intent to be seen; it does not itself create a queue entry —
    Queue Entry is a separate, explicit event (BUSINESS_RULES.md §6).
    """

    visit_id: str
    patient_id: str
    visit_type: VisitType
    created_at: datetime
    scheduled_time: Optional[datetime] = None
