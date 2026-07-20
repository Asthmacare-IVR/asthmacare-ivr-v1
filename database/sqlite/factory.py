"""
Configuration-driven construction — SQLITE_REPOSITORY_DESIGN.md §12.

"Configuration values are supplied to the Repository at construction time
by config/; the Repository does not read its own configuration from the
environment directly." This module is the single point config/ calls to
obtain a working SQLite-backed Repository Interface implementation; no
other module should construct SqliteConnectionManager or SqliteUnitOfWork
directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from database.sqlite.connection import SqliteConnectionManager
from database.sqlite.unit_of_work import SqliteRepositories, SqliteUnitOfWork


@dataclass(frozen=True)
class SqliteConfig:
    """Every operational parameter the SQLite Repository needs, per
    SQLITE_REPOSITORY_DESIGN.md §12. Supplied by config/, never read from
    the environment by this package directly."""

    database_path: str


class SqliteRepositoryProvider:
    """
    Owns one application-scoped SqliteConnectionManager
    (SQLITE_REPOSITORY_DESIGN.md §5, §15 OD-1) and hands out either:

      - a fresh SqliteUnitOfWork — the Transaction Boundary
        (REPOSITORY_INTERFACE.md §8) — per call to `unit_of_work()`, for
        multi-step workflows that must succeed or fail together; or
      - a SqliteRepositories bundle per call to `repositories()`, for a
        single Repository Interface operation that needs no explicit
        transaction boundary (REPOSITORY_INTERFACE.md §8: "a single
        repository operation is implicitly transactional with respect to
        itself").

    Both share the same underlying connection and single-writer
    serialization (SQLITE_REPOSITORY_DESIGN.md §11).
    """

    def __init__(self, config: SqliteConfig) -> None:
        self._manager = SqliteConnectionManager(config.database_path)

    def unit_of_work(self) -> SqliteUnitOfWork:
        return SqliteUnitOfWork(self._manager)

    def repositories(self) -> SqliteRepositories:
        return SqliteRepositories(self._manager)

    def dispose(self) -> None:
        self._manager.dispose()


def build_unit_of_work(config: SqliteConfig) -> SqliteRepositoryProvider:
    """Entry point config/ uses to obtain a Repository Interface
    implementation without ever importing a database.sqlite class
    directly by name."""
    return SqliteRepositoryProvider(config)
