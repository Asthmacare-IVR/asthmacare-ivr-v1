from __future__ import annotations

from database.domain import Patient
from database.errors import NotFoundError
from database.interfaces import PatientRepository
from database.sqlite.base_repository import SqliteRepositoryBase
from database.sqlite.mapping import patient_to_row, row_to_patient


class SqlitePatientRepository(SqliteRepositoryBase, PatientRepository):
    aggregate_name = "Patient"

    def get_by_id(self, patient_id: str) -> Patient:
        cursor = self._execute_read(
            "SELECT * FROM patients WHERE patient_id = :patient_id",
            {"patient_id": patient_id},
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(
                f"No patient with id {patient_id!r}", aggregate=self.aggregate_name
            )
        return row_to_patient(row)

    def find_by_phone_number(self, phone_number: str) -> Patient | None:
        cursor = self._execute_read(
            "SELECT * FROM patients WHERE phone_number = :phone_number",
            {"phone_number": phone_number},
        )
        row = cursor.fetchone()
        return row_to_patient(row) if row is not None else None

    def add(self, patient: Patient) -> Patient:
        self._execute_write(
            """
            INSERT INTO patients (patient_id, name, phone_number, created_at)
            VALUES (:patient_id, :name, :phone_number, :created_at)
            """,
            patient_to_row(patient),
        )
        return patient

    def update(self, patient: Patient) -> Patient:
        cursor = self._execute_write(
            """
            UPDATE patients
               SET name = :name,
                   phone_number = :phone_number
             WHERE patient_id = :patient_id
            """,
            patient_to_row(patient),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No patient with id {patient.patient_id!r}",
                aggregate=self.aggregate_name,
            )
        return patient

    def remove(self, patient_id: str) -> None:
        cursor = self._execute_write(
            "DELETE FROM patients WHERE patient_id = :patient_id",
            {"patient_id": patient_id},
        )
        if cursor.rowcount == 0:
            raise NotFoundError(
                f"No patient with id {patient_id!r}", aggregate=self.aggregate_name
            )

    def exists(self, patient_id: str) -> bool:
        cursor = self._execute_read(
            "SELECT 1 FROM patients WHERE patient_id = :patient_id LIMIT 1",
            {"patient_id": patient_id},
        )
        return cursor.fetchone() is not None
