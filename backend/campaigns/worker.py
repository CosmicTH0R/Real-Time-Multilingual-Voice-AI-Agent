"""
Background job worker using Redis Queue (RQ).

Processes outbound campaign calls asynchronously.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("voice-ai.campaigns.worker")


def process_outbound_call(patient_id: str, campaign_type: str, campaign_id: str):
    """
    RQ job: process a single outbound call.
    This function runs in the worker process.
    """
    logger.info(
        "Processing outbound call: patient=%s, type=%s, campaign=%s",
        patient_id, campaign_type, campaign_id,
    )
    # In production, this would:
    # 1. Initiate a WebSocket/telephony connection
    # 2. Run the voice pipeline in outbound mode
    # 3. Record the outcome
    return {"patient_id": patient_id, "outcome": "completed"}


if __name__ == "__main__":
    """Run the RQ worker."""
    from redis import Redis
    from rq import Worker, Queue

    from config import get_settings

    settings = get_settings()

    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue("campaigns", connection=redis_conn)

    logger.info("Starting campaign worker...")
    worker = Worker([queue], connection=redis_conn)
    worker.work()
