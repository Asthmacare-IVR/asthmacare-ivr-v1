from __future__ import annotations

from database.interfaces import UnitOfWork
from database.memory.in_memory_repository import (
    InMemoryPatientRepository,
    InMemoryQueueEntryRepository,
    InMemoryStore,
    InMemoryVisitRepository,
)


class InMemoryUnitOfWork(UnitOfWork):
    """
    Mock Transaction Boundary. Snapshots the store on entry and restores it
    on rollback/exception, giving the same "all or nothing" guarantee as
    SqliteUnitOfWork (REPOSITORY_INTERFACE.md §8) without any real storage
    engine — this is what makes it suitable for fast, deterministic Queue
    Engine tests (REPOSITORY_INTERFACE.md §11).
    """

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._snapshot: InMemoryStore | None = None
        self._committed = False

    def __enter__(self) -> "InMemoryUnitOfWork":
        self._snapshot = self._store.snapshot()
        self._committed = False
        self.patients = InMemoryPatientRepository(self._store)
        self.queue_entries = InMemoryQueueEntryRepository(self._store)
        self.visits = InMemoryVisitRepository(self._store)
        return self

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        assert self._snapshot is not None
        self._store.restore(self._snapshot)
        self._committed = True

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None or not self._committed:
            assert self._snapshot is not None
            self._store.restore(self._snapshot)
        self._snapshot = None
        return None
