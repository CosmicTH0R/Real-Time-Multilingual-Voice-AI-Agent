import pytest
import uuid
import json
from unittest.mock import AsyncMock, patch

from memory.manager import MemoryManager
from memory.session import SessionMemory
from memory.persistent import PersistentMemory
from db.models import Patient

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def session_memory(mock_redis):
    mem = SessionMemory()
    mem.redis = mock_redis
    return mem

@pytest.mark.asyncio
async def test_session_memory_update_intent(session_memory, mock_redis):
    session_id = "test-123"
    await session_memory.update_intent(session_id, "book_appointment")
    
    args, kwargs = mock_redis.setex.call_args
    assert args[0] == f"session:{session_id}:intent"
    assert args[2] == b"book_appointment"

@pytest.mark.asyncio
async def test_session_memory_add_entity(session_memory, mock_redis):
    session_id = "test-123"
    mock_redis.get.return_value = json.dumps({"specialization": "Cardiology"}).encode()
    
    await session_memory.add_entity(session_id, "date", "2023-12-01")
    args, kwargs = mock_redis.setex.call_args
    stored_data = json.loads(args[2].decode())
    assert stored_data["specialization"] == "Cardiology"
    assert stored_data["date"] == "2023-12-01"

@pytest.fixture
def persistent_memory():
    return PersistentMemory()

@pytest.mark.asyncio
@patch("memory.persistent.async_session_factory")
async def test_persistent_memory_get_profile(mock_session_factory, persistent_memory):
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    patient_id = uuid.uuid4()
    mock_patient = Patient(id=patient_id, name="Test Patient", language_pref="en")
    mock_session.get.return_value = mock_patient
    
    profile = await persistent_memory.get_patient_profile(str(patient_id))
    
    assert profile["name"] == "Test Patient"
    assert profile["language_pref"] == "en"

@pytest.mark.asyncio
@patch("memory.manager.PersistentMemory")
@patch("memory.manager.SessionMemory")
async def test_memory_manager_get_context(mock_session_class, mock_persistent_class):
    mock_session = AsyncMock()
    mock_session_class.return_value = mock_session
    mock_persistent = AsyncMock()
    mock_persistent_class.return_value = mock_persistent
    
    mock_session.get_intent.return_value = "book_appointment"
    mock_session.get_entities.return_value = {"date": "tomorrow"}
    mock_session.get_state.return_value = "COLLECTING_INFO"
    mock_session.get_turns.return_value = [{"role": "user", "content": "hello"}]
    
    mock_persistent.get_patient_profile.return_value = {"name": "Test", "language_pref": "en"}
    mock_persistent.get_recent_history.return_value = []
    
    manager = MemoryManager()
    context = await manager.get_context(patient_id="123", session_id="abc")
    
    assert context.intent == "book_appointment"
    assert context.entities == {"date": "tomorrow"}
    assert context.patient_profile["name"] == "Test"
    assert "Test" in context.formatted_prompt
