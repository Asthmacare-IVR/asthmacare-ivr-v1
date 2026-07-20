"""
Shared fixtures for contract tests.

`uow_factory` is parametrized over both concrete Repository Interface
implementations (SQLite and in-memory), so every test written against it
runs once per implementation — this is the "contract tests, not
implementation tests" principle from REPOSITORY_INTERFACE.md §11 and
SQLITE_REPOSITORY_DESIGN.md §14.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from database.domain import Patient, QueueEntry, QueueState, Visit, VisitType
from database.memory.in_memory_repository import InMemoryStore
from database.memory.unit_of_work import InMemoryUnitOfWork
from database.sqlite.connection import SqliteConnectionManager
from database.sqlite.unit_of_work import SqliteUnitOfWork


def _sqlite_uow_factory(tmp_path):
    manager = SqliteConnectionManager(str(tmp_path / "test.db"))

    def factory() -> SqliteUnitOfWork:
        return SqliteUnitOfWork(manager)

    return factory, manager


@pytest.fixture(params=["sqlite", "memory"])
def uow_factory(request, tmp_path):
    """Yields a zero-argument callable that produces a fresh UnitOfWork
    bound to the same underlying store, for the current implementation
    under test."""
    if request.param == "sqlite":
        factory, manager = _sqlite_uow_factory(tmp_path)
        yield factory
        manager.dispose()
    else:
        store = InMemoryStore()

        def factory() -> InMemoryUnitOfWork:
            return InMemoryUnitOfWork(store)

        yield factory


def make_patient(**overrides) -> Patient:
    defaults = dict(
        patient_id=str(uuid.uuid4()),
        name="Test Patient",
        phone_number=f"+8801{uuid.uuid4().int % 10**9:09d}",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Patient(**defaults)


def make_queue_entry(patient_id: str, queue_number: int, **overrides) -> QueueEntry:
    now = datetime.now(timezone.utc)
    defaults = dict(
        entry_id=str(uuid.uuid4()),
        patient_id=patient_id,
        queue_date=date.today(),
        queue_number=queue_number,
        state=QueueState.WAITING,
        entry_timestamp=now,
        last_updated_at=now,
        notification_attempts=0,
        appointment_id=None,
    )
    defaults.update(overrides)
    return QueueEntry(**defaults)


def make_visit(patient_id: str, **overrides) -> Visit:
    defaults = dict(
        visit_id=str(uuid.uuid4()),
        patient_id=patient_id,
        visit_type=VisitType.WALK_IN,
        created_at=datetime.now(timezone.utc),
        scheduled_time=None,
    )
    defaults.update(overrides)
    return Visit(**defaults)
