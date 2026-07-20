"""
SqliteUnitOfWork — the concrete Transaction Boundary implementation
(REPOSITORY_INTERFACE.md §8, SQLITE_REPOSITORY_DESIGN.md §9).

Also defines SqliteRepositories, the standalone (non-UnitOfWork) access
path for a single Repository Interface operation — see its docstring.
"""

from __future__ import annotations

from database.interfaces import UnitOfWork
from database.sqlite.connection import SqliteConnectionManager
from database.sqlite.patient_repository import SqlitePatientRepository
from database.sqlite.queue_entry_repository import SqliteQueueEntryRepository
from database.sqlite.visit_repository import SqliteVisitRepository


class SqliteRepositories:
    """
    Standalone repository access for a single Repository Interface call,
    with no explicit Unit of Work required.

    REPOSITORY_INTERFACE.md §8 requires an explicit unit-of-work boundary
    only for "multi-step workflows that span more than one operation";
    "a single repository operation is implicitly transactional with
    respect to itself." SQLITE_REPOSITORY_DESIGN.md §7 states the same
    thing from the SQLite side: "One interface operation, one storage
    transaction." Forcing every caller to open `with provider.unit_of_work()
    as uow:` just to perform one `get_by_id` would satisfy the letter of
    neither document and would leave `SqliteRepositoryBase._execute_write`'s
    per-call auto-commit branch (used whenever no Unit of Work is active)
    permanently unreachable.

    Each attribute here is bound to the same application-scoped connection
    and write lock as SqliteUnitOfWork (SQLITE_REPOSITORY_DESIGN.md §11:
    single-writer, serialized at the Database boundary), so a write issued
    through this bundle still blocks behind a concurrently in-progress
    SqliteUnitOfWork rather than racing it — the single-writer guarantee
    holds regardless of which access path a caller uses.
    """

    def __init__(self, connection_manager: SqliteConnectionManager) -> None:
        connection_manager.activate()
        connection = connection_manager.connection
        write_lock = connection_manager.write_lock
        tx_context = connection_manager.tx_context

        self.patients = SqlitePatientRepository(connection, write_lock, tx_context)
        self.queue_entries = SqliteQueueEntryRepository(connection, write_lock, tx_context)
        self.visits = SqliteVisitRepository(connection, write_lock, tx_context)


class SqliteUnitOfWork(UnitOfWork):
    def __init__(self, connection_manager: SqliteConnectionManager) -> None:
        self._manager = connection_manager
        self._committed = False

    def __enter__(self) -> "SqliteUnitOfWork":
        self._manager.activate()
        self._manager.write_lock.acquire()
        self._manager.tx_context.active = True
        connection = self._manager.connection
        write_lock = self._manager.write_lock
        tx_context = self._manager.tx_context

        self.patients = SqlitePatientRepository(connection, write_lock, tx_context)
        self.queue_entries = SqliteQueueEntryRepository(connection, write_lock, tx_context)
        self.visits = SqliteVisitRepository(connection, write_lock, tx_context)
        self._committed = False
        return self

    def commit(self) -> None:
        self._manager.connection.commit()
        self._committed = True

    def rollback(self) -> None:
        self._manager.connection.rollback()
        self._committed = True  # already resolved; __exit__ must not roll back again

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            # No partial visibility (REPOSITORY_INTERFACE.md §8): unless
            # commit() was explicitly reached, every change made through
            # this unit of work's repositories is discarded — including
            # when an exception propagated out of the `with` block.
            if exc_type is not None or not self._committed:
                self._manager.connection.rollback()
        finally:
            self._manager.tx_context.active = False
            self._manager.write_lock.release()
        return None  # never suppress an exception raised inside the block
