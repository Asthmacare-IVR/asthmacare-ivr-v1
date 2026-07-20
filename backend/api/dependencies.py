"""Dependency injection providers for the FastAPI application.

Only configuration is wired here in this phase (Backend API Foundation,
GitHub Issue #1). Business-logic dependencies (Queue Engine, Database,
Telephony) are intentionally not introduced yet — see
``docs/architecture/SYSTEM_ARCHITECTURE.md`` §4 for the module dependency
rule this respects (``api/`` may depend on ``queue_engine/``, but does not
yet; it must never depend on ``database/`` or ``telephony/`` directly).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.config.settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
"""Injectable application settings, resolved once per process via
``get_settings``'s ``lru_cache`` and reused across requests."""
