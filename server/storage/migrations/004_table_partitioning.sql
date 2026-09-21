BEGIN;

-- 1. Drop foreign keys referencing raw_payloads
DO $$
DECLARE
    row record;
BEGIN
    FOR row IN
        SELECT tc.table_name, tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'raw_payloads'
    LOOP
        EXECUTE 'ALTER TABLE ' || quote_ident(row.table_name) || ' DROP CONSTRAINT ' || quote_ident(row.constraint_name);
    END LOOP;
END;
$$;

-- 2. Create the new partitioned raw_payloads table
CREATE TABLE IF NOT EXISTS raw_payloads_partitioned (
    payload_id TEXT,
    agent_id TEXT,
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
    duplicate_attempt_count INTEGER DEFAULT 0,
    PRIMARY KEY (payload_id, received_at)
) PARTITION BY RANGE (received_at);

-- 3. Create the new partitioned collector_results table
CREATE TABLE IF NOT EXISTS collector_results_partitioned (
    id SERIAL,
    payload_id TEXT NOT NULL,
    agent_id TEXT,
    collector TEXT,
    collector_collected_at TIMESTAMP WITH TIME ZONE,
    hostname TEXT,
    status TEXT,
    payload_json JSONB,
    error_type TEXT,
    error_message TEXT,
    source_quality TEXT,
    -- PostgreSQL requires the partition key to be part of the primary key
    PRIMARY KEY (id, collector_collected_at)
) PARTITION BY RANGE (collector_collected_at);

-- 4. Create a function to generate weekly partitions
CREATE OR REPLACE FUNCTION create_weekly_partitions(start_date DATE, weeks INTEGER) RETURNS void AS $$
DECLARE
    cur_date DATE := date_trunc('week', start_date);
    end_date DATE;
    table_name TEXT;
BEGIN
    -- Create a catch-all old partition for data before our start date, just in case
    EXECUTE format('CREATE TABLE IF NOT EXISTS raw_payloads_old_data PARTITION OF raw_payloads_partitioned FOR VALUES FROM (MINVALUE) TO (%L);', cur_date);
    EXECUTE format('CREATE TABLE IF NOT EXISTS collector_results_old_data PARTITION OF collector_results_partitioned FOR VALUES FROM (MINVALUE) TO (%L);', cur_date);

    FOR i IN 0..weeks LOOP
        end_date := cur_date + '7 days'::interval;
        
        table_name := 'raw_payloads_w_' || to_char(cur_date, 'YYYY_MM_DD');
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF raw_payloads_partitioned FOR VALUES FROM (%L) TO (%L);', table_name, cur_date, end_date);
        
        table_name := 'collector_results_w_' || to_char(cur_date, 'YYYY_MM_DD');
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF collector_results_partitioned FOR VALUES FROM (%L) TO (%L);', table_name, cur_date, end_date);
        
        cur_date := end_date;
    END LOOP;
    
    -- Create a catch-all future partition to prevent insert failures if script fails to run
    -- Note: When retention script runs, it will need to detach this default partition to add new ones.
    -- Actually, to keep it simple, let's just generate 52 weeks (1 year) into the future during migration.
    -- The retention script will generate them dynamically well before we run out.
END;
$$ LANGUAGE plpgsql;

-- Generate partitions for 8 weeks back and 52 weeks forward
SELECT create_weekly_partitions((CURRENT_DATE - INTERVAL '8 weeks')::DATE, 60);

-- 5. Copy data to new partitioned tables
-- We use COALESCE for collector_collected_at since it's the partition key, falling back to '1970-01-01' if NULL
INSERT INTO raw_payloads_partitioned
SELECT * FROM raw_payloads;

INSERT INTO collector_results_partitioned
SELECT 
    id, payload_id, agent_id, collector, 
    COALESCE(collector_collected_at, '1970-01-01 00:00:00+00') as collector_collected_at, 
    hostname, status, payload_json, error_type, error_message, source_quality 
FROM collector_results;

-- 6. Swap table names
ALTER TABLE raw_payloads RENAME TO raw_payloads_archive;
ALTER TABLE raw_payloads_partitioned RENAME TO raw_payloads;

ALTER TABLE collector_results RENAME TO collector_results_archive;
ALTER TABLE collector_results_partitioned RENAME TO collector_results;

-- 7. Re-apply Indexes
CREATE INDEX IF NOT EXISTS idx_raw_payloads_agent_received_part ON raw_payloads(agent_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_payloads_hostname_part ON raw_payloads(hostname);
CREATE INDEX IF NOT EXISTS idx_raw_payloads_username_part ON raw_payloads(username);

CREATE INDEX IF NOT EXISTS idx_collector_results_payload_part ON collector_results(payload_id);
CREATE INDEX IF NOT EXISTS idx_collector_results_agent_collector_time_part ON collector_results(agent_id, collector, collector_collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_collector_results_status_part ON collector_results(status);
CREATE INDEX IF NOT EXISTS idx_collector_results_payload_json_part ON collector_results USING gin (payload_json jsonb_path_ops);

-- Update sequences for collector_results (since id is SERIAL)
SELECT setval(pg_get_serial_sequence('collector_results', 'id'), COALESCE(MAX(id), 1)) FROM collector_results_archive;

COMMIT;
