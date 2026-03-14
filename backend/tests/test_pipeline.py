import pytest
from unittest.mock import AsyncMock, patch

from backend.pipeline.orchestrator import PipelineOrchestrator

@pytest.fixture
def orchestrator():
    return PipelineOrchestrator()

@pytest.mark.asyncio
@patch("backend.pipeline.orchestrator.STTPipeline")
@patch("backend.pipeline.orchestrator.TTSPipeline")
@patch("backend.pipeline.orchestrator.VoiceAgent")
@patch("backend.pipeline.orchestrator.MemoryManager")
async def test_end_to_end_pipeline(MockMemory, MockAgent, MockTTS, MockSTT, orchestrator):
    # Setup mocks
    mock_stt = MockSTT.return_value
    mock_tts = MockTTS.return_value
    mock_agent = MockAgent.return_value
    mock_memory = MockMemory.return_value
    
    # Mock agent response
    mock_agent.generate_response.return_value = "Your appointment is confirmed."
    
    # Run the orchestrator process utterance manually
    response_text = await orchestrator.process_utterance(
        patient_id="123",
        session_id="abc",
        transcript="Book an appointment",
        is_final=True
    )
    
    assert response_text == "Your appointment is confirmed."
    
    # Verify memory injection was called
    mock_memory.get_context.assert_called_once()
    
    # Verify agent was called
    mock_agent.generate_response.assert_called_once()

@pytest.mark.asyncio
async def test_barge_in_handling(orchestrator):
    # Simulate a barge in event
    orchestrator.tts.stop_streaming = AsyncMock()
    
    await orchestrator.handle_barge_in("abc")
    
    # Ensure TTS streaming is stopped
    assert orchestrator.tts.stop_streaming.called
