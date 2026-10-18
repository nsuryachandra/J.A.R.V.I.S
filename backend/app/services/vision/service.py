"""Domain service for Vision, Camera, & Screen multimodal inspection and privacy lifecycle."""

import json
import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.user import User
from app.models.vision import VisionFrame, VisionSession
from app.services.audit_service import AuditService
from app.services.policy_broker import PolicyBroker
from app.services.vision.providers import BaseVisionProvider
from app.services.vision.schemas import (
    AnalyzeFrameRequest,
    CreateVisionSessionRequest,
    StandaloneVisionAnalysisRequest,
    StandaloneVisionAnalysisResponse,
    TogglePrivacyRequest,
    TogglePrivacyResponse,
    VisionFrameResponse,
    VisionSessionSummary,
)
from app.services.vision.validator import VisionValidator
from app.services.vision.vision_agent import VisionAgent


class VisionService:
    """Service orchestrating multimodal vision sessions, privacy states, and frame reasoning."""

    def __init__(
        self,
        broker: Optional[PolicyBroker] = None,
        provider: Optional[BaseVisionProvider] = None,
    ):
        self._broker = broker or PolicyBroker()
        self._agent = VisionAgent(provider=provider)

    @property
    def agent(self) -> VisionAgent:
        return self._agent

    async def create_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: CreateVisionSessionRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> VisionSessionSummary:
        """Create a new user-scoped vision capture or streaming session with mandatory consent."""
        session_type = request.session_type.upper()
        VisionValidator.validate_session_constraints(
            session_type=session_type,
            consent_granted=request.consent_granted,
        )

        session_rec = VisionSession(
            user_id=user_id,
            title=request.title or "Vision Inspection Session",
            session_type=session_type,
            status="ACTIVE",
            privacy_indicator=True,
            consent_granted=request.consent_granted,
            device_info=request.device_info,
        )
        db.add(session_rec)
        await db.commit()
        await db.refresh(session_rec)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="vision.session_create",
            resource_scope=f"vision_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "title": session_rec.title,
                "session_type": session_rec.session_type,
                "device_info": session_rec.device_info,
            },
        )
        await db.commit()

        return VisionSessionSummary(
            id=session_rec.id,
            user_id=session_rec.user_id,
            title=session_rec.title,
            session_type=session_rec.session_type,
            status=session_rec.status,
            privacy_indicator=session_rec.privacy_indicator,
            consent_granted=session_rec.consent_granted,
            device_info=session_rec.device_info,
            frames_count=0,
            created_at=session_rec.created_at.isoformat(),
            updated_at=session_rec.updated_at.isoformat(),
        )

    async def list_user_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[VisionSessionSummary]:
        """List authenticated user's vision sessions with strict tenant isolation."""
        stmt = (
            select(VisionSession)
            .where(VisionSession.user_id == user_id)
            .options(selectinload(VisionSession.frames))
            .order_by(desc(VisionSession.created_at))
        )
        result = await db.execute(stmt)
        sessions = result.scalars().all()

        return [
            VisionSessionSummary(
                id=s.id,
                user_id=s.user_id,
                title=s.title,
                session_type=s.session_type,
                status=s.status,
                privacy_indicator=s.privacy_indicator,
                consent_granted=s.consent_granted,
                device_info=s.device_info,
                frames_count=len(s.frames),
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat(),
            )
            for s in sessions
        ]

    async def get_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> VisionSession:
        """Fetch session ensuring tenant isolation."""
        stmt = (
            select(VisionSession)
            .where(VisionSession.id == session_id, VisionSession.user_id == user_id)
            .options(selectinload(VisionSession.frames))
        )
        result = await db.execute(stmt)
        session_rec = result.scalar_one_or_none()
        if not session_rec:
            raise EntityNotFoundError("VisionSession", session_id)
        return session_rec

    async def toggle_privacy(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        request: TogglePrivacyRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> TogglePrivacyResponse:
        """Toggle capture privacy state (MUTE, UNMUTE, STOP)."""
        session_rec = await self.get_session(db, user_id, session_id)

        action = request.action.upper()
        if action == "MUTE":
            session_rec.status = "MUTED"
            session_rec.privacy_indicator = False
            msg = "Vision capture feed muted. Visual indicators turned off."
        elif action == "UNMUTE":
            session_rec.status = "ACTIVE"
            session_rec.privacy_indicator = True
            msg = "Vision capture feed active. Visual indicator illuminated."
        elif action == "STOP":
            session_rec.status = "STOPPED"
            session_rec.privacy_indicator = False
            msg = "Vision session terminated. Camera and screen sharing disabled."
        else:
            raise ValidationError(f"Invalid privacy action '{request.action}'. Supported: 'MUTE', 'UNMUTE', 'STOP'.")

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="vision.privacy_toggle",
            resource_scope=f"vision_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={"action": action, "new_status": session_rec.status},
        )
        await db.commit()

        return TogglePrivacyResponse(
            session_id=session_rec.id,
            status=session_rec.status,
            privacy_indicator=session_rec.privacy_indicator,
            message=msg,
        )

    async def analyze_frame(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        request: AnalyzeFrameRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> VisionFrameResponse:
        """Ingest, validate, and analyze a visual frame within an active session."""
        session_rec = await self.get_session(db, user_id, session_id)

        # Enforce privacy state
        if session_rec.status == "MUTED":
            raise PermissionDeniedError(
                "Cannot analyze frames while vision session is MUTED. Unmute session to resume."
            )
        if session_rec.status == "STOPPED":
            raise PermissionDeniedError(
                "Cannot analyze frames on a STOPPED vision session."
            )

        # Process and analyze image
        analysis_dict, image_bytes, detected_media_type = await self._agent.process_and_analyze(
            image_base64=request.image_base64,
            prompt=request.query_prompt,
        )

        detected_objects = analysis_dict.get("detected_objects", [])

        frame = VisionFrame(
            session_id=session_rec.id,
            user_id=user_id,
            media_type=detected_media_type,
            image_base64=request.image_base64,
            width=request.width or 1280,
            height=request.height or 720,
            size_bytes=len(image_bytes),
            query_prompt=request.query_prompt,
            analysis_result=analysis_dict["analysis_result"],
            ocr_text=analysis_dict.get("ocr_text"),
            detected_objects=json.dumps(detected_objects),
        )
        db.add(frame)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="vision.frame_analyze",
            resource_scope=f"vision_frame:{frame.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "session_id": str(session_rec.id),
                "media_type": detected_media_type,
                "size_bytes": len(image_bytes),
                "detected_objects_count": len(detected_objects),
            },
        )
        await db.commit()
        await db.refresh(frame)

        return VisionFrameResponse(
            id=frame.id,
            session_id=frame.session_id,
            media_type=frame.media_type,
            width=frame.width,
            height=frame.height,
            size_bytes=frame.size_bytes,
            query_prompt=frame.query_prompt,
            analysis_result=frame.analysis_result,
            ocr_text=frame.ocr_text,
            detected_objects=detected_objects,
            created_at=frame.created_at.isoformat(),
        )

    async def list_frames(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> List[VisionFrameResponse]:
        """List all analyzed visual frames for session."""
        session_rec = await self.get_session(db, user_id, session_id)

        stmt = (
            select(VisionFrame)
            .where(VisionFrame.session_id == session_rec.id)
            .order_by(desc(VisionFrame.created_at))
        )
        result = await db.execute(stmt)
        frames = result.scalars().all()

        out: List[VisionFrameResponse] = []
        for f in frames:
            objs = []
            if f.detected_objects:
                try:
                    objs = json.loads(f.detected_objects)
                except Exception:
                    objs = []
            out.append(
                VisionFrameResponse(
                    id=f.id,
                    session_id=f.session_id,
                    media_type=f.media_type,
                    width=f.width,
                    height=f.height,
                    size_bytes=f.size_bytes,
                    query_prompt=f.query_prompt,
                    analysis_result=f.analysis_result,
                    ocr_text=f.ocr_text,
                    detected_objects=objs,
                    created_at=f.created_at.isoformat(),
                )
            )
        return out

    async def analyze_standalone(
        self,
        request: StandaloneVisionAnalysisRequest,
    ) -> StandaloneVisionAnalysisResponse:
        """Perform direct visual analysis without a persistent session."""
        analysis_dict, _, _ = await self._agent.process_and_analyze(
            image_base64=request.image_base64,
            prompt=request.query_prompt,
        )

        return StandaloneVisionAnalysisResponse(
            analysis_result=analysis_dict["analysis_result"],
            ocr_text=analysis_dict.get("ocr_text"),
            detected_objects=analysis_dict.get("detected_objects", []),
            model_used=analysis_dict.get("model_used", "mock-vision"),
        )
