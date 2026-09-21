BEGIN;

ALTER TABLE IF EXISTS raw_payloads
  ALTER COLUMN encrypted_envelope_json TYPE jsonb USING encrypted_envelope_json::jsonb;

ALTER TABLE IF EXISTS collector_results
  ALTER COLUMN payload_json TYPE jsonb USING payload_json::jsonb;

ALTER TABLE IF EXISTS normalized_features
  ALTER COLUMN feature_value_json TYPE jsonb USING feature_value_json::jsonb;

ALTER TABLE IF EXISTS model_outputs
  ALTER COLUMN feature_contributions_json TYPE jsonb USING feature_contributions_json::jsonb;

ALTER TABLE IF EXISTS anomalies
  ALTER COLUMN detectors_json TYPE jsonb USING detectors_json::jsonb,
  ALTER COLUMN top_features_json TYPE jsonb USING top_features_json::jsonb;

ALTER TABLE IF EXISTS risk_events
  ALTER COLUMN correlated_signals_json TYPE jsonb USING correlated_signals_json::jsonb;

ALTER TABLE IF EXISTS baseline_snapshots
  ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb;

CREATE INDEX IF NOT EXISTS idx_collector_results_payload_json ON collector_results USING gin (payload_json jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_normalized_features_json ON normalized_features USING gin (feature_value_json jsonb_path_ops);

COMMIT;
