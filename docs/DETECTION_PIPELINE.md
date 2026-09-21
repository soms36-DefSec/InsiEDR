# InsiEDR Multi-Layer Detection Pipeline

The InsiEDR detection framework combines deterministic rules with a multi-stage machine learning pipeline to detect insider threat patterns that evade conventional endpoint controls.

---

## 1. Threat Scenarios (CERT Insider Threat Mapping)

InsiEDR models threat behaviors derived from the CERT Insider Threat Dataset specification:

* **Scenario 1 (IT Sabotage / Disgruntled Employee)**:
  * User logs in after business hours and accesses systems they normally do not visit.
  * Attempts to tamper with privileges, services, or persistence mechanisms.
* **Scenario 2 (Intellectual Property Theft / Data Hoarding)**:
  * User begins browsing and copying an unusually high volume of files across distinct directories.
  * Accumulates sensitive documents before an impending termination or departure.
* **Scenario 3 (Data Exfiltration via Removable Media)**:
  * Abnormal file collection followed immediately by unauthorized USB flash drive insertion and bulk transfer.
* **Scenario 4 (Cloud Exfiltration)**:
  * Large outbound data bursts directed to unauthorized cloud storage or file-sharing websites.
* **Honeytoken / Bait Traps**:
  * Decoy files (`decoy_monitor.py`) planted in predictable directories. Any interaction triggers an immediate, zero-false-positive `CRITICAL` alert.

---

## 2. The 4 Analytical Layers

```
 Raw Feature Vector (Logon, File, Device, HTTP)
        │
        ├───> [ Layer 1: Deterministic Heuristics ] ────> Immediate Severity & Scenario Tags
        │
        ├───> [ Layer 2: Isolation Forest ] ───────────> Domain Anomaly Scores (0 - 100)
        │
        ├───> [ Layer 3: XGBoost Classifier ] ─────────> Scenario Probabilities (s1, s2, s3, normal)
        │
        └───> [ Layer 4: RedRVFL Sequence Modeler ] ───> Temporal Behavioral Risk (0 - 100)
                                                                 │
                                                                 ▼
                                                  [ Composite Risk Aggregator ]
```

### Layer 1: Deterministic Heuristics
The heuristic engine evaluates rigid behavioral boundaries:
* Multi-PC lateral movement ($\ge 3$ distinct machines in 24 hours).
* After-hours logon ratio spikes ($> 50\%$ outside normal working hours).
* Bulk file harvesting ($> 500$ distinct files modified/read).
* Removable media access combined with elevated file operations.

### Layer 2: Domain Isolation Forest
* Algorithms: Scikit-learn `IsolationForest`.
* Computes anomaly scores across domain subsets:
  $$\text{Score}_{\text{domain}} = - \frac{\mathbb{E}[h(x)]}{c(n)}$$
* Produces four domain-level scores:
  * `logon_risk` (0 - 100)
  * `file_risk` (0 - 100)
  * `device_risk` (0 - 100)
  * `http_risk` (0 - 100)

### Layer 3: Supervised XGBoost Classifier
* Model artifact: `scenario_xgb.pkl`.
* Trained on engineered behavioral features from historical insider threat events.
* Generates a calibrated multi-class probability vector:
  $$P(\text{Scenario}_k \mid X)$$

### Layer 4: RedRVFL (Random Vector Functional Link) Network
Traditional models treat events as isolated snapshots. InsiEDR employs an **RVFL network with RandomLSTM recurrent connections**:
* Takes historical user day vectors over rolling time horizons (e.g., 7 to 30 days).
* Directly captures chronological progression:
  $$\text{Reconnaissance} \longrightarrow \text{Hoarding} \longrightarrow \text{Staging} \longrightarrow \text{Exfiltration}$$
* Yields a continuous `behavioral_risk` score (0 - 100) that exhibits natural temporal decay as benign behavior resumes.

---

## 3. Composite Risk Aggregation

The final `composite_risk_score` is computed by the Risk Aggregator (`server/risk/aggregator.py`):
$$\text{Risk}_{\text{final}} = \max\left(S_{\text{heuristics}}, \; \alpha \cdot S_{\text{IF}} + \beta \cdot S_{\text{XGB}} + \gamma \cdot S_{\text{RVFL}}\right)$$

Where:
* $S_{\text{heuristics}}$ acts as an absolute floor (a Honeytoken trip guarantees a score of 100).
* Weights $\alpha, \beta, \gamma$ balance anomaly detection against sequence trajectory.
* Scores map into severity tiers:
  * **0 – 39**: `LOW`
  * **40 – 69**: `MEDIUM`
  * **70 – 89**: `HIGH`
  * **90 – 100**: `CRITICAL`
