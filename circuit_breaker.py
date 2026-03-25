"""
ACOE -- Circuit Breaker & Self-Healing
Protects agents from cascading failures with circuit breaker logic.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Callable, Any

from config import get_config

logger = logging.getLogger("acoe.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, blocking calls
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern for agent-level fault isolation.
    CLOSED -> failures exceed threshold -> OPEN
    OPEN -> timeout expires -> HALF_OPEN
    HALF_OPEN -> success -> CLOSED / failure -> OPEN
    """

    def __init__(self, name: str):
        self.name = name
        self._cfg = get_config()
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    @property
    def failure_threshold(self) -> int:
        return self._cfg.cb_failure_threshold

    @property
    def recovery_timeout(self) -> float:
        return self._cfg.cb_recovery_timeout

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func through the circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"Circuit [{self.name}]: HALF_OPEN - testing recovery")
            else:
                remaining = self.recovery_timeout - (time.time() - self._last_failure_time)
                logger.warning(
                    f"Circuit [{self.name}]: OPEN - blocking call "
                    f"({remaining:.0f}s until recovery attempt)"
                )
                raise CircuitOpenError(
                    f"Circuit breaker [{self.name}] is OPEN. "
                    f"Recovery in {remaining:.0f}s."
                )

        if self.state == CircuitState.HALF_OPEN:
            max_calls = self._cfg.get("circuit_breaker.half_open_max_calls", 1)
            if self._half_open_calls >= max_calls:
                raise CircuitOpenError(
                    f"Circuit [{self.name}] HALF_OPEN max calls reached"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit [{self.name}]: CLOSED - recovery successful")
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0

    def _on_failure(self, error: Exception):
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit [{self.name}]: recovery FAILED -> OPEN: {error}"
            )
        elif self._failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit [{self.name}]: threshold reached ({self._failure_count}) -> OPEN: {error}"
            )
        else:
            logger.warning(
                f"Circuit [{self.name}]: failure {self._failure_count}/{self.failure_threshold}: {error}"
            )

    def _should_attempt_recovery(self) -> bool:
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def reset(self):
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failure_count,
            "threshold": self.failure_threshold,
        }


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open."""
    pass


# ── Agent Circuit Breaker Manager ────────────────────────────────────────────

class CircuitBreakerManager:
    """Manages circuit breakers for all agents."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, agent_name: str) -> CircuitBreaker:
        if agent_name not in self._breakers:
            self._breakers[agent_name] = CircuitBreaker(agent_name)
        return self._breakers[agent_name]

    def get_all_status(self) -> list[dict]:
        return [cb.get_status() for cb in self._breakers.values()]

    def reset_all(self):
        for cb in self._breakers.values():
            cb.reset()
