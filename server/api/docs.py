"""
server/api/docs.py
------------------
Interactive OpenAPI 3.0 specification and Swagger UI documentation for InsiEDR FastAPI.
Served at /api/docs and /docs.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/api", tags=["Documentation"])
bp = router  # Backward compatibility alias

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "InsiEDR Enterprise Threat Defense API",
        "description": "Enterprise-grade REST and SSE API for endpoint telemetry ingestion, threat analysis, ML risk scoring, and streaming defense operations.",
        "version": "1.0.0",
        "contact": {"name": "InsiEDR Security Engineering Team"},
    },
    "servers": [
        {"url": "/", "description": "Local InsiEDR Server"}
    ],
    "tags": [
        {"name": "Ingestion", "description": "Cryptographically secure telemetry ingestion from remote Windows agents"},
        {"name": "Real-Time Streaming (SSE)", "description": "Server-Sent Events for zero-latency live alert feeds"},
        {"name": "Streaming Export", "description": "High-throughput chunked CSV and JSON streaming exports"},
        {"name": "Fleet & Endpoints", "description": "Monitored endpoint inventory and health tracking"},
        {"name": "Threat Intelligence", "description": "Fused heuristic and ML-driven risk assessments"},
        {"name": "System & Observability", "description": "Health checks, task queue metrics, and baseline profiles"},
    ],
    "paths": {
        "/api/logs": {
            "post": {
                "tags": ["Ingestion"],
                "summary": "Ingest Encrypted Agent Telemetry",
                "description": "Receives AES-GCM encrypted telemetry envelopes from Windows endpoint agents. Decrypts, validates replay protection, and enqueues for ML inference.",
                "parameters": [
                    {"name": "X-Crypto-Scheme", "in": "header", "required": True, "schema": {"type": "string", "example": "aes-256-gcm"}},
                    {"name": "X-Protocol-Version", "in": "header", "required": True, "schema": {"type": "string", "example": "1.0.0"}},
                    {"name": "X-Agent-ID", "in": "header", "required": True, "schema": {"type": "string", "example": "agent-001"}},
                    {"name": "X-Payload-ID", "in": "header", "required": True, "schema": {"type": "string", "example": "550e8400-e29b-41d4-a716-446655440000"}},
                    {"name": "X-Key-ID", "in": "header", "required": True, "schema": {"type": "string", "example": "k1"}},
                ],
                "responses": {
                    "202": {"description": "Telemetry envelope accepted and enqueued for inference"},
                    "400": {"description": "Malformed envelope or protocol version mismatch"},
                    "403": {"description": "Authentication failed or HTTPS required"},
                    "422": {"description": "Payload schema validation error"},
                }
            },
            "get": {
                "tags": ["Ingestion"],
                "summary": "Query Ingested Telemetry Logs",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
                    {"name": "username", "in": "query", "schema": {"type": "string"}},
                    {"name": "collector", "in": "query", "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"description": "Paginated list of telemetry records"}
                }
            }
        },
        "/api/v1/stream/threats": {
            "get": {
                "tags": ["Real-Time Streaming (SSE)"],
                "summary": "Live Threat Alert Stream (SSE)",
                "description": "Server-Sent Events endpoint pushing real-time threat detections, ML behavioral anomalies, and heuristic rule triggers.",
                "responses": {
                    "200": {
                        "description": "SSE text/event-stream delivering live threat notifications",
                        "content": {"text/event-stream": {}}
                    }
                }
            }
        },
        "/api/v1/stream/agents": {
            "get": {
                "tags": ["Real-Time Streaming (SSE)"],
                "summary": "Live Agent Status Stream (SSE)",
                "description": "Server-Sent Events endpoint pushing real-time endpoint online/offline state transitions and heartbeat updates.",
                "responses": {
                    "200": {
                        "description": "SSE text/event-stream delivering agent status updates",
                        "content": {"text/event-stream": {}}
                    }
                }
            }
        },
        "/api/v1/export/logs": {
            "get": {
                "tags": ["Streaming Export"],
                "summary": "Stream Telemetry Logs (CSV / JSON)",
                "description": "Streams telemetry records line-by-line using chunked transfer encoding, ensuring constant low memory usage (<10MB).",
                "parameters": [
                    {"name": "format", "in": "query", "schema": {"type": "string", "enum": ["csv", "json"], "default": "csv"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50000}},
                    {"name": "username", "in": "query", "schema": {"type": "string"}},
                    {"name": "collector", "in": "query", "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"description": "Attachment stream (CSV or NDJSON)"}
                }
            }
        },
        "/api/v1/export/threats": {
            "get": {
                "tags": ["Streaming Export"],
                "summary": "Stream Risk Events & Threats (CSV / JSON)",
                "description": "Streams risk events with fused heuristic and ML detection data.",
                "parameters": [
                    {"name": "format", "in": "query", "schema": {"type": "string", "enum": ["csv", "json"], "default": "csv"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50000}},
                ],
                "responses": {
                    "200": {"description": "Attachment stream (CSV or NDJSON)"}
                }
            }
        },
        "/api/agents": {
            "get": {
                "tags": ["Fleet & Endpoints"],
                "summary": "List Monitored Endpoints",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
                ],
                "responses": {
                    "200": {"description": "Active agent list with version and last-seen timestamp"}
                }
            }
        },
        "/api/stats": {
            "get": {
                "tags": ["System & Observability"],
                "summary": "Fleet Overview Statistics",
                "description": "Aggregated fleet metrics (agents, logs, anomalies). Protected by 5s in-memory TTL caching.",
                "responses": {
                    "200": {"description": "System statistical counts"}
                }
            }
        },
        "/api/health": {
            "get": {
                "tags": ["System & Observability"],
                "summary": "Deep System Health & Readiness",
                "description": "Inspects status of PostgreSQL storage, Redis queue buffer, active crypto schemes, and ML model bridge readiness.",
                "responses": {
                    "200": {"description": "Subsystem health report"}
                }
            }
        }
    }
}


@router.get("/docs", include_in_schema=False)
async def api_docs():
    """Redirect to native FastAPI Swagger UI."""
    return RedirectResponse(url="/docs")


@router.get("/redoc", include_in_schema=False)
async def api_redoc():
    """Redirect to native FastAPI ReDoc."""
    return RedirectResponse(url="/redoc")


@router.get("/openapi.json", include_in_schema=False)
def openapi_json():
    """Returns the OpenAPI 3.0 JSON specification."""
    from fastapi.responses import JSONResponse
    return JSONResponse(OPENAPI_SPEC)

