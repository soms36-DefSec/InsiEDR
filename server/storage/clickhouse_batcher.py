"""
server/storage/clickhouse_batcher.py
------------------------------------
Asynchronous Micro-Batching Buffer with Dead-Letter Queue (DLQ) for ClickHouse.

Architecture & Design:
======================
ClickHouse is an OLAP columnar database designed to ingest thousands of rows in
large block writes. Single-row inserts on every HTTP ingest call causes part
fragmentation and severe CPU overhead ("too many parts" error).

This module implements `ClickHouseBatcher`:
  - Enqueues incoming records into dedicated per-table thread-safe buffers.
  - Flushes batches to ClickHouse when:
      1. Batch size threshold is reached (default: 500 rows per table), OR
      2. Time interval expires (default: 1.0 second), OR
      3. Server shutdown is initiated (guaranteed zero data loss).
  - Exponential backoff retry logic on network or server compaction hiccups.
  - Zero Data-Loss Dead-Letter Queue (DLQ): If ClickHouse is permanently
    unreachable after all retries, the failed batch is spooled to an on-disk
    JSONL file in `data/dlq/` with restrictive permissions.
  - DLQ Replay: Provides `replay_dlq()` to re-insert spooled records once
    ClickHouse is healthy again.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("insiedr.clickhouse.batcher")


class ClickHouseBatcher:
    """
    Thread-safe asynchronous micro-batch buffer with on-disk Dead-Letter Queue (DLQ)
    for guaranteed telemetry durability.
    """

    def __init__(
        self,
        insert_fn: Callable[[str, List[Dict[str, Any]]], None],
        batch_size: int = 500,
        flush_interval: float = 1.0,
        max_retries: int = 3,
        dlq_dir: str | Path = "data/dlq",
        dlq_enabled: bool = True,
    ) -> None:
        self._insert_fn = insert_fn
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.dlq_dir = Path(dlq_dir)
        self.dlq_enabled = dlq_enabled

        # Per-table record queues
        self._buffers: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._last_flush_time = time.time()

        # Telemetry metrics
        self.total_queued = 0
        self.total_flushed = 0
        self.total_errors = 0
        self.total_spooled_to_dlq = 0

    def start(self) -> None:
        """Start the background micro-batch worker thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._flush_loop,
                name="ClickHouse_BatchWorker",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info("ClickHouse micro-batch worker started (batch_size=%d, interval=%.1fs, dlq=%s)",
                        self.batch_size, self.flush_interval, "enabled" if self.dlq_enabled else "disabled")

    def stop(self, timeout: float = 10.0) -> None:
        """Stop worker and synchronously flush all remaining buffered data."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._cond.notify_all()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

        # Final synchronous flush
        self.flush_all()
        logger.info("ClickHouse micro-batch worker stopped cleanly.")

    def add(self, table: str, row: Dict[str, Any]) -> None:
        """Add a single record to the table buffer."""
        self.add_many(table, [row])

    def add_many(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """Add multiple records to the table buffer."""
        if not rows:
            return

        with self._lock:
            if table not in self._buffers:
                self._buffers[table] = []
            self._buffers[table].extend(rows)
            self.total_queued += len(rows)

            # If any table reaches batch size, wake up flush worker immediately
            if len(self._buffers[table]) >= self.batch_size:
                self._cond.notify_all()

    def flush_all(self) -> None:
        """Synchronously flush all pending buffers across all tables."""
        with self._lock:
            snapshot = {table: list(rows) for table, rows in self._buffers.items() if rows}
            for table in snapshot:
                self._buffers[table].clear()
            self._last_flush_time = time.time()

        for table, rows in snapshot.items():
            self._flush_table_with_retry(table, rows)

    def _flush_loop(self) -> None:
        """Continuous background loop triggering flushes on interval or threshold."""
        while True:
            with self._cond:
                # Wait until flush_interval expires or explicit notify
                self._cond.wait(timeout=self.flush_interval)
                if not self._running:
                    break

                now = time.time()
                should_flush = (now - self._last_flush_time >= self.flush_interval) or any(
                    len(rows) >= self.batch_size for rows in self._buffers.values()
                )

                if not should_flush:
                    continue

                snapshot = {table: list(rows) for table, rows in self._buffers.items() if rows}
                for table in snapshot:
                    self._buffers[table].clear()
                self._last_flush_time = now

            for table, rows in snapshot.items():
                self._flush_table_with_retry(table, rows)

    def _flush_table_with_retry(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """Attempt to insert rows into ClickHouse with exponential backoff and DLQ spooling."""
        if not rows:
            return

        for attempt in range(1, self.max_retries + 1):
            try:
                self._insert_fn(table, rows)
                self.total_flushed += len(rows)
                logger.debug("Successfully flushed %d rows to ClickHouse table '%s'", len(rows), table)
                return
            except Exception as exc:
                logger.warning(
                    "ClickHouse batch flush attempt %d/%d failed for table '%s' (%d rows): %s",
                    attempt, self.max_retries, table, len(rows), exc
                )
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                else:
                    self.total_errors += len(rows)
                    # Spool to Dead-Letter Queue (DLQ) to guarantee zero data loss
                    if self.dlq_enabled:
                        self._spool_to_dlq(table, rows, exc)
                    else:
                        logger.error("DLQ disabled. ClickHouse batch failed permanently for table '%s' (%d rows dropped)",
                                     table, len(rows), exc_info=True)

    def _spool_to_dlq(self, table: str, rows: List[Dict[str, Any]], error: Exception) -> None:
        """Write failed telemetry rows to an on-disk Dead-Letter Queue file."""
        try:
            self.dlq_dir.mkdir(parents=True, exist_ok=True)
            timestamp_str = int(time.time())
            dlq_file = self.dlq_dir / f"dlq_{table}_{timestamp_str}_{os.getpid()}.jsonl"

            with open(dlq_file, "a", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, default=str) + "\n")

            # Restrict file permissions to owner only (chmod 600) on POSIX
            try:
                os.chmod(dlq_file, 0o600)
            except Exception:
                pass

            self.total_spooled_to_dlq += len(rows)
            logger.error("Spooling %d rows to DLQ '%s' due to ClickHouse error: %s", len(rows), dlq_file, error)
        except Exception as dlq_err:
            logger.critical("Failed writing to DLQ disk storage! Error: %s", dlq_err, exc_info=True)

    def replay_dlq(self, table: Optional[str] = None) -> int:
        """
        Replay spooled DLQ files back into ClickHouse.
        Returns total number of recovered rows.
        """
        if not self.dlq_dir.is_dir():
            return 0

        replayed_total = 0
        pattern = f"dlq_{table}_*.jsonl" if table else "dlq_*.jsonl"
        dlq_files = list(self.dlq_dir.glob(pattern))

        for file_path in dlq_files:
            try:
                parts = file_path.stem.split("_")
                target_table = parts[1] if len(parts) >= 2 else table
                if not target_table:
                    continue

                rows = []
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            rows.append(json.loads(line))

                if rows:
                    self._insert_fn(target_table, rows)
                    replayed_total += len(rows)
                    logger.info("Successfully replayed %d rows from DLQ file '%s'", len(rows), file_path.name)

                # Remove DLQ file upon successful replay
                file_path.unlink()
            except Exception as exc:
                logger.error("Failed replaying DLQ file '%s': %s", file_path, exc)

        return replayed_total
