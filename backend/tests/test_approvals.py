"""Tests for approval exact-action binding, expiry, atomic consumption, and concurrency."""

import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    ApprovalExpiredError,
    InvalidApprovalError,
    ReplayDetectedError,
)
from app.models.user import User
from app.services.approval_service import ApprovalService, canonicalize_arguments
from app.services.policy_broker import BrokerDecision, PolicyBroker


@pytest.fixture
def mock_actor() -> User:
    return User(
        email="commander@jarvis.ai",
        hashed_password="hashed_pw",
        timezone="Asia/Kolkata",
    )


@pytest.mark.asyncio
async def test_exact_argument_matching_and_consumption(
    db_session: AsyncSession, mock_actor: User
):
    """Verify that approving exact parameters allows atomic execution and marks status CONSUMED."""
    db_session.add(mock_actor)
    await db_session.flush()

    args = {"recipient": "officer@jarvis.ai", "subject": "Briefing", "body": "Ready"}
    appr = await ApprovalService.create_request(
        session=db_session,
        user_id=mock_actor.id,
        tool_name="email.send_mock",
        tool_version="1.0.0",
        arguments=args,
        target_resource="email_client",
    )

    # Approve request
    await ApprovalService.approve_request(
        session=db_session,
        approval_id=appr.id,
        user_id=mock_actor.id,
    )

    # Evaluate through broker with exact matching arguments
    broker = PolicyBroker()
    eval_res = await broker.evaluate_action(
        session=db_session,
        actor=mock_actor,
        tool_name="email.send_mock",
        arguments=args,
        approval_id=appr.id,
        actor_capabilities={"email:send"},
    )
    assert eval_res.decision == BrokerDecision.ALLOW
    assert appr.status == "CONSUMED"


@pytest.mark.asyncio
async def test_argument_tampering_rejected(
    db_session: AsyncSession, mock_actor: User
):
    """Verify that changing any argument (e.g. recipient) fails validation with INVALID_REQUEST."""
    db_session.add(mock_actor)
    await db_session.flush()

    original_args = {"recipient": "safe@jarvis.ai", "subject": "Transfer", "body": "OK"}
    appr = await ApprovalService.create_request(
        session=db_session,
        user_id=mock_actor.id,
        tool_name="email.send_mock",
        tool_version="1.0.0",
        arguments=original_args,
        target_resource="email_client",
    )

    # User approves original arguments
    await ApprovalService.approve_request(
        session=db_session,
        approval_id=appr.id,
        user_id=mock_actor.id,
    )

    # Adversary / model attempts to call with tampered recipient!
    tampered_args = {"recipient": "evil@jarvis.ai", "subject": "Transfer", "body": "OK"}

    broker = PolicyBroker()
    eval_res = await broker.evaluate_action(
        session=db_session,
        actor=mock_actor,
        tool_name="email.send_mock",
        arguments=tampered_args,
        approval_id=appr.id,
        actor_capabilities={"email:send"},
    )
    assert eval_res.decision == BrokerDecision.INVALID_REQUEST
    assert "mismatch" in eval_res.reason.lower()
    # Ensure approval was NOT consumed
    assert appr.status == "GRANTED"


@pytest.mark.asyncio
async def test_expired_approval_rejected(
    db_session: AsyncSession, mock_actor: User
):
    """Verify that an approval older than its expiration window is rejected with EXPIRED_APPROVAL."""
    db_session.add(mock_actor)
    await db_session.flush()

    args = {"recipient": "user@jarvis.ai", "subject": "Time", "body": "Tick"}
    # Create request with negative lifespan (already expired)
    appr = await ApprovalService.create_request(
        session=db_session,
        user_id=mock_actor.id,
        tool_name="email.send_mock",
        tool_version="1.0.0",
        arguments=args,
        target_resource="email_client",
        expire_seconds=-10,
    )
    # Force status to GRANTED to test expired consumption
    appr.status = "GRANTED"
    await db_session.flush()

    broker = PolicyBroker()
    eval_res = await broker.evaluate_action(
        session=db_session,
        actor=mock_actor,
        tool_name="email.send_mock",
        arguments=args,
        approval_id=appr.id,
        actor_capabilities={"email:send"},
    )
    assert eval_res.decision == BrokerDecision.EXPIRED_APPROVAL


@pytest.mark.asyncio
async def test_replay_attack_rejected(
    db_session: AsyncSession, mock_actor: User
):
    """Verify that a consumed approval cannot be reused (replay detection)."""
    db_session.add(mock_actor)
    await db_session.flush()

    args = {"recipient": "target@jarvis.ai", "subject": "Order", "body": "1 unit"}
    appr = await ApprovalService.create_request(
        session=db_session,
        user_id=mock_actor.id,
        tool_name="email.send_mock",
        tool_version="1.0.0",
        arguments=args,
        target_resource="email_client",
    )
    await ApprovalService.approve_request(session=db_session, approval_id=appr.id, user_id=mock_actor.id)

    broker = PolicyBroker()
    # 1. First execution: Allowed
    eval_1 = await broker.evaluate_action(
        session=db_session,
        actor=mock_actor,
        tool_name="email.send_mock",
        arguments=args,
        approval_id=appr.id,
        actor_capabilities={"email:send"},
    )
    assert eval_1.decision == BrokerDecision.ALLOW

    # 2. Replay execution with same approval ID: MUST be rejected with REPLAY_DETECTED
    eval_2 = await broker.evaluate_action(
        session=db_session,
        actor=mock_actor,
        tool_name="email.send_mock",
        arguments=args,
        approval_id=appr.id,
        actor_capabilities={"email:send"},
    )
    assert eval_2.decision == BrokerDecision.REPLAY_DETECTED


@pytest.mark.asyncio
async def test_concurrent_approval_consumption_race_condition(
    db_session: AsyncSession, mock_actor: User
):
    """Verify concurrent tasks attempting to consume the same approval ID result in exactly 1 success."""
    db_session.add(mock_actor)
    await db_session.flush()

    args = {"recipient": "bank@jarvis.ai", "subject": "Transfer", "body": "100"}
    _, args_hash = canonicalize_arguments(args)

    appr = await ApprovalService.create_request(
        session=db_session,
        user_id=mock_actor.id,
        tool_name="email.send_mock",
        tool_version="1.0.0",
        arguments=args,
        target_resource="bank",
    )
    await ApprovalService.approve_request(session=db_session, approval_id=appr.id, user_id=mock_actor.id)
    await db_session.commit()

    # Define consumer task
    async def try_consume():
        try:
            return await ApprovalService.consume_atomically(
                session=db_session,
                approval_id=appr.id,
                user_id=mock_actor.id,
                expected_tool_name="email.send_mock",
                expected_arguments_hash=args_hash,
            )
        except ReplayDetectedError:
            return False

    # Run 5 concurrent consumption tasks
    results = await asyncio.gather(*(try_consume() for _ in range(5)))

    # Exactly one task must succeed; four must fail
    assert results.count(True) == 1
    assert results.count(False) == 4
