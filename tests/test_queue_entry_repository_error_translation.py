"""
Regression test — Phase 6 audit finding.

`SqliteQueueEntryRepository.update()` performs an optimistic-lock
pre-read (SQLITE_REPOSITORY_DESIGN.md §9) before issuing its conditional
UPDATE. That pre-read must go through the same error-translation wrapper
as every other statement (SQLITE_REPOSITORY_DESIGN.md §10,
REPOSITORY_INTERFACE.md §7: "Queue Engine must never observe a
storage-specific exception, error code, or failure type") — previously it
used the raw connection directly and bypassed translation entirely.
"""

from __future__ import annotations

import sqlite3

import pytest

from database.errors import RepositoryError, UnknownRepositoryError
from database.sqlite.base_repository import SqliteRepositoryBase
from database.sqlite.connection import SqliteConnectionManager
from database.sqlite.error_translation import translate_sqlite_errors
from database.sqlite.unit_of_work import SqliteUnitOfWork
from tests.conftest import make_patient, make_queue_entry


def test_update_pre_read_failure_is_translated_not_leaked(monkeypatch):
    manager = SqliteConnectionManager(":memory:")
    manager.activate()

    patient = make_patient()
    entry = make_queue_entry(patient.patient_id, queue_number=1)
    uow = SqliteUnitOfWork(manager)
    with uow as u:
        u.patients.add(patient)
        u.queue_entries.add(entry)
        u.commit()

    real_execute_read = SqliteRepositoryBase._execute_read
    calls = {"n": 0}

    def flaky_execute_read(self, sql, params):
        # Fail only the optimistic-lock pre-read (a bare SELECT ... state
        # FROM queue_entries), not every statement, so we isolate the
        # exact code path under test. The failure is raised *through*
        # translate_sqlite_errors, exactly as the real _execute_read does
        # — this proves update() routes its pre-read through the
        # error-translation seam. If update() still used the raw
        # connection for this read (the bug being regression-tested),
        # this patch would never fire and calls["n"] would stay 0.
        if "SELECT state FROM queue_entries" in sql:
            calls["n"] += 1
            with translate_sqlite_errors(self.aggregate_name):
                raise sqlite3.OperationalError("simulated unrecognized failure")
        return real_execute_read(self, sql, params)

    monkeypatch.setattr(SqliteRepositoryBase, "_execute_read", flaky_execute_read)

    with SqliteUnitOfWork(manager) as u2:
        with pytest.raises(RepositoryError) as excinfo:
            u2.queue_entries.update(entry)

    # Must be a RepositoryError subclass (translated) — proving update()
    # now routes its pre-read through _execute_read (and therefore through
    # translate_sqlite_errors), never a raw, untranslated sqlite3 error.
    assert isinstance(excinfo.value, UnknownRepositoryError)
    assert calls["n"] == 1

    manager.dispose()
