"""Health check endpoint.

``GET /health`` — liveness probe. Returns a fixed shape and never touches
any downstream dependency, so it reflects only whether the process is
running and able to handle HTTP requests.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Return a fixed liveness payload.

    Returns:
        A mapping with a single ``status`` key, always ``"ok"`` while the
        process is up and serving requests.
    """
    return {"status": "ok"}
