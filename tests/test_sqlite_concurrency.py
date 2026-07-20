"""
SQLITE_REPOSITORY_DESIGN.md §11: "Concurrent writers are serialized at the
Database boundary rather than pushed upward as a caller concern" and
REPOSITORY_INTERFACE.md §9: "Conflict visibility, not silent loss" — two
callers racing to claim the same queue number must not both succeed, and
concurrent writers assigning *different* queue numbers must not corrupt
or lose any of them.
"""

from __future__ import annotations

import threading
from datetime import date

from database.errors import ConflictError
from database.sqlite.factory import SqliteConfig, build_unit_of_work
from tests.conftest import make_patient, make_queue_entry


def test_concurrent_writers_never_lose_or_corrupt_an_entry(tmp_path):
    provider = build_unit_of_work(
        SqliteConfig(database_path=str(tmp_path / "concurrency.db"))
    )
    today = date.today()
    thread_count = 8
    patients = [make_patient() for _ in range(thread_count)]
    for patient in patients:
        provider.repositories().patients.add(patient)

    errors: list[Exception] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            entry = make_queue_entry(
                patients[index].patient_id, queue_number=index + 1, queue_date=today
            )
            provider.repositories().queue_entries.add(entry)
        except Exception as exc:  # pragma: no cover - failure path recorded, not raised
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(thread_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    stored = provider.repositories().queue_entries.list_by_queue_date(today)
    assert {e.queue_number for e in stored} == set(range(1, thread_count + 1))
    assert len(stored) == thread_count
    provider.dispose()


def test_concurrent_writers_racing_for_the_same_queue_number_yield_exactly_one_winner(
    tmp_path,
):
    provider = build_unit_of_work(
        SqliteConfig(database_path=str(tmp_path / "concurrency_race.db"))
    )
    today = date.today()
    contender_count = 6
    patients = [make_patient() for _ in range(contender_count)]
    for patient in patients:
        provider.repositories().patients.add(patient)

    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        entry = make_queue_entry(
            patients[index].patient_id, queue_number=1, queue_date=today
        )
        try:
            provider.repositories().queue_entries.add(entry)
            with lock:
                outcomes.append("won")
        except ConflictError:
            with lock:
                outcomes.append("lost")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(contender_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every non-winner must observe a Conflict — never a silent lost
    # write and never an untranslated exception (REPOSITORY_INTERFACE.md
    # §9: "Conflict visibility, not silent loss").
    assert outcomes.count("won") == 1
    assert outcomes.count("lost") == contender_count - 1
    provider.dispose()
