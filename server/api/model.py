from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/model", tags=["Machine Learning Pipeline"])
bp = router  # Backward compatibility alias


@router.post("/recalibrate")
async def recalibrate():
    """
    The current G-model is a static, pre-trained InferenceEngine.
    Retraining on the server is disabled to preserve the model exactly as provided.
    """
    return JSONResponse(
        content={
            "ok": False,
            "error": "The G-model is static and pre-trained. On-server retraining is disabled.",
        },
        status_code=400,
    )

