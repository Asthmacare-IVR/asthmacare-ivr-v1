"""
Error-translation layer — SQLITE_REPOSITORY_DESIGN.md §10.

Maps every sqlite3 failure mode onto the closed error vocabulary defined
in database.errors (REPOSITORY_INTERFACE.md §7). No sqlite3 exception ever
escapes this module.
"""

from __future__ import annotations

import contextlib
import sqlite3

from database.errors import (
    ConflictError,
    UnavailableError,
    UnknownRepositoryError,
    ValidationFailureError,
)

_UNAVAILABLE_OPERATIONAL_SUBSTRINGS = (
    "database is locked",
    "disk i/o error",
    "unable to open database file",
    "database disk image is malformed",
)


@contextlib.contextmanager
def translate_sqlite_errors(aggregate: str):
    """
    Wrap a single storage operation so that any sqlite3 failure is
    re-raised as the appropriate database.errors.RepositoryError subclass.

    Design principles applied (SQLITE_REPOSITORY_DESIGN.md §10):
      - Closed vocabulary: only RepositoryError subclasses escape.
      - No silent downgrade: every branch re-raises; nothing is swallowed.
      - No business meaning added: this layer reports that a constraint
        was violated, not what that violation means for a patient or
        queue — that remains Business Rules'/Queue Engine's concern.
    """
    try:
        yield
    except sqlite3.IntegrityError as exc:
        message = str(exc).lower()
        if "unique" in message:
            raise ConflictError(str(exc), aggregate=aggregate) from exc
        if "check" in message or "foreign key" in message or "not null" in message:
            raise ValidationFailureError(str(exc), aggregate=aggregate) from exc
        # Any other integrity failure is still, conservatively, a
        # conflict rather than a silent success.
        raise ConflictError(str(exc), aggregate=aggregate) from exc
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if any(substring in message for substring in _UNAVAILABLE_OPERATIONAL_SUBSTRINGS):
            raise UnavailableError(str(exc), aggregate=aggregate) from exc
        raise UnknownRepositoryError(str(exc), aggregate=aggregate) from exc
    except sqlite3.Error as exc:
        raise UnknownRepositoryError(str(exc), aggregate=aggregate) from exc
