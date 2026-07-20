from __future__ import annotations

import pytest

from database.errors import ConflictError, NotFoundError
from tests.conftest import make_patient


def test_get_by_id_raises_not_found_when_missing(uow_factory):
    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.patients.get_by_id("does-not-exist")


def test_add_then_get_by_id_round_trips(uow_factory):
    patient = make_patient(name="Ayesha Rahman")
    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.commit()

    with uow_factory() as uow:
        fetched = uow.patients.get_by_id(patient.patient_id)
    assert fetched == patient


def test_add_duplicate_patient_id_raises_conflict(uow_factory):
    patient = make_patient()
    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(ConflictError):
            uow.patients.add(patient)


def test_add_duplicate_phone_number_raises_conflict(uow_factory):
    first = make_patient(phone_number="+8801700000001")
    second = make_patient(phone_number="+8801700000001")
    with uow_factory() as uow:
        uow.patients.add(first)
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(ConflictError):
            uow.patients.add(second)


def test_update_persists_new_values(uow_factory):
    patient = make_patient(name="Original Name")
    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.commit()

    updated = make_patient(
        patient_id=patient.patient_id,
        name="Updated Name",
        phone_number=patient.phone_number,
        created_at=patient.created_at,
    )
    with uow_factory() as uow:
        uow.patients.update(updated)
        uow.commit()

    with uow_factory() as uow:
        fetched = uow.patients.get_by_id(patient.patient_id)
    assert fetched.name == "Updated Name"


def test_update_duplicate_phone_number_raises_conflict(uow_factory):
    first = make_patient(phone_number="+8801700000001")
    second = make_patient(phone_number="+8801700000002")
    with uow_factory() as uow:
        uow.patients.add(first)
        uow.patients.add(second)
        uow.commit()

    updated_second = make_patient(
        patient_id=second.patient_id,
        name=second.name,
        phone_number=first.phone_number,
        created_at=second.created_at,
    )
    with uow_factory() as uow:
        with pytest.raises(ConflictError):
            uow.patients.update(updated_second)


def test_update_missing_patient_raises_not_found(uow_factory):
    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.patients.update(make_patient())


def test_remove_then_exists_is_false(uow_factory):
    patient = make_patient()
    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.commit()

    with uow_factory() as uow:
        uow.patients.remove(patient.patient_id)
        uow.commit()

    with uow_factory() as uow:
        assert uow.patients.exists(patient.patient_id) is False


def test_remove_missing_patient_raises_not_found(uow_factory):
    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.patients.remove("does-not-exist")
