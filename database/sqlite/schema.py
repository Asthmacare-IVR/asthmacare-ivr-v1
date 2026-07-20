"""
Schema (DDL) for the pilot's SQLite storage engine.

Storage-level integrity here is a backstop to Business Rules, not a
replacement for it (SQLITE_REPOSITORY_DESIGN.md §6). In particular:

  - The partial unique index on queue_entries(patient_id) enforces
    BUSINESS_RULES.md §5.6 / §12 ("Single active entry per patient") as a
    storage-level backstop; the authoritative decision to reject a
    duplicate registration still belongs to Business Rules (§4.2
    Validation), which is expected to check before ever reaching this
    layer. The repository's role is to guarantee the invariant can never
    be silently violated even if an upstream check is bypassed.
  - The unique index on (queue_date, queue_number) enforces
    BUSINESS_RULES.md §12 ("Queue number uniqueness").

Nothing in this module is imported or referenced outside database.sqlite.

`SCHEMA_STATEMENTS` is the current-state DDL. `database.sqlite.migrations`
is the versioned application of it (and of any future schema change) to a
given database file. `ensure_schema` below is kept as the stable entry
point `connection.py` already calls — it now delegates to the migration
runner rather than re-issuing raw DDL directly, so every activation both
creates a fresh database correctly and upgrades an existing one
idempotently, with the applied revision tracked in `schema_migrations`.
"""

from __future__ import annotations

import sqlite3

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS patients (
        patient_id    TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        phone_number  TEXT NOT NULL,
        created_at    TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_phone_number
        ON patients(phone_number)
    """,
    """
    CREATE TABLE IF NOT EXISTS visits (
        visit_id       TEXT PRIMARY KEY,
        patient_id     TEXT NOT NULL REFERENCES patients(patient_id),
        visit_type     TEXT NOT NULL CHECK (visit_type IN ('APPOINTMENT', 'WALK_IN')),
        created_at     TEXT NOT NULL,
        scheduled_time TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_visits_patient_id
        ON visits(patient_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS queue_entries (
        entry_id               TEXT PRIMARY KEY,
        patient_id             TEXT NOT NULL REFERENCES patients(patient_id),
        queue_date             TEXT NOT NULL,
        queue_number           INTEGER NOT NULL,
        state                  TEXT NOT NULL CHECK (state IN (
            'REQUESTED', 'ADMITTED', 'WAITING', 'NOTIFIED', 'CONFIRMED',
            'IN_SERVICE', 'COMPLETED', 'NO_SHOW', 'CANCELLED', 'EXPIRED'
        )),
        entry_timestamp        TEXT NOT NULL,
        last_updated_at        TEXT NOT NULL,
        notification_attempts  INTEGER NOT NULL DEFAULT 0,
        appointment_id         TEXT REFERENCES visits(visit_id)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_entries_date_number
        ON queue_entries(queue_date, queue_number)
    """,
    # Storage-level backstop for BUSINESS_RULES.md §5.6/§12: at most one
    # non-terminal queue entry per patient.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_entries_single_active
        ON queue_entries(patient_id)
        WHERE state NOT IN ('COMPLETED', 'NO_SHOW', 'CANCELLED', 'EXPIRED')
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_queue_entries_queue_date
        ON queue_entries(queue_date)
    """,
)


def ensure_schema(connection: sqlite3.Connection) -> None:
    """Idempotently brings every table/index this repository requires up
    to the latest known schema version. Safe to call on every activation
    (SQLITE_REPOSITORY_DESIGN.md §5), whether the database file is brand
    new, already fully migrated, or partially migrated by an older build
    of this codebase.

    Delegates to database.sqlite.migrations, which tracks the applied
    revision in a `schema_migrations` table rather than blindly re-running
    `CREATE ... IF NOT EXISTS` statements with no version awareness.
    """
    from database.sqlite.migrations import apply_migrations

    apply_migrations(connection)
