# ACOE Codebase Guide (Developer-Focused)

This guide is a quick "how to read and change the system safely" document for new contributors.

## 1) Mental model in 60 seconds

ACOE runs a **7-stage pipeline** every cycle:

1. Ingestion (`agents/ingestion.py`)
2. Detection (`agents/detection.py`)
3. Decision (`agents/decision.py`)
4. Execution (`agents/execution.py`)
5. Verification (`agents/verification.py`)
6. Impact (`agents/impact.py`)
7. Audit (`agents/audit.py`)

`orchestrator/engine.py` coordinates these stages and writes state/telemetry through optional integration components.

---

## 2) Recommended reading order

Follow this order when onboarding:

1. `run_acoe.py` and `main.py` (entry points)
2. `process_manager.py` (wiring: orchestrator + API + loop)
3. `orchestrator/engine.py` (core lifecycle)
4. `models/schemas.py` (contracts shared across all agents)
5. `agents/*.py` in pipeline order
6. `tests/test_pipeline.py` (expected behavior)

---

## 3) Data contracts and type safety

- Pydantic models in `models/schemas.py` are the canonical contracts.
- Each stage should pass typed models forward (not raw dicts) whenever possible.
- If you add a field:
  - update schema first,
  - update stage logic that creates/consumes it,
  - then update tests.

---

## 4) Where to make common changes

### Change detection thresholds
- Start in `config.yaml` / `config.py`.
- Detection rules live in `agents/detection.py`.

### Change action prioritization
- `agents/decision.py` owns ROI/risk/confidence logic.

### Change retry/idempotency behavior
- `agents/execution.py` owns retries and dedup keys.
- `state_manager.py` persists executed keys across restarts.

### Change output/reporting
- `agents/impact.py` formats savings and impact.
- `dashboard/app.py` and `api/server.py` expose runtime state.

---

## 5) Safe-change checklist

Before committing:

1. Run tests: `pytest -q`
2. Run one full demo cycle: `python run_acoe.py`
3. Confirm no new warnings from model config or serialization
4. Ensure idempotency still works (re-running actions should skip as expected)

---

## 6) Performance notes

- Keep heavy computation in agents, not the orchestration loop control flow.
- Avoid repeated schema conversions in hot loops.
- Use deterministic IDs/keys where possible for easier replay and debugging.

