# JARVIS — Testing Strategy

This document defines the automated testing hierarchy, validation frameworks, temporal test cases, and provider mocking standards for JARVIS adhering to Section 36 of `PRD.md`.

---

## 1. Testing Pyramid

```text
       ┌───────────────────────┐
       │   E2E Scenario Tests  │  <-- Multi-turn conversations, full approval flows
       ├───────────────────────┤
       │   Integration Tests   │  <-- DB migrations, API routes, Redis/broker interactions
       ├───────────────────────┤
       │      Unit Tests       │  <-- Temporal engine, risk classifier, schemas, token signing
       └───────────────────────┘
```

---

## 2. Testing Framework & Tooling

* **Test Runner:** `pytest` with `pytest-asyncio` for asynchronous endpoint and service tests.
* **HTTP Test Client:** `httpx.AsyncClient` with `FastAPI` dependency overrides.
* **Database Testing:** In-memory SQLite (for fast unit testing) or isolated test PostgreSQL database (via Docker or local instance) for migration and relational integrity validation.
* **Mocking:** `unittest.mock` and `respx` for mocking external HTTP calls to NVIDIA NIM and ElevenLabs.

---

## 3. Critical Verification Suites

### 3.1 Temporal & Timezone Suite
* **Timezone Invariance:** Verify all database entities save UTC `datetime` objects and deserialize correctly into `Asia/Kolkata` local time (+05:30).
* **Relative Parsing:**
  * `"today"` -> current local calendar date in Asia/Kolkata.
  * `"tomorrow at 3 PM"` -> correct UTC equivalent for 15:00 IST.
  * `"next Monday"` -> exact upcoming Monday date.
* **Leap Years & Month Rollovers:** Verify recurrence rule expansion across February 28/29 and year boundaries.

### 3.2 Routine & Event Acceptance Suite (The Fasting Scenarios)
* **Test Case 1: Declaration**
  * *Input:* User says: *"Every Monday I fast."*
  * *Assertion:* Creates a routine in `routines` with recurrence `FREQ=WEEKLY;BYDAY=MO`. Generates planned occurrences for upcoming Mondays in `routine_occurrences`.
* **Test Case 2: Past Query with Planned Future**
  * *State:* Monday, Oct 12 confirmed completed. Today is Wednesday, Oct 14. Next Monday is Oct 19 (planned).
  * *Input:* User asks: *"When was my last fasting?"*
  * *Assertion:* Response must state Monday, Oct 12. Must **never** report Oct 19 as completed.
* **Test Case 3: Ad-hoc Fasting**
  * *Input:* User says: *"I am fasting only today."*
  * *Assertion:* Creates a one-time event, not a recurring routine.
* **Test Case 4: Confirmation**
  * *Input:* User says: *"I fasted today."*
  * *Assertion:* Creates an entry in `routine_confirmations` for today's occurrence. Sets occurrence status to `CONFIRMED`.

### 3.3 Security & Permission Suite
* **Interception Test:** Calling a `CONSEQUENTIAL` tool (e.g. `send_email`) without a valid token raises `PermissionDeniedError` and creates an `ApprovalRequest`.
* **Token Tampering Test:** Altering the recipient or subject argument after generating the approval token results in `TokenValidationError` on submission.
* **Expiration Test:** Attempting to claim an approval token after 5 minutes returns `TokenExpiredError`.
* **Tenant Isolation Test:** User B attempting to read User A's task or memory returns HTTP 404 or empty set.

### 3.4 Provider Mocking Suite
* **NVIDIA NIM Mock:** Pre-recorded deterministic JSON responses for chat completions, tool proposals, and embeddings.
* **ElevenLabs Mock:** Generates deterministic synthetic WAV/MP3 byte headers without calling the external billing endpoint during test runs.

---

## 4. Definition of Done for Any Phase
A phase is considered complete **only when**:
1. All unit tests pass with 100% green status.
2. Integration tests for new endpoints/schemas pass.
3. Zero linting or type errors (`ruff` / `mypy` / `tsc`).
4. Explicit manual verification commands are executed and documented.
5. The phase completion report `docs/PHASE_<ID>_COMPLETION.md` is produced.
