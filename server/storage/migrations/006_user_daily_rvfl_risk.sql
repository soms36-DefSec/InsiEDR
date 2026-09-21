-- Migration 006: user_daily_rvfl_risk
-- Stores the per-user, per-day fused RVFL risk value produced by the G-model.
-- This table is the "memory" that lets RedRVFL build its 7-day behavioral sequences
-- in real-time from live telemetry, without needing the original CSV dataset.
--
-- Written by: AdvancedPipelineDetector integration (InsiEDR-G-model-latest-dataset)
-- Direction:  UP (forward migration, auto-applied on server start)

CREATE TABLE IF NOT EXISTS user_daily_rvfl_risk (
    id          SERIAL PRIMARY KEY,
    username    TEXT        NOT NULL,
    date        DATE        NOT NULL DEFAULT CURRENT_DATE,
    rvfl_risk   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One row per (user, date). UPSERT on conflict updates the value intraday.
    CONSTRAINT uq_user_daily_rvfl UNIQUE (username, date)
);

CREATE INDEX IF NOT EXISTS idx_rvfl_risk_user_date
    ON user_daily_rvfl_risk (username, date DESC);

COMMENT ON TABLE user_daily_rvfl_risk IS
    'Per-user daily fused RVFL risk values used by the G-model RedRVFL 7-day sequence window.';
