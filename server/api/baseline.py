from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from server.api.deps import get_storage

router = APIRouter(prefix="/api", tags=["Threat Intelligence"])
bp = router  # Backward compatibility alias


@router.get("/baseline/{username}")
@router.get("/v1/baseline/{username}")
async def get_baseline(
    username: str,
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
    storage=Depends(get_storage),
):
    """Retrieve statistical baseline profiles for an individual user.
    
    Prefers direct username lookup via storage.load_baseline() to prevent false-negative
    pagination dropouts when total baselines exceed the requested limit/offset window.
    Falls back gracefully to filtered list_baselines().
    """
    if storage is None:
        return JSONResponse({"ok": False, "error": "storage is not configured", "baseline": []}, status_code=503)

    # 1. Targeted direct lookup for the specific user
    if hasattr(storage, "load_baseline") and callable(storage.load_baseline):
        direct_row = storage.load_baseline(username)
        if direct_row:
            return {"ok": True, "username": username, "baseline": [direct_row]}

    # 2. Fallback to list_baselines
    items = [row for row in storage.list_baselines(limit=limit, offset=offset) if row.get("username") == username]
    return {"ok": True, "username": username, "baseline": items}

