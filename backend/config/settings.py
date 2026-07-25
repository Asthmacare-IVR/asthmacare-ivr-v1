"""Application configuration for the AsthmaCare IVR Platform backend.

Loaded via ``pydantic-settings`` from environment variables (and an
optional ``.env`` file). Per ``docs/architecture/SYSTEM_ARCHITECTURE.md``
§4 and ``backend/config/README.md``, this module depends on nothing else
in the project and may be depended upon by any other layer that needs
settings (``api/``, ``queue_engine/``, ``database/``, ``telephony/``).

No business logic, database access, or I/O beyond reading configuration
values lives here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend API.

    Values are read from environment variables (prefixed with
    ``ASTHMACARE_``) and, if present, a local ``.env`` file. Every field
    has a safe default so the application can start with zero
    configuration during local development.
    """

    model_config = SettingsConfigDict(
        env_prefix="ASTHMACARE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "AsthmaCare-IVR"
    version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_path: str = "asthmacare.db"
    """Filesystem path for the SQLite Repository Interface implementation
    (SQLITE_REPOSITORY_DESIGN.md §12: "configuration values are supplied
    to the Repository by config/"). Consumed by
    ``backend.api.dependencies`` to construct the ``SqliteConfig`` handed
    to ``database.sqlite.factory.build_unit_of_work`` — added by GitHub
    Issue #3 (Queue Engine Integration), which is the first phase to need
    a real, request-scoped ``UnitOfWork``."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance.

    Cached with ``lru_cache`` so environment variables are parsed once per
    process rather than on every dependency resolution.

    Returns:
        The singleton ``Settings`` instance for this process.
    """
    return Settings()