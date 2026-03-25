"""
ACOE -- Process Manager
Production entry point with health checks, graceful shutdown, and scheduler.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime

import uvicorn

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config
from state_manager import StateManager
from circuit_breaker import CircuitBreakerManager
from safety import SafetyGuard
from metrics import MetricsTracker
from simulation import SimulationEngine
from prediction import CostPredictor
from adapters import AdapterRegistry
from orchestrator.engine import ACOEOrchestrator
from api.server import app, set_orchestrator

# ── Logging Setup ────────────────────────────────────────────────────────────

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

cfg = get_config()

LOG_FORMAT = "%(asctime)s | %(name)-22s | %(levelname)-7s | %(message)s"
JSON_FORMAT = '{"time":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","msg":"%(message)s"}'

handlers = []
# Console handler (human-readable)
if cfg.get("logging.console_logs", True):
    console_handler = logging.StreamHandler(
        io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    )
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    handlers.append(console_handler)

# File handler (JSON or plain)
log_dir = cfg.log_dir
os.makedirs(log_dir, exist_ok=True)
file_handler = logging.FileHandler(
    os.path.join(log_dir, "acoe_system.log"), encoding="utf-8"
)
fmt = JSON_FORMAT if cfg.get("logging.json_logs", True) else LOG_FORMAT
file_handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
handlers.append(file_handler)

logging.basicConfig(
    level=getattr(logging, cfg.get("logging.level", "INFO")),
    handlers=handlers,
)

logger = logging.getLogger("acoe.process_manager")


# ── Process Manager ──────────────────────────────────────────────────────────

class ProcessManager:
    """
    Production process manager with:
    - Health checks
    - Graceful shutdown
    - Internal scheduler with backoff
    - Component lifecycle management
    """

    def __init__(self):
        self._cfg = get_config()
        self._running = False
        self._healthy = False
        self._start_time = datetime.utcnow()
        self._consecutive_failures = 0

        # Initialize components
        self.state_db = StateManager(self._cfg.db_path)
        self.cb_manager = CircuitBreakerManager()
        self.safety = SafetyGuard()
        self.metrics = MetricsTracker(self.state_db)
        self.simulation = SimulationEngine()
        self.predictor = CostPredictor()
        self.adapters = AdapterRegistry(mock_mode=self._cfg.demo_mode)

        # Initialize orchestrator with all components
        self.orchestrator = ACOEOrchestrator(
            state_db=self.state_db,
            cb_manager=self.cb_manager,
            safety=self.safety,
            metrics_tracker=self.metrics,
            simulation=self.simulation,
            predictor=self.predictor,
        )

        # Wire to FastAPI
        set_orchestrator(self.orchestrator)

        # Attach components to API for endpoint access
        app.state.metrics = self.metrics
        app.state.simulation = self.simulation
        app.state.predictor = self.predictor
        app.state.state_db = self.state_db
        app.state.cb_manager = self.cb_manager
        app.state.safety = self.safety

    def health_check(self) -> dict:
        """System health check."""
        uptime = (datetime.utcnow() - self._start_time).total_seconds()
        return {
            "healthy": self._healthy,
            "running": self._running,
            "uptime_seconds": round(uptime, 1),
            "consecutive_failures": self._consecutive_failures,
            "total_cycles": self.state_db.get_cycle_count(),
            "cumulative_savings_inr": self.state_db.get_cumulative_savings(),
            "circuit_breakers": self.cb_manager.get_all_status(),
            "safety_constraints": self.safety.get_constraints_summary(),
            "adapters": self.adapters.list_adapters(),
        }

    async def start(self):
        """Main entry point - start all components."""
        self._running = True
        self._healthy = True

        logger.info("=" * 70)
        logger.info("  ACOE -- AUTONOMOUS COST OPTIMIZATION ENGINE v2")
        logger.info("  Process Manager starting...")
        logger.info(f"  Mode:       {'DEMO' if self._cfg.demo_mode else 'PRODUCTION'}")
        logger.info(f"  Execution:  {self._cfg.get('system.mode', 'AUTO')}")
        logger.info(f"  Interval:   {self._cfg.loop_interval}s")
        logger.info(f"  Database:   {self._cfg.db_path}")
        logger.info(f"  API:        http://localhost:{self._cfg.api_port}")
        logger.info(f"  Dashboard:  streamlit run dashboard/app.py")
        logger.info("=" * 70)

        # Start FastAPI in background thread
        api_thread = threading.Thread(target=self._run_api, daemon=True)
        api_thread.start()
        logger.info(f"FastAPI server started on http://localhost:{self._cfg.api_port}")

        # Handle signals
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        # Start autonomous scheduler loop
        await self._scheduler_loop()

    async def _scheduler_loop(self):
        """Internal scheduler with backoff on failure."""
        interval = self._cfg.loop_interval
        max_backoff = self._cfg.get("scheduler.max_backoff_seconds", 300)
        backoff_mult = self._cfg.get("scheduler.backoff_multiplier", 2.0)
        max_failures = self._cfg.get("scheduler.max_consecutive_failures", 5)

        current_interval = interval

        while self._running:
            try:
                await self.orchestrator.trigger_cycle()
                self._consecutive_failures = 0
                current_interval = interval  # Reset on success
                self._healthy = True
            except Exception as e:
                self._consecutive_failures += 1
                logger.error(
                    f"Scheduler: cycle failed ({self._consecutive_failures}x): {e}"
                )

                if self._consecutive_failures >= max_failures:
                    logger.critical(
                        f"Scheduler: {max_failures} consecutive failures - "
                        f"entering degraded mode"
                    )
                    self._healthy = False

                # Exponential backoff
                current_interval = min(
                    interval * (backoff_mult ** self._consecutive_failures),
                    max_backoff,
                )
                logger.info(f"Scheduler: backoff interval -> {current_interval:.0f}s")

            if self._running:
                logger.info(f"Next cycle in {current_interval:.0f}s...")
                await asyncio.sleep(current_interval)

    def _run_api(self):
        """Run FastAPI in background thread."""
        try:
            uvicorn.run(
                app,
                host=self._cfg.api_host,
                port=self._cfg.api_port,
                log_level="warning",
                access_log=False,
            )
        except Exception as e:
            logger.error(f"FastAPI server error: {e}")

    def _handle_shutdown(self, sig, frame):
        """Graceful shutdown."""
        logger.info(f"Shutdown signal {sig} received")
        self._running = False
        self.orchestrator.stop()
        self.state_db.close()
        logger.info("Process Manager shutdown complete")

    def stop(self):
        self._running = False
        self.orchestrator.stop()
        self.state_db.close()


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    pm = ProcessManager()
    try:
        await pm.start()
    except KeyboardInterrupt:
        pm.stop()
    finally:
        logger.info("ACOE daemon stopped.")


if __name__ == "__main__":
    asyncio.run(main())
