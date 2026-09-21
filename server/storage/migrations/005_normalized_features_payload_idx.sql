BEGIN;

CREATE INDEX IF NOT EXISTS idx_normalized_features_payload ON normalized_features(payload_id);

COMMIT;
