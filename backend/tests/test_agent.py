import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.agent.core import VoiceAgent
from backend.agent.prompts import SYSTEM_PROMPT_TEMPLATE

@pytest.fixture
def agent():
    return VoiceAgent()

@pytest.mark.asyncio
@patch("backend.agent.core.execute_tool")
async def test_agent_tool_calling_loop(mock_execute_tool, agent):
    # Mock LLM generation to return a tool call
    mock_response = MagicMock()
    
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "check_availability"
    mock_tool_call.function.arguments = '{"specialization": "Cardiology"}'
    
    mock_message = MagicMock()
    mock_message.tool_calls = [mock_tool_call]
    mock_message.content = None
    mock_response.choices = [MagicMock(message=mock_message)]
    
    # Second iteration mocked to return final text
    mock_response2 = MagicMock()
    mock_message2 = MagicMock()
    mock_message2.tool_calls = None
    mock_message2.content = "Dr. Smith is available tomorrow."
    mock_response2.choices = [MagicMock(message=mock_message2)]
    
    agent.client.chat.completions.create = AsyncMock(side_effect=[mock_response, mock_response2])
    
    # Mock tool execution return
    mock_execute_tool.return_value = {"available": True, "slots": []}
    
    response = await agent.generate_response(
        patient_id="123",
        session_id="abc",
        transcript="Is there a cardiologist available?",
        language="en"
    )
    
    assert response == "Dr. Smith is available tomorrow."
    assert mock_execute_tool.called
    assert len(agent.reasoning.traces) > 0
    
@pytest.mark.asyncio
async def test_agent_ambiguous_input(agent):
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.tool_calls = None
    mock_message.content = "What department do you need?"
    mock_response.choices = [MagicMock(message=mock_message)]
    
    agent.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    response = await agent.generate_response(
        patient_id="123", session_id="abc",
        transcript="I need a doctor.", language="en"
    )
    
    assert response == "What department do you need?"
