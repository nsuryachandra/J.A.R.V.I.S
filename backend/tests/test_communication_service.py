"""Unit and domain integration tests for Communication & Calls: Messaging and Telephony."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.user import User
from app.services.approval_service import ApprovalService
from app.services.communication.providers import MockCommunicationProvider
from app.services.communication.schemas import (
    CreateMessageDraftRequest,
    InitiateCallRequest,
    PlanCallRequest,
    SendMessageRequest,
)
from app.services.communication.service import CommunicationService


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    """Create test user fixture."""
    u = User(
        id=uuid.uuid4(),
        email=f"comm_unit_{uuid.uuid4().hex[:6]}@jarvis.ai",
        hashed_password="hashed_pw_test",
        timezone="Asia/Kolkata",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


class TestCommunicationService:
    """Domain tests for message drafting, consequential dispatch, calls, approvals, and audits."""

    @pytest.fixture
    def mock_provider(self) -> MockCommunicationProvider:
        return MockCommunicationProvider()

    @pytest.fixture
    def comm_service(self, mock_provider: MockCommunicationProvider) -> CommunicationService:
        return CommunicationService(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_message_draft_and_consequential_approval_gate(
        self,
        db_session: AsyncSession,
        user: User,
        comm_service: CommunicationService,
    ):
        # 1. Draft email (SAFE action)
        draft_req = CreateMessageDraftRequest(
            channel="EMAIL",
            recipient="client@enterprise.com",
            subject="Quarterly Strategy Sync",
            body="Hi Team,\nHere is the executive summary for Q4.",
        )
        draft = await comm_service.create_draft(
            db=db_session,
            user_id=user.id,
            request=draft_req,
        )
        assert draft.channel == "EMAIL"
        assert draft.recipient == "client@enterprise.com"
        assert draft.status == "DRAFT"
        assert draft.sent_at is None

        # 2. Dispatch without approval must raise PermissionDeniedError (CONSEQUENTIAL action)
        with pytest.raises(PermissionDeniedError, match="Approval required to dispatch EMAIL message"):
            await comm_service.send_message(
                db=db_session,
                user=user,
                draft_id=draft.id,
                request=SendMessageRequest(approval_id=None),
            )

        # Refresh draft to retrieve generated approval_id
        draft_db = await comm_service.get_draft(db=db_session, user_id=user.id, draft_id=draft.id)
        assert draft_db.status == "APPROVAL_REQUIRED"
        assert draft_db.approval_id is not None

        # Authorize approval via ApprovalService
        app_req = await db_session.get(ApprovalRequest, draft_db.approval_id)
        assert app_req is not None
        await ApprovalService.approve_request(
            session=db_session,
            approval_id=app_req.id,
            user_id=user.id,
        )

        # 3. Dispatch with approved authorization
        send_res = await comm_service.send_message(
            db=db_session,
            user=user,
            draft_id=draft.id,
            request=SendMessageRequest(approval_id=app_req.id),
        )
        assert send_res.status == "SENT"
        assert send_res.sent_at is not None

        # Verify provider dispatched
        assert len(comm_service.agent.provider.sent_messages) == 1
        assert comm_service.agent.provider.sent_messages[0]["recipient"] == "client@enterprise.com"

        # 4. Idempotency: re-sending already sent draft succeeds without re-dispatching
        send_again = await comm_service.send_message(
            db=db_session,
            user=user,
            draft_id=draft.id,
            request=SendMessageRequest(approval_id=app_req.id),
        )
        assert send_again.status == "SENT"
        assert len(comm_service.agent.provider.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_call_planning_and_consequential_initiation_gate(
        self,
        db_session: AsyncSession,
        user: User,
        comm_service: CommunicationService,
    ):
        # 1. Plan call and compile briefing (SAFE action)
        plan_req = PlanCallRequest(
            recipient_phone="+1-555-0199",
            recipient_name="David Miller",
            purpose="Follow-up on enterprise security contract",
            briefing_notes="Confirm SLA terms and SOC2 compliance timeline.",
            recording_consent_disclosed=True,
        )
        call = await comm_service.plan_call(
            db=db_session,
            user_id=user.id,
            request=plan_req,
        )
        assert call.recipient_phone == "+1-555-0199"
        assert call.purpose == "Follow-up on enterprise security contract"
        assert call.status == "PLANNED"
        assert call.recording_consent_disclosed is True
        assert "Outbound Call Briefing with David Miller" in (call.briefing_notes or "")

        # 2. Initiate call without approval must raise PermissionDeniedError (CONSEQUENTIAL action)
        with pytest.raises(PermissionDeniedError, match="Approval required to dial out phone call"):
            await comm_service.initiate_call(
                db=db_session,
                user=user,
                call_id=call.id,
                request=InitiateCallRequest(approval_id=None),
            )

        # Refresh call to retrieve generated approval_id
        call_db = await comm_service.get_call(db=db_session, user_id=user.id, call_id=call.id)
        assert call_db.status == "APPROVAL_REQUIRED"
        assert call_db.approval_id is not None

        # Authorize approval via ApprovalService
        app_req = await db_session.get(ApprovalRequest, call_db.approval_id)
        assert app_req is not None
        await ApprovalService.approve_request(
            session=db_session,
            approval_id=app_req.id,
            user_id=user.id,
        )

        # 3. Initiate call with approved authorization
        init_res = await comm_service.initiate_call(
            db=db_session,
            user=user,
            call_id=call.id,
            request=InitiateCallRequest(approval_id=app_req.id),
        )
        assert init_res.status == "COMPLETED"
        assert init_res.transcript is not None
        assert "This call is recorded" in init_res.transcript
        assert init_res.call_summary is not None

        # Verify provider recorded call
        assert len(comm_service.agent.provider.placed_calls) == 1
        assert comm_service.agent.provider.placed_calls[0]["recipient_phone"] == "+1-555-0199"

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        db_session: AsyncSession,
        user: User,
        comm_service: CommunicationService,
    ):
        draft = await comm_service.create_draft(
            db=db_session,
            user_id=user.id,
            request=CreateMessageDraftRequest(
                channel="SMS",
                recipient="+1-555-0100",
                body="Private SMS code",
            ),
        )
        call = await comm_service.plan_call(
            db=db_session,
            user_id=user.id,
            request=PlanCallRequest(
                recipient_phone="+1-555-0200",
                purpose="Private conversation",
            ),
        )

        other_user_id = uuid.uuid4()
        with pytest.raises(EntityNotFoundError):
            await comm_service.get_draft(db=db_session, user_id=other_user_id, draft_id=draft.id)

        with pytest.raises(EntityNotFoundError):
            await comm_service.get_call(db=db_session, user_id=other_user_id, call_id=call.id)

    @pytest.mark.asyncio
    async def test_audit_trail_recorded(
        self,
        db_session: AsyncSession,
        user: User,
        comm_service: CommunicationService,
    ):
        draft = await comm_service.create_draft(
            db=db_session,
            user_id=user.id,
            request=CreateMessageDraftRequest(
                channel="EMAIL",
                recipient="audit@jarvis.ai",
                subject="Audit Verification",
                body="Test audit logging",
            ),
        )
        call = await comm_service.plan_call(
            db=db_session,
            user_id=user.id,
            request=PlanCallRequest(
                recipient_phone="+1-555-9999",
                purpose="Audit Telephony",
            ),
        )

        stmt = AuditLog.__table__.select().where(AuditLog.user_id == user.id)
        result = await db_session.execute(stmt)
        rows = result.fetchall()
        action_types = [r.action_type for r in rows]
        assert "communication.draft_create" in action_types
        assert "communication.call_plan" in action_types
