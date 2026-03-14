import pytest
import time
from pipeline.latency import LatencyTracker, LatencyStats

def test_latency_tracker_checkpoints():
    tracker = LatencyTracker()
    tracker.mark("speech_end")
    assert tracker.elapsed_ms("speech_end", "speech_end") == 0.0
    
    tracker.mark("stt_final")
    
    tracker.mark("llm_first_token")
    tracker.mark("tts_first_chunk")
    
    stats = tracker.breakdown()
    # Ensure they are valid positive integers (or zero if too fast)
    assert stats["total_ms"] >= 0

def test_latency_rolling_average():
    tracker1 = LatencyTracker()
    tracker1.mark("tts_first_chunk")  # total 0ms roughly
    
    # We can fake the stats for test purposes
    
    stats_obj = LatencyStats(window_size=10)
    stats_obj.record(tracker1)
    
    summary = stats_obj.summary()
    assert summary["count"] == 1
    assert summary["total_ms"]["mean"] >= 0
