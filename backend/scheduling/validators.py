"""
Booking validators for the scheduling engine.

Validates:
  - Slot is not in the past
  - Doctor exists
  - Patient exists
  - Slot belongs to requested doctor
  - No overlapping existing appointments
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Doctor, TimeSlot, Appointment, Patient

logger = logging.getLogger("voice-ai.scheduling.validators")


async def validate_booking(
    session: AsyncSession,
    patient_id: str,
    doctor_id: str,
    slot_id: str,
) -> dict:
    """
    Validate all preconditions for booking an appointment.
    Returns {"valid": True} or {"valid": False, "error": "..."}.
    """
    # 1. Validate patient exists
    patient = await session.get(Patient, uuid.UUID(patient_id))
    if not patient:
        return {"valid": False, "error": "Patient not found."}

    # 2. Validate doctor exists
    doctor = await session.get(Doctor, uuid.UUID(doctor_id))
    if not doctor:
        return {"valid": False, "error": "Doctor not found."}

    # 3. Validate slot exists and belongs to doctor
    slot = await session.get(TimeSlot, uuid.UUID(slot_id))
    if not slot:
        return {"valid": False, "error": "Time slot not found."}
    if slot.doctor_id != uuid.UUID(doctor_id):
        return {"valid": False, "error": "The selected slot does not belong to the requested doctor."}

    # 4. Validate slot is still available
    if not slot.is_available:
        return {"valid": False, "error": "This time slot is no longer available."}

    # 5. Validate slot is not in the past
    now = datetime.now(timezone.utc)
    if slot.start_time < now:
        return {"valid": False, "error": "Cannot book an appointment in the past."}

    # 6. Check for overlapping appointments for the same patient
    overlap_result = await session.execute(
        select(Appointment)
        .join(TimeSlot, Appointment.slot_id == TimeSlot.id)
        .where(
            and_(
                Appointment.patient_id == uuid.UUID(patient_id),
                Appointment.status == "confirmed",
                TimeSlot.start_time < slot.end_time,
                TimeSlot.end_time > slot.start_time,
            )
        )
    )
    existing = overlap_result.scalars().first()
    if existing:
        return {
            "valid": False,
            "error": "You already have an appointment during this time. Please reschedule or cancel the existing one first.",
        }

    return {"valid": True}
