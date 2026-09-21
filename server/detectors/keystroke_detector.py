import logging
from typing import Any, Dict, List

log = logging.getLogger("keystroke_detector")

ENROLLMENT_TARGET = 100

_engines: Dict[str, Any] = {}

def get_engine(username: str):
    if username not in _engines:
        import sys
        from pathlib import Path
        try:
            from src.server.keystroke_inference import KeystrokeInferenceEngine
            _engines[username] = KeystrokeInferenceEngine()
        except Exception as e:
            log.error(f"Failed to load KeystrokeInferenceEngine for {username}: {e}")
            _engines[username] = False
            
    return _engines[username]

def evaluate_keystrokes(keystroke_timings: List[List[float]], username: str) -> Dict[str, Any]:
    engine = get_engine(username)
    result = {
        "detector_name": "keystroke_biometrics",
        "score": 0.0,
        "confidence": 0.0,
        "is_anomaly": False,
        "feature_contributions": {},
        "reason": "Normal typing behavior."
    }
    
    if not engine:
        result["reason"] = "Keystroke engine not available."
        return result
        
    if not keystroke_timings:
        return result

    try:
        # Predict Risk (runs Gate 1 heuristics regardless of enrollment)
        risk = engine.predict_risk(keystroke_timings)
        
        if risk.get("is_bot"):
            result["score"] = risk.get("risk_score", 1.0) * 100.0
            result["confidence"] = 0.95
            result["is_anomaly"] = True
            result["reason"] = f"Automated Bot/Script Activity Detected: {risk.get('bot_reason')}"
            return result

        # Enrollment phase logic (first sufficient chunk if not a bot)
        if engine.baseline_embedding is None and len(keystroke_timings) >= 10:
            import numpy as np
            formatted_timings = []
            for ht, ft in keystroke_timings:
                formatted_timings.append([0.0, float(ht), float(ft)])
            chunk = np.array(formatted_timings)
            
            if len(chunk) > ENROLLMENT_TARGET:
                chunk = chunk[:ENROLLMENT_TARGET]
            elif len(chunk) < ENROLLMENT_TARGET:
                chunk = np.pad(chunk, ((0, ENROLLMENT_TARGET - len(chunk)), (0, 0)), mode='constant')
                
            engine.enroll_user(np.expand_dims(chunk, axis=0))
            result["reason"] = "Enrolled baseline typing profile."
            return result
        
        # Scale 0.0-1.0 to 0-100 for the aggregator
        result["score"] = risk.get("risk_score", 0.0) * 100.0
        result["confidence"] = 0.95 if risk.get("biometric_mismatch") else 0.8
        
        if risk.get("biometric_mismatch"):
            result["is_anomaly"] = True
            result["reason"] = f"Biometric Mismatch (Score: {result['score']:.2f}). Possible Workstation Hijacking."
            
        return result
    except Exception as e:
        log.error(f"Error evaluating keystrokes: {e}")
        result["reason"] = f"Error: {e}"
        return result
