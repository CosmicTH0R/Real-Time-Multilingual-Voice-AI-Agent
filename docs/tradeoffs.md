# Tradeoffs & Known Limitations

Building a production-grade WebRTC/WebSocket Voice AI system involves balancing latency, cost, and complexity.

## Known Limitations

1. **Audio Codecs**: The current implementation streams raw PCM audio (16kHz, 16-bit) over WebSockets. For a true production system over unstable cellular networks, WebRTC using Opus or G.711 codecs is vastly superior to raw PCM over WebSockets due to packet loss resilience (FEC) and jitter buffers.
2. **Gemini Tool-Calling Parity**: While GPT-4o performs natively with JSON Schema function calling, Gemini fallback currently utilizes a slightly abstracted function calling mechanism in the backend. Sometimes intent classification speed dips by ~50ms when falling back.
3. **Outbound Campaign Dialing**: The current outbound campaign logic utilizes Redis Job Queues (RQ) but stops at HTTP/WebSocket mock initiation. Real outbound routing requires SIP/Twilio infrastructure which is out of scope for browser-based mocks. 
4. **Single-Node WebSocket Concurrency**: The FastAPI `WebSocket` implementation is stateful per connection. Scaling horizontally to multiple pods necessitates sticky sessions on the load balancer or externalizing the `SessionMemory` state fully to Redis (which we have partially mitigated by placing session memory in Redis).

## Explicit Tradeoffs

### Deepgram STT vs Local Whisper
* **Tradeoff**: Cost vs Latency.
* **Decision**: We chose Deepgram Streaming WebSocket STT over a local Whisper model. While Local Whisper is free and circumvents network latency, it prevents us from accessing ultra-low latency *streaming* `< 100ms` interim endpointing necessary for fluid barge-in without massive GPU overhead.

### Google Cloud TTS vs ElevenLabs
* **Tradeoff**: Multilingual reliability vs Voice realism.
* **Decision**: We chose Google Cloud TTS for the primary integration because `Wavenet` offers remarkably stable `en-IN`, `hi-IN`, and `ta-IN` voice profiles, whereas ElevenLabs, while sounding strictly better/hyper-realistic, tends to hallucinate phonemes across distinct Indic language switches.

### PostgreSQL Locking vs Redis Redlock
* **Tradeoff**: Throughput vs Data Integrity.
* **Decision**: We utilized strict PostgreSQL `SELECT ... FOR UPDATE` row-level locks on the `time_slots` table. A distributed Redis lock (`Redlock`) would offer higher throughput, but since appointment slots are the core business asset, we opted for CP (Consistency) over AP (Availability) to guarantee zero double bookings.
