"""
tests/test_architectural_plugins.py
-----------------------------------
Tests verifying the pluggable detector/feature registries, bug fixes, and route parity:
1. Pluggable DetectorRegistry and custom detector extension
2. Pluggable FeatureExtractorRegistry and custom extractor extension
3. Fault tolerance against failing detector/extractor plugins
4. Bug 1: Nested dictionary feature unpacking in ModelBridge
5. Bug 6: Webhook NoneType risk_score formatting guard
6. Bug 4: Export schema field aliasing for Postgres raw_payloads
7. Bug 5: Baseline direct load_baseline query priority
8. Bug 8: Route aliases parity (/v1/risk-events, /v1/dashboard-summary, /threats)
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from server.app import create_app
from server.detectors.base import Detector
from server.detectors.registry import detector_registry, register_detector
from server.features.base import BaseFeatureExtractor
from server.features.registry import feature_registry, register_feature_extractor
from server.model_bridge import ModelBridge
from server.utils.webhook import _send_webhook


def test_detector_registry_and_custom_plugin():
    """Verify built-in detectors, custom detector registration, and execution."""
    # Ensure defaults are initialized
    detector_registry.initialize_defaults()
    default_names = [d.name for d in detector_registry.get_all()]
    assert "tamper_detector" in default_names
    assert "auth_burst" in default_names
    assert "zscore" in default_names
    assert "advanced_pipeline" in default_names

    # Register a new custom detector
    @register_detector
    class CustomTelemetryDetector(Detector):
        @property
        def name(self) -> str:
            return "custom_telemetry_detector"

        def detect(self, payload_id, agent_id, username, features, baseline, storage=None):
            return self.format_result(
                detector_name=self.name,
                score=42.0,
                confidence=0.88,
                is_anomaly=True,
                reason="Custom test detection trigger",
            )

    try:
        registered = detector_registry.get("custom_telemetry_detector")
        assert registered is not None
        assert registered.name == "custom_telemetry_detector"

        results = detector_registry.run_all(
            payload_id="p-101",
            agent_id="a-101",
            username="analyst_test",
            features={"logon_count": 5},
            baseline=None,
        )

        custom_res = next((r for r in results if r["detector_name"] == "custom_telemetry_detector"), None)
        assert custom_res is not None
        assert custom_res["score"] == 42.0
        assert custom_res["is_anomaly"] is True
    finally:
        detector_registry.unregister("custom_telemetry_detector")


def test_detector_registry_fault_tolerance():
    """Verify that a failing detector plugin does not crash run_all()."""
    @register_detector
    class CrashingDetector(Detector):
        @property
        def name(self) -> str:
            return "crashing_detector"

        def detect(self, payload_id, agent_id, username, features, baseline, storage=None):
            raise RuntimeError("Simulated detector explosion")

    try:
        results = detector_registry.run_all(
            payload_id="p-crash",
            agent_id="a-crash",
            username="victim",
            features={},
            baseline=None,
        )

        crash_res = next((r for r in results if r["detector_name"] == "crashing_detector"), None)
        assert crash_res is not None
        assert crash_res["score"] == 0.0
        assert crash_res["is_anomaly"] is False
        assert "Simulated detector explosion" in crash_res["reason"]
    finally:
        detector_registry.unregister("crashing_detector")


def test_feature_extractor_registry_and_custom_plugin():
    """Verify feature extractor registration and combined feature extraction."""
    feature_registry.initialize_defaults()
    names = [e.name for e in feature_registry.get_all()]
    assert "lanl_edr" in names

    @register_feature_extractor
    class CustomCloudAuditExtractor(BaseFeatureExtractor):
        @property
        def name(self) -> str:
            return "cloud_audit_extractor"

        def extract(self, payload):
            return {"cloud_api_call_count": 12.0, "s3_bucket_access_count": 3.0}

    try:
        features = feature_registry.extract_all({"dummy": "payload"})
        assert features.get("cloud_api_call_count") == 12.0
        assert features.get("s3_bucket_access_count") == 3.0
    finally:
        feature_registry._extractors.pop("cloud_audit_extractor", None)


def test_nested_dict_feature_unpacking_bugfix():
    """Verify Bug 1 fix: nested dictionaries unpack leaves into features without keeping parent dicts."""
    payload = {
        "collectors": [
            {
                "collector": "test-nested-collector",
                "status": "success",
                "payload": {
                    "system_metrics": {
                        "cpu_usage_pct": 78.5,
                        "ram_usage_mb": 4096.0,
                    },
                    "simple_feature": 10.0,
                },
            }
        ]
    }

    extracted = ModelBridge._payload_features(payload)
    assert extracted.get("cpu_usage_pct") == 78.5
    assert extracted.get("ram_usage_mb") == 4096.0
    assert extracted.get("simple_feature") == 10.0
    # Prior to fix, system_metrics key would be stored with entire dict value
    assert not isinstance(extracted.get("system_metrics"), dict)


def test_webhook_none_formatting_bugfix():
    """Verify Bug 6 fix: risk_score=None does not raise TypeError during string formatting."""
    event = {
        "username": "charlie",
        "agent_id": "agent-99",
        "risk_score": None,
        "summary": "Suspicious USB event",
    }

    with patch("server.utils.webhook.os.environ.get", return_value="http://fake-webhook.local/alert"):
        with patch("server.utils.webhook.requests.post") as mock_post:
            _send_webhook(event)
            assert mock_post.called
            sent_payload = mock_post.call_args[1]["json"]
            assert "0.00/100" in sent_payload["text"]


def test_export_schema_aliasing_postgres_raw_payloads():
    """Verify Bug 4 fix: export generators alias Postgres raw_payloads fields to id, collected_at, status."""
    class MockPostgresStorage:
        def list_logs(self, limit=100, offset=0, **kwargs):
            return [
                {
                    "payload_id": "pg-uuid-1234",
                    "payload_collected_at": "2026-09-12T05:00:00Z",
                    "agent_id": "agent-pg",
                    "hostname": "PG-HOST",
                    "username": "pg_user",
                    "collector": "auth-collector",
                    "validation_status": "accepted",
                    "encrypted_envelope_json": "{}",
                }
            ]

        def list_risk_events(self, limit=100, offset=0):
            return []

    app = create_app(storage=MockPostgresStorage(), apply_migrations=False)
    client = TestClient(app)

    # 1. CSV export
    csv_resp = client.get("/api/v1/export/logs.csv")
    assert csv_resp.status_code == 200
    csv_lines = csv_resp.text.strip().splitlines()
    header = csv_lines[0]
    data_row = csv_lines[1]
    assert "id,collected_at,agent_id,hostname,username,collector,status" in header
    # Check that payload_id aliased to id column
    assert "pg-uuid-1234" in data_row
    assert "2026-09-12T05:00:00Z" in data_row
    assert "accepted" in data_row

    # 2. NDJSON export
    ndjson_resp = client.get("/api/v1/export/logs.json")
    assert ndjson_resp.status_code == 200
    json_obj = json.loads(ndjson_resp.text.strip().splitlines()[0])
    assert json_obj.get("id") == "pg-uuid-1234"
    assert json_obj.get("collected_at") == "2026-09-12T05:00:00Z"
    assert json_obj.get("status") == "accepted"


def test_baseline_load_baseline_priority():
    """Verify Bug 5 fix: baseline endpoint prioritizes storage.load_baseline() for targeted lookup."""
    mock_storage = MagicMock()
    mock_storage.load_baseline.return_value = {
        "username": "special_agent",
        "mean_value": 45.2,
        "sample_count": 100,
    }

    app = create_app(storage=mock_storage, apply_migrations=False)
    client = TestClient(app)

    resp = client.get("/api/v1/baseline/special_agent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["username"] == "special_agent"
    assert len(body["baseline"]) == 1
    assert body["baseline"][0]["mean_value"] == 45.2
    # Verify load_baseline was queried directly
    mock_storage.load_baseline.assert_called_once_with("special_agent")


def test_route_aliases_parity():
    """Verify Bug 8 fix: symmetric route aliases exist for /v1/risk-events, /v1/dashboard-summary, /threats."""
    mock_storage = MagicMock()
    mock_storage.list_risk_events.return_value = []
    mock_storage.list_anomalies.return_value = []
    mock_storage.list_agents.return_value = []
    mock_storage.get_stats.return_value = {}
    mock_storage.get_pc_status.return_value = {"online": 1, "offline": 0}

    app = create_app(storage=mock_storage, apply_migrations=False)
    client = TestClient(app)

    # 1. /api/v1/risk-events vs /api/risk-events
    r1 = client.get("/api/v1/risk-events")
    r2 = client.get("/api/risk-events")
    assert r1.status_code == 200
    assert r2.status_code == 200

    # 2. /api/v1/dashboard-summary vs /api/dashboard-summary
    d1 = client.get("/api/v1/dashboard-summary")
    d2 = client.get("/api/dashboard-summary")
    assert d1.status_code == 200
    assert d2.status_code == 200

    # 3. /api/threats vs /api/v1/threats
    t1 = client.get("/api/threats")
    t2 = client.get("/api/v1/threats")
    assert t1.status_code == 200
    assert t2.status_code == 200
