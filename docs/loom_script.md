# 🎥 Voice AI Agent — Loom Walkthrough Script

**Duration**: ~3-5 minutes  
**Goal**: Demonstrate the system architecture, real-time voice capabilities, conflict resolution, multilingual support, and agentic reasoning traces.

---

## 1. Introduction (0:00 - 0:30)
**Visual:** Screen showing the frontend web client (`localhost:5173`).
> "Hi everyone, this is a demonstration of the Real-Time Multilingual Voice AI Agent I designed for clinical appointment booking. The goal of this system is to handle end-to-end patient scheduling across multiple languages via a natural voice interface, with strict sub-500 millisecond latency and zero double-booking."

## 2. Architecture & Tech Stack (0:30 - 1:00)
**Visual:** Switch to your IDE showing `docs/architecture.md` diagram or the project structure.
> "On the backend, I built a Python FastAPI gateway connecting to a TypeScript Vite frontend via WebSockets. 
> 
> To achieve ultra-low latency, I implemented Pipeline Overlapping: Deepgram handles streaming Speech-to-Text with VAD chunking. As soon as the transcript is ready, we concurrently fetch session memory from Redis and patient history from PostgreSQL. The context is injected into the LLM Agent—using OpenAI or Gemini—and the response is streamed directly to Google Cloud TTS, which chunks audio back to the browser."

## 3. Demo 1: Core Booking Flow (1:00 - 1:45)
**Visual:** Switch back to the web client. Expand the "Reasoning Traces" debug panel on the right.
> "Let's test the primary workflow. I'll ask to book a cardiology appointment."
> 
> **(Action)**: Click microphone and say: *"Hi, I need to book an appointment with a cardiologist tomorrow morning."*
> 
> "As you can see, the agent instantly retrieves the available slots. On the right, the Reasoning Trace panel shows exactly what the LLM is doing behind the scenes: evaluating intent, extracting the 'Cardiology' entity, and executing the `check_availability` SQL tool natively before generating a voice response."

## 4. Demo 2: Conflict Resolution & Locking (1:45 - 2:30)
**Visual:** Frontend web client.
> "A major challenge in scheduling AI is race conditions. In `scheduling/engine.py`, I implemented strict PostgreSQL `SELECT ... FOR UPDATE` row-level locks. Let's try to double-book a slot."
> 
> **(Action)**: Say *"Actually, I want whatever slot the previous patient just took."* (Or ask for a specific doctor/time you know is full). 
> 
> "The engine explicitly blocks the transaction, and the Conflict Resolver immediately suggests nearby alternative slots for the same doctor, or same-day slots for a different doctor in the same department."

## 5. Demo 3: Multilingual Support (2:30 - 3:00)
**Visual:** Frontend web client.
> "The system dynamically detects languages based on script and Deepgram heuristics. Let's switch contexts."
> 
> **(Action)**: Say something in Hindi or Tamil. For example: *"Mujhe kal subah doctor se milna hai."* (I need to see the doctor tomorrow morning).
> 
> "The persistent memory in PostgreSQL immediately logs this language preference so future sessions default to it, and the TTS engine automatically switches to the appropriate Indic Wavenet voice profile."

## 6. Demo 4: Barge-in / Interruptions (3:00 - 3:30)
**Visual:** Frontend web client.
> "Finally, conversational AI needs to handle interruptions gracefully."
> 
> **(Action)**: Ask a broad question: *"What are the doctor's available times?"* When the AI starts listing them off, interrupt loudly: *"Actually, cancel that, just book Friday!"*
> 
> "The WebSocket immediately detects the user speaking, cancels the active TTS audio playback stream, and seamlessly re-routes the new utterance into the pipeline without hallucinating."

## 7. Conclusion (3:30 - 4:00)
**Visual:** Show `docker-compose.yml` or just a final shot of the UI.
> "In summary, we have a fully containerized, production-ready Voice AI agent capable of tool-calling, strict database mutation, session TTL memory management, and dynamic language switching, all operating within a strict latency budget. 
> 
> Thanks for watching!"
