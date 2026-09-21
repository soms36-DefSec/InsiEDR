"""
server/storage/repositories/telemetry_repo.py
---------------------------------------------
Telemetry & Logs Repository.
Coordinates high-throughput telemetry ingestion and analytical queries,
routing to ClickHouse when available, with resilient fallback to PostgreSQL.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("insiedr.storage.telemetry_repo")


class TelemetryRepository:
    """Encapsulates raw payload logs, collector execution data, and normalized features."""

    def __init__(self, postgres_storage: Any, clickhouse_storage: Optional[Any] = None) -> None:
        self.pg = postgres_storage
        self.ch = clickhouse_storage

    def _has_ch(self) -> bool:
        return self.ch is not None and getattr(self.ch, "is_connected", lambda: False)()

    def store_payload(self, envelope: Dict[str, Any], decrypted_payload: Dict[str, Any]) -> None:
        """Store telemetry into ClickHouse (OLAP) and fallback to Postgres if necessary."""
        if self._has_ch():
            self.ch.store_raw_payload(envelope, decrypted_payload)
        else:
            # Standalone fallback to PostgreSQL
            self.pg.store_raw_payload(envelope, decrypted_payload)

    def list_logs(self, limit: int = 100, offset: int = 0, **filters) -> List[Dict[str, Any]]:
        """Query raw payload logs."""
        if self._has_ch():
            return self.ch.list_logs(limit=limit, offset=offset, **filters)
        return self.pg.list_logs(limit=limit, offset=offset, **filters)

    def list_collector_results(self, limit: int = 100, offset: int = 0, **filters) -> List[Dict[str, Any]]:
        """Query collector observation history."""
        if self._has_ch():
            return self.ch.list_collector_results(limit=limit, offset=offset, **filters)
        return self.pg.list_collector_results(limit=limit, offset=offset, **filters)

    def get_feature_vector(self, payload_id: str) -> Dict[str, Any]:
        """Retrieve all normalized features for a given payload."""
        if self._has_ch():
            feats = self.ch.get_feature_vector(payload_id)
            if feats:
                return feats
        return self.pg.get_feature_vector(payload_id)

    def list_daily_feature_vectors(self, username: str | None, hostname: str | None, limit: int = 16) -> List[Dict[str, Any]]:
        """Retrieve day-bucketed feature vectors for time-series anomaly models."""
        return self.pg.list_daily_feature_vectors(username=username, hostname=hostname, limit=limit)
