from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from server.api.cache import api_cache
from server.api.responses import api_error
from server.api.deps import get_storage

router = APIRouter(prefix="/api", tags=["System & Observability"])
bp = router  # Backward compatibility alias


@router.get("/stats")
@router.get("/v1/stats")
async def get_stats(request: Request, storage=Depends(get_storage)):
    """Returns aggregated fleet overview stats, protected by 5s in-memory TTL caching."""
    cached_stats = api_cache.get("fleet_stats")
    if cached_stats is not None:
        return cached_stats

    if storage is None:
        return api_error(
            code="STORAGE_UNAVAILABLE",
            message="Storage is not configured",
            status_code=503,
            error="storage is not configured",
        )

    stats = storage.get_stats()
    api_cache.set("fleet_stats", stats, ttl=5.0)
    return stats

