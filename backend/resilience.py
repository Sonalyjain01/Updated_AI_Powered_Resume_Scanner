"""Protection against a slow or failing AI provider.

Every model call gets a timeout, and a circuit breaker stops calling the provider after
repeated failures so scans fail fast (and use the keyword fallback) instead of each
waiting out a timeout.

LLM_TIMEOUT_SECONDS             per-call timeout (default 30)
LLM_BREAKER_FAILURES            consecutive failures that open the circuit (default 5)
LLM_BREAKER_COOLDOWN_SECONDS    how long it stays open before one trial call (default 30)
"""
import os
import time
from typing import Callable, Optional


class CircuitOpenError(Exception):
    """The AI provider has failed repeatedly; calls are paused for a short time"""


class CircuitBreaker:
    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0,
                 clock: Callable[[], float] = time.monotonic):
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._trial_in_flight = False

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return self.CLOSED
        if self._clock() - self._opened_at >= self.cooldown_seconds:
            return self.HALF_OPEN
        return self.OPEN

    def before_call(self) -> None:
        """Raise CircuitOpenError if the call should not be attempted"""
        state = self.state
        if state == self.OPEN:
            raise CircuitOpenError("AI provider is paused after repeated failures")
        if state == self.HALF_OPEN:
            if self._trial_in_flight:
                raise CircuitOpenError("AI provider is being re-tested")
            self._trial_in_flight = True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._trial_in_flight = False

    def record_failure(self) -> None:
        self._trial_in_flight = False
        self._failures += 1
        if self._opened_at is not None or self._failures >= self.failure_threshold:
            self._opened_at = self._clock()  # a failed trial re-opens for a full cooldown


def breaker_from_env() -> CircuitBreaker:
    return CircuitBreaker(
        failure_threshold=int(os.getenv("LLM_BREAKER_FAILURES", "5")),
        cooldown_seconds=float(os.getenv("LLM_BREAKER_COOLDOWN_SECONDS", "30")),
    )


def llm_timeout_seconds() -> float:
    return float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
