"""
Persistent cross-session memory backed by PostgreSQL.

Stores: patient history, preferences, language preferences,
past conversation summaries.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from db.connection import async_session_factory

logger = logging.getLogger("voice-ai.memory.persistent")


class PersistentMemory:
    """PostgreSQL-backed cross-session memory."""

    async def get_patient_profile(self, patient_id: str) -> dict:
        """Retrieve the patient profile by ID."""
        try:
            from db.models import Patient

            async with async_session_factory() as session:
                patient = await session.get(Patient, uuid.UUID(patient_id))
                if not patient:
                    return {}
                return {
                    "name": patient.name,
                    "phone": patient.phone,
                    "language_pref": patient.language_pref,
                }
        except Exception as exc:
            logger.warning("Failed to get patient profile: %s", exc)
            return {}

    async def get_recent_history(self, patient_id: str, limit: int = 10) -> list[dict]:
        """Get recent appointment history for a patient."""
        try:
            from db.models import Appointment, Patient, Doctor

            async with async_session_factory() as session:
                result = await session.execute(
                    select(Appointment, Doctor)
                    .join(Doctor, Appointment.doctor_id == Doctor.id)
                    .where(Appointment.patient_id == uuid.UUID(patient_id))
                    .order_by(Appointment.created_at.desc())
                    .limit(limit)
                )
                rows = result.all()

                appointments = []
                for appt, doctor in rows:
                    appointments.append({
                        "id": str(appt.id),
                        "doctor": doctor.name,
                        "specialization": doctor.specialization,
                        "status": appt.status,
                        "created_at": str(appt.created_at),
                    })
                return appointments
        except Exception as exc:
            logger.warning("Failed to get recent history: %s", exc)
            return []

    async def get_patient_history(self, patient_id: str) -> dict:
        """Retrieve patient's appointment history and preferences."""
        try:
            from db.models import Appointment, Patient, Doctor

            async with async_session_factory() as session:
                patient = await session.get(Patient, uuid.UUID(patient_id))
                if not patient:
                    return {}

                result = await session.execute(
                    select(Appointment, Doctor)
                    .join(Doctor, Appointment.doctor_id == Doctor.id)
                    .where(Appointment.patient_id == uuid.UUID(patient_id))
                    .order_by(Appointment.created_at.desc())
                    .limit(10)
                )
                rows = result.all()

                past_appointments = []
                for appt, doctor in rows:
                    past_appointments.append({
                        "id": str(appt.id),
                        "doctor": doctor.name,
                        "specialization": doctor.specialization,
                        "status": appt.status,
                        "created_at": str(appt.created_at),
                    })

                return {
                    "name": patient.name,
                    "phone": patient.phone,
                    "past_appointments": past_appointments,
                    "preferences": {
                        "language": patient.language_pref,
                    },
                }
        except Exception as exc:
            logger.warning("Failed to get patient history: %s", exc)
            return {}

    async def get_language_pref(self, patient_id: str) -> str | None:
        """Get patient's stored language preference."""
        try:
            from db.models import Patient

            async with async_session_factory() as session:
                patient = await session.get(Patient, uuid.UUID(patient_id))
                return patient.language_pref if patient else None
        except Exception as exc:
            logger.warning("Failed to get language pref: %s", exc)
            return None

    async def save_language_pref(self, patient_id: str, language: str):
        """Update patient's language preference."""
        try:
            from db.models import Patient

            async with async_session_factory() as session:
                patient = await session.get(Patient, uuid.UUID(patient_id))
                if patient:
                    patient.language_pref = language
                    await session.commit()
        except Exception as exc:
            logger.warning("Failed to save language pref: %s", exc)

    async def save_conversation(
        self,
        session_id: str,
        patient_id: str | None,
        turns: list[dict],
        language: str = "en",
    ):
        """Persist a completed conversation to the database."""
        try:
            from db.models import ConversationLog

            async with async_session_factory() as session:
                log = ConversationLog(
                    session_id=session_id,
                    patient_id=uuid.UUID(patient_id) if patient_id else None,
                    language=language,
                    turns=turns,
                )
                session.add(log)
                await session.commit()
                logger.info("Conversation saved: session=%s", session_id)
        except Exception as exc:
            logger.warning("Failed to save conversation: %s", exc)
