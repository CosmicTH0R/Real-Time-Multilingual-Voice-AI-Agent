import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from scheduling.engine import SchedulingEngine
from db.models import Doctor, TimeSlot, Appointment, Patient

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def engine():
    return SchedulingEngine()

@pytest.mark.asyncio
@patch("scheduling.engine.async_session_factory")
async def test_check_availability(mock_session_factory, engine, mock_session):
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_result = MagicMock()
    mock_slot = TimeSlot(
        id=uuid.uuid4(), doctor_id=uuid.uuid4(),
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
        is_available=True
    )
    mock_result.scalars.return_value.all.return_value = [mock_slot]
    mock_session.execute.return_value = mock_result
    
    mock_doctor = Doctor(id=mock_slot.doctor_id, name="Dr. Smith", specialization="Cardiology")
    mock_session.get.return_value = mock_doctor
    
    response = await engine.check_availability(specialization="Cardiology")
    
    assert response["available"] is True
    assert response["count"] == 1
    assert response["slots"][0]["doctor_name"] == "Dr. Smith"

@pytest.mark.asyncio
@patch("scheduling.engine.validate_booking")
@patch("scheduling.engine.async_session_factory")
async def test_book_appointment_success(mock_session_factory, mock_validate, engine, mock_session):
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_validate.return_value = {"valid": True}
    
    # Mock slot retrieval
    mock_slot_result = MagicMock()
    mock_slot = TimeSlot(
        id=uuid.uuid4(), doctor_id=uuid.uuid4(),
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
        is_available=True
    )
    mock_slot_result.scalar_one_or_none.return_value = mock_slot
    mock_session.execute.return_value = mock_slot_result
    
    # Mock doctor retrieval
    mock_doctor = Doctor(id=mock_slot.doctor_id, name="Dr. Smith")
    mock_session.get.return_value = mock_doctor
    
    patient_id = str(uuid.uuid4())
    doctor_id = str(mock_slot.doctor_id)
    slot_id = str(mock_slot.id)
    
    response = await engine.book_appointment(patient_id, doctor_id, slot_id)
    
    assert response["success"] is True
    assert mock_slot.is_available is False
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
@patch("scheduling.engine.async_session_factory")
async def test_cancel_appointment(mock_session_factory, engine, mock_session):
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    appt_id = uuid.uuid4()
    slot_id = uuid.uuid4()
    
    mock_appt = Appointment(
        id=appt_id, patient_id=uuid.uuid4(), doctor_id=uuid.uuid4(),
        slot_id=slot_id, status="confirmed"
    )
    mock_slot = TimeSlot(
        id=slot_id, doctor_id=mock_appt.doctor_id,
        is_available=False
    )
    
    async def mock_get(model, id, *args, **kwargs):
        if model == Appointment: return mock_appt if str(id) == str(appt_id) else None
        if model == TimeSlot: return mock_slot if str(id) == str(slot_id) else None
        return None
        
    mock_session.get.side_effect = mock_get
    
    response = await engine.cancel_appointment(str(appt_id))
    
    assert response["success"] is True
    assert mock_appt.status == "cancelled"
    assert mock_slot.is_available is True
    mock_session.commit.assert_called_once()
