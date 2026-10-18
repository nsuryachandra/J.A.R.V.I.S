# JARVIS — Risk Register

This document tracks identified technical, operational, safety, and financial risks along with mitigation strategies and ownership.

---

## Risk Assessment Matrix

| Risk ID | Category | Risk Description | Severity | Likelihood | Mitigation Strategy |
|---|---|---|---|---|---|
| **RSK-01** | Safety | Model claims a task or fasting routine is completed without database verification. | HIGH | HIGH | **Deterministic Verification Gate:** The model cannot set `is_completed=True`. Only a verified tool call returning a DB confirmation record allows the orchestrator to confirm completion to the user. |
| **RSK-02** | Security | Malicious prompt injection triggers unapproved destructive command or email dispatch. | CRITICAL | MEDIUM | **Policy Broker Chokepoint:** Consequential actions are intercepted at the Python framework layer. An execution token is generated and requires cryptographic user confirmation before execution. |
| **RSK-03** | Reliability | Timezone confusion between Render UTC cron triggers and Asia/Kolkata user calendar. | HIGH | MEDIUM | **Explicit Timezone Engine:** Store all datetimes as UTC `timestamptz`. Strict localized conversion via `zoneinfo.ZoneInfo("Asia/Kolkata")` in all date-parsing tools and cron schedules. |
| **RSK-04** | Financial | Uncontrolled LLM loops or voice synthesis exhaust API credits unexpectedly. | HIGH | MEDIUM | **Circuit Breakers & Quota Budgets:** Per-session token budgets; audio character limiters; deterministic unit tests run against local mocks without calling live provider endpoints. |
| **RSK-05** | Performance| Render free/starter instance cold-start latency degrading conversational responsiveness. | MEDIUM | HIGH | **Stateless Keep-Alive & Lightweight Core:** Fast ASGI startup (<1.5s), optimized dependencies, asynchronous background dispatch for long-running workflows. |
| **RSK-06** | Privacy | Sensitive user data, memories, or API keys leaked via error logs or model prompt contexts. | CRITICAL | LOW | **Strict Secret & Log Masking:** API keys kept exclusively server-side in memory/env; logs filter authorization headers; memories classified by sensitivity (`public`, `private`, `secret`). |
| **RSK-07** | UX / Proactive | Proactive check-ins (e.g. 2 PM meal check-in) becoming repetitive or annoying to the user. | MEDIUM | MEDIUM | **Anti-Nagging State Machine:** Configurable quiet hours; strict throttle preventing duplicate unprompted messages if previous check-in was unacknowledged. |
