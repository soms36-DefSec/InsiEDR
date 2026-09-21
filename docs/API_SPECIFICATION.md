# InsiEDR Server: API Specification

The InsiEDR Central Server provides a RESTful and Server-Sent Events (SSE) interface for agent ingestion, forensic queries, threat feeds, and analyst dashboard interactions.

---

## 1. Authentication & Security Headers

* **Agent Ingestion Authentication**:
  * `X-InsiEDR-Agent-Id`: Unique agent hostname or hardware UUID.
  * `X-InsiEDR-Payload-Id`: Unique UUIDv4 assigned to the telemetry payload.
  * `X-InsiEDR-Crypto-Scheme`: Cryptographic cipher used (`aes-gcm`, `hpke`, `fernet`, `plaintext`).
  * `Authorization`: Optional Bearer token or pre-shared agent authorization token.
* **Error Format**: Conforms to the RFC 7807 Problem Details JSON format:
  ```json
  {
    "type": "https://insiedr.local/errors/invalid-payload",
    "title": "Invalid Payload",
    "status": 400,
    "detail": "Failed to decrypt payload using configured AES key.",
    "instance": "/api/logs"
  }
  ```

---

## 2. Ingestion Endpoints

### `POST /api/logs`
Primary telemetry ingestion endpoint for remote agents.

* **Request Format**: Encrypted JSON envelope:
  ```json
  {
    "payload_id": "a548e6c7-31ef-42d8-9189-72c0ecdbb912",
    "ciphertext": "base64_encoded_ciphertext...",
    "nonce": "base64_encoded_12_byte_nonce...",
    "tag": "base64_encoded_16_byte_auth_tag...",
    "timestamp": "2026-09-21T13:00:00Z"
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "status": "success",
    "payload_id": "a548e6c7-31ef-42d8-9189-72c0ecdbb912",
    "queued": false,
    "composite_risk_score": 78.5,
    "severity": "HIGH",
    "scenarios_detected": ["Multi-PC Lateral Movement", "Abnormal USB Staging"]
  }
  ```

---

## 3. Threat Intelligence & Forensic Endpoints

### `GET /api/threats`
Retrieves a paginated list of classified threats and anomalies.
* **Query Parameters**:
  * `limit` *(int, default 50)*: Number of items to return.
  * `offset` *(int, default 0)*: Pagination offset.
  * `severity` *(string, optional)*: Filter by severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  * `scenario` *(string, optional)*: Filter by threat scenario tag.
  * `agent_id` *(string, optional)*: Filter by specific agent identifier.

### `GET /api/anomalies`
Returns detected statistical anomalies produced by the Isolation Forest engine.

### `GET /api/baseline`
Returns the behavioral baseline profile for a specific user or fleet average.
* **Query Parameters**:
  * `username` *(string, required)*: Target user.
  * `domain` *(string, optional)*: `file`, `logon`, `device`, or `http`.

### `GET /api/agents`
Lists all registered endpoints, their current operational state, last heartbeat, and risk score.

---

## 4. Real-Time Streaming Endpoints (SSE)

### `GET /api/v1/stream/sse`
Unified Server-Sent Events stream for the analyst dashboard.
* **Content-Type**: `text/event-stream`
* **Event Types**:
  * `threat`: New threat detection event emitted.
  * `agent_heartbeat`: Agent status change (online/offline).
  * `kpi_update`: Aggregated fleet risk statistics.

### `GET /api/stream/threats`
Dedicated stream emitting only security threat alerts in real time.

---

## 5. Export Endpoints

### `GET /api/export/logs`
Streams raw or normalized telemetry logs.
* **Query Parameters**:
  * `format` *(string)*: `csv` or `ndjson`.
  * `start_time` *(ISO8601 string)*.
  * `end_time` *(ISO8601 string)*.

### `GET /api/export/threats`
Streams classified threat events in CSV or NDJSON format for SIEM ingestion (e.g. Splunk, Elastic, Sentinel).

---

## 6. Health & System Status

### `GET /api/health`
Returns health check status for backend components:
```json
{
  "status": "healthy",
  "database": "connected",
  "clickhouse": "connected",
  "redis": "connected",
  "model_bridge": "ready",
  "version": "1.0.0"
}
```

### `GET /api/model/readiness`
Reports the status of loaded ML models, artifact files, and feature schema matrices.
