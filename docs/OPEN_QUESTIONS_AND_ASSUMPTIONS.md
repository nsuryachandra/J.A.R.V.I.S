# JARVIS — Open Questions and Assumptions

This document catalogs open questions, technical trade-offs, and explicit architecture assumptions identified during the PRD and repository analysis.

---

## 1. Assumptions

1. **Deployment Architecture:**
   * Backend will be built in **Python 3.11+ using FastAPI**, providing async native support, strict Pydantic v2 schemas, and seamless integration with AI libraries.
   * Frontend will be built using **Vite + React (TypeScript)** with modern CSS tokens, delivering the 2D holographic UI, audio waveforms, and HUD controls.
2. **Local Development vs. Cloud Deployment:**
   * In local development, the system will support SQLite (with JSON column extensions) or local PostgreSQL for zero-cost testing.
   * In production, the system will target Render with managed PostgreSQL (`pgvector` enabled).
3. **Provider Isolation:**
   * Unit tests and initial phase validations must run 100% offline using deterministic mocks for NVIDIA NIM and ElevenLabs. No API calls or financial spend will occur during test suites.
4. **Primary User Context:**
   * The primary user profile defaults to:
     * Timezone: `Asia/Kolkata` (+05:30)
     * City: Hyderabad, India
     * Preferred form of address: "sir" (respectful, concise, not repeated unnaturally)

---

## 2. Open Questions for Future Phases

| ID | Category | Question | Current Working Assumption |
|---|---|---|---|
| **OQ-1** | PRD Scope | Section 38 was truncated at line 3388 (`Use free or low-cost tiers duri...`). What additional clauses exist in Section 38? | Working assumption: Focus on free/low-cost tiers for development (Render free/starter, free PostgreSQL tier, NVIDIA trial credits, ElevenLabs free tier). |
| **OQ-2** | Storage | Will external object storage (S3 / Cloudflare R2) be needed before Phase 10 (Voice caching) and Phase 14 (Screenshots)? | No. Text conversations, tasks, memories, and routine records will be stored directly in PostgreSQL. Object storage will be provisioned in Phase 10/14. |
| **OQ-3** | Browser Agent | Will the Browser Agent (Phase 14) run server-side via Playwright headless or client-side companion? | Server-side containerized headless Chromium on Render (or external service if Render memory is constrained). |
| **OQ-4** | Voice Streaming | Should ElevenLabs audio stream directly via WebSockets to client or be cached server-side as temporary MP3 URLs? | Hybrid: WebSocket chunk streaming for real-time speech, with ephemeral server caching for repeated responses. |
