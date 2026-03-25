# ACOE — Autonomous Cost Optimization Engine

A fully autonomous, self-running, production-grade multi-agent system that continuously detects enterprise cost inefficiencies, decides optimal actions, executes them, and reports quantified financial impact in ₹ — all without human intervention.

## Architecture

```
INGEST → DETECT → DECIDE → ACT → VERIFY → LOG → REPORT → REPEAT
```

### Multi-Agent System

| Agent | Responsibility |
|-------|---------------|
| **Ingestion** | Load CSV/JSON enterprise data, validate, normalize |
| **Detection** | Rule-based + z-score anomaly detection for 5 issue types |
| **Decision** | Map issues → actions with ROI, risk, confidence scoring |
| **Execution** | Mock API execution with retry (3x exponential backoff) + idempotency |
| **Verification** | Compare expected vs actual outcomes, flag mismatches |
| **Audit** | Structured JSON + human-readable logs for every cycle |
| **Impact** | Compute realized, projected savings + avoided SLA penalties in ₹ |

### Detection Capabilities

- **Duplicate Vendors** — Same service category, multiple providers
- **SaaS Underutilization** — Active users below threshold (default: 40%)
- **Cloud Over-provisioning** — Avg usage well below capacity (default: 35%)
- **SLA Breach Risk** — Time-to-breach estimation (default: 48h window)
- **Cost Anomalies** — Z-score outliers above threshold (default: 2.0σ)

## Quick Start

### 1. Install Dependencies

```bash
cd ACOE
pip install -r requirements.txt
```

### 2. Run Autonomous Mode (One Command)

```bash
python main.py
```

This starts:
- **Autonomous orchestrator loop** (60s interval, configurable)
- **FastAPI API server** on `http://localhost:8000`

The system immediately begins its first cycle: ingesting data, detecting issues, executing corrective actions, and reporting savings.

### 3. Launch Dashboard (Optional)

```bash
streamlit run dashboard/app.py
```

Opens a read-only observability dashboard at `http://localhost:8501`.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /status` | System health, cycle count, uptime |
| `GET /ingest` | Latest ingested data summary |
| `GET /analyze` | Detected inefficiencies with severity |
| `GET /act` | Executed actions + verification status |
| `GET /report` | Financial impact report with ₹ savings |
| `GET /docs` | Swagger UI |

## Configuration

Edit `config.py` to adjust:

```python
LOOP_INTERVAL_SECONDS = 60          # Cycle frequency
SAAS_UTILIZATION_THRESHOLD = 0.40   # Flag if < 40% utilization
CLOUD_UTILIZATION_THRESHOLD = 0.35  # Flag if < 35% utilization
SLA_BREACH_WINDOW_HOURS = 48        # Flag if breach < 48h away
APPROVAL_GATE_ENABLED = False       # Set True for manual approval
DEMO_MODE = True                    # Deterministic outputs
```

## Sample Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CYCLE #1 — COMPLETED in 2.3s
  Issues: 22 | Actions: 18
  Savings: ₹45,80,000 | Errors: 0
  Cumulative: ₹45,80,000
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Unused Licenses: 120
Action: Downgrade Plan
Savings: ₹3,60,000/year

SLA Risk Avoided:
Penalty Saved: ₹1,20,000
```

## Project Structure

```
ACOE/
├── main.py                 # Daemon entry point
├── config.py               # Central configuration
├── requirements.txt
├── data/                   # Synthetic datasets
│   ├── procurement.csv
│   ├── saas_subscriptions.csv
│   ├── cloud_usage.csv
│   └── sla_metrics.csv
├── models/
│   └── schemas.py          # Pydantic data models
├── agents/
│   ├── ingestion.py        # Data ingestion
│   ├── detection.py        # Anomaly + rule detection
│   ├── decision.py         # Action planning
│   ├── execution.py        # Mock API execution
│   ├── verification.py     # Outcome verification
│   ├── audit.py            # Audit logging
│   └── impact.py           # Financial impact
├── orchestrator/
│   └── engine.py           # Autonomous pipeline
├── api/
│   └── server.py           # FastAPI endpoints
├── dashboard/
│   └── app.py              # Streamlit dashboard
├── logs/                   # Runtime audit logs
└── state/                  # Persistent state
```

## Key Design Principles

- **Zero human-in-the-loop** after `python main.py`
- **Self-healing** — catches all exceptions, logs, continues
- **Idempotent execution** — dedup keys prevent re-execution
- **State persistence** — survives restarts via JSON state file
- **Deterministic** — reproducible results in demo mode
- **Full auditability** — every decision logged with reasoning
