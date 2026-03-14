"""
Reasoning trace logger for the LLM Agent.

Captures each step of the agentic loop for debugging and transparency.
"""

from __future__ import annotations

import time
import logging
from typing import Any

logger = logging.getLogger("voice-ai.reasoning")


class ReasoningTracer:
    """
    Records reasoning steps during agent processing.

    Each trace is a timestamped record of what the agent did and why.
    Traces are sent to the frontend for the debug panel.
    """

    def __init__(self):
        self._traces: list[dict] = []
        self._start_time: float = time.perf_counter()

    def reset(self):
        """Clear traces for a new processing cycle."""
        self._traces = []
        self._start_time = time.perf_counter()

    def trace(self, step_type: str, data: Any = None):
        """
        Record a reasoning step.

        step_type: one of "input", "llm_call", "tool_call", "tool_result", "response"
        data: relevant data for this step
        """
        elapsed_ms = (time.perf_counter() - self._start_time) * 1000
        entry = {
            "step": step_type,
            "elapsed_ms": round(elapsed_ms, 2),
            "data": data,
            "timestamp": time.time(),
        }
        self._traces.append(entry)
        logger.debug("Reasoning [%s] +%.1fms: %s", step_type, elapsed_ms, data)

    def get_traces(self) -> list[dict]:
        """Return all recorded traces."""
        return self._traces.copy()
