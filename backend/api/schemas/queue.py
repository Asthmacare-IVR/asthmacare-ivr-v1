from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from database.domain import QueueEntry


class AdmitRequest(BaseModel):
    patient_id: str
    queue_date: Optional[date] = None


class QueueEntryIdRequest(BaseModel):
    entry_id: str


class QueueEntryResponse(BaseModel):
    entry_id: str
    patient_id: str
    queue_date: date
    queue_number: int
    state: str
    entry_timestamp: datetime
    last_updated_at: datetime
    notification_attempts: int
    appointment_id: Optional[str] = None

    @classmethod
    def from_domain(cls, entry: QueueEntry):
        return cls(
            entry_id=entry.entry_id,
            patient_id=entry.patient_id,
            queue_date=entry.queue_date,
            queue_number=entry.queue_number,
            state=entry.state.value,
            entry_timestamp=entry.entry_timestamp,
            last_updated_at=entry.last_updated_at,
            notification_attempts=entry.notification_attempts,
            appointment_id=entry.appointment_id,
        )


class QueuePositionResponse(BaseModel):
    entry_id: str
    position: Optional[int] = Field(default=None)