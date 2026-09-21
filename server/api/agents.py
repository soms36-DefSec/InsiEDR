from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from server.api.deps import get_storage

router = APIRouter(prefix="/api", tags=["Fleet & Endpoints"])
bp = router  # Backward compatibility alias


@router.get("/agents")
@router.get("/v1/agents")
async def get_agents(
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
    storage=Depends(get_storage),
):
    if storage is None:
        return JSONResponse({"ok": False, "error": "storage is not configured", "agents": []}, status_code=503)
    return {"ok": True, "agents": storage.list_agents(limit=limit, offset=offset)}


@router.get("/agents/tamper-alerts")
@router.get("/v1/agents/tamper-alerts")
async def get_tamper_alerts(
    limit: int = Query(50, ge=1),
    storage=Depends(get_storage),
):
    """Returns recent risk events where tamper_detector fired."""
    if storage is None:
        return JSONResponse({"ok": False, "error": "storage is not configured", "alerts": []}, status_code=503)

    try:
        risk_events = storage.list_risk_events(limit=500, offset=0)

        tamper_alerts = []
        for ev in risk_events:
            try:
                signals = ev.get("correlated_signals_json")
                if isinstance(signals, str):
                    signals = json.loads(signals)
                elif signals is None:
                    signals = {}

                if signals.get("tamper_detector", {}).get("is_anomaly") is True:
                    level = (ev.get("risk_level") or "").upper()
                    if not level or level in ["NONE", "INFO"]:
                        score = float(ev.get("risk_score") or 0.0)
                        if score >= 85.0:
                            level = "CRITICAL"
                        elif score >= 60.0:
                            level = "HIGH"
                        elif score >= 35.0:
                            level = "MEDIUM"
                        else:
                            level = "LOW"
                    ev["risk_level"] = level
                    tamper_alerts.append(ev)
            except Exception:
                continue

            if len(tamper_alerts) >= limit:
                break

        return {"ok": True, "alerts": tamper_alerts}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "alerts": []}, status_code=500)

