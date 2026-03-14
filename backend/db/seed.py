"""
Database seed script — populates with sample doctors, patients, and time slots.
"""

from __future__ import annotations

import asyncio
import uuid
import logging
from datetime import datetime, timedelta, timezone

from db.connection import init_db, async_session_factory
from db.models import Doctor, Patient, TimeSlot

logger = logging.getLogger("voice-ai.seed")

# ── Sample Doctors ──
DOCTORS = [
    {"name": "Dr. Priya Sharma", "specialization": "General Medicine"},
    {"name": "Dr. Rajesh Kumar", "specialization": "Cardiology"},
    {"name": "Dr. Anitha Sundaram", "specialization": "Dermatology"},
    {"name": "Dr. Vikram Patel", "specialization": "Orthopedics"},
    {"name": "Dr. Lakshmi Venkatesh", "specialization": "Pediatrics"},
]

# ── Sample Patients ──
PATIENTS = [
    {"name": "Amit Gupta", "phone": "+91-9876543210", "language_pref": "en"},
    {"name": "Priya Nair", "phone": "+91-9876543211", "language_pref": "en"},
    {"name": "राहुल शर्मा", "phone": "+91-9876543212", "language_pref": "hi"},
    {"name": "सुनीता देवी", "phone": "+91-9876543213", "language_pref": "hi"},
    {"name": "முருகன் கணேசன்", "phone": "+91-9876543214", "language_pref": "ta"},
    {"name": "லக்ஷ்மி பாலா", "phone": "+91-9876543215", "language_pref": "ta"},
    {"name": "Rohan Mehta", "phone": "+91-9876543216", "language_pref": "en"},
    {"name": "Deepa Iyer", "phone": "+91-9876543217", "language_pref": "en"},
    {"name": "कविता मिश्रा", "phone": "+91-9876543218", "language_pref": "hi"},
    {"name": "Arjun Das", "phone": "+91-9876543219", "language_pref": "en"},
]


async def seed_database():
    """Populate the database with sample data."""
    await init_db()

    async with async_session_factory() as session:
        # ── Seed Doctors ──
        doctor_ids = []
        for doc_data in DOCTORS:
            doctor = Doctor(**doc_data)
            session.add(doctor)
            doctor_ids.append(doctor.id)

        await session.flush()

        # ── Seed Time Slots (7 days, 8 slots per doctor per day) ──
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        slot_count = 0

        for doctor in await session.execute(
            __import__("sqlalchemy").select(Doctor)
        ):
            doc = doctor[0]
            for day_offset in range(1, 8):  # Next 7 days
                day = now + timedelta(days=day_offset)
                for hour in range(9, 17):  # 9 AM to 5 PM
                    slot = TimeSlot(
                        doctor_id=doc.id,
                        start_time=day.replace(hour=hour),
                        end_time=day.replace(hour=hour) + timedelta(minutes=30),
                        is_available=True,
                    )
                    session.add(slot)
                    slot_count += 1

        # ── Seed Patients ──
        patient_count = 0
        for pt_data in PATIENTS:
            patient = Patient(**pt_data)
            session.add(patient)
            patient_count += 1

        await session.commit()

        logger.info(
            "✅ Seeded: %d doctors, %d slots, %d patients",
            len(DOCTORS), slot_count, patient_count,
        )
        print(f"✅ Seeded: {len(DOCTORS)} doctors, {slot_count} slots, {patient_count} patients")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_database())
