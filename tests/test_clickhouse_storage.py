"""
tests/test_clickhouse_storage.py
--------------------------------
Unit tests for ClickHouseBatcher, Dead-Letter Queue (DLQ), and ClickHouseStorage adapter.
"""
import time
from pathlib import Path
from unittest.mock import MagicMock

from server.storage.clickhouse_batcher import ClickHouseBatcher
from server.storage.clickhouse_storage import ClickHouseStorage, _format_dt, _json_str


def test_clickhouse_batcher_size_trigger():
    flushed_tables = []
    flushed_records = []

    def mock_insert(table, rows):
        flushed_tables.append(table)
        flushed_records.extend(rows)

    batcher = ClickHouseBatcher(insert_fn=mock_insert, batch_size=3, flush_interval=10.0, dlq_enabled=False)
    batcher.start()

    # Adding 2 rows should not flush yet
    batcher.add("test_table", {"val": 1})
    batcher.add("test_table", {"val": 2})
    time.sleep(0.1)
    assert len(flushed_records) == 0

    # Adding 3rd row triggers threshold flush
    batcher.add("test_table", {"val": 3})
    time.sleep(0.2)
    assert len(flushed_records) == 3
    assert flushed_tables == ["test_table"]

    batcher.stop()


def test_clickhouse_batcher_interval_flush():
    flushed_records = []

    def mock_insert(table, rows):
        flushed_records.extend(rows)

    batcher = ClickHouseBatcher(insert_fn=mock_insert, batch_size=100, flush_interval=0.2, dlq_enabled=False)
    batcher.start()

    batcher.add("test_table", {"foo": "bar"})
    assert len(flushed_records) == 0

    # Wait for interval to fire
    time.sleep(0.35)
    assert len(flushed_records) == 1
    batcher.stop()


def test_clickhouse_batcher_dlq_spooling_and_replay(tmp_path: Path):
    """Test that permanent insert failures are spooled to DLQ and can be replayed."""
    fail_count = 0
    recovered_rows = []

    def failing_insert(table, rows):
        nonlocal fail_count
        fail_count += 1
        raise RuntimeError("ClickHouse connection refused (simulated)")

    def recovery_insert(table, rows):
        recovered_rows.extend(rows)

    # 1. Batcher with failing insert function
    dlq_dir = tmp_path / "dlq"
    batcher = ClickHouseBatcher(
        insert_fn=failing_insert,
        batch_size=2,
        flush_interval=0.1,
        max_retries=2,
        dlq_dir=dlq_dir,
        dlq_enabled=True,
    )
    batcher.start()

    batcher.add("raw_payloads", {"payload_id": "p-failed-1"})
    batcher.add("raw_payloads", {"payload_id": "p-failed-2"})

    # Wait for retries and spooling
    time.sleep(1.0)
    batcher.stop()

    assert batcher.total_spooled_to_dlq == 2
    dlq_files = list(dlq_dir.glob("*.jsonl"))
    assert len(dlq_files) == 1

    # 2. Recovery: replay DLQ files using healthy insert function
    batcher._insert_fn = recovery_insert
    replayed = batcher.replay_dlq(table="raw_payloads")
    assert replayed == 2
    assert len(recovered_rows) == 2
    assert recovered_rows[0]["payload_id"] == "p-failed-1"

    # DLQ file should be cleaned up after replay
    assert len(list(dlq_dir.glob("*.jsonl"))) == 0


def test_clickhouse_storage_helpers():
    now_str = "2026-09-08T10:00:00Z"
    dt = _format_dt(now_str)
    assert dt is not None
    assert dt.year == 2026

    # JSON helper
    assert _json_str({"key": 42}) == '{"key":42}'
    assert _json_str(None) == "{}"


def test_clickhouse_storage_with_mock_client():
    mock_client = MagicMock()
    mock_client.command.return_value = None
    mock_client.query.return_value.column_names = ["payload_id", "received_at"]
    mock_client.query.return_value.result_rows = [["p-1", "2026-09-08T10:00:00Z"]]

    ch = ClickHouseStorage(client=mock_client, query_timeout=25, max_memory_usage=1500000000)
    assert ch.is_connected() is True

    # Test list_logs passes query quotas
    logs = ch.list_logs(limit=10, offset=0, hostname="DESKTOP-SEC01")
    assert len(logs) == 1
    assert logs[0]["payload_id"] == "p-1"

    # Verify query guards (timeout and memory limits) were supplied to client.query
    _, kwargs = mock_client.query.call_args
    assert kwargs.get("settings", {}).get("max_execution_time") == 25
    assert kwargs.get("settings", {}).get("max_memory_usage") == 1500000000

    # Test store_raw_payload queues into batcher
    ch.store_raw_payload(
        envelope={"scheme": "aes_gcm", "key_id": "k1"},
        decrypted_payload={
            "payload_id": "p-123",
            "agent_id": "a-123",
            "hostname": "HOST-1",
            "collectors": [
                {"collector": "file", "status": "success", "payload": {"file_count": 5}}
            ],
        },
    )
    # Stop flushes batcher to client
    ch.close()
    assert mock_client.insert.called
