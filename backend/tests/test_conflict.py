import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from scheduling.conflict import ConflictResolver
from db.models import Doctor, TimeSlot

@pytest.fixture
def conflict_resolver():
    return ConflictResolver()

@pytest.mark.asyncio
async def test_suggest_alternatives_same_doctor(conflict_resolver):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    
    # Mock return 2 slots
    slot1 = TimeSlot(
        id=uuid.uuid4(), doctor_id=uuid.uuid4(),
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, minutes=30)
    )
    slot2 = TimeSlot(
        id=uuid.uuid4(), doctor_id=slot1.doctor_id,
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        end_time=datetime.now(timezone.utc) + timedelta(days=2, minutes=30)
    )
    mock_result.scalars.return_value.all.return_value = [slot1, slot2]
    mock_session.execute.return_value = mock_result
    
    # Mock doctor
    mock_doctor = Doctor(id=slot1.doctor_id, name="Dr. Jones")
    mock_session.get.return_value = mock_doctor
    
    alts = await conflict_resolver.suggest_alternatives(
        session=mock_session,
        doctor_id=str(slot1.doctor_id)
    )
    
    assert len(alts) == 2
    assert alts[0]["type"] == "same_doctor_different_time"
    assert alts[0]["doctor_name"] == "Dr. Jones"
    
@pytest.mark.asyncio
async def test_suggest_alternatives_different_doctor(conflict_resolver):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    
    slot1 = TimeSlot(
        id=uuid.uuid4(), doctor_id=uuid.uuid4(),
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, minutes=30)
    )
    mock_result.scalars.return_value.all.return_value = [slot1]
    mock_session.execute.return_value = mock_result
    
    mock_doctor = Doctor(id=slot1.doctor_id, name="Dr. Smith", specialization="Cardiology")
    mock_session.get.return_value = mock_doctor
    
    alts = await conflict_resolver.suggest_alternatives(
        session=mock_session,
        specialization="Cardiology"
    )
    
    assert len(alts) == 1
    assert alts[0]["type"] == "different_doctor_same_specialization"
    assert alts[0]["specialization"] == "Cardiology"
