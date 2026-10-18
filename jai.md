Proceed directly to Phase 8: {PHASE NAME}.

The previous phase is complete. I have provided its completion report above.
Use that report and the existing repository as the source of truth.

Do not create another analysis round.
Do not create another roadmap.
Do not ask me to approve a separate plan.
Do not start any phase other than Phase 8.
Do not modify unrelated completed phases.
Do not deploy.
Do not commit.
Stop after implementing, testing, verifying, and documenting Phase 8.

# Required workflow

1. Read only the documents necessary for Phase 8, including:
   - PRD.md
   - docs/IMPLEMENTATION_ROADMAP.md
   - docs/DATA_MODEL_PLAN.md
   - docs/SECURITY_AND_PERMISSION_PLAN.md
   - the previous phase completion report
   - any phase-specific design document

2. Inspect the current repository implementation before editing.

3. Implement Phase 8 completely according to the repository roadmap.

4. Preserve all behavior from previous phases.

5. Add strict typing, validation, security checks, and deterministic behavior
   wherever applicable.

6. Do not silently expand scope. If a required feature belongs to a later
   phase, leave it unimplemented and document it.

# Mandatory security rules

- Preserve authentication and server-side identity enforcement.
- Never trust client-supplied user IDs.
- Enforce user and tenant isolation in every query and service operation.
- Do not expose secrets, passwords, tokens, API keys, or private data in logs.
- Route consequential actions through the existing Policy Broker.
- Require exact approvals for consequential actions.
- Do not allow the language model to authorize or execute actions directly.
- Do not add external calls unless this phase explicitly requires them.
- Do not add shell, browser, payment, communication, camera, microphone, or
  device actions unless explicitly in scope and policy-controlled.
- Preserve append-only audit behavior and hash-chain integrity.
- Validate all external and user-controlled inputs.
- Add rate limits or resource bounds for potentially expensive operations.

# Mandatory compatibility rules

- Preserve every previous test.
- Preserve SQLite/offline test compatibility unless the phase explicitly
  requires another database.
- Avoid destructive migrations.
- Use additive migrations when database changes are necessary.
- Reuse existing configuration, database, authentication, temporal, audit,
  policy, and schema conventions.
- Do not duplicate existing services.
- Do not refactor unrelated code.

# Testing requirements

Before completion:

1. Run the complete test suite from the correct project directory.
2. Confirm all previous tests pass.
3. Add focused tests for every new Phase 8 behavior.
4. Add negative tests for invalid input and unauthorized access.
5. Add security tests for isolation, replay, tampering, leakage, and misuse
   wherever relevant.
6. Add edge-case tests.
7. Run syntax/compile checks.
8. Run linting and type checking if configured.
9. Verify no unintended external network calls occurred.
10. Review the final diff for out-of-scope changes.

Do not claim completion unless the tests actually run and pass.

# Required completion report

Create:

docs/PHASE_8_COMPLETION.md

Use exactly these sections:

# Phase 8 Completion

## Implemented

## Not Implemented

## Files Changed

## Architecture Changes

## API Changes

## Database Changes

## Security And Privacy

## Tests Added

## Tests Run

## Test Results

## Manual Verification

## Known Limitations

## Rollback Information

## Recommended Next Phase

The report must state exact test counts and results. It must distinguish
implemented work from planned or unimplemented work.

# Final stopping rule

After creating and verifying the completion report:

- Do not start Phase 9.
- Do not create a Phase 9 plan.
- Do not make unrelated improvements.
- Stop and wait for me to send the completion report and request the next phase.