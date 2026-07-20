"""
SqliteRepositories — standalone, single-operation Repository Interface
access with no explicit Unit of Work (REPOSITORY_INTERFACE.md §8: "a
single repository operation is implicitly transactional with respect to
itself"). See database/sqlite/unit_of_work.py::SqliteRepositories for the
audit finding this closes.
"""

from __future__ import annotations

import pytest

from database.errors import NotFoundError
from database.sqlite.factory import SqliteConfig, build_unit_of_work
from tests.conftest import make_patient


@pytest.fixture
def provider(tmp_path):
    provider = build_unit_of_work(SqliteConfig(database_path=str(tmp_path / "standalone.db")))
    yield provider
    provider.dispose()


def test_single_write_is_immediately_durable_without_a_unit_of_work(provider):
    patient = make_patient()
    provider.repositories().patients.add(patient)

    # A fresh repositories() call (and a fresh connection-backed read) must
    # see the write — it was never left inside an uncommitted transaction.
    fetched = provider.repositories().patients.get_by_id(patient.patient_id)
    assert fetched == patient


def test_standalone_read_of_missing_record_raises_not_found(provider):
    with pytest.raises(NotFoundError):
        provider.repositories().patients.get_by_id("does-not-exist")


def test_standalone_and_unit_of_work_share_the_same_underlying_store(provider):
    patient = make_patient()
    with provider.unit_of_work() as uow:
        uow.patients.add(patient)
        uow.commit()

    # Written through an explicit UnitOfWork, readable through the
    # standalone path — both bind to the same application-scoped
    # connection (SQLITE_REPOSITORY_DESIGN.md §5, §11).
    assert provider.repositories().patients.exists(patient.patient_id) is True
