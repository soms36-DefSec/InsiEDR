BEGIN;

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    hostname TEXT,
    username_last_seen TEXT,
    os_system TEXT,
    os_release TEXT,
    os_version TEXT,
    os_machine TEXT,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_payload_id TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS training_labels (
    agent_id TEXT PRIMARY KEY REFERENCES agents(agent_id),
    is_malicious BOOLEAN NOT NULL DEFAULT FALSE,
    labeled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    labeled_by TEXT
);

CREATE TABLE IF NOT EXISTS raw_payloads (
    payload_id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(agent_id),
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    envelope_created_at TIMESTAMP WITH TIME ZONE,
    payload_collected_at TIMESTAMP WITH TIME ZONE,
    hostname TEXT,
    username TEXT,
    crypto_scheme TEXT,
    key_id TEXT,
    nonce_hash TEXT,
    ciphertext_hash TEXT,
    decrypted_payload_hash TEXT,
    encrypted_envelope_json JSONB,
    validation_status TEXT,
    duplicate_attempt_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS collector_results (
    id SERIAL PRIMARY KEY,
    payload_id TEXT NOT NULL REFERENCES raw_payloads(payload_id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(agent_id),
    collector TEXT,
    collector_collected_at TIMESTAMP WITH TIME ZONE,
    hostname TEXT,
    status TEXT,
    payload_json JSONB,
    error_type TEXT,
    error_message TEXT,
    source_quality TEXT
);

CREATE TABLE IF NOT EXISTS normalized_features (
    id SERIAL PRIMARY KEY,
    payload_id TEXT NOT NULL REFERENCES raw_payloads(payload_id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(agent_id),
    username TEXT,
    hostname TEXT,
    collector TEXT,
    entity_user TEXT,
    feature_name TEXT,
    feature_value_numeric DOUBLE PRECISION,
    feature_value_text TEXT,
    feature_value_json JSONB,
    feature_timestamp TIMESTAMP WITH TIME ZONE,
    source_quality TEXT,
    quality_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_outputs (
    id SERIAL PRIMARY KEY,
    payload_id TEXT REFERENCES raw_payloads(payload_id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(agent_id),
    username TEXT,
    detector_name TEXT,
    model_version TEXT,
    score DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    is_anomaly BOOLEAN,
    feature_contributions_json JSONB,
    reason_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS anomalies (
    id SERIAL PRIMARY KEY,
    payload_id TEXT REFERENCES raw_payloads(payload_id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(agent_id),
    username TEXT,
    anomaly_type TEXT,
    severity TEXT,
    detectors_json JSONB,
    top_features_json JSONB,
    status TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by TEXT
);

CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    payload_id TEXT REFERENCES raw_payloads(payload_id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(agent_id),
    username TEXT,
    risk_score DOUBLE PRECISION,
    risk_level TEXT,
    correlated_signals_json JSONB,
    summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS baseline_snapshots (
    id SERIAL PRIMARY KEY,
    agent_id TEXT REFERENCES agents(agent_id),
    username TEXT,
    feature_name TEXT,
    baseline_scope TEXT,
    window_start TIMESTAMP WITH TIME ZONE,
    window_end TIMESTAMP WITH TIME ZONE,
    mean_value DOUBLE PRECISION,
    std_value DOUBLE PRECISION,
    sample_count INTEGER,
    logic_version TEXT,
    metadata_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_payloads_agent_received ON raw_payloads(agent_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_payloads_hostname ON raw_payloads(hostname);
CREATE INDEX IF NOT EXISTS idx_raw_payloads_username ON raw_payloads(username);
CREATE INDEX IF NOT EXISTS idx_collector_results_payload ON collector_results(payload_id);
CREATE INDEX IF NOT EXISTS idx_collector_results_agent_collector_time ON collector_results(agent_id, collector, collector_collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_collector_results_status ON collector_results(status);
CREATE INDEX IF NOT EXISTS idx_normalized_features_lookup ON normalized_features(agent_id, username, feature_name, feature_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_normalized_features_quality ON normalized_features(source_quality);
CREATE INDEX IF NOT EXISTS idx_model_outputs_payload ON model_outputs(payload_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_agent_created ON anomalies(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_agent_user_created ON risk_events(agent_id, username, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_baseline_snapshots_lookup ON baseline_snapshots(agent_id, username, feature_name, window_end DESC);

COMMIT;
