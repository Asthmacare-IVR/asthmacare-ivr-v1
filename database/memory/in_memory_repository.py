"""
Mock/In-Memory Repository — REPOSITORY_INTERFACE.md §11.

Enforces the same domain invariants as the SQLite Repository (single
active queue entry per patient, queue-number uniqueness, terminal-state
immutability) so that contract tests (tests/test_contract_*.py) can run
unchanged against either implementation, per SQLITE_REPOSITORY_DESIGN.md
§14: "the same test suite shape should be reusable, unchanged, against
any future concrete repository."
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, Optional

from database.domain import (
    TERMINAL_QUEUE_STATES,
    Patient,
    QueueEntry,
    QueueState,
    Visit,
)
from database.errors import ConflictError, NotFoundError
from database.interfaces import PatientRepository, QueueEntryRepository, VisitRepository


class InMemoryStore:
    """Shared backing storage for one 'database', so that repositories
    handed out by different InMemoryUnitOfWork instances constructed from
    the same store observe each other's committed writes."""

    def __init__(self) -> None:
        self.patients: Dict[str, Patient] = {}
        self.queue_entries: Dict[str, QueueEntry] = {}
        self.visits: Dict[str, Visit] = {}

    def snapshot(self) -> "InMemoryStore":
        clone = InMemoryStore()
        clone.patients = dict(self.patients)
        clone.queue_entries = dict(self.queue_entries)
        clone.visits = dict(self.visits)
        return clone

    def restore(self, snapshot: "InMemoryStore") -> None:
        self.patients = snapshot.patients
        self.queue_entries = snapshot.queue_entries
        self.visits = snapshot.visits


class InMemoryPatientRepository(PatientRepository):
    aggregate_name = "Patient"

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def get_by_id(self, patient_id: str) -> Patient:
        try:
            return self._store.patients[patient_id]
        except KeyError:
            raise NotFoundError(
                f"No patient with id {patient_id!r}", aggregate=self.aggregate_name
            ) from None

    def find_by_phone_number(self, phone_number: str) -> Optional[Patient]:
        for patient in self._store.patients.values():
            if patient.phone_number == phone_number:
                return patient
        return None

    def add(self, patient: Patient) -> Patient:
        if patient.patient_id in self._store.patients:
            raise ConflictError(
                f"Patient {patient.patient_id!r} already exists",
                aggregate=self.aggregate_name,
            )
        if self.find_by_phone_number(patient.phone_number) is not None:
            raise ConflictError(
                f"Phone number {patient.phone_number!r} already registered",
                aggregate=self.aggregate_name,
            )
        self._store.patients[patient.patient_id] = patient
        return patient

    def update(self, patient: Patient) -> Patient:
        if patient.patient_id not in self._store.patients:
            raise NotFoundError(
                f"No patient with id {patient.patient_id!r}",
                aggregate=self.aggregate_name,
            )
        existing_with_phone = self.find_by_phone_number(patient.phone_number)
        if (
            existing_with_phone is not None
            and existing_with_phone.patient_id != patient.patient_id
        ):
            raise ConflictError(
                f"Phone number {patient.phone_number!r} already registered",
                aggregate=self.aggregate_name,
            )
        self._store.patients[patient.patient_id] = patient
        return patient

    def remove(self, patient_id: str) -> None:
        try:
            del self._store.patients[patient_id]
        except KeyError:
            raise NotFoundError(
                f"No patient with id {patient_id!r}", aggregate=self.aggregate_name
            ) from None

    def exists(self, patient_id: str) -> bool:
        return patient_id in self._store.patients


class InMemoryQueueEntryRepository(QueueEntryRepository):
    aggregate_name = "QueueEntry"

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def get_by_id(self, entry_id: str) -> QueueEntry:
        try:
            return self._store.queue_entries[entry_id]
        except KeyError:
            raise NotFoundError(
                f"No queue entry with id {entry_id!r}", aggregate=self.aggregate_name
            ) from None

    def list_by_queue_date(
        self, queue_date: date, *, states: Optional[Iterable[QueueState]] = None
    ) -> list[QueueEntry]:
        state_set = set(states) if states is not None else None
        entries = [
            entry
            for entry in self._store.queue_entries.values()
            if entry.queue_date == queue_date
            and (state_set is None or entry.state in state_set)
        ]
        return sorted(entries, key=lambda entry: entry.queue_number)

    def find_active_for_patient(self, patient_id: str) -> Optional[QueueEntry]:
        for entry in self._store.queue_entries.values():
            if entry.patient_id == patient_id and entry.state not in TERMINAL_QUEUE_STATES:
                return entry
        return None

    def next_queue_number(self, queue_date: date) -> int:
        numbers = [
            entry.queue_number
            for entry in self._store.queue_entries.values()
            if entry.queue_date == queue_date
        ]
        return (max(numbers) + 1) if numbers else 1

    def add(self, entry: QueueEntry) -> QueueEntry:
        if entry.entry_id in self._store.queue_entries:
            raise ConflictError(
                f"Queue entry {entry.entry_id!r} already exists",
                aggregate=self.aggregate_name,
            )
        for existing in self._store.queue_entries.values():
            if (
                existing.queue_date == entry.queue_date
                and existing.queue_number == entry.queue_number
            ):
                raise ConflictError(
                    f"Queue number {entry.queue_number} already assigned for "
                    f"{entry.queue_date.isoformat()}",
                    aggregate=self.aggregate_name,
                )
        if entry.state not in TERMINAL_QUEUE_STATES:
            existing_active = self.find_active_for_patient(entry.patient_id)
            if existing_active is not None:
                raise ConflictError(
                    f"Patient {entry.patient_id!r} already has an active queue entry "
                    f"(BUSINESS_RULES.md §5.6)",
                    aggregate=self.aggregate_name,
                )
        self._store.queue_entries[entry.entry_id] = entry
        return entry

    def update(self, entry: QueueEntry) -> QueueEntry:
        current = self._store.queue_entries.get(entry.entry_id)
        if current is None:
            raise NotFoundError(
                f"No queue entry with id {entry.entry_id!r}",
                aggregate=self.aggregate_name,
            )
        if current.state in TERMINAL_QUEUE_STATES:
            raise ConflictError(
                f"Queue entry {entry.entry_id!r} is terminal "
                f"({current.state.value}) and cannot be updated",
                aggregate=self.aggregate_name,
            )
        self._store.queue_entries[entry.entry_id] = entry
        return entry

    def remove(self, entry_id: str) -> None:
        try:
            del self._store.queue_entries[entry_id]
        except KeyError:
            raise NotFoundError(
                f"No queue entry with id {entry_id!r}", aggregate=self.aggregate_name
            ) from None

    def exists(self, entry_id: str) -> bool:
        return entry_id in self._store.queue_entries


class InMemoryVisitRepository(VisitRepository):
    aggregate_name = "Visit"

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def get_by_id(self, visit_id: str) -> Visit:
        try:
            return self._store.visits[visit_id]
        except KeyError:
            raise NotFoundError(
                f"No visit with id {visit_id!r}", aggregate=self.aggregate_name
            ) from None

    def list_for_patient(self, patient_id: str) -> list[Visit]:
        visits = [v for v in self._store.visits.values() if v.patient_id == patient_id]
        return sorted(visits, key=lambda v: v.created_at)

    def add(self, visit: Visit) -> Visit:
        if visit.visit_id in self._store.visits:
            raise ConflictError(
                f"Visit {visit.visit_id!r} already exists", aggregate=self.aggregate_name
            )
        self._store.visits[visit.visit_id] = visit
        return visit

    def update(self, visit: Visit) -> Visit:
        if visit.visit_id not in self._store.visits:
            raise NotFoundError(
                f"No visit with id {visit.visit_id!r}", aggregate=self.aggregate_name
            )
        self._store.visits[visit.visit_id] = visit
        return visit

    def remove(self, visit_id: str) -> None:
        try:
            del self._store.visits[visit_id]
        except KeyError:
            raise NotFoundError(
                f"No visit with id {visit_id!r}", aggregate=self.aggregate_name
            ) from None

    def exists(self, visit_id: str) -> bool:
        return visit_id in self._store.visits
