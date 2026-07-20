"""
Schema migration system — Phase 6 addition.

`SQLITE_REPOSITORY_DESIGN.md` §6 scopes SQLite to "durable storage ... per
the schema defined in `DATABASE_DESIGN.md`" and §12 reserves "operational
parameters" to the Database boundary. Tracking *which* schema revision a
given database file is on is such an operational concern: it lives
entirely inside `database.sqlite` and is invisible above the Database
boundary — nothing in `queue_engine`, `api/`, or `database.interfaces` is aware
migrations exist (SQLITE_REPOSITORY_DESIGN.md §3, §6).

Each migration is a numbered, named, idempotent-on-reapply DDL step.
Migrations are applied in order, inside a single transaction, and the
applied version is recorded in `schema_migrations`. Re-running
`apply_migrations` on an already-current database is a no-op.

This module intentionally defines only the migration that captures the
schema already frozen in `DATABASE_DESIGN.md` (see `schema.py`). Adding a
future migration means appending one new entry to `_MIGRATIONS` — nothing
else in this module, or in any caller, needs to change.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Callable, NamedTuple

from database.sqlite.schema import SCHEMA_STATEMENTS


class Migration(NamedTuple):
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _apply_initial_schema(connection: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)


# Ordered, append-only. Never edit or remove an existing entry once it has
# shipped — a schema correction is a new migration with a higher version
# number, never a rewrite of history (this is what makes `apply_migrations`
# safe to run against a database that already has some migrations applied).
_MIGRATIONS: tuple[Migration, ...] = (Migration(1, "initial_schema", _apply_initial_schema),)

_TRACKING_TABLE_DDL = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        applied_at  TEXT NOT NULL
    )
"""


def _current_version(connection: sqlite3.Connection) -> int:
    connection.execute(_TRACKING_TABLE_DDL)
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return row["version"] if row is not None else 0


def apply_migrations(connection: sqlite3.Connection) -> int:
    """
    Idempotently brings `connection`'s schema up to the latest known
    version. Safe to call on every activation
    (SQLITE_REPOSITORY_DESIGN.md §5), including against a database that
    already has some or all migrations applied, or none at all (a
    brand-new file).

    Returns the schema version the connection is at after this call.
    """
    with connection:
        current = _current_version(connection)
        latest = current
        for migration in _MIGRATIONS:
            if migration.version <= current:
                continue
            migration.apply(connection)
            connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) "
                "VALUES (:version, :name, :applied_at)",
                {
                    "version": migration.version,
                    "name": migration.name,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            latest = migration.version
        return latest


def latest_known_version() -> int:
    """The highest migration version this codebase knows how to apply."""
    return _MIGRATIONS[-1].version if _MIGRATIONS else 0
