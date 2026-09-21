"""
server/storage/repositories/fleet_repo.py
-----------------------------------------
Fleet Management & Agent Health Repository.
Operates primarily against PostgreSQL 16 for ACID state consistency.
"""
from __future__ import annotations

import logging
from contextlib import closing
from typing import Any, Dict, List

logger = logging.getLogger("insiedr.storage.fleet_repo")


class FleetRepository:
    """Encapsulates fleet discovery, agent lifecycle, and PC online/offline status."""

    def __init__(self, postgres_storage: Any) -> None:
        self.pg = postgres_storage

    def upsert_agent(self, decrypted_payload: Dict[str, Any]) -> None:
        """Register or update an agent's heartbeat and host hardware profile."""
        agent_id = decrypted_payload.get("agent_id")
        if not agent_id:
            return

        hostname = decrypted_payload.get("hostname")
        username = decrypted_payload.get("username")
        os_info = decrypted_payload.get("os") or {}

        with self.pg.connection() as conn:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    """
                    INSERT INTO agents (
                        agent_id, hostname, username_last_seen, os_system, os_release, 
                        os_version, os_machine, first_seen_at, last_seen_at, last_payload_id, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s)
                    ON CONFLICT (agent_id) DO UPDATE SET
                        hostname = COALESCE(EXCLUDED.hostname, agents.hostname),
                        username_last_seen = COALESCE(EXCLUDED.username_last_seen, agents.username_last_seen),
                        os_system = COALESCE(EXCLUDED.os_system, agents.os_system),
                        os_release = COALESCE(EXCLUDED.os_release, agents.os_release),
                        os_version = COALESCE(EXCLUDED.os_version, agents.os_version),
                        os_machine = COALESCE(EXCLUDED.os_machine, agents.os_machine),
                        last_seen_at = EXCLUDED.last_seen_at,
                        last_payload_id = EXCLUDED.last_payload_id,
                        status = EXCLUDED.status
                    """,
                    (
                        agent_id,
                        hostname,
                        username,
                        os_info.get("system"),
                        os_info.get("release"),
                        os_info.get("version"),
                        os_info.get("machine"),
                        decrypted_payload.get("payload_id"),
                        "active",
                    ),
                )
                conn.commit()

    def list_agents(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List registered fleet endpoints with dynamic active/offline status."""
        with self.pg.connection() as conn:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    """
                    SELECT agent_id, hostname, username_last_seen, os_system, os_release, os_version, os_machine,
                           first_seen_at, last_seen_at, last_payload_id,
                           CASE WHEN last_seen_at > CURRENT_TIMESTAMP - INTERVAL '5 minutes' THEN 'active' ELSE 'offline' END as status
                    FROM agents
                    ORDER BY last_seen_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                cols = [col[0] for col in cur.description or []]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_pc_status(self, seconds_since_online: int = 300) -> Dict[str, Any]:
        """Compute unique total, online, and offline PC counts."""
        with self.pg.connection() as conn:
            with closing(conn.cursor()) as cur:
                try:
                    cur.execute("SELECT COUNT(DISTINCT hostname) FROM agents WHERE hostname IS NOT NULL")
                    total_pcs = cur.fetchone()[0] or 0

                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT hostname) FROM agents 
                        WHERE hostname IS NOT NULL 
                        AND last_seen_at > CURRENT_TIMESTAMP - INTERVAL '1 second' * %s
                        """,
                        (seconds_since_online,)
                    )
                    online_pcs = cur.fetchone()[0] or 0
                    offline_pcs = max(0, total_pcs - online_pcs)

                    return {
                        "total_pcs": total_pcs,
                        "online_pcs": online_pcs,
                        "offline_pcs": offline_pcs,
                    }
                except Exception as exc:
                    logger.warning("Error fetching pc status: %s", exc)
                    return {"total_pcs": 0, "online_pcs": 0, "offline_pcs": 0}
