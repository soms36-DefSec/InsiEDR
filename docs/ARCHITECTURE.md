# InsiEDR Server: System Architecture & Data Flow

This document provides a technical deep-dive into the internal architecture, ingestion pipeline, detection engine handoffs, and storage strategies of the **InsiEDR Central Server**.

---

## 1. High-Level Architectural Diagram

```
                             [ Windows Endpoints ]
                   (InsiEDR-Agent: 30+ Telemetry Collectors)
                                       │
                      POST /api/logs   │ AES-256-GCM / HPKE Encrypted
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         InsiEDR FastAPI ASGI Server                         │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        1. Ingestion Layer                             │  │
│  │  • Payload Authentication & Replay Protection                         │  │
│  │  • Cryptographic Plugin Engine (AES-256-GCM / HPKE / Fernet)          │  │
│  │  • Schema Normalization & Validation (Pydantic v2)                    │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                      │
│                                      ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                   2. Multi-Stage Detection Pipeline                   │  │
│  │                                                                       │  │
│  │   ┌─────────────────────────────┐     ┌────────────────────────────┐  │  │
│  │   │  Deterministic Heuristics   │     │  Unsupervised Isolation    │  │  │
│  │   │  • CERT Behavioral Rules    │     │  Forest (Domain Anomaly)   │  │  │
│  │   │  • Honeytoken/Decoy Alert   │     │  • Overall & Sub-Domain    │  │  │
│  │   └──────────────┬──────────────┘     └─────────────┬──────────────┘  │  │
│  │                  │                                  │                 │  │
│  │                  ▼                                  ▼                 │  │
│  │   ┌─────────────────────────────┐     ┌────────────────────────────┐  │  │
│  │   │  Supervised XGBoost         │     │  Temporal Sequence         │  │  │
│  │   │  Classifier                 │     │  Modeler (RedRVFL / LSTM)  │  │  │
│  │   │  • Scenario Attribution     │     │  • Historical Trajectory   │  │  │
│  │   └──────────────┬──────────────┘     └─────────────┬──────────────┘  │  │
│  │                  └────────────────┬─────────────────┘                 │  │
│  │                                   ▼                                   │  │
│  │                     Risk Aggregator & Corroborator                    │  │
│  │                     • Composite Score: 0 - 100                        │  │
│  │                     • Threat Severity (LOW -> CRITICAL)               │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                      │
│                   ┌──────────────────┴──────────────────┐                   │
│                   ▼                                     ▼                   │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐  │
│  │      3. Dual-Storage Engine     │   │     4. Event Broadcaster        │  │
│  │  • PostgreSQL: Entities, alerts,│   │  • Server-Sent Events (SSE)     │  │
│  │    baselines, task queues       │   │  • /api/stream/threats          │  │
│  │  • ClickHouse: High-volume raw  │   │  • /api/stream/agents           │  │
│  │    telemetry & columnar events  │   │  • Real-time SOC updates        │  │
│  └─────────────────────────────────┘   └────────────────┬────────────────┘  │
└─────────────────────────────────────────────────────────┼───────────────────┘
                                                          │
                                                          ▼
                                ┌───────────────────────────────────┐
                                │   Analyst Dashboard (React 19)    │
                                │   Fleet KPIs, Matrix, Forensics   │
                                └───────────────────────────────────┘
```

---

## 2. Telemetry Ingestion & Cryptographic Decryption

When telemetry arrives at `POST /api/logs`:
1. **Header Verification**: Validates the `X-InsiEDR-Agent-Id`, `X-InsiEDR-Payload-Id`, and signature headers.
2. **Replay Protection**: The payload ID is tracked against recent memory caches and PostgreSQL `telemetry_payloads` to prevent replay attacks.
3. **Pluggable Decryption Engine (`server/crypto/`)**:
   - `AESGCMCryptoPlugin`: Default symmetric cipher using 256-bit keys and 12-byte initialization vectors (IVs).
   - `HPKECryptoPlugin`: RFC 9180 Hybrid Public Key Encryption for asymmetric forward-secrecy deployments.
   - `FernetCryptoPlugin`: Backward compatibility mode.
4. **Queue Spooling & Task Queue**: Payloads can be evaluated synchronously or offloaded to an asynchronous durable worker thread pool (8x ML background workers) via `server/task_queue.py`.

---

## 3. The 4-Tier Detection Pipeline (`ModelBridge`)

Decrypted telemetry is extracted into a normalized feature vector across four domains:
* **Logon Activity**: Logon frequency, after-hours ratio, distinct machine counts.
* **File Activity**: Total reads, modifications, daily unique filenames, Honeytoken trips.
* **Device Activity**: USB insertions, unapproved hardware connects.
* **HTTP / Network**: Upload volumes, external domains, file-sharing domain visits.

### Layer 1: Deterministic Heuristics (`heuristics/`)
* Evaluates non-negotiable behavioral boundaries based on the CERT Insider Threat dataset.
* Immediately generates a deterministic severity level (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
* Example: Any interaction with a known decoy file immediately trips a `CRITICAL` severity rating with 100% confidence.

### Layer 2: Domain Isolation Forest (`model/`)
* Unsupervised outlier scoring (`domain_isolation_forest.pkl`).
* Evaluates domain-specific distributions (File, Logon, Device, HTTP) against learned baseline parameters.
* Identifies "unknown unknowns" that violate statistical normality without tripping a hardcoded rule.

### Layer 3: Supervised XGBoost Classifier (`model/`)
* Multiclass gradient-boosted decision tree (`scenario_xgb.pkl`).
* Classifies feature combinations into specific insider threat scenario classes (e.g., Scenario 1: IT sabotage, Scenario 2: Intellectual property theft, Scenario 3: Bulk data exfiltration).

### Layer 4: RedRVFL Temporal Sequence Modeler (`model/`)
* Random Vector Functional Link (RedRVFL) network with RandomLSTM recurrent units (`rvfl_model.pkl`).
* Evaluates rolling sequences of historical user days.
* Computes temporal behavioral velocity: identifies whether activity is accelerating toward exfiltration or decaying back to normal.

---

## 4. Storage Architecture: Hybrid PostgreSQL + ClickHouse

The server uses a specialized dual-storage architecture to balance transactional integrity with big-data analytics throughput:

### 1. PostgreSQL (Transactional Nervous System)
* Stores structured entities, registered agents, security incidents, baselines, and background job states.
* Includes 8 automated schema migrations (`server/storage/migrations/`):
  * `001_initial_schema.sql` — Core telemetry, agents, alerts.
  * `004_table_partitioning.sql` — Daily and monthly partition tables for scalable log management.
  * `005_normalized_features_payload_idx.sql` — Feature indexes.
  * `006_user_daily_rvfl_risk.sql` — Historical temporal score caching.
  * `007_task_queue.sql` — Durable job worker queue.
  * `008_performance_indexes.sql` — B-Tree and BRIN indexes for high-speed queries.

### 2. ClickHouse (Columnar Telemetry Warehouse)
* When enabled via `CLICKHOUSE_ENABLED=true`, raw high-volume event telemetry is streamed into ClickHouse.
* Allows sub-second aggregation and forensic searches across tens of millions of raw log entries.

---

## 5. Real-Time Streaming & Dashboard Interface

* **Server-Sent Events (SSE)**: The frontend connects to `/api/v1/stream/sse` and `/api/stream/threats` for low-latency reactive updates without polling.
* **React 19 Single-Page Application**: The production build (`frontend/dist/`) is served directly by the FastAPI backend at `/dashboard/`.
* **API Documentation**: Interactive OpenAPI 3.0 documentation is auto-generated and served at `/docs` (Swagger UI) and `/redoc` (ReDoc).
