from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from database.domain import TERMINAL_QUEUE_STATES, QueueEntry, QueueState
from database.errors import ConflictError, NotFoundError
from database.interfaces import QueueEntryRepository
from database.sqlite.base_repository import SqliteRepositoryBase
from database.sqlite.mapping import queue_entry_to_row, row_to_queue_entry

_TERMINAL_STATE_VALUES = tuple(state.value for state in TERMINAL_QUEUE_STATES)


class SqliteQueueEntryRepository(SqliteRepositoryBase, QueueEntryRepository):
    aggregate_name = "QueueEntry"

    def get_by_id(self, entry_id: str) -> QueueEntry:
        cursor = self._execute_read(
            "SELECT * FROM queue_entries WHERE entry_id = :entry_id",
            {"entry_id": entry_id},
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(
                f"No queue entry with id {entry_id!r}", aggregate=self.aggregate_name
            )
        return row_to_queue_entry(row)

    def list_by_queue_date(
        self, queue_date: date, *, states: Optional[Iterable[QueueState]] = None
    ) -> list[QueueEntry]:
        params: dict = {"queue_date": queue_date.isoformat()}
        sql = "SELECT * FROM queue_entries WHERE queue_date = :queue_date"
        if states is not None:
            state_values = [state.value for state in states]
            placeholders = []
            for index, value in enumerate(state_values):
                key = f"state_{index}"
                params[key] = value
                placeholders.append(f":{key}")
            sql += f" AND state IN ({', '.join(placeholders)})"
        sql += " ORDER BY queue_number ASC"
        cursor = self._execute_read(sql, params)
        return [row_to_queue_entry(row) for row in cursor.fetchall()]

    def find_active_for_patient(self, patient_id: str) -> Optional[QueueEntry]:
        placeholders = ", ".join(f":terminal_{i}" for i in range(len(_TERMINAL_STATE_VALUES)))
        params = {"patient_id": patient_id}
        params.update(
            {f"terminal_{i}": value for i, value in enumerate(_TERMINAL_STATE_VALUES)}
        )
        cursor = self._execute_read(
            f"""
            SELECT * FROM queue_entries
             WHERE patient_id = :patient_id
               AND state NOT IN ({placeholders})
             LIMIT 1
            """,
            params,
        )
        row = cursor.fetchone()
        return row_to_queue_entry(row) if row is not None else None

    def next_queue_number(self, queue_date: date) -> int:
        cursor = self._execute_read(
            """
            SELECT COALESCE(MAX(queue_number), 0) + 1 AS next_number
              FROM queue_entries
             WHERE queue_date = :queue_date
            """,
            {"queue_date": queue_date.isoformat()},
        )
        return cursor.fetchone()["next_number"]

    def add(self, entry: QueueEntry) -> QueueEntry:
        self._execute_write(
            """
            INSERT INTO queue_entries (
                entry_id, patient_id, queue_date, queue_number, state,
                entry_timestamp, last_updated_at, notification_attempts,
                appointment_id
            ) VALUES (
                :entry_id, :patient_id, :queue_date, :queue_number, :state,
                :entry_timestamp, :last_updated_at, :notification_attempts,
                :appointment_id
            )
            """,
            queue_entry_to_row(entry),
        )
        return entry

    def update(self, entry: QueueEntry) -> QueueEntry:
        # Read-then-write: SQLITE_REPOSITORY_DESIGN.md §9 requires the
        # Terminal State Invariant (QUEUE_RULES.md §5.4) be enforced as a
        # storage-level backstop. The conditional WHERE clause below closes
        # the race between this read and the write with a Conflict rather
        # than a silent lost update (REPOSITORY_INTERFACE.md §9).
        current = self._execute_read(
            "SELECT state FROM queue_entries WHERE entry_id = :entry_id",
            {"entry_id": entry.entry_id},
        ).fetchone()
        if current is None:
            raise NotFoundError(
                f"No queue entry with id {entry.entry_id!r}",
                aggregate=self.aggregate_name,
            )
        current_state = QueueState(current["state"])
        if current_state in TERMINAL_QUEUE_STATES:
            raise ConflictError(
                f"Queue entry {entry.entry_id!r} is terminal "
                f"({current_state.value}) and cannot be updated",
                aggregate=self.aggregate_name,
            )

        row = queue_entry_to_row(entry)
        row["expected_current_state"] = current_state.value
        cursor = self._execute_write(
            """
            UPDATE queue_entries
               SET state = :state,
                   last_updated_at = :last_updated_at,
                   notification_attempts = :notification_attempts,
                   appointment_id = :appointment_id
             WHERE entry_id = :entry_id
               AND state = :expected_current_state
            """,
            row,
        )
        if cursor.rowcount == 0:
            raise ConflictError(
                f"Queue entry {entry.entry_id!r} was concurrently modified",
                aggregate=self.aggregate_name,
            )
        return entry

    def remove(self, entry_id: str) -> None:
        cursor = self._execute_write(
            "DELETE FROM queue_entries WHERE entry_id = :entry_id",
            {"entry_id": entry_id},
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No queue entry with id {entry_id!r}", aggregate=self.aggregate_name
            )

    def exists(self, entry_id: str) -> bool:
        cursor = self._execute_read(
            "SELECT 1 FROM queue_entries WHERE entry_id = :entry_id LIMIT 1",
            {"entry_id": entry_id},
        )
        return cursor.fetchone() is not None
