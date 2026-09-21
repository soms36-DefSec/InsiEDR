from __future__ import annotations

from typing import Any
from fastapi import Request


def get_storage(request: Request) -> Any:
    """Extract storage instance from FastAPI app.state or legacy extensions."""
    if hasattr(request.app.state, "storage"):
        return request.app.state.storage
    if hasattr(request.app, "extensions"):
        return request.app.extensions.get("insiedr_storage")
    return None


def get_task_queue(request: Request) -> Any:
    """Extract task queue instance from FastAPI app.state or legacy extensions."""
    if hasattr(request.app.state, "task_queue"):
        return request.app.state.task_queue
    if hasattr(request.app, "extensions"):
        return request.app.extensions.get("task_queue")
    return None
