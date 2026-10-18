# JARVIS — PRD Analysis

## 1. Executive Summary & Vision
JARVIS is a personal AI operating system designed to run as a cloud-hosted service (targeted initially for Render) that provides human-like, continuous assistance across conversation, memory, tasks, routines, multi-agent delegations, and multimodal inputs (voice, vision, screen, browsing).

Unlike a conventional stateless LLM chat interface, JARVIS acts as a stateful, proactive personal assistant that remembers facts, tracks pending commitments, respects time and date contexts (specifically Asia/Kolkata timezone with Hyderabad context), and requires strict user approval before executing consequential real-world actions.

---

## 2. Scope & Requirement Breakdown

| PRD Section | Category | Core Requirements | Technical Implications |
|---|---|---|---|
| **§1 - §4** | Identity & Principles | Original branding (no copyrighted imitation); Calm, respectful, concise tone; Optional "sir"; Truthful continuity (never hallucinate memories or completed tasks). | System prompt constraints, validation layers to prevent model claims of completion without DB verification. |
| **§7 - §8** | Architecture & Agents | Orchestrator delegates to specialized sub-agents (Memory, Tasks, Routines, Research, Coding, Browser, Vision, Calls, Writing, Business). | Decoupled agent state machines; strict separation between model planning and deterministic tool execution. |
| **§9** | Model Strategy | Primary provider: NVIDIA NIM APIs. Model router for `fast_chat`, `reasoning`, `coding`, `vision`, `document`, `embedding`. Fallback chains. | Abstract LLM gateway interface (`LLMProvider`), configuration-driven model mapping, retry and latency tracking. |
| **§10** | Voice System | ElevenLabs TTS integration; Configurable voice profiles (Indian English M/F, Hindi, Telugu, neutral M/F); Speed/stability settings; Private voice mode. | Server-side API key protection, streaming audio endpoints, voice profile registry, strict consent for voice cloning. |
| **§11 - §12** | Conversation & Memory | Continuous sessions, provenance-tracked memory extraction, semantic retrieval + exact filtering, explicit "save/forget/correct" memory capabilities. | Vector embeddings + relational metadata in PostgreSQL (`pgvector`), confidence score thresholding, privacy tiers (public, private, secret). |
| **§13 - §15** | Temporal, Tasks & Routines | Asia/Kolkata timezone awareness, UTC storage; Relative date parsing; Distinction between *recurring routines*, *planned occurrences*, and *confirmed completed events*. | Deterministic temporal engine (Python `zoneinfo`/`pendulum`), separate tables for `routines`, `routine_occurrences`, and `routine_confirmations`. |
| **§16** | Proactive Intelligence | Contextual check-ins (e.g. meal check-in at ~2 PM if enabled); Due routine prompts; Quiet hours; No repetitive nagging. | Background scheduler / cron worker, notification throttling, status check before triggering proactive messages. |
| **§17 - §20** | Research, Coding & Browser | Web search & synthesis; Isolated sandbox for coding; Headless browser automation with screenshots; Strict approval on form submissions/clicks. | Controlled tool executors; Browser subagent isolation; Diff reviews and approval gates. |
| **§21 - §24** | Multimodal, Calls & Business | Vision/screen analysis; Telephony/call workflows with consent; Order/booking preparation with double approval before financial execution. | WebRTC/streaming feeds with camera indicators, Twilio/telephony gateway stubs, multi-factor approval tokens for transactions. |
| **§26 - §27** | Permissions & Security | Policy & Permission Broker; Risk tiers (Safe, Moderate, Consequential); Irreversible actions require user approval; Server-side secrets. | Cryptographic tokens for approval requests; Immutable audit logging; Strict data isolation per user. |
| **§28** | Hologram UI | Futuristic 2D UI (cyan/blue glowing aesthetic, orbital rings, pulsing core, live voice waveforms, glassmorphism, command center). | Modern Web UI (Vite + Vanilla CSS / React / WebSockets), Web Audio API for reactive waveforms, Canvas/WebGL visuals. |
| **§31 - §33** | Jobs, Data & APIs | Render Cron (UTC expressions mapped to IST); REST + WebSocket real-time events; Normalized relational data model. | FastAPI backend, async worker / scheduler, standard JSON API schemas, idempotent job handlers. |

---

## 3. Analysis of Critical PRD Nuances

### 3.1 Temporal Rigor: Recurring vs. Planned vs. Completed
A frequent failure mode in AI assistants is assuming that a recurring rule implies task completion.
* *Example:* "Every Monday I fast."
* *Condition:* On Wednesday, October 14, user asks: "When was my last fasting?"
* *Rule:* JARVIS must check `routine_confirmations`. If the user confirmed on Monday, October 12, that is the last confirmed fasting date. Monday, October 19 is merely a *planned occurrence* and must **never** be reported as completed or as the "last fasting".

### 3.2 Human-in-the-Loop Consequential Actions
The PRD strictly forbids the AI agent from authorizing its own tools or side-effects.
* **Safe:** Read-only operations (search, memory lookup, status check).
* **Moderate:** Internal reversible writes (drafting an email, creating a task, setting a reminder).
* **Consequential / High Risk:** External writes (sending an email, placing orders, spending money, executing bash commands, deleting data, camera activation).
* *Rule:* Any high-risk tool call generates a pending `ApprovalRequest` entity with exact arguments and HMAC/UUID token. The tool executor will refuse execution until an authenticated approval is signed by the user.

### 3.3 Separation of Model Output from Execution Engine
Models propose actions in structured JSON schemas (`tool_call`), but never execute code directly. The deterministic Python execution layer verifies:
1. User session & authentication.
2. Capability permissions & active scopes.
3. Policy broker approval status.
4. Rate limits and quota allowances.
Only when all pass does the tool execute, and results are recorded in the tamper-evident audit log.

---

## 4. Identified Ambiguities and Clarifications

1. **Section 38 Truncation:** Line 3388 in `PRD.md` ends abruptly (`Use free or low-cost tiers duri...`). The intent is clear: utilize free tiers of Render, PostgreSQL (e.g. Supabase/Neon/Render PG), NVIDIA NIM free trial quotas, and ElevenLabs free tier during early development.
2. **Local AI Model Requirement:** Section 1.4 confirms "Local AI model requirement: None for the first version." Everything is cloud-API driven (NVIDIA NIM endpoints).
3. **Multi-Tenant vs. Single-User:** The architecture specifies user isolation and user profiles, but initial development will focus on the single primary user (Asia/Kolkata / Hyderabad), built cleanly with standard `user_id` multi-tenant schemas.
