"""
SQLITE_REPOSITORY_DESIGN.md §10 / REPOSITORY_INTERFACE.md §7: every
storage-level failure mode must be reachable and correctly surfaced as the
closed Repository Interface error vocabulary, not as a raw sqlite3
exception.
"""

from __future__ import annotations

import sqlite3

import pytest

from database.errors import ConflictError, UnavailableError, UnknownRepositoryError, ValidationFailureError
from database.sqlite.error_translation import translate_sqlite_errors


def test_unique_violation_translates_to_conflict():
    with pytest.raises(ConflictError):
        with translate_sqlite_errors("TestAggregate"):
            raise sqlite3.IntegrityError("UNIQUE constraint failed: patients.phone_number")


def test_check_violation_translates_to_validation_failure():
    with pytest.raises(ValidationFailureError):
        with translate_sqlite_errors("TestAggregate"):
            raise sqlite3.IntegrityError("CHECK constraint failed: queue_entries")


def test_foreign_key_violation_translates_to_validation_failure():
    with pytest.raises(ValidationFailureError):
        with translate_sqlite_errors("TestAggregate"):
            raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")


def test_database_locked_translates_to_unavailable():
    with pytest.raises(UnavailableError):
        with translate_sqlite_errors("TestAggregate"):
            raise sqlite3.OperationalError("database is locked")


def test_unrecognized_operational_error_translates_to_unknown():
    with pytest.raises(UnknownRepositoryError):
        with translate_sqlite_errors("TestAggregate"):
            raise sqlite3.OperationalError("some unrecognized condition")


def test_generic_sqlite_error_translates_to_unknown():
    with pytest.raises(UnknownRepositoryError):
        with translate_sqlite_errors("TestAggregate"):
            raise sqlite3.Error("unclassified failure")


def test_no_error_passes_through_untouched():
    with translate_sqlite_errors("TestAggregate"):
        result = 1 + 1
    assert result == 2
