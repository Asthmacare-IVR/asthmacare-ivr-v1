"""
Shared plumbing for SQLite repository units
(SQLITE_REPOSITORY_DESIGN.md §4: "a set of entity-focused repository
units"). Not part of the Repository Interface itself — purely an
implementation convenience shared by database.sqlite.*_repository modules.
"""

from __future__ import annotations

import sqlite3
import threading

from database.errors import RepositoryError
from database.sqlite.connection import TransactionContext
from database.sqlite.error_translation import translate_sqlite_errors


class SqliteRepositoryBase:
    aggregate_name: str = "unknown"

    def __init__(
        self,
        connection: sqlite3.Connection,
        write_lock: threading.RLock,
        tx_context: TransactionContext,
    ) -> None:
        self._connection = connection
        self._write_lock = write_lock
        self._tx_context = tx_context

    def _execute_write(self, sql: str, params: dict) -> sqlite3.Cursor:
        """
        Execute one write statement.

        - Atomicity per interface operation (§9): if no SqliteUnitOfWork
          is active, this single statement is committed (or rolled back on
          failure) immediately, so the caller sees a single all-or-nothing
          operation.
        - If a SqliteUnitOfWork *is* active, this method neither commits
          nor rolls back — that responsibility belongs entirely to the
          active unit of work (§8: "Ownership resides above the
          repository" for multi-step workflows).
        """
        with self._write_lock:
            try:
                with translate_sqlite_errors(self.aggregate_name):
                    cursor = self._connection.execute(sql, params)
                if not self._tx_context.active:
                    self._connection.commit()
                return cursor
            except RepositoryError:
                if not self._tx_context.active:
                    self._connection.rollback()
                raise

    def _execute_read(self, sql: str, params: dict) -> sqlite3.Cursor:
        with translate_sqlite_errors(self.aggregate_name):
            return self._connection.execute(sql, params)
