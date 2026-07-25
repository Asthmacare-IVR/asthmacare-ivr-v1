"""Queue Router — backend/api/routers/queue.py

Production-grade FastAPI router for the AsthmaCare IVR Platform.

Architecture compliance:
- backend.api → queue_engine → database.interfaces (Dependency Rule)
- Routers NEVER implement business logic (delegated to QueueEngine)
- Routers NEVER change QueueEntry.state directly
- Routers NEVER call commit() or rollback() (UoW managed by dependencies)
- All state transitions go through QueueEngine
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.dependencies import QueueEngineDep, UnitOfWorkDep
from database.domain import QueueEntry, QueueState
from database.errors import (
    ConflictError,
    NotFoundError,
    RepositoryError,
    UnavailableError,
    ValidationFailureError,
)
from database.interfaces import UnitOfWork
from queue_engine.engine import InvalidTransitionError, QueueEngine

router = APIRouter(prefix="/queue", tags=["queue"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class QueueEntryResponse(BaseModel):
    """Public representation of a QueueEntry."""

    model_config = ConfigDict(from_attributes=True)

    entry_id: str
    patient_id: str
    queue_date: date
    queue_number: int
    state: str
    entry_timestamp: datetime
    last_updated_at: datetime
    notification_attempts: int = 0
    appointment_id: Optional[str] = None
    is_terminal: bool = False

    @classmethod
    def from_domain(cls, entry: QueueEntry) -> "QueueEntryResponse":
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
            is_terminal=entry.is_terminal,
        )


class QueuePositionResponse(BaseModel):
    """Computed queue position for a single entry."""

    entry_id: str
    patient_id: str
    queue_number: int
    state: str
    position: int


class AdmitRequest(BaseModel):
    """Request body to create and admit a new queue entry."""

    patient_id: str = Field(..., min_length=1)
    queue_date: date
    appointment_id: Optional[str] = Field(None)


class QueueEntryIdRequest(BaseModel):
    """Request body referencing an existing queue entry."""

    entry_id: str = Field(..., min_length=1)


class StateTransitionResponse(BaseModel):
    """Response after a successful state transition."""

    entry_id: str
    previous_state: str
    current_state: str
    transitioned_at: datetime

    @classmethod
    def from_result(
        cls, entry: QueueEntry, previous_state: QueueState
    ) -> "StateTransitionResponse":
        return cls(
            entry_id=entry.entry_id,
            previous_state=previous_state.value,
            current_state=entry.state.value,
            transitioned_at=entry.last_updated_at,
        )


class QueueListResponse(BaseModel):
    """Paginated list of queue entries for a date."""

    queue_date: date
    total: int
    entries: list[QueueEntryResponse]


class QueuePositionsResponse(BaseModel):
    """Current computed positions for a queue date."""

    queue_date: date
    positions: list[QueuePositionResponse]


# ---------------------------------------------------------------------------
# Error Translation
# ---------------------------------------------------------------------------


def _map_repository_error(exc: RepositoryError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)
    if isinstance(exc, ValidationFailureError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        )
    if isinstance(exc, UnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
    )


def _map_transition_error(exc: InvalidTransitionError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Invalid state transition: {exc}",
    )


# ---------------------------------------------------------------------------
# READ Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/entries",
    response_model=QueueListResponse,
    summary="List queue entries for a date",
)
def list_queue_entries(
    uow: UnitOfWorkDep,
    queue_date: Annotated[date, Query(description="Queue date to query")],
    state_filter: Annotated[
        Optional[list[str]],
        Query(description="Filter to specific states (e.g. WAITING,NOTIFIED)"),
    ] = None,
) -> QueueListResponse:
    try:
        states = None
        if state_filter:
            states = [QueueState(s.upper()) for s in state_filter]
        entries = uow.queue_entries.list_by_queue_date(queue_date, states=states)
        return QueueListResponse(
            queue_date=queue_date,
            total=len(entries),
            entries=[QueueEntryResponse.from_domain(e) for e in entries],
        )
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.get(
    "/entries/{entry_id}",
    response_model=QueueEntryResponse,
    summary="Get a single queue entry",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Entry not found"}},
)
def get_queue_entry(
    uow: UnitOfWorkDep,
    entry_id: Annotated[str, Path(..., description="Queue entry identifier")],
) -> QueueEntryResponse:
    try:
        entry = uow.queue_entries.get_by_id(entry_id)
        return QueueEntryResponse.from_domain(entry)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.get(
    "/positions",
    response_model=QueuePositionsResponse,
    summary="Get computed queue positions",
)
def get_queue_positions(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    queue_date: Annotated[date, Query(description="Queue date to query")],
) -> QueuePositionsResponse:
    try:
        entries = uow.queue_entries.list_by_queue_date(queue_date)
        ordered = engine.get_positions(entries)
        positions = [
            QueuePositionResponse(
                entry_id=o.entry.entry_id,
                patient_id=o.entry.patient_id,
                queue_number=o.entry.queue_number,
                state=o.entry.state.value,
                position=o.position,
            )
            for o in ordered
        ]
        return QueuePositionsResponse(queue_date=queue_date, positions=positions)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.get(
    "/next",
    response_model=Optional[QueueEntryResponse],
    summary="Get the next patient to call",
)
def get_next_to_call(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    queue_date: Annotated[date, Query(description="Queue date to query")],
) -> Optional[QueueEntryResponse]:
    try:
        entries = uow.queue_entries.list_by_queue_date(queue_date)
        next_entry = engine.get_next_to_call(entries)
        if next_entry is None:
            return None
        return QueueEntryResponse.from_domain(next_entry)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.get(
    "/entries/{entry_id}/position",
    response_model=int,
    summary="Get position of a specific entry",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Entry not found or not orderable"}
    },
)
def get_entry_position(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    entry_id: Annotated[str, Path(..., description="Queue entry identifier")],
    queue_date: Annotated[date, Query(description="Queue date")],
) -> int:
    try:
        entry = uow.queue_entries.get_by_id(entry_id)
        entries = uow.queue_entries.list_by_queue_date(queue_date)
        position = engine.get_position(entry_id, entries)
        if position is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Entry {entry_id!r} is not in an orderable state "
                    f"(current state: {entry.state.value})"
                ),
            )
        return position
    except RepositoryError as exc:
        raise _map_repository_error(exc)


# ---------------------------------------------------------------------------
# WRITE Endpoints — All transitions delegated to QueueEngine
# ---------------------------------------------------------------------------


@router.post(
    "/admit",
    response_model=StateTransitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and admit a new queue entry",
    description=(
        "Creates a QueueEntry in REQUESTED state, then immediately "
        "transitions it to WAITING via QueueEngine.admit()."
    ),
    responses={
        status.HTTP_409_CONFLICT: {"description": "Duplicate or conflict"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation failure"},
    },
)
def admit(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    request: AdmitRequest,
) -> StateTransitionResponse:
    try:
        now = datetime.now()
        entry = QueueEntry(
            entry_id=str(uuid4()),
            patient_id=request.patient_id,
            queue_date=request.queue_date,
            queue_number=uow.queue_entries.next_queue_number(request.queue_date),
            state=QueueState.REQUESTED,
            entry_timestamp=now,
            last_updated_at=now,
            appointment_id=request.appointment_id,
        )
        previous_state = entry.state
        updated = engine.admit(entry, uow)
        return StateTransitionResponse.from_result(updated, previous_state)
    except InvalidTransitionError as exc:
        raise _map_transition_error(exc)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.post(
    "/notify",
    response_model=StateTransitionResponse,
    summary="Notify patient (call forward)",
    description="Transitions WAITING -> NOTIFIED via QueueEngine.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Entry not found"},
        status.HTTP_409_CONFLICT: {"description": "Invalid transition"},
    },
)
def notify(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    request: QueueEntryIdRequest,
) -> StateTransitionResponse:
    try:
        entry = uow.queue_entries.get_by_id(request.entry_id)
        previous_state = entry.state
        updated = engine.notify(entry, uow)
        return StateTransitionResponse.from_result(updated, previous_state)
    except InvalidTransitionError as exc:
        raise _map_transition_error(exc)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.post(
    "/confirm",
    response_model=StateTransitionResponse,
    summary="Confirm patient presence",
    description="Transitions NOTIFIED -> CONFIRMED via QueueEngine.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Entry not found"},
        status.HTTP_409_CONFLICT: {"description": "Invalid transition"},
    },
)
def confirm(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    request: QueueEntryIdRequest,
) -> StateTransitionResponse:
    try:
        entry = uow.queue_entries.get_by_id(request.entry_id)
        previous_state = entry.state
        updated = engine.confirm(entry, uow)
        return StateTransitionResponse.from_result(updated, previous_state)
    except InvalidTransitionError as exc:
        raise _map_transition_error(exc)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.post(
    "/start-service",
    response_model=StateTransitionResponse,
    summary="Start consultation/service",
    description="Transitions CONFIRMED -> IN_SERVICE via QueueEngine.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Entry not found"},
        status.HTTP_409_CONFLICT: {"description": "Invalid transition"},
    },
)
def start_service(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    request: QueueEntryIdRequest,
) -> StateTransitionResponse:
    try:
        entry = uow.queue_entries.get_by_id(request.entry_id)
        previous_state = entry.state
        updated = engine.start_service(entry, uow)
        return StateTransitionResponse.from_result(updated, previous_state)
    except InvalidTransitionError as exc:
        raise _map_transition_error(exc)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.post(
    "/complete",
    response_model=StateTransitionResponse,
    summary="Complete consultation",
    description="Transitions IN_SERVICE -> COMPLETED via QueueEngine.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Entry not found"},
        status.HTTP_409_CONFLICT: {"description": "Invalid transition"},
    },
)
def complete(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    request: QueueEntryIdRequest,
) -> StateTransitionResponse:
    try:
        entry = uow.queue_entries.get_by_id(request.entry_id)
        previous_state = entry.state
        updated = engine.complete(entry, uow)
        return StateTransitionResponse.from_result(updated, previous_state)
    except InvalidTransitionError as exc:
        raise _map_transition_error(exc)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.post(
    "/cancel",
    response_model=StateTransitionResponse,
    summary="Cancel queue entry",
    description=(
        "Transitions WAITING or NOTIFIED -> CANCELLED via QueueEngine. "
        "Cancellation from IN_SERVICE is forbidden per ADR-004."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Entry not found"},
        status.HTTP_409_CONFLICT: {"description": "Invalid transition"},
    },
)
def cancel(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    request: QueueEntryIdRequest,
) -> StateTransitionResponse:
    try:
        entry = uow.queue_entries.get_by_id(request.entry_id)
        previous_state = entry.state
        updated = engine.cancel(entry, uow)
        return StateTransitionResponse.from_result(updated, previous_state)
    except InvalidTransitionError as exc:
        raise _map_transition_error(exc)
    except RepositoryError as exc:
        raise _map_repository_error(exc)


@router.post(
    "/no-show",
    response_model=StateTransitionResponse,
    summary="Mark entry as no-show",
    description=(
        "Transitions NOTIFIED or CONFIRMED -> NO_SHOW via QueueEngine."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Entry not found"},
        status.HTTP_409_CONFLICT: {"description": "Invalid transition"},
    },
)
def no_show(
    engine: QueueEngineDep,
    uow: UnitOfWorkDep,
    request: QueueEntryIdRequest,
) -> StateTransitionResponse:
    try:
        entry = uow.queue_entries.get_by_id(request.entry_id)
        previous_state = entry.state
        updated = engine.mark_no_show(entry, uow)
        return StateTransitionResponse.from_result(updated, previous_state)
    except InvalidTransitionError as exc:
        raise _map_transition_error(exc)
    except RepositoryError as exc:
        raise _map_repository_error(exc)
