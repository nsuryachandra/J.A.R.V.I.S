# Phase 13 Completion

## Implemented

1. **Coding Domain Data Models (`backend/app/models/coding.py`)**:
   - `CodingSession`: Workspace-scoped refactoring sessions with user isolation, status tracking (`ACTIVE`, `COMPLETED`, `ARCHIVED`), and cascade deletion.
   - `CodeChangeProposal`: Structured refactoring proposals containing target file paths, unified git diff content, baseline original content, proposed content, review status (`PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `APPLIED`, `FAILED`), and foreign key linking to `ApprovalRequest`.
   - `CodeExecutionRun`: Sandboxed execution run records tracking commands, execution directory, exit codes, stdout, stderr, execution duration, and pass/fail boolean state.
   - Exported through `backend/app/models/__init__.py`.

2. **Static Code Inspector & Path Traversal Defense (`backend/app/services/coding/inspector.py`)**:
   - `CodeInspector`:
     - Path resolution strictly constrained within approved workspace boundaries (`Path.resolve().relative_to(base)`), raising `ValueError` upon directory traversal attempts (e.g. `../../etc/shadow`).
     - Python AST parsing via `ast.parse` extracting top-level and class-scoped symbols (classes, methods, functions, async functions, arguments, docstrings).
     - Static syntax verification without code execution, catching and isolating `SyntaxError` with line numbers and messages.
     - Recursive workspace directory scanner respecting `max_depth` and excluding cache/vendor directories (`.git`, `node_modules`, `venv`, `__pycache__`).

3. **Unified Diff Engine & Atomic Patch Application (`backend/app/services/coding/diff_engine.py`)**:
   - `DiffEngine`:
     - Generates standard git-compatible unified diffs (`difflib.unified_diff`) with standard headers (`--- a/...`, `+++ b/...`).
     - Analyzes diff statistics (`additions`, `deletions`, `hunks`).
     - Dry-run validation verifying that current file contents match the expected proposal baseline before attempting modifications.
     - Atomic patch application: writes to an ephemeral temp file and renames atomically, creating timestamped backup snapshots (`.bak_YYYYMMDD_HHMMSS`) with automated rollback recovery on write errors.

4. **Sandboxed Test & Diagnostic Execution Runner (`backend/app/services/coding/sandbox_runner.py`)**:
   - `SandboxRunner`:
     - Executes commands inside isolated subdirectories without `shell=True` to eliminate shell injection attack surfaces.
     - Allowlisted binaries (`pytest`, `python`, `unittest`, `ruff`, `flake8`) with strict blocking of destructive command patterns (`rm -rf /`, `curl | bash`, fork bombs).
     - Strict execution timeouts (configurable default 15s) with automated process termination on timeout.
     - Output truncation guards (64 KB cap) to prevent memory exhaustion attacks.
     - Pytest output parser extracting pass/fail/error counts and test durations.

5. **Coding Agent Reasoning Orchestrator (`backend/app/services/coding/coding_agent.py`)**:
   - `CodingAgent`:
     - Coordinates codebase inspection, diff preparation, dry-run validation, and sandboxed test execution.

6. **Coding Domain Service & Policy Broker Gating (`backend/app/services/coding/service.py`)**:
   - `CodingService`:
     - Manages session lifecycle (`create_session`, `list_user_sessions`, `get_session`) with tenant isolation.
     - Safe code inspection (`inspect_code`) and proposal generation (`propose_change`).
     - Consequential file modification gating: `apply_change` routes through `PolicyBroker`, requiring a cryptographically signed and approved `ApprovalRequest` token. Unapproved requests raise `PermissionDeniedError` and return HTTP 403.
     - Dry-run capability allows previewing patch applicability without modifying file contents.
     - Sandboxed test execution (`run_tests`) persisting execution runs to database and emitting audit records.
     - Immutable audit trail logging for all actions: `code.session_create`, `code.inspect`, `code.propose_change`, `code.apply_change`, `code.run_tests`.

7. **Tool Registry Integration (`backend/app/services/tool_registry.py`)**:
   - Registered 4 tools in the global tool catalog:
     - `code.inspect` (v1.0.0, `SAFE`): Inspect code hierarchy and AST symbols.
     - `code.propose_change` (v1.0.0, `SAFE`): Generate planned refactoring diff proposals.
     - `code.apply_change` (v1.0.0, `CONSEQUENTIAL`): Apply approved diff directly to target workspace, enforcing mandatory cryptographic approval.
     - `code.run_tests` (v1.0.0, `SAFE` in sandbox): Run sandboxed tests with timeout bounds.

8. **REST API Endpoints (`backend/app/api/v1/coding.py`)**:
   - Mounted at `/api/v1/coding`:
     - `POST /api/v1/coding/sessions`: Create workspace coding session.
     - `GET /api/v1/coding/sessions`: List user's coding sessions.
     - `GET /api/v1/coding/sessions/{session_id}`: Retrieve session details and proposal counts.
     - `POST /api/v1/coding/inspect`: Inspect workspace files, directory tree, or specific symbols.
     - `POST /api/v1/coding/proposals`: Create a change proposal with unified diff preview.
     - `GET /api/v1/coding/proposals`: List proposals for user or session.
     - `GET /api/v1/coding/proposals/{proposal_id}`: Get proposal details, diff, and review status.
     - `POST /api/v1/coding/proposals/{proposal_id}/apply`: Apply approved change proposal (supports dry-run).
     - `POST /api/v1/coding/tests/run`: Run sandboxed tests and return structured test metrics.
   - Enforces user authentication via `get_current_user_and_session` and strict tenant isolation on every endpoint.

---

## Not Implemented

- Headless browser automation and DOM manipulation (deferred to Phase 14: Browser & Computer Agent).
- Direct git remote push/merge operations against remote repositories (GitHub/GitLab remote operations belong to Phase 18: External Actions).
- Docker-in-Docker container isolation daemon (lightweight directory and subprocess sandboxing with command allowlists is active; full container runtime integration belongs to production hardening in Phase 21).

---

## Files Changed

### Backend

- `backend/app/models/coding.py` (Created): Database models `CodingSession`, `CodeChangeProposal`, `CodeExecutionRun`.
- `backend/app/models/__init__.py` (Modified): Exported coding models.
- `backend/app/services/coding/schemas.py` (Created): Pydantic contracts and schemas for coding sessions, inspection, diffs, proposals, and test runs.
- `backend/app/services/coding/inspector.py` (Created): `CodeInspector` with path traversal defense and AST extraction.
- `backend/app/services/coding/diff_engine.py` (Created): `DiffEngine` with unified diff generation, dry-run checks, and atomic patch application.
- `backend/app/services/coding/sandbox_runner.py` (Created): `SandboxRunner` with allowlisted subprocess execution and pytest parsing.
- `backend/app/services/coding/coding_agent.py` (Created): `CodingAgent` orchestrator.
- `backend/app/services/coding/service.py` (Created): `CodingService` domain service with Policy Broker integration and audit logging.
- `backend/app/services/coding/__init__.py` (Created): Package exports.
- `backend/app/services/approval_service.py` (Modified): Added `synchronize_session="fetch"` to `consume_atomically` for safe identity map refresh during atomic updates.
- `backend/app/services/tool_registry.py` (Modified): Added `List` import, Pydantic schemas, and registered `code.inspect`, `code.propose_change`, `code.apply_change`, `code.run_tests`.
- `backend/app/api/v1/coding.py` (Created): FastAPI REST router with 9 coding endpoints.
- `backend/app/api/v1/__init__.py` (Modified): Mounted `coding_router` in `api_v1_router`.
- `backend/tests/test_coding_service.py` (Created): Unit and domain service tests for inspector, diff engine, sandbox runner, lifecycle, and isolation.
- `backend/tests/test_coding_api.py` (Created): Integration tests for coding REST endpoints, consequential approval flow, path traversal defense, and tenant isolation.

---

## Architecture Changes

```mermaid
graph TD
    Client[Client / Frontend / CLI] -->|Bearer JWT| CodingAPI["/api/v1/coding/*"]
    CodingAPI -->|User & Session Auth| CodingService[CodingService]
    
    CodingService -->|Static Analysis| CodeInspector[CodeInspector (AST & Path Sandbox)]
    CodingService -->|Diff & Patch| DiffEngine[DiffEngine (Unified Diffs & Rollback)]
    CodingService -->|Execution & Tests| SandboxRunner[SandboxRunner (Timeout & Command Guards)]
    CodingService -->|Consequential Gating| PolicyBroker[PolicyBroker (Approval Required)]
    CodingService -->|Audit Events| AuditService[AuditService (Hash-Chained)]
    CodingService -->|ORM Persistence| DB[(SQLite / PostgreSQL)]
    
    PolicyBroker -->|Verify Signed Token| ApprovalService[ApprovalService]
    
    DB --> CodingSessionsTable[coding_sessions]
    DB --> CodeProposalsTable[code_change_proposals]
    DB --> CodeRunsTable[code_execution_runs]
```

---

## API Changes

| HTTP Method | Route | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/coding/sessions` | Create a new coding workspace session | Yes (Bearer JWT) |
| `GET` | `/api/v1/coding/sessions` | List user's coding sessions | Yes (Bearer JWT) |
| `GET` | `/api/v1/coding/sessions/{session_id}` | Retrieve details of a specific coding session | Yes (Bearer JWT) |
| `POST` | `/api/v1/coding/inspect` | Inspect workspace code files, AST symbols, and syntax | Yes (Bearer JWT) |
| `POST` | `/api/v1/coding/proposals` | Draft a refactoring proposal with unified git diff | Yes (Bearer JWT) |
| `GET` | `/api/v1/coding/proposals` | List proposals for the user or filtered by session | Yes (Bearer JWT) |
| `GET` | `/api/v1/coding/proposals/{proposal_id}` | Retrieve details, diff content, and approval status | Yes (Bearer JWT) |
| `POST` | `/api/v1/coding/proposals/{proposal_id}/apply` | Apply approved diff (requires ApprovalRequest token) | Yes (Bearer JWT) |
| `POST` | `/api/v1/coding/tests/run` | Run sandboxed tests with timeout bounds | Yes (Bearer JWT) |

---

## Database Changes

### New Tables Added

1. **`coding_sessions`**:
   - `id`: UUID (Primary Key)
   - `user_id`: UUID (Foreign Key -> `users.id`, `ON DELETE CASCADE`)
   - `workspace_path`: String(512)
   - `title`: String(255)
   - `status`: String(32), default "ACTIVE"
   - `created_at`, `updated_at`: DateTime(timezone=True)
   - Indexes: `ix_coding_sessions_user_created` (`user_id`, `created_at`)

2. **`code_change_proposals`**:
   - `id`: UUID (Primary Key)
   - `session_id`: UUID (Foreign Key -> `coding_sessions.id`, `ON DELETE CASCADE`)
   - `user_id`: UUID (Foreign Key -> `users.id`, `ON DELETE CASCADE`)
   - `title`: String(255)
   - `description`: Text
   - `target_file`: String(512)
   - `diff_content`: Text
   - `original_content`: Text
   - `proposed_content`: Text
   - `status`: String(32), default "PENDING_APPROVAL"
   - `approval_id`: UUID (Foreign Key -> `approval_requests.id`, `ON DELETE SET NULL`, Nullable)
   - `applied_at`: DateTime(timezone=True) (Nullable)
   - `created_at`, `updated_at`: DateTime(timezone=True)
   - Indexes: `ix_code_proposals_user_status` (`user_id`, `status`), `ix_code_proposals_user_created` (`user_id`, `created_at`)

3. **`code_execution_runs`**:
   - `id`: UUID (Primary Key)
   - `session_id`: UUID (Foreign Key -> `coding_sessions.id`, `ON DELETE CASCADE`)
   - `user_id`: UUID (Foreign Key -> `users.id`, `ON DELETE CASCADE`)
   - `command`: String(512)
   - `sandbox_dir`: String(512)
   - `exit_code`: Integer
   - `stdout`: Text
   - `stderr`: Text
   - `duration_ms`: Integer, default 0
   - `passed`: Boolean, default False
   - `created_at`: DateTime(timezone=True)
   - Indexes: `ix_code_execution_runs_user_created` (`user_id`, `created_at`)

---

## Security And Privacy

- **Server-Side Authentication**: All `/api/v1/coding/*` endpoints reject unauthenticated requests with HTTP 401 Unauthorized.
- **Strict Tenant & User Isolation**: All sessions, change proposals, and execution runs are strictly filtered by `user_id`. Cross-user access returns HTTP 404 Not Found without leaking resource existence.
- **Path Traversal Defense**: All target file and workspace paths are verified using resolved absolute paths. Paths escaping the workspace boundary raise a blocked traversal error and return HTTP 400.
- **Mandatory Approval for Consequential Actions**: File modifications outside the sandbox (`code.apply_change`) are registered as `CONSEQUENTIAL` in `ToolRegistry`. Unapproved apply attempts raise `PermissionDeniedError` with an approval request requirement. Modifying files requires an authorized approval token.
- **Subprocess Sandbox Security**: Shell invocation avoids `shell=True`, preventing argument injection. Destructive commands (`rm -rf /`, `curl | sh`) and unallowlisted binaries are rejected before subprocess launch. Execution is bounded by strict timeouts and 64 KB output limits.
- **Tamper-Evident Audit Logging**: All coding actions (`code.session_create`, `code.inspect`, `code.propose_change`, `code.apply_change`, `code.run_tests`) are recorded in the append-only `audit_logs` table via `AuditService`.

---

## Tests Added

1. **`backend/tests/test_coding_service.py`**:
   - `test_code_inspector_safe_path_validation`: Verifies path boundary enforcement and blocks directory traversal attempts (`../../etc/passwd`).
   - `test_code_inspector_ast_parsing_and_syntax`: Verifies AST symbol extraction (classes, methods, functions, docstrings) and static syntax error reporting.
   - `test_diff_engine_unified_diff_and_analysis`: Tests unified git diff generation, hunk and line addition/deletion counting, and dry-run drift detection.
   - `test_diff_engine_safe_patch_application_and_rollback`: Tests atomic temporary file replacement, automatic backup snapshot creation, and rollback safety.
   - `test_sandbox_runner_safety_validation`: Verifies command allowlist enforcement and destructive pattern rejection.
   - `test_sandbox_runner_execution_and_parsing`: Tests sandboxed test execution and pytest output statistic parsing.
   - `test_coding_service_lifecycle_proposals_and_audit`: Tests the complete lifecycle: session creation, file inspection, change proposal generation, dry-run apply, consequential approval gating, approved patch application, and audit log generation.
   - `test_coding_service_tenant_isolation`: Verifies that User B cannot view or retrieve User A's coding sessions or change proposals.

2. **`backend/tests/test_coding_api.py`**:
   - `test_unauthenticated_coding_endpoints_rejected`: Verifies HTTP 401 Unauthorized across all coding REST endpoints.
   - `test_coding_session_inspect_and_proposals_api`: Tests session creation, file inspection, AST symbol lookup, and proposal generation via REST API.
   - `test_coding_consequential_apply_and_approval_flow`: Tests the full human-in-the-loop approval workflow: dry-run inspection, unapproved apply rejection (HTTP 403), authorization via `/api/v1/approvals/{id}/approve`, and successful patch application.
   - `test_coding_api_tenant_isolation`: Verifies HTTP 404 Not Found when User B attempts to access or apply User A's coding proposals.
   - `test_coding_api_validation_and_path_traversal`: Verifies input validation bounds (empty title -> 422) and path traversal rejection (HTTP 400).

---

## Tests Run

```bash
# Focused Phase 13 tests:
pytest tests/test_coding_service.py tests/test_coding_api.py -v
# Result: 13 passed in 5.33s

# Complete test suite:
pytest -v
# Result: 215 passed in 28.11s

# Frontend production bundle validation:
cd frontend && npm run build
# Result: built in 282ms with 0 errors
```

---

## Test Results

- **Backend Total Tests**: **215 passed, 0 failed, 0 skipped** (up from 202 in Phase 12).
- **Execution Time**: **28.11 seconds**.
- **Regressions**: **0 regressions detected**.
- **Frontend Build**: **Passing cleanly** (`vite build` in 282ms).

---

## Manual Verification

1. **Path Traversal Defense Verification**:
   - Attempted path resolution for `"../../outside.py"` and `"../../etc/passwd"`.
   - Verified `CodeInspector.validate_safe_path` raised `ValueError: Path traversal blocked` and API returned HTTP 400.
2. **AST Symbol Extraction**:
   - Inspected Python module containing class definitions, async methods, and helper functions.
   - Verified extracted symbol list contained class names, function names, line numbers, argument lists, and docstrings.
3. **Unified Diff & Dry-Run Preview**:
   - Generated a diff changing `def process(): return 'v1'` to `def process(): return 'v2'`.
   - Verified standard unified diff with `--- a/core.py`, `+++ b/core.py`, and `+ return 'v2'`.
   - Verified dry-run execution succeeded with `applied=False` without touching the file on disk.
4. **Consequential Policy Broker Approval Flow**:
   - Attempted applying change without approval: blocked with HTTP 403 Forbidden and generated an `ApprovalRequest`.
   - Approved the request via `/api/v1/approvals/{approval_id}/approve`.
   - Retried application with approved ID: patch applied atomically, created backup file, updated file contents to v2, and recorded tamper-evident audit logs.
5. **Sandboxed Pytest Execution**:
   - Executed `SandboxRunner` in a temp workspace directory.
   - Verified pytest process executed without `shell=True`, returned exit code 5 (no tests collected), and completed cleanly within timeout bounds.
6. **Cross-Tenant Security**:
   - User A created a session and proposal.
   - User B querying `/api/v1/coding/sessions/{id}` and `/api/v1/coding/proposals/{id}` received HTTP 404.

---

## Known Limitations

- **Language-Specific AST**: Full syntax and AST symbol parsing is currently implemented for Python (`ast.parse`). Non-Python files (TypeScript, JavaScript, JSON, Markdown) are inspected for size, line count, and diff generation.
- **Local Sandbox Execution**: Test runs execute using the local Python interpreter with timeout and command allowlists. Full container runtime isolation (Docker/Firecracker) is deferred to Phase 21: Production Hardening.
- **Git Push/Merge Automation**: Remote repository operations (GitHub Pull Requests, branch pushes) belong to Phase 18: External Actions.

---

## Rollback Information

If rollback of Phase 13 is needed:
1. Remove `backend/app/api/v1/coding.py` and unmount `coding_router` in `backend/app/api/v1/__init__.py`.
2. Remove `backend/app/services/coding/` directory.
3. Remove `backend/app/models/coding.py` and remove its exports in `backend/app/models/__init__.py`.
4. Revert tool registrations in `backend/app/services/tool_registry.py`.
5. Remove test files `backend/tests/test_coding_service.py` and `backend/tests/test_coding_api.py`.
6. Run `pytest -v` to confirm reversion back to the 202 passing tests of Phase 12.

---

## Recommended Next Phase

- **Phase 14: Browser & Computer Agent**:
  - Headless browser automation for structured web interaction.
  - Action sandbox and visual screenshot logging.
  - Form submission approval gates and external web safety boundaries.
