import os
import sys
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server.config import config
from server.storage.postgres_storage import PostgresStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def get_weekly_partitions(cursor, parent_table):
    cursor.execute("""
        SELECT c.relname
        FROM pg_class c
        JOIN pg_inherits i ON c.oid = i.inhrelid
        JOIN pg_class p ON i.inhparent = p.oid
        WHERE p.relname = %s
    """, (parent_table,))
    return [row[0] for row in cursor.fetchall()]

def drop_old_partitions(cursor, parent_table, cutoff_date):
    partitions = get_weekly_partitions(cursor, parent_table)
    dropped = 0
    for part in partitions:
        # Expected format: tablename_w_YYYY_MM_DD
        if "_w_" in part:
            date_str = part.split("_w_")[-1]
            try:
                part_date = datetime.strptime(date_str, "%Y_%m_%d").replace(tzinfo=timezone.utc)
                # If the partition's start date is more than 7 days BEFORE the cutoff, it is entirely safe to drop
                # e.g., if cutoff is 30 days ago, a partition starting 40 days ago is safe. 
                # (A partition starting 29 days ago might still contain data we want)
                if part_date + timedelta(days=7) < cutoff_date:
                    log.info(f"Dropping old partition: {part}")
                    cursor.execute(f"DROP TABLE IF EXISTS {part}")
                    dropped += 1
            except ValueError:
                pass
    return dropped

def create_future_partitions(cursor, parent_table, weeks_ahead=4):
    now = datetime.now(timezone.utc)
    for i in range(weeks_ahead):
        target_date = now + timedelta(weeks=i)
        # Week starts on Monday
        start_date = target_date - timedelta(days=target_date.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
        
        part_name = f"{parent_table}_w_{start_date.strftime('%Y_%m_%d')}"
        
        cursor.execute("SELECT 1 FROM pg_class WHERE relname = %s", (part_name,))
        if not cursor.fetchone():
            log.info(f"Pre-creating future partition: {part_name}")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {part_name} PARTITION OF {parent_table} FOR VALUES FROM ('{start_date.strftime('%Y-%m-%d')}') TO ('{end_date.strftime('%Y-%m-%d')}')")

def run_retention_cleanup():
    log.info("Starting Partition-Aware Data Retention Cleanup...")
    storage = PostgresStorage(config.database_dsn)
    
    payload_days = config.payload_retention_days
    feature_days = config.feature_retention_days
    
    now = datetime.now(timezone.utc)
    payload_cutoff = now - timedelta(days=payload_days)
    feature_cutoff = now - timedelta(days=feature_days)
    
    log.info(f"Payload Retention: {payload_days} days (Cutoff: {payload_cutoff.isoformat()})")
    log.info(f"Feature Retention: {feature_days} days (Cutoff: {feature_cutoff.isoformat()})")
    
    with storage.connection() as conn:
        with conn.cursor() as cursor:
            # 1. Prune via Partition Dropping (O(1) time, no table locks)
            dropped_payload_parts = drop_old_partitions(cursor, "raw_payloads", payload_cutoff)
            dropped_collector_parts = drop_old_partitions(cursor, "collector_results", payload_cutoff)
            
            # 2. Pre-create future partitions for seamless ingestion
            create_future_partitions(cursor, "raw_payloads", weeks_ahead=4)
            create_future_partitions(cursor, "collector_results", weeks_ahead=4)
            
            # 3. Prune Unpartitioned Child Tables manually since FK CASCADE was removed
            cursor.execute("DELETE FROM model_outputs WHERE created_at < %s", (payload_cutoff,))
            cursor.execute("DELETE FROM anomalies WHERE created_at < %s", (payload_cutoff,))
            cursor.execute("DELETE FROM risk_events WHERE created_at < %s", (payload_cutoff,))
            
            cursor.execute("DELETE FROM normalized_features WHERE created_at < %s RETURNING id", (feature_cutoff,))
            deleted_features = cursor.rowcount
            
            conn.commit()
            
    log.info(f"Cleanup Complete. Dropped {dropped_payload_parts} payload partitions and {dropped_collector_parts} collector partitions.")
    log.info(f"Purged {deleted_features} normalized features.")

if __name__ == "__main__":
    run_retention_cleanup()
