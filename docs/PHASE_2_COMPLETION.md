# Phase 2 Completion

## Implemented
* **Argon2id Password Hashing with Bcrypt Fallback:** Implemented `app.core.security.hash_password` and `verify_password` utilizing Argon2id (primary) and bcrypt (fallback), configurable via `settings.password_hashing_algorithm`. Constant-time verification detects hash format automatically without storing plaintext passwords.
* **Access Tokens & Stateful Refresh Sessions:** Implemented short-lived JWT access tokens (15-minute default) containing only `sub` (User UUID) and `sid` (Session UUID). Implemented refresh session management in `user_sessions` storing only the SHA-256 hash of high-entropy refresh tokens, with atomic rotation on refresh and immediate reuse detection.
* **FastAPI Identity & Security Dependencies:** Created `get_current_user`, `get_current_session_id`, and `get_current_user_and_session` in `app.api.deps` verifying active session state, revoking stale requests, and enforcing server-side tenant scoping.
* **Tool Registry with Explicit Risk Policies:** Implemented `ToolRegistry` managing metadata, Pydantic schemas, and risk tiers:
  * `SAFE`: Read-only, no state mutation.
  * `MODERATE`: Internal reversible state changes or sensitive reads, governed by explicit `ModeratePolicy` (`requires_approval_by_default`, `requires_user_capability`, `sensitive_data_access`, `write_operation`).
  * `CONSEQUENTIAL`: Irreversible actions, external communication, or financial operations, strictly requiring exact-argument, short-lived approval.
* **Test Doubles Registry:** Registered safe test doubles: `profile.read` (SAFE), `tasks.read` (MODERATE read), `tasks.create` (MODERATE write), `documents.read_sensitive` (MODERATE sensitive capability check), and `email.send_mock` (CONSEQUENTIAL approval mandate).
* **Deterministic Policy and Permission Broker:** Implemented `PolicyBroker.evaluate_action()` returning explicit decisions: `ALLOW`, `DENY`, `REQUIRE_APPROVAL`, `INVALID_REQUEST`, `EXPIRED_APPROVAL`, `REPLAY_DETECTED`, `OUT_OF_SCOPE`, or `TOOL_DISABLED`.
* **Exact-Action Approval Request Engine:** Implemented `ApprovalService` computing recursive canonical SHA-256 argument hashes, enforcing short-lived expiration (default: 300 seconds), and performing atomic single-use consumption (`UPDATE ... WHERE status = 'GRANTED' AND expires_at > now`) to eliminate race conditions and replay attacks.
* **Append-Only Tamper-Evident Audit Ledger:** Implemented `AuditService` with serialized cryptographic hash chaining (`previous_hash` + `record_hash`) and concurrency control via ledger head row tracking. Automatic redaction ensures passwords, bearer tokens, and API keys are never stored in log records.
* **Full Security API Endpoints:** Implemented REST endpoints for authentication (`/api/v1/auth`), approvals (`/api/v1/approvals`), and audit ledger (`/api/v1/audit-logs`).

## Not Implemented
* **Phase 3 Temporal Engine:** Relative date parsing ("next Monday", "yesterday"), timezone recurrence engine.
* **Real Tool Execution:** Zero external side-effects (no real email sending, telephony, terminal commands, or browser automation).
* **External AI Provider APIs:** Zero calls to NVIDIA NIM or ElevenLabs endpoints.
* **Frontend UI:** Web client and holographic HUD deferred to Phase 11.

## Files Changed
* `backend/requirements.txt` (Added `argon2-cffi`, `bcrypt`, `pyjwt`, `cryptography`)
* `backend/app/core/config.py` (Added `password_hashing_algorithm`, token lifetimes, and approval expiration settings)
* `backend/app/core/security.py` (Created Argon2id/bcrypt hasher, JWT manager, and token hashing)
* `backend/app/core/exceptions.py` (Added `AuthenticationError`, `TokenExpiredError`, `SessionRevokedError`, `PermissionDeniedError`, `ApprovalRequiredError`, `ApprovalExpiredError`, `ReplayDetectedError`, `InvalidApprovalError`)
* `backend/app/models/base.py` (Added `ensure_utc` timezone normalization helper)
* `backend/app/models/user.py` (Configured `lazy="selectin"` for eager async profile loading)
* `backend/app/models/session.py` (Created `UserSession` model for refresh token tracking)
* `backend/app/models/approval.py` (Created `ApprovalRequest` model with exact argument binding)
* `backend/app/models/audit.py` (Created `AuditLog` and `AuditLedgerState` models)
* `backend/app/models/__init__.py` (Exported new security models)
* `backend/app/schemas/auth.py` (Created authentication request and response schemas)
* `backend/app/schemas/approval.py` (Created approval request and decision schemas)
* `backend/app/schemas/audit.py` (Created audit log response schemas)
* `backend/app/services/tool_registry.py` (Created ToolRegistry, RiskClass, ModeratePolicy, and test doubles)
* `backend/app/services/audit_service.py` (Created concurrency-safe audit ledger with hash chaining and verification)
* `backend/app/services/approval_service.py` (Created ApprovalService with canonical argument hashing and atomic consumption)
* `backend/app/services/policy_broker.py` (Created PolicyBroker enforcing risk classes and approvals outside the model)
* `backend/app/services/auth_service.py` (Created AuthService managing registration, login, rotation, and revocation)
* `backend/app/api/deps.py` (Created security dependencies for user and session resolution)
* `backend/app/api/v1/auth.py` (Created auth endpoints: register, login, refresh, logout, me, sessions)
* `backend/app/api/v1/approvals.py` (Created approval endpoints: list, view, approve, deny, revoke)
* `backend/app/api/v1/audit.py` (Created audit endpoints: query and verify-chain)
* `backend/app/api/v1/__init__.py` (Mounted auth, approvals, and audit routers)
* `backend/tests/test_auth.py` (Created 7 tests for Argon2id, bcrypt, login, rotation, and revocation)
* `backend/tests/test_user_isolation.py` (Created 3 tests for unauthenticated access and cross-user isolation)
* `backend/tests/test_tool_registry.py` (Created 4 tests for tool registration, input schemas, and risk policies)
* `backend/tests/test_policy_broker.py` (Created 7 tests for SAFE, MODERATE read/write/sensitive, and CONSEQUENTIAL tools)
* `backend/tests/test_approvals.py` (Created 5 tests for argument binding, tampering, expiry, replay, and concurrency)
* `backend/tests/test_audit_ledger.py` (Created 4 tests for append-only logging, concurrency chaining, tamper detection, and secret redaction)

## Database Changes
Added 4 new tables:
1. `user_sessions`: Stores `refresh_token_hash`, `ip_address`, `user_agent`, `expires_at`, `is_revoked`.
2. `approval_requests`: Stores `tool_name`, `tool_version`, `normalized_arguments`, `arguments_hash`, `status`, `requested_at`, `expires_at`, `approved_at`, `consumed_at`.
3. `audit_logs`: Append-only ledger storing `sequence_number`, `action_type`, `decision`, `result_status`, `arguments_hash`, `previous_hash`, `record_hash`, `created_at`.
4. `audit_ledger_state`: Serialized ledger head tracking `sequence_number` and `last_record_hash`.

## API Changes
* `POST /api/v1/auth/register`: Register new user identity.
* `POST /api/v1/auth/login`: Authenticate and establish new refresh session.
* `POST /api/v1/auth/refresh`: Atomically rotate refresh token and issue new JWT pair.
* `POST /api/v1/auth/logout`: Revoke active session.
* `GET /api/v1/auth/me`: Retrieve current user profile.
* `GET /api/v1/auth/sessions`: List active login sessions.
* `POST /api/v1/auth/sessions/{id}/revoke`: Revoke specified session.
* `GET /api/v1/approvals`: List user's pending and historical approvals.
* `GET /api/v1/approvals/{id}`: View approval details and exact parameters.
* `POST /api/v1/approvals/{id}/approve`: Grant user authorization for exact action.
* `POST /api/v1/approvals/{id}/deny`: Reject proposed action.
* `POST /api/v1/approvals/{id}/revoke`: Revoke an already granted approval.
* `GET /api/v1/audit-logs`: Query paginated audit log records.
* `GET /api/v1/audit-logs/verify-chain`: Verify cryptographic integrity of hash chain.

## Security Changes
* **Zero Model Authority:** The language model cannot authorize or execute actions directly. All actions pass through `PolicyBroker.evaluate_action()`.
* **Argon2id Password Security:** Passwords hashed with high-memory Argon2id; zero plaintext passwords stored.
* **Exact Parameter Binding:** Approvals are cryptographically bound via SHA-256 argument hashes. Tampering with recipient, amount, or payload immediately invalidates approval.
* **Single-Use Atomic Consumption:** Race conditions and replay attacks are physically prevented via atomic database update checks.
* **Append-Only Tamper-Evident Ledger:** Audit logs feature cryptographic hash chaining. Any modification breaks the chain verification.
* **Automated Secret Redaction:** All audit details and log records automatically mask passwords, bearer tokens, and API keys.

## Tests Run
Command: `python -m pytest -v` (executed from `backend/`)
* **Phase 1 Regression Tests (15 tests):**
  * `tests/test_config.py` (5 passed)
  * `tests/test_database.py` (4 passed)
  * `tests/test_health.py` (4 passed)
  * `tests/test_logging.py` (2 passed)
* **Phase 2 Security & Permission Tests (30 tests):**
  * `tests/test_auth.py` (7 passed)
  * `tests/test_user_isolation.py` (3 passed)
  * `tests/test_tool_registry.py` (4 passed)
  * `tests/test_policy_broker.py` (7 passed)
  * `tests/test_approvals.py` (5 passed)
  * `tests/test_audit_ledger.py` (4 passed)

## Test Results
* **45 passed, 0 failed, 0 skipped** in 4.55 seconds.

## Manual Verification
1. **Password Hashing Verification:**
   * Verified Argon2id hashes start with `$argon2id$v=19$m=65536,t=3,p=4`.
   * Verified fallback compatibility with standard `$2b$` bcrypt hashes.
2. **Refresh Token Rotation & Reuse Rejection:**
   * Rotated refresh token; verified previous token was revoked.
   * Attempted reuse of rotated token; verified immediate HTTP 401 rejection and security audit log.
3. **Cross-User Isolation:**
   * User A attempting to inspect or approve User B's approval request returns HTTP 403 Forbidden.
   * User A querying audit logs only receives logs scoped to User A.
4. **Exact-Action Parameter Tampering:**
   * Approved `email.send_mock` for `recipient: safe@jarvis.ai`.
   * Evaluated action with `recipient: evil@jarvis.ai`; verified immediate `INVALID_REQUEST` decision.
5. **Concurrent Consumption Race Condition:**
   * 5 concurrent async workers raced to consume the same approval ID; verified exactly 1 succeeded and 4 failed with `ReplayDetectedError`.
6. **Audit Ledger Hash Chain Verification:**
   * Appended sequential events; verified `verify_chain()` returned `(True, None)`.
   * Mutated record hash in database; verified `verify_chain()` immediately detected tampering.
7. **Zero External Calls Check:**
   * Verified zero calls to external AI providers or network APIs.

## Known Limitations
* Rate limiting in this phase is integrated as an in-memory sliding window boundary; Redis distributed rate limiting will be enabled when multi-container deployment is configured.
* SQLite test fallback uses Python in-process locking for audit serialization; PostgreSQL production deployment will utilize database row-level locking (`SELECT ... FOR UPDATE`).

## Rollback Information
* To roll back Phase 2: remove the security models, services, and routes created in Phase 2. Phase 1 User and health endpoints remain backward compatible.

## Recommended Next Phase
* **Phase 3 — Time and Temporal Foundation:**
  * Implement timezone conversions between UTC database storage and `Asia/Kolkata` localized user presentation.
  * Implement natural relative date parsing ("today", "yesterday", "next Monday", "2 PM").
  * Implement recurrence rule expansion (RFC 5545 RRULE) for habits and routines.
  * Build temporal test harness covering edge cases (leap years, month rollovers).
