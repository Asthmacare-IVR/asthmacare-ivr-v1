"""Dependency injection providers for the FastAPI application.

GitHub Issue #1 (Backend API Foundation) wired only ``Settings``. GitHub
Issue #3 (Queue Engine Integration) extends this module with the two
providers routers need to reach the Queue Engine and the Repository
layer, per ``docs/architecture/SYSTEM_ARCHITECTURE.md`` §4's dependency
rule:

    backend.api -> queue_engine -> database.interfaces -> database.sqlite

``backend.api`` never imports a concrete repository module directly by
name for construction purposes other than the single, config-driven
factory call below (``database.sqlite.factory.build_unit_of_work``),
which is the sanctioned entry point ``SQLITE_REPOSITORY_DESIGN.md`` §12
designates for exactly this purpose. Routers themselves depend only on
``database.interfaces.UnitOfWork`` and ``queue_engine.engine.QueueEngine``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from backend.config.settings import Settings, get_settings
from database.interfaces import UnitOfWork
from database.sqlite.factory import (
    SqliteConfig,
    SqliteRepositoryProvider,
    build_unit_of_work,
)
from queue_engine.engine import QueueEngine, QueueEngineConfig
from queue_engine.events import QueueEvent

logger = logging.getLogger("asthmacare_ivr.queue_engine")

SettingsDep = Annotated[Settings, Depends(get_settings)]
"""Injectable application settings, resolved once per process via
``get_settings``'s ``lru_cache`` and reused across requests."""


def _log_queue_event(event: QueueEvent) -> None:
    """Log a single Queue Engine event.

    This is the first Queue Engine event handler
    (``queue_engine.engine.QueueEngine.register_event_handler``) and,
    per Issue #3's scope, only logs. The registration mechanism is
    intentionally reusable: additional handlers for the Dashboard,
    Telephony, Notification, and Audit concerns can be attached the same
    way, at the same call site, without touching this one.

    Args:
        event: The immutable event emitted by the Queue Engine on a
            state transition or retry attempt.
    """
    logger.info(
        "queue_event event_type=%s entry_id=%s patient_id=%s "
        "from_state=%s to_state=%s",
        event.event_type.value,
        event.entry_id,
        event.patient_id,
        event.from_state.value,
        event.to_state.value,
    )


@lru_cache(maxsize=1)
def _build_queue_engine() -> QueueEngine:
    """Construct the process-wide ``QueueEngine`` singleton.

    The Queue Engine is stateless with respect to persistence (all
    persistence flows through the ``UnitOfWork`` passed into each of its
    methods) so a single, cached instance per process is safe to share
    across requests. Cached with ``lru_cache`` for the same reason
    ``get_settings`` is: construct once, reuse everywhere.

    Returns:
        A ``QueueEngine`` configured with default operational parameters
        and the logging event handler already registered.
    """
    engine = QueueEngine(QueueEngineConfig())
    engine.register_event_handler(_log_queue_event)
    return engine


def get_queue_engine() -> QueueEngine:
    """FastAPI dependency provider for the ``QueueEngine``.

    Returns:
        The process-wide ``QueueEngine`` singleton.
    """
    return _build_queue_engine()


QueueEngineDep = Annotated[QueueEngine, Depends(get_queue_engine)]
"""Injectable Queue Engine orchestrator."""


@lru_cache(maxsize=1)
def _get_repository_provider(database_path: str) -> SqliteRepositoryProvider:
    """Construct the process-wide SQLite repository provider.

    Cached per ``database_path`` (rather than per ``Settings`` instance,
    which is not hashable) so the underlying
    ``database.sqlite.connection.SqliteConnectionManager`` — and its
    single-writer lock (SQLITE_REPOSITORY_DESIGN.md §11) — is shared
    across requests instead of reopening a connection every time.

    Args:
        database_path: Filesystem path to the SQLite database file, from
            ``Settings.database_path``.

    Returns:
        The ``SqliteRepositoryProvider`` for this ``database_path``.
    """
    return build_unit_of_work(SqliteConfig(database_path=database_path))


def get_repository_provider(settings: SettingsDep) -> SqliteRepositoryProvider:
    """FastAPI dependency provider for the ``SqliteRepositoryProvider``.

    Args:
        settings: Injected application settings.

    Returns:
        The process-wide ``SqliteRepositoryProvider``.
    """
    return _get_repository_provider(settings.database_path)


def get_unit_of_work(
    provider: Annotated[SqliteRepositoryProvider, Depends(get_repository_provider)],
) -> Iterator[UnitOfWork]:
    """FastAPI dependency provider for a request-scoped ``UnitOfWork``.

    Opens one ``UnitOfWork`` (REPOSITORY_INTERFACE.md §8 Transaction
    Boundary) per request and yields it for the duration of the request.
    Queue Engine operations call ``uow.commit()`` themselves once a
    transition has been executed and persisted; if a route never reaches
    that point (e.g. it raises before calling the Queue Engine, or the
    Queue Engine itself raises before persisting), the ``UnitOfWork``'s
    own ``__exit__`` rolls back any uncommitted work automatically —
    routers never call ``commit()`` or ``rollback()`` directly.

    Args:
        provider: Injected repository provider owning the shared
            connection and write lock.

    Yields:
        A ``UnitOfWork`` bound to ``uow.patients``, ``uow.queue_entries``,
        and ``uow.visits`` repositories for this request.
    """
    with provider.unit_of_work() as uow:
        yield uow


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]
"""Injectable, request-scoped Unit of Work / Transaction Boundary."""
