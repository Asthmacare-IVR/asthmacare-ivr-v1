"""
database.sqlite.migrations — versioned, idempotent schema application.
"""

from __future__ import annotations

from database.sqlite.connection import SqliteConnectionManager
from database.sqlite.migrations import apply_migrations, latest_known_version


def test_apply_migrations_on_fresh_database_reaches_latest_version():
    manager = SqliteConnectionManager(":memory:")
    manager.activate()  # calls ensure_schema -> apply_migrations internally

    row = manager.connection.execute(
        "SELECT MAX(version) AS v FROM schema_migrations"
    ).fetchone()
    assert row["v"] == latest_known_version()
    manager.dispose()


def test_apply_migrations_is_idempotent_and_does_not_duplicate_rows():
    manager = SqliteConnectionManager(":memory:")
    manager.activate()

    version_after_first = apply_migrations(manager.connection)
    version_after_second = apply_migrations(manager.connection)
    rows = manager.connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()

    assert version_after_first == version_after_second == latest_known_version()
    assert [r["version"] for r in rows] == list(range(1, latest_known_version() + 1))
    manager.dispose()


def test_reopening_an_existing_database_file_does_not_reapply_migrations(tmp_path):
    db_path = str(tmp_path / "migrations_reopen.db")

    first = SqliteConnectionManager(db_path)
    first.activate()
    first.dispose()

    second = SqliteConnectionManager(db_path)
    second.activate()
    rows = second.connection.execute(
        "SELECT version FROM schema_migrations"
    ).fetchall()
    second.dispose()

    # Exactly one row per migration — re-opening must not re-run or
    # duplicate any already-applied migration.
    assert len(rows) == latest_known_version()


def test_expected_tables_and_indexes_exist_after_migration():
    manager = SqliteConnectionManager(":memory:")
    manager.activate()

    names = {
        row["name"]
        for row in manager.connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        ).fetchall()
    }
    for expected in (
        "patients",
        "visits",
        "queue_entries",
        "schema_migrations",
        "idx_patients_phone_number",
        "idx_visits_patient_id",
        "idx_queue_entries_date_number",
        "idx_queue_entries_single_active",
        "idx_queue_entries_queue_date",
    ):
        assert expected in names, f"expected {expected!r} to exist after migration"
    manager.dispose()
