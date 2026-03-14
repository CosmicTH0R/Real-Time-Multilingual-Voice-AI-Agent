# 🏥 Real-Time Multilingual Voice AI Agent

> Clinical Appointment Booking — A real-time voice AI agent that manages clinical appointments through natural voice conversations in English, Hindi, and Tamil.

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue.svg)](https://typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    TypeScript Web Client                        │
│  [Mic Capture] → WebSocket ← [Audio Playback + Transcript UI]  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket (binary audio + JSON)
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Gateway (Python)                       │
│                                                                  │
│  ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌────────────┐  │
│  │ STT      │──▶│ LLM Agent │──▶│ TTS      │──▶│ WS Stream  │  │
│  │ Deepgram │   │ GPT-4o /  │   │ Google   │   │ Back to    │  │
│  │ Streaming│   │ Gemini    │   │ Cloud    │   │ Client     │  │
│  └──────────┘   └─────┬─────┘   └──────────┘   └────────────┘  │
│                       │                                          │
│         ┌─────────────┼─────────────┐                           │
│         ▼             ▼             ▼                            │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐                     │
│  │ Scheduling │ │ Memory   │ │ Campaign  │                     │
│  │ Engine     │ │ Manager  │ │ Manager   │                     │
│  └─────┬──────┘ └────┬─────┘ └─────┬─────┘                     │
│        ▼             ▼             ▼                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │PostgreSQL│  │  Redis   │  │Redis Queue│                      │
│  └──────────┘  └──────────┘  └──────────┘                       │
└──────────────────────────────────────────────────────────────────┘
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Real-time Voice** | WebSocket streaming STT → LLM → TTS pipeline |
| **Multilingual** | English, Hindi, Tamil with auto-detection |
| **Agentic Reasoning** | Tool-calling loop with visible reasoning traces |
| **Dual LLM Support** | OpenAI GPT-4o primary, Gemini fallback (free) |
| **Scheduling Engine** | DB-level locking, conflict resolution, alternatives |
| **Contextual Memory** | Redis session (TTL) + PostgreSQL persistent |
| **Outbound Campaigns** | Reminder/follow-up calls via background workers |
| **Barge-in Support** | Interrupt agent mid-speech |
| **Latency Tracking** | Per-utterance breakdown (target < 450ms) |
| **Mock Mode** | Full pipeline testing without API costs |

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- API Keys (optional — `MOCK_MODE=true` works without them)

### 1. Clone & Configure

```bash
git clone https://github.com/CosmicTH0R/Real-Time-Multilingual-Voice-AI-Agent.git
cd Real-Time-Multilingual-Voice-AI-Agent

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys (or leave MOCK_MODE=true)
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

### 3. Open the UI

Navigate to **http://localhost:5173** in your browser.

### Local Development (without Docker)

```bash
# Backend
cd backend
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m db.seed                # Seed sample data
uvicorn main:app --reload        # Start API server

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Project Structure

```
voice-ai-agent/
├── docker-compose.yml          # All services (PG, Redis, backend, frontend, worker)
├── .env.example                # Configuration template
│
├── backend/
│   ├── main.py                 # FastAPI app + WebSocket endpoint
│   ├── config.py               # Pydantic settings
│   ├── pipeline/
│   │   ├── orchestrator.py     # STT → Memory → Agent → TTS pipeline
│   │   ├── stt.py              # Deepgram streaming STT
│   │   ├── tts.py              # Google Cloud TTS
│   │   └── latency.py          # Per-utterance latency tracking
│   ├── agent/
│   │   ├── core.py             # LLM agent with tool-calling loop
│   │   ├── tools.py            # 6 scheduling tools
│   │   ├── prompts.py          # Multilingual system prompts
│   │   └── reasoning.py        # Reasoning trace logger
│   ├── scheduling/
│   │   ├── engine.py           # Booking/rescheduling/cancellation
│   │   ├── conflict.py         # Alternative slot suggestions
│   │   └── validators.py       # Booking validation rules
│   ├── memory/
│   │   ├── manager.py          # Unified memory → prompt injection
│   │   ├── session.py          # Redis session memory (TTL)
│   │   └── persistent.py       # PostgreSQL cross-session memory
│   ├── campaigns/
│   │   ├── outbound.py         # Campaign call initiation
│   │   └── worker.py           # RQ background job worker
│   └── db/
│       ├── models.py           # 6 ORM models
│       ├── connection.py       # Async SQLAlchemy engine
│       └── seed.py             # Sample data (doctors, patients, slots)
│
└── frontend/
    ├── index.html              # Main page
    └── src/
        ├── main.ts             # Entry point, event wiring
        ├── websocket.ts        # WebSocket client
        ├── audio.ts            # Mic capture + playback
        ├── ui.ts               # UI controller
        └── styles.css          # Dark theme healthcare UI
```

---

## Architectural Decisions

### Voice Pipeline (Target: < 450ms)

| Stage | Technology | Target Latency | Strategy |
|-------|-----------|---------------|----------|
| STT | Deepgram streaming | ~100ms | WebSocket streaming + VAD |
| Memory | Redis + PostgreSQL | ~20ms | Parallel with STT finalization |
| LLM | GPT-4o / Gemini | ~200ms | Streaming response, first-token |
| TTS | Google Cloud | ~100ms | Chunked streaming delivery |
| Overhead | WebSocket | ~30ms | Keep-alive, connection pooling |

**Key optimizations:**
- Pipeline stages overlap — memory fetch starts during STT finalization
- TTS streams first audio chunk while LLM generates remaining text
- Speculative LLM warm-up on interim STT transcripts

### Memory Design

**Two-tier architecture:**

1. **Session Memory (Redis)** — TTL: 30 min
   - Current intent, collected entities, pending confirmations
   - Conversation turn history (last 10 turns)
   - State machine: `IDLE → COLLECTING_INFO → CONFIRMING → EXECUTING → COMPLETE`

2. **Persistent Memory (PostgreSQL)** — Permanent
   - Patient profile, language preference
   - Appointment history summaries
   - Past conversation logs

**Prompt injection**: `MemoryManager.get_context()` merges both layers into a concise string injected into the LLM system prompt, keeping token usage efficient.

### Scheduling & Conflict Resolution

- **Atomic booking** with `SELECT ... FOR UPDATE` PostgreSQL row-level locks
- **Double-booking prevention** at DB level (not just application logic)
- **Conflict resolution strategies:**
  1. Same doctor, nearby time slots
  2. Same specialization, different doctor

### Multilingual Handling

- Auto-detection via Unicode script analysis + Deepgram `detect_language`
- Language preference persisted per patient across sessions
- System prompt dynamically switches response language
- Separate TTS voice profiles per language

---

## LLM Agent Tools

| Tool | Purpose |
|------|---------|
| `check_availability` | Query available slots by doctor/specialization/date |
| `book_appointment` | Book with conflict check + DB lock |
| `reschedule_appointment` | Release old slot + book new atomically |
| `cancel_appointment` | Cancel + free slot |
| `get_patient_history` | Retrieve appointments, preferences |
| `get_doctor_info` | Lookup doctor details + available count |

All tools execute real DB operations — no hardcoded/simulated responses.

---

## Tradeoffs & Known Limitations

| Tradeoff | Decision | Rationale |
|----------|----------|-----------|
| ScriptProcessorNode (deprecated) | Used for mic capture | Wide browser support, AudioWorklet alternative noted |
| Gemini tool-calling | Simplified schema conversion | Full Gemini native function calling may differ slightly |
| Single-process worker | RQ with Redis | Sufficient for demo; Celery for production scale |
| Mock mode latency | 50ms simulated delays | Real API latency will differ |

**Known limitations:**
- Live Deepgram/TTS integration requires API keys (mock mode available)
- No telephony integration (WebRTC/SIP) — browser-only demo
- Campaign outbound is simulated (no actual phone calls)
- Audio codec is raw PCM — production would use Opus/WebM

---

## Bonus Features

- ✅ **Barge-in handling** — TTS cancellation on user interrupt
- ✅ **Redis-backed memory with TTL** — 30-minute session expiry
- ✅ **Background job queues** — RQ workers for campaign execution
- ⬜ **Horizontal scalability** — Designed for (not yet deployed to) cloud

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v --tb=short
```

---

## License

MIT
