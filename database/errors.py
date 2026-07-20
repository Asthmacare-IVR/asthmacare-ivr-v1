"""
Error Contracts — REPOSITORY_INTERFACE.md §7.

Every concrete repository (SQLite, in-memory/mock, and any future
PostgreSQL repository) must translate storage-level failures into exactly
one of these categories before the failure crosses the Repository
Interface boundary. Callers (Queue Engine, Business Rules) must never
observe a storage-specific exception type (e.g. sqlite3.IntegrityError).

Resolution of REPOSITORY_INTERFACE.md §12, Open Decision 1: represented as
an exception hierarchy rather than explicit result/Either values, since
Python's ecosystem (pytest, calling conventions used elsewhere in this
codebase) idiomatically favors exceptions for this kind of boundary. This
is an implementation-phase choice, not a re-opening of the architecture
document.
"""

from __future__ import annotations


class RepositoryError(Exception):
    """
    Base class for every error a repository may raise across the
    Repository Interface boundary. Callers may catch this base class to
    handle "some repository failure occurred" generically, or catch a
    specific subclass to handle a specific category.
    """

    def __init__(self, message: str, *, aggregate: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.aggregate = aggregate


class NotFoundError(RepositoryError):
    """The requested record does not exist (REPOSITORY_INTERFACE.md §7)."""


class ConflictError(RepositoryError):
    """
    The operation would violate a uniqueness or state constraint, e.g. a
    duplicate identity or an attempt to persist a record that has been
    concurrently modified since it was read (REPOSITORY_INTERFACE.md §7,
    §9 Concurrency Expectations — "Conflict visibility, not silent loss").
    """


class ValidationFailureError(RepositoryError):
    """
    The data presented for persistence does not satisfy the *structural*
    requirements of the domain object. Distinct from business-rule
    validation, which occurs above the Repository Interface boundary
    (REPOSITORY_INTERFACE.md §7).
    """


class UnavailableError(RepositoryError):
    """
    The underlying storage cannot currently be reached or is not currently
    able to service the request (REPOSITORY_INTERFACE.md §7).
    """


class UnknownRepositoryError(RepositoryError):
    """
    Catch-all for failures that do not fit any other category, preserved
    so the calling layer can respond safely rather than crash on an
    unrecognized condition (REPOSITORY_INTERFACE.md §7).
    """
