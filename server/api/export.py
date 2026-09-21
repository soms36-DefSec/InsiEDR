from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Generator
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from server.api.deps import get_storage

router = APIRouter(prefix="/api", tags=["Streaming Export"])
bp = router  # Backward compatibility alias

CHUNK_BATCH_SIZE = 1000


def _format_timestamp(val: Any) -> str:
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val or "")


def _stream_csv_logs(storage, filters: dict[str, Any], limit: int) -> Generator[str, None, None]:
    """Generator yielding CSV rows in chunks for telemetry logs."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    # Header
    writer.writerow([
        "id",
        "collected_at",
        "agent_id",
        "hostname",
        "username",
        "collector",
        "status",
        "payload_json",
    ])
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    offset = 0
    exported = 0

    while exported < limit:
        batch_limit = min(CHUNK_BATCH_SIZE, limit - exported)
        rows = storage.list_logs(limit=batch_limit, offset=offset, **filters)
        if not rows:
            break

        for row in rows:
            payload_str = ""
            if row.get("payload"):
                payload_str = json.dumps(row["payload"], default=str)
            elif row.get("payload_json"):
                payload_str = str(row["payload_json"])
            elif row.get("encrypted_envelope_json"):
                payload_str = str(row["encrypted_envelope_json"])

            writer.writerow([
                row.get("id") or row.get("payload_id", ""),
                _format_timestamp(row.get("collected_at") or row.get("payload_collected_at") or row.get("received_at")),
                row.get("agent_id", ""),
                row.get("hostname", ""),
                row.get("username", ""),
                row.get("collector", ""),
                row.get("status") or row.get("validation_status", ""),
                payload_str,
            ])

        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        count = len(rows)
        exported += count
        offset += count
        if count < batch_limit:
            break


def _stream_json_logs(storage, filters: dict[str, Any], limit: int) -> Generator[str, None, None]:
    """Generator yielding JSON lines (NDJSON) for telemetry logs."""
    offset = 0
    exported = 0

    while exported < limit:
        batch_limit = min(CHUNK_BATCH_SIZE, limit - exported)
        rows = storage.list_logs(limit=batch_limit, offset=offset, **filters)
        if not rows:
            break

        for row in rows:
            # Symmetrically guarantee canonical aliases for consumers
            if "id" not in row and "payload_id" in row:
                row["id"] = row["payload_id"]
            if "collected_at" not in row and "payload_collected_at" in row:
                row["collected_at"] = row["payload_collected_at"]
            if "status" not in row and "validation_status" in row:
                row["status"] = row["validation_status"]
            yield json.dumps(row, default=str) + "\n"

        count = len(rows)
        exported += count
        offset += count
        if count < batch_limit:
            break


def _stream_csv_threats(storage, limit: int) -> Generator[str, None, None]:
    """Generator yielding CSV rows for risk events."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow([
        "id",
        "created_at",
        "payload_id",
        "agent_id",
        "username",
        "risk_level",
        "risk_score",
        "summary",
        "correlated_signals_json",
    ])
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    offset = 0
    exported = 0

    while exported < limit:
        batch_limit = min(CHUNK_BATCH_SIZE, limit - exported)
        rows = storage.list_risk_events(limit=batch_limit, offset=offset)
        if not rows:
            break

        for row in rows:
            signals_str = ""
            signals = row.get("correlated_signals_json")
            if isinstance(signals, (dict, list)):
                signals_str = json.dumps(signals)
            elif signals is not None:
                signals_str = str(signals)

            writer.writerow([
                row.get("id", ""),
                _format_timestamp(row.get("created_at")),
                row.get("payload_id", ""),
                row.get("agent_id", ""),
                row.get("username", ""),
                (row.get("risk_level") or "").upper(),
                row.get("risk_score", 0.0),
                row.get("summary", ""),
                signals_str,
            ])

        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        count = len(rows)
        exported += count
        offset += count
        if count < batch_limit:
            break


def _stream_json_threats(storage, limit: int) -> Generator[str, None, None]:
    """Generator yielding JSON lines for risk events."""
    offset = 0
    exported = 0

    while exported < limit:
        batch_limit = min(CHUNK_BATCH_SIZE, limit - exported)
        rows = storage.list_risk_events(limit=batch_limit, offset=offset)
        if not rows:
            break

        for row in rows:
            yield json.dumps(row, default=str) + "\n"

        count = len(rows)
        exported += count
        offset += count
        if count < batch_limit:
            break


@router.get("/v1/export/logs")
@router.get("/export/logs")
@router.get("/v1/export/logs.csv")
@router.get("/export/logs.csv")
@router.get("/v1/export/logs.json")
@router.get("/export/logs.json")
async def export_logs(
    request: Request,
    format: str = Query("csv"),
    limit: int = Query(50000),
    agent_id: str | None = None,
    hostname: str | None = None,
    username: str | None = None,
    collector: str | None = None,
    status: str | None = None,
    storage=Depends(get_storage),
):
    """Stream telemetry logs in CSV or JSON format with constant memory usage."""
    if storage is None:
        return JSONResponse({"ok": False, "error": "Storage is not configured"}, status_code=503)

    path = request.url.path.lower()
    if path.endswith(".json") or path.endswith(".jsonl"):
        export_format = "json"
    elif path.endswith(".csv"):
        export_format = "csv"
    else:
        export_format = format.lower()

    bounded_limit = min(max(1, limit), 200000)

    filters = {
        k: v for k, v in {
            "agent_id": agent_id,
            "hostname": hostname,
            "username": username,
            "collector": collector,
            "status": status,
        }.items() if v
    }

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if export_format in ("json", "jsonl"):
        generator = _stream_json_logs(storage, filters, bounded_limit)
        mimetype = "application/x-ndjson"
        filename = f"insiedr_telemetry_{timestamp_str}.jsonl"
    else:
        generator = _stream_csv_logs(storage, filters, bounded_limit)
        mimetype = "text/csv; charset=utf-8"
        filename = f"insiedr_telemetry_{timestamp_str}.csv"

    return StreamingResponse(
        generator,
        media_type=mimetype,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/v1/export/threats")
@router.get("/export/threats")
@router.get("/v1/export/threats.csv")
@router.get("/export/threats.csv")
@router.get("/v1/export/threats.json")
@router.get("/export/threats.json")
async def export_threats(
    request: Request,
    format: str = Query("csv"),
    limit: int = Query(50000),
    storage=Depends(get_storage),
):
    """Stream risk events and threat detections in CSV or JSON format."""
    if storage is None:
        return JSONResponse({"ok": False, "error": "Storage is not configured"}, status_code=503)

    path = request.url.path.lower()
    if path.endswith(".json") or path.endswith(".jsonl"):
        export_format = "json"
    elif path.endswith(".csv"):
        export_format = "csv"
    else:
        export_format = format.lower()

    bounded_limit = min(max(1, limit), 200000)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if export_format in ("json", "jsonl"):
        generator = _stream_json_threats(storage, bounded_limit)
        mimetype = "application/x-ndjson"
        filename = f"insiedr_threats_{timestamp_str}.jsonl"
    else:
        generator = _stream_csv_threats(storage, bounded_limit)
        mimetype = "text/csv; charset=utf-8"
        filename = f"insiedr_threats_{timestamp_str}.csv"

    return StreamingResponse(
        generator,
        media_type=mimetype,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )

