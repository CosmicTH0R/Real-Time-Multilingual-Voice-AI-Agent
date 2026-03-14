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

from config import Settings, LLMProvider
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


class AgentCore:
    """
    LLM Agent with tool-calling loop.

    Flow:
      1. Build system prompt + memory context
      2. Call LLM with tools
      3. If tool_call → execute tool → feed result → loop
      4. If text response → return to pipeline
      5. Log reasoning trace at each step
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.llm_provider
        self.tracer = ReasoningTracer()
        self._max_tool_iterations = 5

    async def process(
        self,
        user_message: str,
        memory_context: Any | None = None,
        language: str = "en",
        session_id: str = "",
    ) -> AgentResponse:
        """
        Process a user message through the agentic loop.
        """
        self.tracer.reset()
        self.tracer.trace("input", {"message": user_message, "language": language})

        # Build system prompt with memory context
        context_str = ""
        if memory_context:
            context_str = memory_context.to_prompt_context()

        system_prompt = build_system_prompt(language=language, context=context_str)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Add conversation history from memory
        if memory_context and memory_context.conversation_turns:
            # Insert previous turns before current user message
            history_msgs = []
            for turn in memory_context.conversation_turns[-10:]:  # Last 10 turns
                history_msgs.append({
                    "role": turn["role"],
                    "content": turn["content"],
                })
            # Insert history before the current user message
            messages = [messages[0]] + history_msgs + [messages[-1]]

        tools_called = []

        # ── Agentic tool-calling loop ──
        for iteration in range(self._max_tool_iterations):
            self.tracer.trace("llm_call", {"iteration": iteration, "provider": self.provider.value})

            try:
                if self.provider == LLMProvider.OPENAI:
                    response = await self._call_openai(messages)
                else:
                    response = await self._call_gemini(messages)
            except Exception as exc:
                logger.error("LLM call failed (provider=%s): %s", self.provider.value, exc)
                # Try fallback provider
                if self.provider == LLMProvider.OPENAI:
                    logger.info("Falling back to Gemini")
                    try:
                        response = await self._call_gemini(messages)
                    except Exception as exc2:
                        logger.error("Fallback also failed: %s", exc2)
                        return AgentResponse(
                            text=self._error_response(language),
                            reasoning_traces=self.tracer.get_traces(),
                            language=language,
                        )
                else:
                    return AgentResponse(
                        text=self._error_response(language),
                        reasoning_traces=self.tracer.get_traces(),
                        language=language,
                    )

            # Check if response contains tool calls
            if response.get("tool_calls"):
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])

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
                        "tool_calls": [tool_call],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", f"call_{tool_name}"),
                        "content": json.dumps(tool_result, default=str),
                    })

                continue  # Loop to get next LLM response

            # No tool calls — we have a final text response
            final_text = response.get("content", "")
            self.tracer.trace("response", {"text": final_text})

            return AgentResponse(
                text=final_text,
                reasoning_traces=self.tracer.get_traces(),
                tools_called=tools_called,
                language=language,
            )

        # Max iterations reached
        return AgentResponse(
            text=self._error_response(language),
            reasoning_traces=self.tracer.get_traces(),
            tools_called=tools_called,
            language=language,
        )

    async def _call_openai(self, messages: list[dict]) -> dict:
        """Call OpenAI GPT-4o API."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        response = await client.chat.completions.create(
            model=self.settings.openai_model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=500,
        )

        choice = response.choices[0]
        result = {"content": choice.message.content}

        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return result

    async def _call_gemini(self, messages: list[dict]) -> dict:
        """Call Google Gemini API."""
        import google.generativeai as genai

        genai.configure(api_key=self.settings.gemini_api_key)

        model = genai.GenerativeModel(
            self.settings.gemini_model,
            tools=self._gemini_tools(),
        )

        # Convert messages to Gemini format
        gemini_history = []
        system_instruction = ""

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                gemini_history.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant" and msg.get("content"):
                gemini_history.append({"role": "model", "parts": [msg["content"]]})
            elif msg["role"] == "tool":
                gemini_history.append({
                    "role": "user",
                    "parts": [f"Tool result: {msg['content']}"],
                })

        # Use system instruction if available
        if system_instruction:
            model = genai.GenerativeModel(
                self.settings.gemini_model,
                system_instruction=system_instruction,
                tools=self._gemini_tools(),
            )

        chat = model.start_chat(history=gemini_history[:-1] if gemini_history else [])

        last_message = gemini_history[-1]["parts"][0] if gemini_history else ""
        response = await chat.send_message_async(last_message)

        # Parse response
        result = {"content": ""}

        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    result["content"] = part.text
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    if "tool_calls" not in result:
                        result["tool_calls"] = []
                    result["tool_calls"].append({
                        "id": f"call_{fc.name}",
                        "function": {
                            "name": fc.name,
                            "arguments": json.dumps(dict(fc.args)),
                        },
                    })

        return result

    def _gemini_tools(self) -> list:
        """Convert OpenAI tool definitions to Gemini format."""
        import google.generativeai as genai

        gemini_tools = []
        for tool_def in TOOL_DEFINITIONS:
            func = tool_def["function"]
            params = func.get("parameters", {})
            # Gemini uses a simplified schema
            gemini_tools.append(
                genai.protos.Tool(
                    function_declarations=[
                        genai.protos.FunctionDeclaration(
                            name=func["name"],
                            description=func["description"],
                            parameters=genai.protos.Schema(
                                type=genai.protos.Type.OBJECT,
                                properties={
                                    k: genai.protos.Schema(
                                        type=genai.protos.Type.STRING,
                                        description=v.get("description", ""),
                                    )
                                    for k, v in params.get("properties", {}).items()
                                },
                                required=params.get("required", []),
                            ),
                        )
                    ]
                )
            )
        return gemini_tools

    def _error_response(self, language: str) -> str:
        """Return a polite error message in the appropriate language."""
        errors = {
            "en": "I'm sorry, I encountered an issue processing your request. Could you please try again?",
            "hi": "मुझे खेद है, आपके अनुरोध को संसाधित करने में कोई समस्या हुई। कृपया पुनः प्रयास करें।",
            "ta": "மன்னிக்கவும், உங்கள் கோரிக்கையை செயலாக்குவதில் சிக்கல் ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.",
        }
        return errors.get(language, errors["en"])
