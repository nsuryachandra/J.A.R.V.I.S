# JARVIS — Feature Dependency Map

This document establishes the strict prerequisite matrix for all features to ensure zero circular dependencies and modular, testable increments.

---

## Dependency Matrix

| Feature Subsystem | Direct Prerequisites | Enables Downstream Systems | Hard Constraints |
|---|---|---|---|
| **Configuration & Health** | None (Phase 1) | Database, Auth, Logging | Must fail fast on missing required env vars |
| **Database & ORM** | Configuration (Phase 1) | Permissions, Memory, Tasks, Routines | PostgreSQL with UTC timestamps; connection pooling |
| **Authentication & Isolation** | Database (Phase 1) | All user-scoped data access | Every query must filter on `user_id` |
| **Policy & Permission Broker** | Auth, Database (Phase 2) | All Agent Tool Executions | LLM cannot bypass policy broker |
| **Audit Ledger** | Database, Policy (Phase 2) | All Tool & Agent Activity | Write-only, tamper-evident logs |
| **Temporal Engine** | Configuration (Phase 3) | Routines, Tasks, Proactive Scheduler | Standard timezone `Asia/Kolkata`; UTC in DB |
| **Memory System** | Database, Policy (Phase 4) | Orchestrator Context Assembly | Deduplication, provenance tracking, sensitivity filtering |
| **Tasks & Projects** | Database, Temporal (Phase 5) | Orchestrator, Proactive Check-ins | Status state machine; verification requirements |
| **Events & Routines** | Temporal Engine, DB (Phase 6) | Proactive Intelligence, Briefings | Separation of planned vs confirmed occurrences |
| **Conversation Orchestrator** | Memory, Tasks, Routines (Phase 7) | Proactive Behavior, Voice, UI | Structured JSON extraction from LLM |
| **Proactive Intelligence** | Orchestrator, Temporal (Phase 8) | Scheduled Operations, UI Notifications | Quiet hours, anti-nagging rate limits |
| **NVIDIA Model Router** | Configuration, Orchestrator (Phase 9) | High-level reasoning across all agents | Automatic fallback chains, latency logging |
| **ElevenLabs Voice** | Configuration (Phase 10) | Voice UI, Hologram Audio | Audio caching, server-side API key isolation |
| **Holographic UI** | Gateway, REST/WS APIs (Phase 11) | Human Interaction, Visual Monitoring | 2D Canvas/WebGL visualizer, reactive waveforms |
| **Research & Writing Agents** | Orchestrator, Policy (Phase 12) | Business & Coding Workflows | Citations required for external facts |
| **Coding Agent** | Orchestrator, Policy (Phase 13) | Code inspection & modifications | Isolated sandbox; mandatory diff approval |
| **Browser Agent** | Orchestrator, Policy (Phase 14) | Shopping, Web Automation | Visual screenshot before action; approval on submit |
| **Vision & Screen** | Orchestrator, Model (Phase 15) | Multimodal Analysis | Active indicator when camera/screen is queried |
| **Communication / Calls** | Policy, External APIs (Phase 17) | Outreach, Reminders | Explicit approval before sending/dialing |
| **External Actions & Shopping**| Policy, DB, Approval (Phase 18) | Orders, Bookings | Double-confirmation with total price & details |
| **Render Background Jobs** | Database, Temporal, Tasks (Phase 19) | Daily briefings, memory consolidation | Idempotency keys for all scheduled triggers |
| **Cross-Device Sync** | UI, Auth, Gateway (Phase 20) | Multi-device handoff | Device registry with distinct capabilities |

---

## Architectural Rules for Dependencies

1. **No Lower-Tier Dependency on Higher-Tier:**
   The Temporal Engine (Phase 3) must never depend on the LLM or Conversation Orchestrator (Phase 7). All date logic must be deterministic code.
2. **Permission Gate as Chokepoint:**
   Tools must not have direct database write access or external network access without passing through the Permission Broker.
3. **Pluggable Model Provider:**
   The entire system must be fully testable with local deterministic mocks for NVIDIA NIM and ElevenLabs without incurring API costs or requiring internet access during unit tests.
