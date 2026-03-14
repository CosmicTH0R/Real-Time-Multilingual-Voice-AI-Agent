# Memory Architecture

To build a conversational agent that feels natural, it must remember context gracefully without blowing up the context window. We implemented a **Two-Tier Memory Architecture**.

## Session Memory (Redis)
* **Purpose**: Keep track of the current conversation flow, state, extracted entities, and turn history.
* **Storage**: Redis, utilizing its in-memory key-value store.
* **TTL**: 30 minutes. If the patient goes silent for 30 minutes, the session is cleared.
* **Data Stored**:
    * `intent`: What the user is trying to accomplish currently (e.g. `reschedule_appointment`).
    * `entities`: Key-value pairs extracted so far (e.g. `{"date": "tomorrow", "specialty": "Cardiology"}`).
    * `state`: The state machine phase (e.g. `COLLECTING_INFO` -> `CONFIRMING` -> `EXECUTING`).
    * `turns`: An array of the last N conversation turns (to avoid context bloat).

## Persistent Memory (PostgreSQL)
* **Purpose**: Remember the patient across multiple interactions. Provide a deeply personalized experience.
* **Storage**: PostgreSQL with JSONB columns. Permanent storage.
* **Data Stored**:
    * `language_preference`: What language the patient usually speaks (English, Hindi, or Tamil). Auto-updates if they switch mid-conversation.
    * `appointment_history`: Summaries of prior completed, missed, or cancelled appointments.
    * `preferences`: Any explicit preferences extracted from past calls (e.g., "I prefer morning slots").

## Retrieval and Prompt Injection (`MemoryManager`)

Before every LLM inference call, the `MemoryManager` fetches both Session and Persistent memory and unifies them into a single `MemoryContext` object. 

This context is injected dynamically into the system prompt:

```text
CURRENT PATIENT CONTEXT:
- Name: Rahul Sharma
- Preferred Language: hi
- Recent History: Cancelled appt with Dr. Smith yesterday.
- Current Intent: reschedule_appointment
- Extracted Entities: {"date": "friday"}
```

This strict layout dramatically improves LLM tool-calling accuracy while consuming < 150 tokens.
