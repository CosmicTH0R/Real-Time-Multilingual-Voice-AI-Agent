"""
Latency instrumentation and statistics.

Tracks per-utterance latency across pipeline components:
  STT → Memory → LLM → TTS → Total
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from collections import deque
from statistics import mean, quantiles

logger = logging.getLogger("voice-ai.latency")


@dataclass
class LatencyCheckpoint:
    """A named timestamp checkpoint within a single utterance processing cycle."""
    name: str
    timestamp: float = field(default_factory=time.perf_counter)


class LatencyTracker:
    """
    Tracks latency checkpoints for a single utterance cycle.

    Usage:
        tracker = LatencyTracker()
        tracker.mark("stt_start")
        # ... STT processing ...
        tracker.mark("stt_end")
        tracker.mark("llm_start")
        # ... LLM processing ...
        tracker.mark("llm_end")
        breakdown = tracker.breakdown()
    """

    def __init__(self):
        self.checkpoints: list[LatencyCheckpoint] = []
        self._start = time.perf_counter()

    def mark(self, name: str) -> None:
        """Record a named checkpoint."""
        self.checkpoints.append(LatencyCheckpoint(name=name))

    def elapsed_ms(self, start_name: str, end_name: str) -> float | None:
        """Get milliseconds between two named checkpoints."""
        start_ts = None
        end_ts = None
        for cp in self.checkpoints:
            if cp.name == start_name:
                start_ts = cp.timestamp
            if cp.name == end_name:
                end_ts = cp.timestamp
        if start_ts is not None and end_ts is not None:
            return (end_ts - start_ts) * 1000
        return None

    def total_ms(self) -> float:
        """Total elapsed since tracker creation."""
        return (time.perf_counter() - self._start) * 1000

    def breakdown(self) -> dict:
        """Return a latency breakdown dict for logging."""
        result = {
            "total_ms": round(self.total_ms(), 2),
            "checkpoints": {},
        }

        # Compute known component durations
        for component in ["stt", "memory", "llm", "tts"]:
            ms = self.elapsed_ms(f"{component}_start", f"{component}_end")
            if ms is not None:
                result["checkpoints"][f"{component}_ms"] = round(ms, 2)

        return result


class LatencyStats:
    """
    Aggregated latency statistics across all utterances.
    Maintains a rolling window for percentile computation.
    """

    def __init__(self, window_size: int = 200):
        self.window_size = window_size
        self._totals: deque[float] = deque(maxlen=window_size)
        self._component_totals: dict[str, deque[float]] = {}
        self._count = 0

    def record(self, tracker: LatencyTracker) -> dict:
        """Record a completed utterance's latency and log it."""
        breakdown = tracker.breakdown()
        total = breakdown["total_ms"]
        self._totals.append(total)
        self._count += 1

        for key, value in breakdown.get("checkpoints", {}).items():
            if key not in self._component_totals:
                self._component_totals[key] = deque(maxlen=self.window_size)
            self._component_totals[key].append(value)

        # Log with target comparison
        target = 450
        status = "✅" if total <= target else "⚠️"
        logger.info(
            "%s Utterance #%d latency: %.1fms (target: %dms) | %s",
            status, self._count, total, target, breakdown["checkpoints"],
        )

        return breakdown

    def summary(self) -> dict:
        """Return aggregated statistics."""
        if not self._totals:
            return {"count": 0, "message": "No utterances recorded yet"}

        totals_list = list(self._totals)
        result = {
            "count": self._count,
            "total_ms": {
                "mean": round(mean(totals_list), 2),
                "p50": round(quantiles(totals_list, n=100)[49], 2) if len(totals_list) >= 2 else round(totals_list[0], 2),
                "p95": round(quantiles(totals_list, n=100)[94], 2) if len(totals_list) >= 2 else round(totals_list[0], 2),
                "min": round(min(totals_list), 2),
                "max": round(max(totals_list), 2),
            },
            "components": {},
        }

        for key, values in self._component_totals.items():
            vals = list(values)
            result["components"][key] = {
                "mean": round(mean(vals), 2),
                "p95": round(quantiles(vals, n=100)[94], 2) if len(vals) >= 2 else round(vals[0], 2),
            }

        return result
