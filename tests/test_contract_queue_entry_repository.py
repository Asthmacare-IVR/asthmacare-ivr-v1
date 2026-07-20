from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from database.domain import QueueState
from database.errors import ConflictError, NotFoundError
from tests.conftest import make_patient, make_queue_entry


def _seed_patient(uow_factory):
    patient = make_patient()
    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.commit()
    return patient


def test_next_queue_number_starts_at_one_and_increments(uow_factory):
    patient = _seed_patient(uow_factory)
    today = date.today()

    with uow_factory() as uow:
        assert uow.queue_entries.next_queue_number(today) == 1
        entry = make_queue_entry(patient.patient_id, queue_number=1, queue_date=today)
        uow.queue_entries.add(entry)
        uow.commit()

    with uow_factory() as uow:
        assert uow.queue_entries.next_queue_number(today) == 2


def test_add_then_get_by_id_round_trips(uow_factory):
    patient = _seed_patient(uow_factory)
    entry = make_queue_entry(patient.patient_id, queue_number=1)
    with uow_factory() as uow:
        uow.queue_entries.add(entry)
        uow.commit()

    with uow_factory() as uow:
        fetched = uow.queue_entries.get_by_id(entry.entry_id)
    assert fetched == entry


def test_duplicate_queue_number_same_day_raises_conflict(uow_factory):
    patient_a = _seed_patient(uow_factory)
    patient_b = _seed_patient(uow_factory)
    today = date.today()
    entry_a = make_queue_entry(patient_a.patient_id, queue_number=1, queue_date=today)
    entry_b = make_queue_entry(patient_b.patient_id, queue_number=1, queue_date=today)

    with uow_factory() as uow:
        uow.queue_entries.add(entry_a)
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(ConflictError):
            uow.queue_entries.add(entry_b)


def test_second_active_entry_for_same_patient_raises_conflict(uow_factory):
    # BUSINESS_RULES.md §5.6 / §12: single active entry per patient.
    patient = _seed_patient(uow_factory)
    first = make_queue_entry(patient.patient_id, queue_number=1, state=QueueState.WAITING)
    second = make_queue_entry(patient.patient_id, queue_number=2, state=QueueState.REQUESTED)

    with uow_factory() as uow:
        uow.queue_entries.add(first)
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(ConflictError):
            uow.queue_entries.add(second)


def test_second_entry_allowed_once_first_is_terminal(uow_factory):
    patient = _seed_patient(uow_factory)
    first = make_queue_entry(patient.patient_id, queue_number=1, state=QueueState.WAITING)
    with uow_factory() as uow:
        uow.queue_entries.add(first)
        uow.commit()

    completed = replace(
        first, state=QueueState.COMPLETED, last_updated_at=datetime.now(timezone.utc)
    )
    with uow_factory() as uow:
        uow.queue_entries.update(completed)
        uow.commit()

    second = make_queue_entry(patient.patient_id, queue_number=2, state=QueueState.REQUESTED)
    with uow_factory() as uow:
        uow.queue_entries.add(second)
        uow.commit()  # must not raise


def test_find_active_for_patient(uow_factory):
    patient = _seed_patient(uow_factory)
    entry = make_queue_entry(patient.patient_id, queue_number=1, state=QueueState.WAITING)
    with uow_factory() as uow:
        uow.queue_entries.add(entry)
        uow.commit()

    with uow_factory() as uow:
        active = uow.queue_entries.find_active_for_patient(patient.patient_id)
    assert active is not None
    assert active.entry_id == entry.entry_id


def test_update_on_terminal_entry_raises_conflict(uow_factory):
    patient = _seed_patient(uow_factory)
    entry = make_queue_entry(patient.patient_id, queue_number=1, state=QueueState.CANCELLED)
    with uow_factory() as uow:
        uow.queue_entries.add(entry)
        uow.commit()

    attempted_update = replace(
        entry, state=QueueState.WAITING, last_updated_at=datetime.now(timezone.utc)
    )
    with uow_factory() as uow:
        with pytest.raises(ConflictError):
            uow.queue_entries.update(attempted_update)


def test_update_missing_entry_raises_not_found(uow_factory):
    patient = _seed_patient(uow_factory)
    entry = make_queue_entry(patient.patient_id, queue_number=1)
    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.queue_entries.update(entry)


def test_list_by_queue_date_filters_by_state(uow_factory):
    patient_a = _seed_patient(uow_factory)
    patient_b = _seed_patient(uow_factory)
    today = date.today()
    waiting = make_queue_entry(
        patient_a.patient_id, queue_number=1, queue_date=today, state=QueueState.WAITING
    )
    cancelled = make_queue_entry(
        patient_b.patient_id, queue_number=2, queue_date=today, state=QueueState.CANCELLED
    )
    with uow_factory() as uow:
        uow.queue_entries.add(waiting)
        uow.queue_entries.add(cancelled)
        uow.commit()

    with uow_factory() as uow:
        only_waiting = uow.queue_entries.list_by_queue_date(
            today, states=[QueueState.WAITING]
        )
        everything = uow.queue_entries.list_by_queue_date(today)

    assert [e.entry_id for e in only_waiting] == [waiting.entry_id]
    assert {e.entry_id for e in everything} == {waiting.entry_id, cancelled.entry_id}


def test_remove_missing_entry_raises_not_found(uow_factory):
    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.queue_entries.remove("does-not-exist")
