"""Unit and domain integration tests for Vision, Camera, & Screen multimodal service."""

import base64
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.audit import AuditLog
from app.models.user import User
from app.services.vision.providers import MockVisionProvider
from app.services.vision.schemas import (
    AnalyzeFrameRequest,
    CreateVisionSessionRequest,
    StandaloneVisionAnalysisRequest,
    TogglePrivacyRequest,
)
from app.services.vision.service import VisionService
from app.services.vision.validator import VisionValidator

# Standard valid 1x1 PNG image base64
VALID_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# Standard valid JPEG image bytes in base64 (\xff\xd8\xff header)
VALID_JPEG_BASE64 = base64.b64encode(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00").decode("utf-8")


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    """Create test user fixture."""
    u = User(
        id=uuid.uuid4(),
        email=f"vision_unit_{uuid.uuid4().hex[:6]}@jarvis.ai",
        hashed_password="hashed_pw_test",
        timezone="Asia/Kolkata",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


class TestVisionValidator:
    """Tests for image validation, magic bytes verification, and privacy constraints."""

    def test_clean_and_decode_valid_png(self):
        raw_data = f"data:image/png;base64,{VALID_PNG_BASE64}"
        image_bytes, media_type = VisionValidator.clean_and_decode_base64(raw_data)
        assert media_type == "image/png"
        assert len(image_bytes) > 0
        assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    def test_clean_and_decode_valid_jpeg(self):
        image_bytes, media_type = VisionValidator.clean_and_decode_base64(VALID_JPEG_BASE64)
        assert media_type == "image/jpeg"
        assert image_bytes.startswith(b"\xff\xd8\xff")

    def test_rejects_corrupt_or_empty_base64(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            VisionValidator.clean_and_decode_base64("")

        with pytest.raises(ValidationError, match="Invalid base64"):
            VisionValidator.clean_and_decode_base64("not-valid-base64-content!@#$%")

    def test_rejects_spoofed_or_unsupported_header(self):
        fake_image = base64.b64encode(b"THIS_IS_PLAIN_TEXT_NOT_AN_IMAGE").decode("utf-8")
        with pytest.raises(ValidationError, match="Unsupported or unrecognized image header"):
            VisionValidator.clean_and_decode_base64(fake_image)

    def test_session_constraints_require_consent(self):
        with pytest.raises(ValidationError, match="Explicit user consent is mandatory"):
            VisionValidator.validate_session_constraints("SCREEN_SHARE", consent_granted=False)

    def test_session_constraints_validate_type(self):
        with pytest.raises(ValidationError, match="Invalid vision session type"):
            VisionValidator.validate_session_constraints("UNSUPPORTED_TYPE", consent_granted=True)


class TestVisionService:
    """Domain tests for session management, privacy toggles, frame analysis, and audits."""

    @pytest.fixture
    def mock_provider(self) -> MockVisionProvider:
        return MockVisionProvider()

    @pytest.fixture
    def vision_service(self, mock_provider: MockVisionProvider) -> VisionService:
        return VisionService(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_session_creation_and_privacy_toggles(
        self,
        db_session: AsyncSession,
        user: User,
        vision_service: VisionService,
    ):
        # 1. Create screen share session
        session_req = CreateVisionSessionRequest(
            title="Desktop Screen Inspection",
            session_type="SCREEN_SHARE",
            consent_granted=True,
            device_info="Primary Display 2560x1440",
        )
        session = await vision_service.create_session(
            db=db_session,
            user_id=user.id,
            request=session_req,
        )
        assert session.title == "Desktop Screen Inspection"
        assert session.session_type == "SCREEN_SHARE"
        assert session.status == "ACTIVE"
        assert session.privacy_indicator is True
        assert session.consent_granted is True

        # 2. Toggle privacy to MUTE
        toggle_mute = await vision_service.toggle_privacy(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=TogglePrivacyRequest(action="MUTE"),
        )
        assert toggle_mute.status == "MUTED"
        assert toggle_mute.privacy_indicator is False

        # Attempting frame analysis while MUTED must be blocked
        with pytest.raises(PermissionDeniedError, match="MUTED"):
            await vision_service.analyze_frame(
                db=db_session,
                user_id=user.id,
                session_id=session.id,
                request=AnalyzeFrameRequest(image_base64=VALID_PNG_BASE64),
            )

        # 3. Toggle privacy to UNMUTE
        toggle_unmute = await vision_service.toggle_privacy(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=TogglePrivacyRequest(action="UNMUTE"),
        )
        assert toggle_unmute.status == "ACTIVE"
        assert toggle_unmute.privacy_indicator is True

        # 4. Toggle privacy to STOP
        toggle_stop = await vision_service.toggle_privacy(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=TogglePrivacyRequest(action="STOP"),
        )
        assert toggle_stop.status == "STOPPED"
        assert toggle_stop.privacy_indicator is False

        # Attempting frame analysis on STOPPED session must be blocked
        with pytest.raises(PermissionDeniedError, match="STOPPED"):
            await vision_service.analyze_frame(
                db=db_session,
                user_id=user.id,
                session_id=session.id,
                request=AnalyzeFrameRequest(image_base64=VALID_PNG_BASE64),
            )

    @pytest.mark.asyncio
    async def test_frame_analysis_and_ocr(
        self,
        db_session: AsyncSession,
        user: User,
        vision_service: VisionService,
    ):
        session = await vision_service.create_session(
            db=db_session,
            user_id=user.id,
            request=CreateVisionSessionRequest(
                title="Invoice OCR Session",
                session_type="IMAGE_UPLOAD",
                consent_granted=True,
            ),
        )

        # Ingest frame asking for OCR
        frame_res = await vision_service.analyze_frame(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=AnalyzeFrameRequest(
                image_base64=VALID_PNG_BASE64,
                query_prompt="Extract all text and OCR data from this document",
                width=1920,
                height=1080,
            ),
        )
        assert frame_res.session_id == session.id
        assert frame_res.media_type == "image/png"
        assert frame_res.ocr_text is not None
        assert "JARVIS Multimodal OCR Engine" in frame_res.ocr_text
        assert "document_header" in frame_res.detected_objects

        # Ingest frame asking for screen UI analysis
        frame_res2 = await vision_service.analyze_frame(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=AnalyzeFrameRequest(
                image_base64=VALID_PNG_BASE64,
                query_prompt="Inspect active screen window layout and buttons",
            ),
        )
        assert "window_frame" in frame_res2.detected_objects
        assert "Screen capture analysis" in frame_res2.analysis_result

        # List frames for session
        frames = await vision_service.list_frames(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
        )
        assert len(frames) == 2

    @pytest.mark.asyncio
    async def test_standalone_analysis(
        self,
        vision_service: VisionService,
    ):
        standalone_res = await vision_service.analyze_standalone(
            request=StandaloneVisionAnalysisRequest(
                image_base64=VALID_PNG_BASE64,
                query_prompt="What is shown in this image?",
            )
        )
        assert standalone_res.analysis_result is not None
        assert len(standalone_res.detected_objects) > 0
        assert standalone_res.model_used == "mock-vision-v1"

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        db_session: AsyncSession,
        user: User,
        vision_service: VisionService,
    ):
        session = await vision_service.create_session(
            db=db_session,
            user_id=user.id,
            request=CreateVisionSessionRequest(title="Isolation Test"),
        )

        other_user_id = uuid.uuid4()
        with pytest.raises(EntityNotFoundError):
            await vision_service.get_session(
                db=db_session,
                user_id=other_user_id,
                session_id=session.id,
            )

    @pytest.mark.asyncio
    async def test_audit_trail_recorded(
        self,
        db_session: AsyncSession,
        user: User,
        vision_service: VisionService,
    ):
        session = await vision_service.create_session(
            db=db_session,
            user_id=user.id,
            request=CreateVisionSessionRequest(title="Audited Session"),
        )
        await vision_service.toggle_privacy(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=TogglePrivacyRequest(action="MUTE"),
        )
        await vision_service.toggle_privacy(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=TogglePrivacyRequest(action="UNMUTE"),
        )
        await vision_service.analyze_frame(
            db=db_session,
            user_id=user.id,
            session_id=session.id,
            request=AnalyzeFrameRequest(image_base64=VALID_PNG_BASE64),
        )

        stmt = AuditLog.__table__.select().where(AuditLog.user_id == user.id)
        result = await db_session.execute(stmt)
        rows = result.fetchall()
        action_types = [r.action_type for r in rows]
        assert "vision.session_create" in action_types
        assert "vision.privacy_toggle" in action_types
        assert "vision.frame_analyze" in action_types
