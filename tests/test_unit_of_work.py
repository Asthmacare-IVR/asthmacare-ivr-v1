"""
REPOSITORY_INTERFACE.md §8: either all included changes are durably
applied, or none are — and no caller may observe an intermediate,
partially-applied state.
"""

from __future__ import annotations

import pytest

from database.errors import NotFoundError
from tests.conftest import make_patient, make_queue_entry


def test_commit_makes_all_changes_in_the_block_visible(uow_factory):
    patient = make_patient()
    entry = make_queue_entry(patient.patient_id, queue_number=1)

    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.queue_entries.add(entry)
        uow.commit()

    with uow_factory() as uow:
        assert uow.patients.exists(patient.patient_id) is True
        assert uow.queue_entries.exists(entry.entry_id) is True


def test_exception_inside_block_rolls_back_every_change(uow_factory):
    patient = make_patient()
    entry = make_queue_entry(patient.patient_id, queue_number=1)

    class DeliberateFailure(Exception):
        pass

    with pytest.raises(DeliberateFailure):
        with uow_factory() as uow:
            uow.patients.add(patient)
            uow.queue_entries.add(entry)
            raise DeliberateFailure()

    with uow_factory() as uow:
        assert uow.patients.exists(patient.patient_id) is False
        assert uow.queue_entries.exists(entry.entry_id) is False


def test_explicit_rollback_discards_uncommitted_changes(uow_factory):
    patient = make_patient()

    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.rollback()

    with uow_factory() as uow:
        assert uow.patients.exists(patient.patient_id) is False


def test_forgetting_to_commit_rolls_back_on_exit(uow_factory):
    patient = make_patient()

    with uow_factory() as uow:
        uow.patients.add(patient)
        # deliberately no uow.commit()

    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.patients.get_by_id(patient.patient_id)
