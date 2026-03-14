"""
Campaign models and data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CampaignType(str, Enum):
    REMINDER = "reminder"
    FOLLOW_UP = "follow_up"
    RESCHEDULE = "reschedule"


class CampaignStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CampaignResult:
    """Result of a single outbound call in a campaign."""
    patient_id: str
    outcome: str  # booked | rescheduled | cancelled | rejected | no_answer
    notes: str = ""
