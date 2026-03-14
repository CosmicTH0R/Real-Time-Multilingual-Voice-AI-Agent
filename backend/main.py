"""
Real-Time Multilingual Voice AI Agent — FastAPI Application

Main entry point providing:
- WebSocket endpoint for real-time voice conversations
- REST endpoints for session management and campaigns
- Latency statistics endpoint
"""

from __future__ import annotations

import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from db.connection import init_db, close_db
from memory.manager import MemoryManager
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.latency import LatencyStats

# ── Logging ──
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("voice-ai")

settings = get_settings()

# ── Global state ──
latency_stats = LatencyStats()
memory_manager: MemoryManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global memory_manager

    logger.info("🚀  Starting Voice AI Agent  (mock_mode=%s)", settings.mock_mode)
    await init_db()
    memory_manager = await MemoryManager.create(settings)
    logger.info("✅  Database & Memory initialised")

    yield

    await close_db()
    if memory_manager:
        await memory_manager.close()
    logger.info("👋  Shutdown complete")


app = FastAPI(
    title="Voice AI Agent",
    description="Real-time multilingual clinical appointment booking agent",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════
# REST Endpoints
# ══════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Simple health check."""
    return {"status": "ok", "mock_mode": settings.mock_mode}


@app.post("/api/session/start")
async def start_session(patient_id: str | None = None):
    """
    Create a new voice session.
    Returns a session_id to use with the WebSocket endpoint.
    """
    session_id = str(uuid.uuid4())
    if memory_manager:
        await memory_manager.create_session(session_id, patient_id)
    logger.info("Session created: %s (patient=%s)", session_id, patient_id)
    return {"session_id": session_id, "patient_id": patient_id}


@app.get("/api/latency/stats")
async def get_latency_stats():
    """Return aggregated latency statistics."""
    return latency_stats.summary()


@app.post("/api/campaigns/trigger")
async def trigger_campaign(campaign_id: str):
    """Trigger an outbound campaign."""
    # Will be fully implemented in Phase 9
    logger.info("Campaign triggered: %s", campaign_id)
    return {"campaign_id": campaign_id, "status": "queued"}


@app.get("/api/campaigns/{campaign_id}/status")
async def get_campaign_status(campaign_id: str):
    """Get campaign execution status."""
    # Will be fully implemented in Phase 9
    return {"campaign_id": campaign_id, "status": "pending", "completed": 0, "total": 0}


# ══════════════════════════════════════════════════════
# WebSocket — Voice Conversation
# ══════════════════════════════════════════════════════

@app.websocket("/ws/voice/{session_id}")
async def voice_websocket(websocket: WebSocket, session_id: str):
    """
    Main voice conversation WebSocket.

    Protocol:
      Client → Server:
        - Binary frames: raw audio PCM 16kHz 16-bit mono
        - JSON frames:   {"type": "control", "action": "...", ...}
      Server → Client:
        - Binary frames: synthesised audio chunks
        - JSON frames:   {"type": "transcript"|"reasoning"|"status", ...}
    """
    await websocket.accept()
    logger.info("WS connected: session=%s", session_id)

    orchestrator = PipelineOrchestrator(
        settings=settings,
        memory_manager=memory_manager,
        latency_stats=latency_stats,
        session_id=session_id,
    )

    try:
        await orchestrator.initialise()

        while True:
            data = await websocket.receive()

            if "bytes" in data:
                # Raw audio data from microphone
                audio_chunk = data["bytes"]
                responses = await orchestrator.process_audio(audio_chunk)

                for resp in responses:
                    if resp["type"] == "audio":
                        await websocket.send_bytes(resp["data"])
                    else:
                        await websocket.send_json(resp)

            elif "text" in data:
                import orjson
                msg = orjson.loads(data["text"])
                msg_type = msg.get("type", "")

                if msg_type == "control":
                    action = msg.get("action", "")
                    if action == "barge_in":
                        await orchestrator.handle_barge_in()
                    elif action == "set_language":
                        await orchestrator.set_language(msg.get("language", "en"))
                    elif action == "end_session":
                        break

                elif msg_type == "text_input":
                    # Allow text-based input for testing
                    text = msg.get("text", "")
                    responses = await orchestrator.process_text(text)
                    for resp in responses:
                        if resp["type"] == "audio":
                            await websocket.send_bytes(resp["data"])
                        else:
                            await websocket.send_json(resp)

    except WebSocketDisconnect:
        logger.info("WS disconnected: session=%s", session_id)
    except Exception as exc:
        logger.exception("WS error session=%s: %s", session_id, exc)
    finally:
        await orchestrator.cleanup()
        logger.info("WS cleanup done: session=%s", session_id)
