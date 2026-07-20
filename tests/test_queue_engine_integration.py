"""Integration tests: QueueEngine + InMemoryUnitOfWork."""

from datetime import datetime

import pytest
from database.domain import QueueEntry, QueueState
from database.memory.unit_of_work import InMemoryUnitOfWork
from queue_engine.engine import QueueEngine, QueueEngineConfig


@pytest.fixture
def engine():
    return QueueEngine(QueueEngineConfig())


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def sample_entry():
    return QueueEntry(
        entry_id="entry-001",
        patient_id="patient-001",
        queue_date=datetime.now().date(),
        queue_number=1,
        state=QueueState.REQUESTED,
        entry_timestamp=datetime.now(),
        last_updated_at=datetime.now(),
    )


class TestAdmitFlow:
    def test_admit_transitions_to_waiting(self, engine, uow, sample_entry):
        result = engine.admit(sample_entry, uow)
        assert result.state == QueueState.WAITING

    def test_admit_persists_in_repository(self, engine, uow, sample_entry):
        result = engine.admit(sample_entry, uow)
        stored = uow.queue_entries.get_by_id(result.entry_id)
        assert stored.state == QueueState.WAITING


class TestNotifyFlow:
    def test_notify_transitions_to_notified(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)
        notified = engine.notify(waiting, uow)
        assert notified.state == QueueState.NOTIFIED


class TestConfirmFlow:
    def test_confirm_transitions_to_confirmed(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)
        notified = engine.notify(waiting, uow)
        confirmed = engine.confirm(notified, uow)
        assert confirmed.state == QueueState.CONFIRMED


class TestCompleteFlow:
    def test_full_patient_journey(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)
        notified = engine.notify(waiting, uow)
        confirmed = engine.confirm(notified, uow)
        in_service = engine.start_service(confirmed, uow)
        completed = engine.complete(in_service, uow)
        assert completed.state == QueueState.COMPLETED


class TestCancelFlow:
    def test_cancel_from_waiting(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)
        cancelled = engine.cancel(waiting, uow)
        assert cancelled.state == QueueState.CANCELLED

    def test_cancel_from_notified(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)
        notified = engine.notify(waiting, uow)
        cancelled = engine.cancel(notified, uow)
        assert cancelled.state == QueueState.CANCELLED


class TestNoShowFlow:
    def test_mark_no_show_from_notified(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)
        notified = engine.notify(waiting, uow)
        no_show = engine.mark_no_show(notified, uow)
        assert no_show.state == QueueState.NO_SHOW


class TestInvalidTransitions:
    def test_cannot_cancel_from_in_service(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)
        notified = engine.notify(waiting, uow)
        confirmed = engine.confirm(notified, uow)
        in_service = engine.start_service(confirmed, uow)

        from queue_engine.engine import InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            engine.cancel(in_service, uow)

    def test_cannot_complete_from_waiting(self, engine, uow, sample_entry):
        waiting = engine.admit(sample_entry, uow)

        from queue_engine.engine import InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            engine.complete(waiting, uow)


class TestEvents:
    def test_state_change_emits_event(self, engine, uow, sample_entry):
        events = []
        engine.register_event_handler(events.append)

        engine.admit(sample_entry, uow)

        assert len(events) == 2  # REQUESTED→ADMITTED + ADMITTED→WAITING
        assert events[0].event_type.name == "STATE_CHANGED"
        assert events[0].from_state == QueueState.REQUESTED
        assert events[0].to_state == QueueState.ADMITTED


class TestOrdering:
    def test_get_positions(self, engine, uow):
        # Create multiple entries
        entries = []
        for i in range(3):
            entry = QueueEntry(
                entry_id=f"entry-{i}",
                patient_id=f"patient-{i}",
                queue_date=datetime.now().date(),
                queue_number=i+1,
                state=QueueState.WAITING,
                entry_timestamp=datetime(2026, 7, 20, 9, i*5),
                last_updated_at=datetime(2026, 7, 20, 9, i*5),
            )
            uow.queue_entries.add(entry)
            entries.append(entry)
        uow.commit()

        positions = engine.get_positions(entries)
        assert len(positions) == 3
        assert positions[0].position == 1
        assert positions[2].position == 3
