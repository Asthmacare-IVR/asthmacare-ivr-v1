"""FastAPI application factory for the AsthmaCare IVR Platform backend.

This module builds and configures the FastAPI application instance. It
contains no business logic, no database access, and no Queue Engine or
Telephony integration — those are introduced in later GitHub issues, per
``docs/architecture/SYSTEM_ARCHITECTURE.md`` §4's dependency rule
(``api/`` may depend on ``queue_engine/``, but does not yet).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routers import health, version, queue,
from backend.config.settings import Settings, get_settings

logger = logging.getLogger("asthmacare_ivr.backend")


def configure_logging(settings: Settings) -> None:
    """Initialize process-wide logging from application settings.

    Args:
        settings: Application settings providing the configured log
            level.
    """
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    Args:
        app: The FastAPI application instance being started.

    Yields:
        Control back to FastAPI while the application is running.
    """
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "Starting %s v%s (environment=%s)",
        settings.project_name,
        settings.version,
        settings.environment,
    )
    yield
    logger.info("Shutting down %s", settings.project_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance.

    Returns:
        A fully configured ``FastAPI`` application, with the health and
        version routers registered and lifespan management attached.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(version.router)
    app.include_router(queue.router)

    return app


app = create_app()
"""Module-level application instance for ASGI servers, e.g.
``uvicorn backend.api.app:app``."""
