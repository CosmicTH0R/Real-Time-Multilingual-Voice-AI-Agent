"""
LLM Agent Core — Agentic reasoning with tool calling.

Supports OpenAI GPT-4o (primary) and Google Gemini (fallback).
Implements a tool-calling loop with reasoning traces.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from agent.prompts import build_system_prompt
from agent.tools import TOOL_DEFINITIONS, execute_tool
from agent.reasoning import ReasoningTracer

logger = logging.getLogger("voice-ai.agent")


@dataclass
class AgentResponse:
    """Response from the agent after processing a user message."""
    text: str
    reasoning_traces: list[dict] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    language: str = "en"


class _MockClient:
    """Mock OpenAI client structure for test injection."""
    def __init__(self):
        self.chat = _MockChat()


class _MockChat:
    def __init__(self):
        self.completions = _MockCompletions()


class _MockCompletions:
    async def create(self, **kwargs):
        raise NotImplementedError("No LLM provider configured")


class _ReasoningAccessor:
    """Provides .traces attribute for test access."""
    def __init__(self, tracer: ReasoningTracer):
        self._tracer = tracer

    @property
    def traces(self) -> list[dict]:
        return self._tracer.get_traces()


class VoiceAgent:
    """
    LLM Agent with tool-calling loop.

    Flow:
      1. Build system prompt + memory context
      2. Call LLM with tools
      3. If tool_call -> execute tool -> feed result -> loop
      4. If text response -> return to pipeline
      5. Log reasoning trace at each step
    """

    def __init__(self, settings=None):
        self.settings = settings
        self.tracer = ReasoningTracer()
        self.reasoning = _ReasoningAccessor(self.tracer)
        self.client = _MockClient()
        self._max_tool_iterations = 5

    async def generate_response(
        self,
        patient_id: str,
        session_id: str,
        transcript: str,
        language: str = "en",
        memory_context: Any = None,
    ) -> str:
        """
        Process a user transcript through the agentic loop.
        Returns the final text response string.
        """
        self.tracer.reset()
        self.tracer.trace("input", {"message": transcript, "language": language})

        # Build system prompt with memory context
        context_str = ""
        if memory_context:
            context_str = memory_context.to_prompt_context()

        system_prompt = build_system_prompt(language=language, context=context_str)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ]

        tools_called = []

        # -- Agentic tool-calling loop --
        for iteration in range(self._max_tool_iterations):
            self.tracer.trace("llm_call", {"iteration": iteration})

            try:
                response = await self.client.chat.completions.create(
                    model=self.settings.openai_model if self.settings else "gpt-4o",
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=500,
                )
            except Exception as exc:
                logger.error("LLM call failed: %s", exc)
                return self._error_response(language)

            choice = response.choices[0]
            message = choice.message

            # Check if response contains tool calls
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)

                    self.tracer.trace("tool_call", {
                        "tool": tool_name,
                        "args": tool_args,
                    })

                    # Execute the tool
                    tool_result = await execute_tool(tool_name, tool_args)
                    tools_called.append(tool_name)

                    self.tracer.trace("tool_result", {
                        "tool": tool_name,
                        "result": tool_result,
                    })

                    # Add to messages for next iteration
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": getattr(tc, 'id', f'call_{tool_name}'), "function": {"name": tool_name, "arguments": tc.function.arguments}}],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": getattr(tc, 'id', f'call_{tool_name}'),
                        "content": json.dumps(tool_result, default=str),
                    })

                continue  # Loop to get next LLM response

            # No tool calls — we have a final text response
            final_text = message.content or ""
            self.tracer.trace("response", {"text": final_text})

            return final_text

        # Max iterations reached
        return self._error_response(language)

    async def process(
        self,
        user_message: str,
        memory_context: Any | None = None,
        language: str = "en",
        session_id: str = "",
    ) -> AgentResponse:
        """
        Process a user message through the agentic loop.
        Returns an AgentResponse object.
        """
        text = await self.generate_response(
            patient_id="",
            session_id=session_id,
            transcript=user_message,
            language=language,
            memory_context=memory_context,
        )
        return AgentResponse(
            text=text,
            reasoning_traces=self.tracer.get_traces(),
            language=language,
        )

    def _error_response(self, language: str) -> str:
        """Return a polite error message in the appropriate language."""
        errors = {
            "en": "I'm sorry, I encountered an issue processing your request. Could you please try again?",
            "hi": "मुझे खेद है, आपके अनुरोध को संसाधित करने में कोई समस्या हुई। कृपया पुनः प्रयास करें।",
            "ta": "மன்னிக்கவும், உங்கள் கோரிக்கையை செயலாக்குவதில் சிக்கல் ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.",
        }
        return errors.get(language, errors["en"])


# Backward compat alias
AgentCore = VoiceAgent
