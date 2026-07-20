"""
Shared mapping layer — SQLITE_REPOSITORY_DESIGN.md §4, §7.

Translates between the domain-facing shapes in database.domain and the
storage-facing row shapes in database.sqlite.schema. No storage concept
(row id, table name) ever crosses back out of this module attached to a
domain object (SQLITE_REPOSITORY_DESIGN.md §7: "No leakage of storage
concepts upward").
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from database.domain import Patient, QueueEntry, QueueState, Visit, VisitType


def _iso(value: datetime | date) -> str:
    return value.isoformat()


def patient_to_row(patient: Patient) -> dict:
    return {
        "patient_id": patient.patient_id,
        "name": patient.name,
        "phone_number": patient.phone_number,
        "created_at": _iso(patient.created_at),
    }


def row_to_patient(row: sqlite3.Row) -> Patient:
    return Patient(
        patient_id=row["patient_id"],
        name=row["name"],
        phone_number=row["phone_number"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def queue_entry_to_row(entry: QueueEntry) -> dict:
    return {
        "entry_id": entry.entry_id,
        "patient_id": entry.patient_id,
        "queue_date": _iso(entry.queue_date),
        "queue_number": entry.queue_number,
        "state": entry.state.value,
        "entry_timestamp": _iso(entry.entry_timestamp),
        "last_updated_at": _iso(entry.last_updated_at),
        "notification_attempts": entry.notification_attempts,
        "appointment_id": entry.appointment_id,
    }


def row_to_queue_entry(row: sqlite3.Row) -> QueueEntry:
    return QueueEntry(
        entry_id=row["entry_id"],
        patient_id=row["patient_id"],
        queue_date=date.fromisoformat(row["queue_date"]),
        queue_number=row["queue_number"],
        state=QueueState(row["state"]),
        entry_timestamp=datetime.fromisoformat(row["entry_timestamp"]),
        last_updated_at=datetime.fromisoformat(row["last_updated_at"]),
        notification_attempts=row["notification_attempts"],
        appointment_id=row["appointment_id"],
    )


def visit_to_row(visit: Visit) -> dict:
    return {
        "visit_id": visit.visit_id,
        "patient_id": visit.patient_id,
        "visit_type": visit.visit_type.value,
        "created_at": _iso(visit.created_at),
        "scheduled_time": _iso(visit.scheduled_time) if visit.scheduled_time else None,
    }


def row_to_visit(row: sqlite3.Row) -> Visit:
    return Visit(
        visit_id=row["visit_id"],
        patient_id=row["patient_id"],
        visit_type=VisitType(row["visit_type"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        scheduled_time=(
            datetime.fromisoformat(row["scheduled_time"])
            if row["scheduled_time"]
            else None
        ),
    )
