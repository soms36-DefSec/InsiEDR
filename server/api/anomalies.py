from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from server.api.deps import get_storage

router = APIRouter(prefix="/api", tags=["Threat Intelligence"])
bp = router  # Backward compatibility alias


@router.get("/anomalies")
@router.get("/v1/anomalies")
@router.get("/threats")
@router.get("/v1/threats")
async def get_anomalies(
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
    storage=Depends(get_storage),
):
    if storage is None:
        return JSONResponse({"ok": False, "error": "storage is not configured", "anomalies": []}, status_code=503)

    risk_events = []
    list_risk_events = getattr(storage, "list_risk_events", None)
    if callable(list_risk_events):
        risk_events = list_risk_events(limit=limit, offset=offset)

    return {
        "ok": True,
        "anomalies": storage.list_anomalies(limit=limit, offset=offset),
        "risk_events": risk_events,
    }

