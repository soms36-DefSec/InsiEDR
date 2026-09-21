from __future__ import annotations

import inspect
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from server.api.ingest import process_encrypted_request, IngestError
from server.api.deps import get_storage

router = APIRouter(prefix="/api", tags=["Telemetry & Ingestion"])
bp = router  # Backward compatibility alias


@router.post("/logs")
@router.post("/v1/logs")
async def post_logs(request: Request):
    try:
        status_code, body = await process_encrypted_request(request)
        return JSONResponse(content=body, status_code=status_code)
    except IngestError as exc:
        return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=exc.status_code)


@router.get("/logs")
@router.get("/v1/logs")
async def get_logs(
    request: Request,
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
    agent_id: str | None = None,
    hostname: str | None = None,
    username: str | None = None,
    collector: str | None = None,
    status: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    storage=Depends(get_storage),
):
    if storage is None:
        return JSONResponse({"ok": False, "error": "storage is not configured", "logs": []}, status_code=503)

    filters = {
        "agent_id": agent_id,
        "hostname": hostname,
        "username": username,
        "collector": collector,
        "status": status,
        "start_time": start_time,
        "end_time": end_time,
    }
    sig = inspect.signature(storage.list_logs)
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    valid_filters = {
        k: v for k, v in filters.items()
        if v and (accepts_kwargs or k in sig.parameters)
    }

    logs = storage.list_logs(limit=limit, offset=offset, **valid_filters)
    return {"ok": True, "logs": logs}


@router.get("/telemetry")
@router.get("/v1/telemetry")
async def get_telemetry(
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
    collector: str | None = None,
    username: str | None = None,
    storage=Depends(get_storage),
):
    if storage is None:
        return JSONResponse({"ok": False, "error": "storage is not configured", "telemetry": []}, status_code=503)

    try:
        telemetry = storage.list_collector_results(limit=limit, offset=offset, collector=collector, username=username)
    except AttributeError:
        return JSONResponse({"ok": False, "error": "storage method not implemented", "telemetry": []}, status_code=501)
    return {"ok": True, "logs": telemetry}

