"""Version endpoint.

``GET /version`` — reports the project name and running version, sourced
from application settings rather than hard-coded, so a single
configuration change (or environment variable) updates both this endpoint
and anywhere else ``Settings.version`` is used.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.dependencies import SettingsDep

router = APIRouter(tags=["version"])


@router.get("/version")
async def get_version(settings: SettingsDep) -> dict[str, str]:
    """Return the project name and version from application settings.

    Args:
        settings: Injected application settings.

    Returns:
        A mapping with ``project`` and ``version`` keys.
    """
    return {"project": settings.project_name, "version": settings.version}
