"""
Agent Tool Definitions & Execution.

Tools available to the LLM:
  - check_availability
  - book_appointment
  - reschedule_appointment
  - cancel_appointment
  - get_patient_history
  - get_doctor_info
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("voice-ai.tools")

# ══════════════════════════════════════════════════════
# Tool Definitions (OpenAI function-calling format)
# ══════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a doctor or specialization on a given date. Returns available time slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Name of the doctor (optional if specialization is provided)",
                    },
                    "specialization": {
                        "type": "string",
                        "description": "Medical specialization (e.g., 'Cardiology', 'Dermatology')",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check availability for (YYYY-MM-DD format)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for a patient with a specific doctor at a given time slot. Validates availability and prevents double-booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "UUID of the patient",
                    },
                    "doctor_id": {
                        "type": "string",
                        "description": "UUID of the doctor",
                    },
                    "slot_id": {
                        "type": "string",
                        "description": "UUID of the time slot to book",
                    },
                },
                "required": ["patient_id", "doctor_id", "slot_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new time slot. Frees the old slot and books the new one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to reschedule",
                    },
                    "new_slot_id": {
                        "type": "string",
                        "description": "UUID of the new time slot",
                    },
                },
                "required": ["appointment_id", "new_slot_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment and free up the time slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to cancel",
                    },
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_history",
            "description": "Retrieve a patient's appointment history, preferences, and past interactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "UUID of the patient",
                    },
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctor_info",
            "description": "Get information about a doctor by name or specialization, including their available slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Name of the doctor",
                    },
                    "specialization": {
                        "type": "string",
                        "description": "Medical specialization to search for",
                    },
                },
                "required": [],
            },
        },
    },
]


# ══════════════════════════════════════════════════════
# Tool Execution
# ══════════════════════════════════════════════════════

async def execute_tool(tool_name: str, args: dict) -> dict:
    """
    Execute a tool by name with given arguments.
    Routes to scheduling engine functions.
    """
    from scheduling.engine import SchedulingEngine

    engine = SchedulingEngine()

    try:
        if tool_name == "check_availability":
            return await engine.check_availability(
                doctor_name=args.get("doctor_name"),
                specialization=args.get("specialization"),
                date=args.get("date"),
            )

        elif tool_name == "book_appointment":
            return await engine.book_appointment(
                patient_id=args["patient_id"],
                doctor_id=args["doctor_id"],
                slot_id=args["slot_id"],
            )

        elif tool_name == "reschedule_appointment":
            return await engine.reschedule_appointment(
                appointment_id=args["appointment_id"],
                new_slot_id=args["new_slot_id"],
            )

        elif tool_name == "cancel_appointment":
            return await engine.cancel_appointment(
                appointment_id=args["appointment_id"],
            )

        elif tool_name == "get_patient_history":
            return await engine.get_patient_history(
                patient_id=args["patient_id"],
            )

        elif tool_name == "get_doctor_info":
            return await engine.get_doctor_info(
                doctor_name=args.get("doctor_name"),
                specialization=args.get("specialization"),
            )

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        logger.error("Tool execution error (%s): %s", tool_name, exc)
        return {"error": str(exc)}
