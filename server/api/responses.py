"""
server/api/responses.py
-----------------------
Standardized JSON response envelopes for InsiEDR FastAPI.
Ensures uniform response structures while preserving legacy 'ok': True/False keys
for existing frontend and telemetry clients.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from fastapi.responses import JSONResponse


def api_success(
    data: Any = None,
    meta: Mapping[str, Any] | None = None,
    status_code: int = 200,
    **legacy_kwargs: Any,
) -> JSONResponse:
    """
    Produce a consistent success response:
    {
        "ok": true,
        "success": true,
        "data": <data>,
        "meta": <meta>,
        "timestamp": "<iso8601>",
        ...<legacy_kwargs>
    }
    """
    payload: dict[str, Any] = {
        "ok": True,
        "success": True,
        "data": data,
        "meta": meta or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Merge any legacy top-level keys (e.g., "agents", "logs", "anomalies") for backward compatibility
    for key, value in legacy_kwargs.items():
        if key not in payload or payload[key] is None:
            payload[key] = value

    return JSONResponse(content=payload, status_code=status_code)


def api_error(
    code: str,
    message: str,
    details: Any = None,
    status_code: int = 400,
    **legacy_kwargs: Any,
) -> JSONResponse:
    """
    Produce a consistent RFC 7807-style error response:
    {
        "ok": false,
        "success": false,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    """
    payload: dict[str, Any] = {
        "ok": False,
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Backward compatibility: if legacy string error explicitly requested
    if "error_str" in legacy_kwargs:
        payload["error_str"] = legacy_kwargs.pop("error_str")

    for key, value in legacy_kwargs.items():
        if key not in payload:
            payload[key] = value

    return JSONResponse(content=payload, status_code=status_code)

