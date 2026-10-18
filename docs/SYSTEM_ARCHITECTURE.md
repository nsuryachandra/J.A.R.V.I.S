# JARVIS — System Architecture

## 1. Architectural Principles

1. **Stateless Compute, Stateful Storage:** The web and worker nodes are stateless, horizontally scalable, and resilient to cloud restarts. All state lives in PostgreSQL, Redis (or in-memory cache with DB fallback), and object storage.
2. **Deterministic Governance:** The LLM does not make policy, access-control, or financial decisions. The application framework deterministically validates every request, model proposed action, and tool parameter.
3. **Decoupled Provider Layer:** AI providers (NVIDIA NIM, ElevenLabs) are abstracted behind strict gateway interfaces (`LLMProvider`, `TTSProvider`), enabling painless swapping or mocking without touching business logic.
4. **Timezone Accuracy:** All database timestamps are strictly stored in UTC with timezone awareness. User temporal interactions are mapped to the user's localized timezone (`Asia/Kolkata`).
5. **Observability & Auditability:** Every tool invocation, agent transition, permission check, and model call is assigned a unique trace ID and logged to an immutable audit ledger.

---

## 2. Logical Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        User Interfaces (Client)                         │
│  ┌───────────────────────┐  ┌────────────────────┐  ┌────────────────┐ │
│  │ Hologram Dashboard UI │  │ Web Companion / PWA│  │ Voice & Audio  │ │
│  └───────────┬───────────┘  └─────────┬──────────┘  └────────┬───────┘ │
└──────────────┼────────────────────────┼──────────────────────┼─────────┘
               │                        │                      │
               ▼                        ▼                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      API Gateway & Security Layer                      │
│  - FastAPI Web Framework                                               │
│  - JWT / Session Authentication & Rate Limiting                         │
│  - WebSocket Real-time Event Broadcaster                               │
│  - CORS, Request Validation (Pydantic v2)                              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          JARVIS Orchestrator                           │
│  - Context Assembler (Temporal Context + Active Tasks + User Profile)  │
│  - Intent Classifier & Router                                          │
│  - Plan Synthesizer & Sub-Agent Coordinator                            │
│  - Model Tool Call Dispatcher                                          │
│  - Response Synthesizer & Verification Gate                            │
└───────────────────┬───────────────────────────────┬────────────────────┘
                    │                               │
                    ▼                               ▼
┌─────────────────────────────────────┐  ┌───────────────────────────────┐
│     Policy & Permission Broker      │  │     Model & Provider Gateway  │
│  - Role & Capability Checks         │  │  - NVIDIA NIM Router          │
│  - Risk Tier Classifier             │  │    (Llama 3.3, Nemotron, etc.)│
│    (Safe / Moderate / Consequential)│  │  - ElevenLabs Voice Synthesizer│
│  - Approval Token Manager           │  │  - Embeddings & Vector Search │
│  - Immutable Audit Ledger           │  │  - Fallback & Retry Policies   │
└───────────────────┬─────────────────┘  └───────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       Specialized Sub-Agents & Tools                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Memory Agent │  │ Task & Proj. │  │ Routine/Time │  │ Research Ag.│ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Coding Agent │  │ Browser Agent│  │ Vision Agent │  │ Comm/Calls  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                             Storage Layer                              │
│  - PostgreSQL Database (Users, Tasks, Routines, Memories, Approvals)   │
│  - pgvector Extension (Semantic Memory Embeddings)                     │
│  - S3-compatible Object Storage (Artifacts, Voice Cache, Screenshots)  │
│  - In-Memory / Redis Queue (Async Worker & Cron Scheduler)             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Subsystem Breakdown

### 3.1 API Gateway & Session Layer
* **Technology:** FastAPI (Python 3.11+), ASGI (Uvicorn), WebSockets.
* **Responsibilities:** Request parsing, authentication, CORS, rate limiting, SSE / WebSocket event dispatch.
* **Non-Responsibilities:** Business workflow coordination or direct tool execution.

### 3.2 JARVIS Orchestrator
* **Responsibilities:**
  * Ingests user input (text or audio transcription).
  * Injects current temporal context (e.g. `Current Time: 2026-10-18T13:20:00+05:30 (Asia/Kolkata)`).
  * Retrieves relevant memories and pending tasks.
  * Prompts the reasoning model for plans and tool proposals.
  * Coordinates multi-agent workflows.

### 3.3 Policy & Permission Broker
* **Responsibilities:**
  * Validates every tool request against user security profile.
  * Intercepts `CONSEQUENTIAL` risk actions (e.g. `send_email`, `execute_bash`, `place_order`, `delete_data`).
  * Emits pending approval events to the client.
  * Verifies cryptographic approval tokens before unlocking tool execution.

### 3.4 Storage & Memory Subsystem
* **Dual Layer Memory:**
  1. *Episodic / Short-Term:* Redis / DB conversation history within the active session.
  2. *Declarative / Long-Term:* PostgreSQL tables with `pgvector` embeddings, confidence scores, source provenance, and privacy classifications.

---

## 4. Technology Stack Selection

| Component | Selected Technology | Rationale |
|---|---|---|
| **Backend Framework** | **Python 3.11+ / FastAPI** | High performance async I/O; native AI ecosystem support; first-class Pydantic schema validation. |
| **Database** | **PostgreSQL + pgvector** | Robust relational integrity for tasks/events + vector search for semantic memory without needing external vector DBs. |
| **AI LLM Endpoints** | **NVIDIA NIM APIs** | Enterprise-grade hosted models (Llama 3.3 70B, Nemotron, Mixtral) with OpenAI-compatible API schemas. |
| **Speech & Voice** | **ElevenLabs API** | Best-in-class natural TTS with granular voice profile settings (speed, stability, style) and multi-locale support. |
| **Frontend Framework** | **Vite + React / TypeScript** | Ultra-responsive rendering, modular component hierarchy, native Web Audio API support for holographic HUD and waveforms. |
| **Styling** | **Vanilla CSS + Modern Tokens** | Sleek glassmorphism, glowing cyan/blue orbital HUD, zero bloat, maximum design control. |
| **Scheduler** | **APScheduler / Render Cron** | Reliable UTC-to-local schedule resolution for briefings, check-ins, and reminders. |
