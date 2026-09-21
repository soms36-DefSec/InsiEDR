-- Migration 007: Durable PostgreSQL-backed task queue
-- Replaces in-memory ThreadPoolExecutor for zero data-loss on server restart.
CREATE TABLE IF NOT EXISTS task_queue (
    id            BIGSERIAL PRIMARY KEY,
    task_type     TEXT        NOT NULL,
    payload_json  JSONB       NOT NULL DEFAULT '{}',
    status        TEXT        NOT NULL DEFAULT 'pending',
    attempts      SMALLINT    NOT NULL DEFAULT 0,
    max_attempts  SMALLINT    NOT NULL DEFAULT 3,
    scheduled_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at     TIMESTAMPTZ,
    locked_by     TEXT,
    completed_at  TIMESTAMPTZ,
    error_message TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient polling: grab pending tasks that are not locked
CREATE INDEX IF NOT EXISTS idx_task_queue_poll
    ON task_queue (status, scheduled_at)
    WHERE status IN ('pending', 'retry');

-- Auto-purge: clean up completed tasks older than 7 days on next vacuum
