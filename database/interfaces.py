"""
Repository Interface — REPOSITORY_INTERFACE.md §5, §8.

Abstract contracts only. No import here may reference sqlite3, a concrete
repository, or any storage-specific construct (REPOSITORY_INTERFACE.md §4).
Concrete repositories (database.sqlite, database.memory) implement these
classes; the Queue Engine and Business Rules layers depend only on them.

Each repository below implements the conceptual operation categories from
REPOSITORY_INTERFACE.md §5: Identify, Enumerate, Persist (Create), Persist
(Update), Remove, Existence Check — scoped to a single aggregate
(REPOSITORY_INTERFACE.md §4), never reaching across aggregate boundaries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Iterable, Optional

from database.domain import Patient, QueueEntry, QueueState, Visit


class PatientRepository(ABC):
    """Repository scoped to the Patient aggregate."""

    @abstractmethod
    def get_by_id(self, patient_id: str) -> Patient:
        """Identify. Raises NotFoundError if no such patient exists."""

    @abstractmethod
    def find_by_phone_number(self, phone_number: str) -> Optional[Patient]:
        """Enumerate (single-result convenience form). Returns None, not an
        error, when no patient matches — this is a normal outcome of a
        search, not a failure (contrast with get_by_id, which identifies a
        specific record expected to exist)."""

    @abstractmethod
    def add(self, patient: Patient) -> Patient:
        """Persist (Create). Raises ConflictError on duplicate identity."""

    @abstractmethod
    def update(self, patient: Patient) -> Patient:
        """Persist (Update). Raises NotFoundError if patient_id is
        unknown."""

    @abstractmethod
    def remove(self, patient_id: str) -> None:
        """Remove. Raises NotFoundError if patient_id is unknown."""

    @abstractmethod
    def exists(self, patient_id: str) -> bool:
        """Existence Check."""


class QueueEntryRepository(ABC):
    """Repository scoped to the Queue Entry aggregate."""

    @abstractmethod
    def get_by_id(self, entry_id: str) -> QueueEntry:
        """Identify. Raises NotFoundError if no such entry exists."""

    @abstractmethod
    def list_by_queue_date(
        self, queue_date: date, *, states: Optional[Iterable[QueueState]] = None
    ) -> list[QueueEntry]:
        """Enumerate — all queue entries for a given day
        (DATABASE_DESIGN.md §6 example), optionally filtered to a set of
        states. Does not expose how the filter is evaluated internally
        (REPOSITORY_INTERFACE.md §5)."""

    @abstractmethod
    def find_active_for_patient(self, patient_id: str) -> Optional[QueueEntry]:
        """Enumerate (single-result convenience form) — supports Duplicate
        Prevention (BUSINESS_RULES.md §5.6): returns the patient's current
        non-terminal entry, if any, or None."""

    @abstractmethod
    def next_queue_number(self, queue_date: date) -> int:
        """Enumerate-adjacent convenience operation: the next monotonic
        queue number to assign for a given day (BUSINESS_RULES.md §5.5).
        Expressed at the domain level only — no assumption about how
        monotonicity is guaranteed internally."""

    @abstractmethod
    def add(self, entry: QueueEntry) -> QueueEntry:
        """Persist (Create). Raises ConflictError if entry_id or
        (queue_date, queue_number) already exists, or if the patient
        already holds a non-terminal entry (BUSINESS_RULES.md §5.6)."""

    @abstractmethod
    def update(self, entry: QueueEntry) -> QueueEntry:
        """Persist (Update). Raises NotFoundError if entry_id is unknown.
        Raises ConflictError if the stored entry is already in a terminal
        state (QUEUE_RULES.md §5.4 Terminal State Invariant) — the
        repository enforces storage-level integrity of this invariant as a
        backstop (REPOSITORY_INTERFACE.md §3), it does not decide queue
        transition legality itself."""

    @abstractmethod
    def remove(self, entry_id: str) -> None:
        """Remove, per whatever retention posture is ultimately ratified
        (REPOSITORY_INTERFACE.md §12, Open Decision 4). Raises
        NotFoundError if entry_id is unknown."""

    @abstractmethod
    def exists(self, entry_id: str) -> bool:
        """Existence Check."""


class VisitRepository(ABC):
    """Repository scoped to the Visit/Appointment aggregate
    (BUSINESS_RULES.md §6)."""

    @abstractmethod
    def get_by_id(self, visit_id: str) -> Visit:
        """Identify. Raises NotFoundError if no such visit exists."""

    @abstractmethod
    def list_for_patient(self, patient_id: str) -> list[Visit]:
        """Enumerate — all visits/appointments for a given patient."""

    @abstractmethod
    def add(self, visit: Visit) -> Visit:
        """Persist (Create). Raises ConflictError on duplicate identity."""

    @abstractmethod
    def update(self, visit: Visit) -> Visit:
        """Persist (Update). Raises NotFoundError if visit_id is
        unknown."""

    @abstractmethod
    def remove(self, visit_id: str) -> None:
        """Remove. Raises NotFoundError if visit_id is unknown."""

    @abstractmethod
    def exists(self, visit_id: str) -> bool:
        """Existence Check."""


class UnitOfWork(ABC):
    """
    Transaction Boundary — REPOSITORY_INTERFACE.md §8.

    Resolution of REPOSITORY_INTERFACE.md §12, Open Decision 2: expressed
    as a context manager, since this is the idiomatic Python shape for "a
    scope in which either all included changes are durably applied or none
    are" and matches SQLITE_REPOSITORY_DESIGN.md §9's "atomicity per
    interface operation, or per an explicitly defined unit of work."

    Usage (illustrative — ownership of the `with` block belongs to the
    calling layer per REPOSITORY_INTERFACE.md §8, never to a repository):

        with unit_of_work as uow:
            uow.patients.add(patient)
            uow.queue_entries.add(entry)
            uow.commit()
        # if commit() was not reached (an exception propagated), every
        # change made through uow.patients / uow.queue_entries / uow.visits
        # inside the block is rolled back — no partial visibility
        # (REPOSITORY_INTERFACE.md §8: "No partial visibility").
    """

    patients: PatientRepository
    queue_entries: QueueEntryRepository
    visits: VisitRepository

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        ...

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Must roll back any uncommitted work if an exception propagated,
        or if commit() was never called."""

    @abstractmethod
    def commit(self) -> None:
        """Durably apply every change made through this unit of work's
        repositories since it was entered."""

    @abstractmethod
    def rollback(self) -> None:
        """Discard every change made through this unit of work's
        repositories since it was entered, without raising."""
