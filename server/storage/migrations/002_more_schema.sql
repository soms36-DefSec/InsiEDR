-- 002_more_schema.sql
-- Add baseline, anomalies, collector results and basic indices

BEGIN;

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    first_seen TEXT,
    last_seen TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS raw_payloads (
    payload_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    created_at TEXT,
    payload_json TEXT,
    UNIQUE(payload_id)
);

CREATE TABLE IF NOT EXISTS collector_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload_id TEXT NOT NULL,
    collector_name TEXT,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS baseline_snapshots (
    agent_id TEXT PRIMARY KEY,
    baseline_json TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT,
    detected_at TEXT,
    anomaly_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_payloads_agent ON raw_payloads(agent_id);
CREATE INDEX IF NOT EXISTS idx_collector_results_payload ON collector_results(payload_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_agent ON anomalies(agent_id);

COMMIT;
