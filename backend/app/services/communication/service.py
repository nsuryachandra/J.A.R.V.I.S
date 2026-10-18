"""Domain service for Communication & Calls: Drafting, Policy-gated dispatch, and Telephony."""

import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.base import utcnow
from app.models.communication import CallSession, MessageDraft
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.communication.communication_agent import CommunicationAgent
from app.services.communication.providers import BaseCommunicationProvider
from app.services.communication.schemas import (
    CallSessionResponse,
    CreateMessageDraftRequest,
    InitiateCallRequest,
    InitiateCallResponse,
    MessageDraftResponse,
    PlanCallRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.policy_broker import BrokerDecision, PolicyBroker


class CommunicationService:
    """Service orchestrating email/SMS messaging and telephony calls under Policy Broker governance."""

    def __init__(
        self,
        broker: Optional[PolicyBroker] = None,
        provider: Optional[BaseCommunicationProvider] = None,
    ):
        self._broker = broker or PolicyBroker()
        self._agent = CommunicationAgent(provider=provider)

    @property
    def agent(self) -> CommunicationAgent:
        return self._agent

    # --- Message Drafts & Dispatch ---

    async def create_draft(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: CreateMessageDraftRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> MessageDraftResponse:
        """Create and refine an outbound message draft (SAFE action)."""
        refined = self._agent.refine_message(
            channel=request.channel,
            recipient=request.recipient,
            body=request.body,
            subject=request.subject,
        )

        draft = MessageDraft(
            user_id=user_id,
            channel=refined["channel"],
            recipient=refined["recipient"],
            subject=refined["subject"],
            body=refined["body"],
            status="DRAFT",
        )
        db.add(draft)
        await db.commit()
        await db.refresh(draft)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="communication.draft_create",
            resource_scope=f"message_draft:{draft.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "channel": draft.channel,
                "recipient": draft.recipient,
                "subject": draft.subject,
            },
        )
        await db.commit()

        return MessageDraftResponse(
            id=draft.id,
            user_id=draft.user_id,
            channel=draft.channel,
            recipient=draft.recipient,
            subject=draft.subject,
            body=draft.body,
            status=draft.status,
            approval_id=draft.approval_id,
            sent_at=draft.sent_at.isoformat() if draft.sent_at else None,
            created_at=draft.created_at.isoformat(),
            updated_at=draft.updated_at.isoformat(),
        )

    async def list_drafts(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        channel: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MessageDraftResponse]:
        """List user's message drafts with tenant isolation."""
        stmt = select(MessageDraft).where(MessageDraft.user_id == user_id)
        if channel:
            stmt = stmt.where(MessageDraft.channel == channel.upper())
        if status:
            stmt = stmt.where(MessageDraft.status == status.upper())
        stmt = stmt.order_by(desc(MessageDraft.created_at))

        result = await db.execute(stmt)
        drafts = result.scalars().all()

        return [
            MessageDraftResponse(
                id=d.id,
                user_id=d.user_id,
                channel=d.channel,
                recipient=d.recipient,
                subject=d.subject,
                body=d.body,
                status=d.status,
                approval_id=d.approval_id,
                sent_at=d.sent_at.isoformat() if d.sent_at else None,
                created_at=d.created_at.isoformat(),
                updated_at=d.updated_at.isoformat(),
            )
            for d in drafts
        ]

    async def get_draft(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> MessageDraft:
        """Fetch single draft ensuring tenant isolation."""
        stmt = select(MessageDraft).where(
            MessageDraft.id == draft_id,
            MessageDraft.user_id == user_id,
        )
        result = await db.execute(stmt)
        draft = result.scalar_one_or_none()
        if not draft:
            raise EntityNotFoundError("MessageDraft", draft_id)
        return draft

    async def send_message(
        self,
        db: AsyncSession,
        user: User,
        draft_id: uuid.UUID,
        request: SendMessageRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> SendMessageResponse:
        """Dispatch message under consequential Policy Broker approval gate."""
        draft = await self.get_draft(db, user.id, draft_id)
        if draft.status == "SENT":
            return SendMessageResponse(
                draft_id=draft.id,
                status=draft.status,
                sent_at=draft.sent_at.isoformat() if draft.sent_at else None,
                message="Message has already been dispatched.",
            )

        # Policy Broker consequential approval evaluation
        eval_result = await self._broker.evaluate_action(
            session=db,
            actor=user,
            tool_name="communication.send_message",
            arguments={
                "draft_id": str(draft.id),
                "channel": draft.channel,
                "recipient": draft.recipient,
            },
            target_resource=f"message_draft:{draft.id}",
            approval_id=request.approval_id,
            session_id=session_id_auth,
        )

        if eval_result.decision != BrokerDecision.ALLOW:
            if eval_result.decision == BrokerDecision.REQUIRE_APPROVAL:
                draft.status = "APPROVAL_REQUIRED"
                if eval_result.approval_request:
                    draft.approval_id = eval_result.approval_request.id
                await db.commit()
                raise PermissionDeniedError(
                    f"Approval required to dispatch {draft.channel} message. Approval request ID: {draft.approval_id}"
                )
            raise PermissionDeniedError(f"Action denied by Policy Broker: {eval_result.reason}")

        # Execute dispatch via provider
        send_res = await self._agent.execute_send(
            channel=draft.channel,
            recipient=draft.recipient,
            subject=draft.subject,
            body=draft.body,
        )

        draft.status = "SENT"
        draft.sent_at = utcnow()
        draft.approval_id = request.approval_id

        await AuditService.record_event(
            session=db,
            user_id=user.id,
            session_id=session_id_auth,
            action_type="communication.message_send",
            resource_scope=f"message_draft:{draft.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "channel": draft.channel,
                "recipient": draft.recipient,
                "approval_id": str(request.approval_id) if request.approval_id else None,
            },
        )
        await db.commit()

        return SendMessageResponse(
            draft_id=draft.id,
            status=draft.status,
            sent_at=draft.sent_at.isoformat() if draft.sent_at else None,
            message=f"{draft.channel} dispatched successfully to {draft.recipient}.",
        )

    # --- Telephony Call Sessions ---

    async def plan_call(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: PlanCallRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> CallSessionResponse:
        """Prepare call briefing notes and agenda dossier (SAFE action)."""
        briefing = self._agent.prepare_call_briefing(
            recipient_phone=request.recipient_phone,
            purpose=request.purpose,
            briefing_notes=request.briefing_notes,
            recipient_name=request.recipient_name,
        )

        call = CallSession(
            user_id=user_id,
            recipient_phone=request.recipient_phone,
            recipient_name=request.recipient_name,
            purpose=request.purpose,
            briefing_notes=briefing,
            recording_consent_disclosed=request.recording_consent_disclosed,
            status="PLANNED",
        )
        db.add(call)
        await db.commit()
        await db.refresh(call)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="communication.call_plan",
            resource_scope=f"call_session:{call.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "recipient_phone": call.recipient_phone,
                "purpose": call.purpose,
            },
        )
        await db.commit()

        return CallSessionResponse(
            id=call.id,
            user_id=call.user_id,
            recipient_phone=call.recipient_phone,
            recipient_name=call.recipient_name,
            purpose=call.purpose,
            briefing_notes=call.briefing_notes,
            recording_consent_disclosed=call.recording_consent_disclosed,
            status=call.status,
            transcript=call.transcript,
            call_summary=call.call_summary,
            approval_id=call.approval_id,
            duration_seconds=call.duration_seconds,
            created_at=call.created_at.isoformat(),
            updated_at=call.updated_at.isoformat(),
        )

    async def list_calls(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[CallSessionResponse]:
        """List user's telephony call sessions with tenant isolation."""
        stmt = (
            select(CallSession)
            .where(CallSession.user_id == user_id)
            .order_by(desc(CallSession.created_at))
        )
        result = await db.execute(stmt)
        calls = result.scalars().all()

        return [
            CallSessionResponse(
                id=c.id,
                user_id=c.user_id,
                recipient_phone=c.recipient_phone,
                recipient_name=c.recipient_name,
                purpose=c.purpose,
                briefing_notes=c.briefing_notes,
                recording_consent_disclosed=c.recording_consent_disclosed,
                status=c.status,
                transcript=c.transcript,
                call_summary=c.call_summary,
                approval_id=c.approval_id,
                duration_seconds=c.duration_seconds,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat(),
            )
            for c in calls
        ]

    async def get_call(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        call_id: uuid.UUID,
    ) -> CallSession:
        """Fetch single call session ensuring tenant isolation."""
        stmt = select(CallSession).where(
            CallSession.id == call_id,
            CallSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        if not call:
            raise EntityNotFoundError("CallSession", call_id)
        return call

    async def initiate_call(
        self,
        db: AsyncSession,
        user: User,
        call_id: uuid.UUID,
        request: InitiateCallRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> InitiateCallResponse:
        """Dial out call under consequential Policy Broker approval gate."""
        call = await self.get_call(db, user.id, call_id)
        if call.status == "COMPLETED":
            return InitiateCallResponse(
                call_id=call.id,
                status=call.status,
                transcript=call.transcript,
                call_summary=call.call_summary,
                message="Call has already been completed.",
            )

        # Policy Broker consequential approval evaluation
        eval_result = await self._broker.evaluate_action(
            session=db,
            actor=user,
            tool_name="communication.initiate_call",
            arguments={
                "call_id": str(call.id),
                "recipient_phone": call.recipient_phone,
                "purpose": call.purpose,
            },
            target_resource=f"call_session:{call.id}",
            approval_id=request.approval_id,
            session_id=session_id_auth,
        )

        if eval_result.decision != BrokerDecision.ALLOW:
            if eval_result.decision == BrokerDecision.REQUIRE_APPROVAL:
                call.status = "APPROVAL_REQUIRED"
                if eval_result.approval_request:
                    call.approval_id = eval_result.approval_request.id
                await db.commit()
                raise PermissionDeniedError(
                    f"Approval required to dial out phone call. Approval request ID: {call.approval_id}"
                )
            raise PermissionDeniedError(f"Action denied by Policy Broker: {eval_result.reason}")

        # Execute call via provider
        call_res = await self._agent.execute_call(
            recipient_phone=call.recipient_phone,
            purpose=call.purpose,
            briefing_notes=call.briefing_notes,
            recording_consent_disclosed=call.recording_consent_disclosed,
        )

        call.status = "COMPLETED"
        call.transcript = call_res.get("transcript")
        call.call_summary = call_res.get("call_summary")
        call.duration_seconds = call_res.get("duration_seconds", 120)
        call.approval_id = request.approval_id

        await AuditService.record_event(
            session=db,
            user_id=user.id,
            session_id=session_id_auth,
            action_type="communication.call_initiate",
            resource_scope=f"call_session:{call.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "recipient_phone": call.recipient_phone,
                "duration_seconds": call.duration_seconds,
                "approval_id": str(request.approval_id) if request.approval_id else None,
            },
        )
        await db.commit()

        return InitiateCallResponse(
            call_id=call.id,
            status=call.status,
            transcript=call.transcript,
            call_summary=call.call_summary,
            message="Call completed successfully.",
        )
