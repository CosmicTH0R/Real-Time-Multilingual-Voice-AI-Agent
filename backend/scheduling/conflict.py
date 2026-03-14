"""
Conflict detection and resolution for appointment scheduling.

Suggests alternatives when requested slots are unavailable.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Doctor, TimeSlot

logger = logging.getLogger("voice-ai.scheduling.conflict")


class ConflictResolver:
    """Detect scheduling conflicts and suggest alternatives."""

    async def suggest_alternatives(
        self,
        session: AsyncSession,
        doctor_name: str | None = None,
        specialization: str | None = None,
        date: str | None = None,
        doctor_id: str | None = None,
        max_suggestions: int = 3,
    ) -> list[dict]:
        """
        Suggest alternative available slots when requested slot is unavailable.

        Strategy:
          1. Same doctor, nearby dates (±2 days)
          2. Same specialization, different doctor, same date
          3. Same specialization, different doctor, nearby dates
        """
        alternatives = []
        now = datetime.now(timezone.utc)

        # --- Strategy 1: Same doctor, nearby dates ---
        if doctor_id or doctor_name:
            query = select(TimeSlot).join(Doctor).where(
                TimeSlot.is_available == True,
                TimeSlot.start_time > now,
            )

            if doctor_id:
                query = query.where(TimeSlot.doctor_id == uuid.UUID(doctor_id))
            elif doctor_name:
                query = query.where(Doctor.name.ilike(f"%{doctor_name}%"))

            query = query.order_by(TimeSlot.start_time).limit(max_suggestions)
            result = await session.execute(query)
            slots = result.scalars().all()

            for slot in slots:
                doctor = await session.get(Doctor, slot.doctor_id)
                alternatives.append({
                    "type": "same_doctor_different_time",
                    "slot_id": str(slot.id),
                    "doctor_id": str(slot.doctor_id),
                    "doctor_name": doctor.name if doctor else "Unknown",
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                })

        # --- Strategy 2: Same specialization, different doctor ---
        if specialization and len(alternatives) < max_suggestions:
            remaining = max_suggestions - len(alternatives)
            existing_doc_ids = [a.get("doctor_id") for a in alternatives]

            query = (
                select(TimeSlot)
                .join(Doctor)
                .where(
                    TimeSlot.is_available == True,
                    TimeSlot.start_time > now,
                    Doctor.specialization.ilike(f"%{specialization}%"),
                )
            )

            if existing_doc_ids:
                for doc_id in existing_doc_ids:
                    if doc_id:
                        query = query.where(TimeSlot.doctor_id != uuid.UUID(doc_id))

            query = query.order_by(TimeSlot.start_time).limit(remaining)
            result = await session.execute(query)
            slots = result.scalars().all()

            for slot in slots:
                doctor = await session.get(Doctor, slot.doctor_id)
                alternatives.append({
                    "type": "different_doctor_same_specialization",
                    "slot_id": str(slot.id),
                    "doctor_id": str(slot.doctor_id),
                    "doctor_name": doctor.name if doctor else "Unknown",
                    "specialization": doctor.specialization if doctor else "Unknown",
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                })

        return alternatives
