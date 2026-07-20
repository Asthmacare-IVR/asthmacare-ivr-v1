from __future__ import annotations

from dataclasses import replace

import pytest

from database.domain import VisitType
from database.errors import NotFoundError
from tests.conftest import make_patient, make_visit


def _seed_patient(uow_factory):
    patient = make_patient()
    with uow_factory() as uow:
        uow.patients.add(patient)
        uow.commit()
    return patient


def test_add_then_get_by_id_round_trips(uow_factory):
    patient = _seed_patient(uow_factory)
    visit = make_visit(patient.patient_id, visit_type=VisitType.APPOINTMENT)
    with uow_factory() as uow:
        uow.visits.add(visit)
        uow.commit()

    with uow_factory() as uow:
        fetched = uow.visits.get_by_id(visit.visit_id)
    assert fetched == visit


def test_list_for_patient_returns_only_that_patients_visits(uow_factory):
    patient_a = _seed_patient(uow_factory)
    patient_b = _seed_patient(uow_factory)
    visit_a = make_visit(patient_a.patient_id)
    visit_b = make_visit(patient_b.patient_id)

    with uow_factory() as uow:
        uow.visits.add(visit_a)
        uow.visits.add(visit_b)
        uow.commit()

    with uow_factory() as uow:
        results = uow.visits.list_for_patient(patient_a.patient_id)
    assert [v.visit_id for v in results] == [visit_a.visit_id]


def test_update_persists_new_values(uow_factory):
    patient = _seed_patient(uow_factory)
    visit = make_visit(patient.patient_id, visit_type=VisitType.WALK_IN)
    with uow_factory() as uow:
        uow.visits.add(visit)
        uow.commit()

    updated = replace(visit, visit_type=VisitType.APPOINTMENT)
    with uow_factory() as uow:
        uow.visits.update(updated)
        uow.commit()

    with uow_factory() as uow:
        fetched = uow.visits.get_by_id(visit.visit_id)
    assert fetched.visit_type is VisitType.APPOINTMENT


def test_remove_missing_visit_raises_not_found(uow_factory):
    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.visits.remove("does-not-exist")


def test_get_by_id_missing_visit_raises_not_found(uow_factory):
    with uow_factory() as uow:
        with pytest.raises(NotFoundError):
            uow.visits.get_by_id("does-not-exist")
