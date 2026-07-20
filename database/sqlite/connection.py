"""
Connection/session boundary — SQLITE_REPOSITORY_DESIGN.md §4, §5.

Responsible for owning access to the underlying storage engine and for
nothing else: no domain logic, no mapping, no error translation lives here.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


def _connect(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database_path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        # Default ("") isolation level: the sqlite3 module issues an
        # implicit BEGIN before the first data-modifying statement and
        # leaves the transaction open until commit()/rollback() is called
        # explicitly. This is what lets SqliteUnitOfWork (§9) group
        # several repository calls into one atomic unit of work.
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    # WAL improves the single-writer/concurrent-reader model described in
    # SQLITE_REPOSITORY_DESIGN.md §11.
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


class TransactionContext:
    """
    Shared, mutable flag indicating whether a SqliteUnitOfWork currently
    owns an open transaction on a connection.

    Resolution of "atomicity per interface operation" (§9): when no unit
    of work is active, each repository write method commits (or rolls
    back) its own single statement, giving atomicity per call by default.
    When a SqliteUnitOfWork is active, repositories defer entirely to it,
    so several calls can be grouped into one durable-or-nothing unit.
    """

    def __init__(self) -> None:
        self.active = False


class SqliteConnectionManager:
    """
    Owns the SQLite connection's lifecycle
    (SQLITE_REPOSITORY_DESIGN.md §5):

        1. Construction  — configured, but no resource acquired yet.
        2. Activation    — connection opened, schema ensured present.
        3. Operation     — connection handed out to repositories/UoW.
        4. Disposal      — connection closed deterministically.

    Resolution of SQLITE_REPOSITORY_DESIGN.md §15 Open Decision OD-1: the
    pilot uses application-scoped activation (a single long-lived
    connection, serialized per §11's single-writer model) rather than
    per-request activation. This is an implementation choice appropriate
    to a single-process Raspberry Pi deployment
    (SQLITE_REPOSITORY_DESIGN.md §11) and can be revisited without any
    change to callers, since callers only ever see the Repository
    Interface.
    """

    def __init__(self, database_path: str, *, ensure_schema: bool = True) -> None:
        self._database_path = database_path
        self._connection: sqlite3.Connection | None = None
        self._write_lock = threading.RLock()
        self._ensure_schema = ensure_schema
        self._tx_context = TransactionContext()

    def activate(self) -> None:
        if self._connection is not None:
            return
        if self._database_path != ":memory:":
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = _connect(self._database_path)
        if self._ensure_schema:
            from database.sqlite.schema import ensure_schema

            ensure_schema(self._connection)

    def dispose(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError(
                "SqliteConnectionManager used before activate() was called."
            )
        return self._connection

    @property
    def write_lock(self) -> threading.RLock:
        """Serializes writers per the single-writer concurrency model
        (SQLITE_REPOSITORY_DESIGN.md §11). Readers are not serialized.
        Reentrant so a UnitOfWork may hold it for an entire block while
        the repositories it hands out also acquire it per statement."""
        return self._write_lock

    @property
    def tx_context(self) -> TransactionContext:
        return self._tx_context

    def __enter__(self) -> "SqliteConnectionManager":
        self.activate()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.dispose()
