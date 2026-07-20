from __future__ import annotations

from database.domain import Visit
from database.errors import NotFoundError
from database.interfaces import VisitRepository
from database.sqlite.base_repository import SqliteRepositoryBase
from database.sqlite.mapping import row_to_visit, visit_to_row


class SqliteVisitRepository(SqliteRepositoryBase, VisitRepository):
    aggregate_name = "Visit"

    def get_by_id(self, visit_id: str) -> Visit:
        cursor = self._execute_read(
            "SELECT * FROM visits WHERE visit_id = :visit_id",
            {"visit_id": visit_id},
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(
                f"No visit with id {visit_id!r}", aggregate=self.aggregate_name
            )
        return row_to_visit(row)

    def list_for_patient(self, patient_id: str) -> list[Visit]:
        cursor = self._execute_read(
            "SELECT * FROM visits WHERE patient_id = :patient_id ORDER BY created_at ASC",
            {"patient_id": patient_id},
        )
        return [row_to_visit(row) for row in cursor.fetchall()]

    def add(self, visit: Visit) -> Visit:
        self._execute_write(
            """
            INSERT INTO visits (visit_id, patient_id, visit_type, created_at, scheduled_time)
            VALUES (:visit_id, :patient_id, :visit_type, :created_at, :scheduled_time)
            """,
            visit_to_row(visit),
        )
        return visit

    def update(self, visit: Visit) -> Visit:
        cursor = self._execute_write(
            """
            UPDATE visits
               SET visit_type = :visit_type,
                   scheduled_time = :scheduled_time
             WHERE visit_id = :visit_id
            """,
            visit_to_row(visit),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No visit with id {visit.visit_id!r}", aggregate=self.aggregate_name
            )
        return visit

    def remove(self, visit_id: str) -> None:
        cursor = self._execute_write(
            "DELETE FROM visits WHERE visit_id = :visit_id",
            {"visit_id": visit_id},
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No visit with id {visit_id!r}", aggregate=self.aggregate_name
            )

    def exists(self, visit_id: str) -> bool:
        cursor = self._execute_read(
            "SELECT 1 FROM visits WHERE visit_id = :visit_id LIMIT 1",
            {"visit_id": visit_id},
        )
        return cursor.fetchone() is not None
