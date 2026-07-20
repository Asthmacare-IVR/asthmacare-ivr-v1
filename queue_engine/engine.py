"""
Queue Engine — QUEUE_RULES.md §3.

Orchestrates: state transitions, ordering, timeouts, retries, events.
Depends ONLY on Repository Interface and Telephony Interface contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence

from database.domain import QueueEntry, QueueState
from database.interfaces import UnitOfWork

from queue_engine.events import EventType, QueueEvent
from queue_engine.ordering import QueueOrdering, OrderedEntry
from queue_engine.retry_manager import RetryExhaustedError, RetryManager
from queue_engine.state_machine import QueueStateMachine, StateMachineError
from queue_engine.timeout_manager import TimeoutConfig, TimeoutManager


@dataclass
class QueueEngineConfig:
    """
    Operational parameters — ALL from Business Rules, never hard-coded.
    QUEUE_RULES.md §8: timeout durations are Business Rules inputs.
    QUEUE_RULES.md §7: retry count is Business Rules input.
    """
    notification_timeout_seconds: float = 300.0   # 5 min
    confirmation_timeout_seconds: float = 600.0  # 10 min
    admission_timeout_seconds: float = 300.0      # 5 min
    max_retry_attempts: int = 3


class QueueEngineError(Exception):
    """Base for Queue Engine errors."""


class InvalidTransitionError(QueueEngineError):
    """Wrapper for StateMachineError at engine level."""


class QueueEngine:
    """
    Main orchestrator. QUEUE_RULES.md §3: owns In-Queue region only.

    Pre-Queue (registration, validation): upstream (Business Rules)
    Post-Queue (terminal states): downstream (Database, API, Dashboard)
    """

    def __init__(
        self,
        config: QueueEngineConfig,
        state_machine: Optional[QueueStateMachine] = None,
        ordering: Optional[QueueOrdering] = None,
        timeout_manager: Optional[TimeoutManager] = None,
        retry_manager: Optional[RetryManager] = None,
    ) -> None:
        self.config = config
        self.state_machine = state_machine or QueueStateMachine()
        self.ordering = ordering or QueueOrdering()
        self.timeout_manager = timeout_manager or TimeoutManager(
            TimeoutConfig(
                admission_timeout=timedelta(seconds=config.admission_timeout_seconds),
                notification_timeout=timedelta(seconds=config.notification_timeout_seconds),
                confirmation_timeout=timedelta(seconds=config.confirmation_timeout_seconds),
            )
        )
        self.retry_manager = retry_manager or RetryManager(config.max_retry_attempts)
        self._event_handlers: list = []

    def register_event_handler(self, handler) -> None:
        """Subscribe to queue events (for Database, API, Dashboard)."""
        self._event_handlers.append(handler)

    def _emit(self, event: QueueEvent) -> None:
        """Emit event to all subscribers. QUEUE_RULES.md §9 Invariant 7."""
        for handler in self._event_handlers:
            handler(event)

    def _transition(
        self,
        entry: QueueEntry,
        new_state: QueueState,
        event_type: EventType
    ) -> QueueEntry:
        """Execute state transition and emit event."""
        from dataclasses import replace

        # Validate
        try:
            self.state_machine.assert_valid(entry.state, new_state)
        except StateMachineError as e:
            raise InvalidTransitionError(str(e)) from e

        # Execute transition
        updated = replace(
            entry,
            state=new_state,
            last_updated_at=datetime.now(),
            notification_attempts=(
                entry.notification_attempts + 1 
                if event_type == EventType.RETRY_ATTEMPTED 
                else entry.notification_attempts
            )
        )

        # Emit event
        event = QueueEvent(
            event_id=f"{entry.entry_id}_{new_state.value}_{datetime.now().timestamp()}",
            event_type=event_type,
            entry_id=entry.entry_id,
            patient_id=entry.patient_id,
            from_state=entry.state,
            to_state=new_state,
            timestamp=datetime.now(),
        )
        self._emit(event)

        return updated

    # === State Transition Operations ===

    def admit(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """
        REQUESTED → ADMITTED → WAITING.
        BUSINESS_RULES.md §4.2: validation must pass before this call.
        """
        # REQUESTED → ADMITTED
        admitted = self._transition(entry, QueueState.ADMITTED, EventType.STATE_CHANGED)
        # ADMITTED → WAITING (automatic per QUEUE_RULES.md §5.3)
        waiting = self._transition(admitted, QueueState.WAITING, EventType.STATE_CHANGED)

        uow.queue_entries.add(waiting)
        uow.commit()
        return waiting

    def notify(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """WAITING → NOTIFIED."""
        notified = self._transition(entry, QueueState.NOTIFIED, EventType.PATIENT_NOTIFIED)
        uow.queue_entries.update(notified)
        uow.commit()
        return notified

    def confirm(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """NOTIFIED → CONFIRMED."""
        confirmed = self._transition(entry, QueueState.CONFIRMED, EventType.PATIENT_CONFIRMED)
        self.retry_manager.reset(entry.entry_id)  # Clear retry count on success
        uow.queue_entries.update(confirmed)
        uow.commit()
        return confirmed

    def start_service(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """CONFIRMED → IN_SERVICE."""
        in_service = self._transition(entry, QueueState.IN_SERVICE, EventType.SERVICE_STARTED)
        uow.queue_entries.update(in_service)
        uow.commit()
        return in_service

    def complete(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """IN_SERVICE → COMPLETED."""
        completed = self._transition(entry, QueueState.COMPLETED, EventType.SERVICE_COMPLETED)
        uow.queue_entries.update(completed)
        uow.commit()
        return completed

    def cancel(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """
        Cancel from WAITING or NOTIFIED.
        BUSINESS_RULES.md §4.9: NOT permitted from IN_SERVICE (ADR-004).
        """
        cancelled = self._transition(entry, QueueState.CANCELLED, EventType.ENTRY_CANCELLED)
        uow.queue_entries.update(cancelled)
        uow.commit()
        return cancelled

    def mark_no_show(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """NOTIFIED or CONFIRMED → NO_SHOW."""
        no_show = self._transition(entry, QueueState.NO_SHOW, EventType.NO_SHOW)
        uow.queue_entries.update(no_show)
        uow.commit()
        return no_show

    def expire(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """REQUESTED → EXPIRED (timeout before admission)."""
        expired = self._transition(entry, QueueState.EXPIRED, EventType.ENTRY_EXPIRED)
        uow.queue_entries.update(expired)
        uow.commit()
        return expired

    # === Retry Handling ===

    def record_retry_attempt(
        self,
        entry: QueueEntry,
        uow: UnitOfWork,
    ) -> QueueEntry:
        """
        Record a retry attempt for NOTIFIED entry.
        QUEUE_RULES.md §7: each retry is distinct and auditable.
        """
        self.retry_manager.record_attempt(entry.entry_id)
        # Emit retry event (state doesn't change, but event is emitted)
        retry_event = QueueEvent(
            event_id=f"{entry.entry_id}_retry_{datetime.now().timestamp()}",
            event_type=EventType.RETRY_ATTEMPTED,
            entry_id=entry.entry_id,
            patient_id=entry.patient_id,
            from_state=entry.state,
            to_state=entry.state,
            timestamp=datetime.now(),
            metadata={"attempt": self.retry_manager.get_state(entry.entry_id).attempts_made}
        )
        self._emit(retry_event)
        return entry

    # === Query Operations ===

    def get_positions(
        self,
        entries: Sequence[QueueEntry]
    ) -> list[OrderedEntry]:
        """Compute queue positions for all orderable entries."""
        return self.ordering.compute_positions(entries)

    def get_position(
        self,
        entry_id: str,
        entries: Sequence[QueueEntry]
    ) -> Optional[int]:
        """Get position for specific entry."""
        return self.ordering.get_position(entry_id, entries)

    def get_next_to_call(
        self,
        entries: Sequence[QueueEntry]
    ) -> Optional[QueueEntry]:
        """Get front-of-queue entry."""
        return self.ordering.get_next_to_call(entries)

    # === Timeout Checks ===

    def check_timeouts(
        self,
        entries: Sequence[QueueEntry],
        uow: UnitOfWork,
    ) -> list[QueueEntry]:
        """
        Evaluate all entries for timeout conditions.
        Idempotent — safe to call repeatedly.
        Returns list of entries that transitioned to terminal state.
        """
        transitioned = []

        for entry in entries:
            if entry.state == QueueState.REQUESTED:
                if self.timeout_manager.check_admission_timeout(
                    entry.entry_id, entry.entry_timestamp
                ):
                    expired = self.expire(entry, uow)
                    transitioned.append(expired)

            elif entry.state == QueueState.NOTIFIED:
                retry_exhausted = self.retry_manager.is_exhausted(entry.entry_id)
                # Use last_updated_at as notification time
                if self.timeout_manager.check_notification_timeout(
                    entry.entry_id, entry.last_updated_at, retry_exhausted
                ):
                    no_show = self.mark_no_show(entry, uow)
                    transitioned.append(no_show)

            elif entry.state == QueueState.CONFIRMED:
                if self.timeout_manager.check_confirmation_timeout(
                    entry.entry_id, entry.last_updated_at
                ):
                    no_show = self.mark_no_show(entry, uow)
                    transitioned.append(no_show)

        return transitioned
