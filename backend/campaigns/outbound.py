"""
Outbound campaign call initiation.
"""

from __future__ import annotations

import uuid
import logging
from typing import Any

from db.connection import async_session_factory
from db.models import Campaign, Patient
from campaigns.models import CampaignType, CampaignStatus

logger = logging.getLogger("voice-ai.campaigns.outbound")


async def initiate_campaign(campaign_id: str) -> dict:
    """
    Start an outbound campaign: fetch patients, enqueue calls.
    """
    async with async_session_factory() as session:
        campaign = await session.get(Campaign, uuid.UUID(campaign_id))
        if not campaign:
            return {"error": "Campaign not found"}

        campaign.status = CampaignStatus.RUNNING.value
        await session.commit()

        patient_ids = campaign.patient_ids or []
        logger.info(
            "Campaign %s started: %d patients, type=%s",
            campaign_id, len(patient_ids), campaign.campaign_type,
        )

        # In production, this would enqueue jobs to the RQ worker
        # For now, we log the intent
        return {
            "campaign_id": str(campaign.id),
            "status": "running",
            "patients_queued": len(patient_ids),
            "campaign_type": campaign.campaign_type,
        }


async def handle_outbound_call(patient_id: str, campaign_type: str) -> dict:
    """
    Handle a single outbound call to a patient.
    Sets up the conversation with a campaign-specific greeting.
    """
    async with async_session_factory() as session:
        patient = await session.get(Patient, uuid.UUID(patient_id))
        if not patient:
            return {"error": "Patient not found"}

        return {
            "patient_id": str(patient.id),
            "patient_name": patient.name,
            "language": patient.language_pref,
            "campaign_type": campaign_type,
            "status": "initiated",
        }
