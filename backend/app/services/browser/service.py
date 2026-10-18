"""Domain service for Browser & Computer Agent sessions, actions, and approvals."""

import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.browser import BrowserAction, BrowserScreenshot, BrowserSession
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.browser.browser_agent import BrowserAgent
from app.services.browser.providers import BaseBrowserProvider
from app.services.browser.schemas import (
    BrowserActionResponse,
    BrowserSessionSummary,
    CaptureScreenshotRequest,
    CreateBrowserSessionRequest,
    FillFormRequest,
    FillFormResponse,
    NavigateRequest,
    NavigateResponse,
    PageElementInfo,
    ReadPageResponse,
    ScreenshotResponse,
    SubmitFormRequest,
    SubmitFormResponse,
)
from app.services.policy_broker import BrokerDecision, PolicyBroker


class BrowserService:
    """Service orchestrating headless browser sessions, page interactions, and approval gates."""

    def __init__(
        self,
        broker: Optional[PolicyBroker] = None,
        provider: Optional[BaseBrowserProvider] = None,
    ):
        self._broker = broker or PolicyBroker()
        self._agent = BrowserAgent(provider=provider)

    @property
    def agent(self) -> BrowserAgent:
        return self._agent

    async def create_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: CreateBrowserSessionRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> BrowserSessionSummary:
        """Create a new user-scoped browser interaction session."""
        session_rec = BrowserSession(
            user_id=user_id,
            title=request.title or "Web Interaction Session",
            current_url="about:blank",
            status="ACTIVE",
            viewport_width=request.viewport_width,
            viewport_height=request.viewport_height,
        )
        db.add(session_rec)
        await db.commit()
        await db.refresh(session_rec)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="browser.session_create",
            resource_scope=f"browser_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "title": session_rec.title,
                "viewport_width": session_rec.viewport_width,
                "viewport_height": session_rec.viewport_height,
            },
        )
        await db.commit()

        return BrowserSessionSummary(
            id=session_rec.id,
            user_id=session_rec.user_id,
            title=session_rec.title,
            current_url=session_rec.current_url,
            status=session_rec.status,
            viewport_width=session_rec.viewport_width,
            viewport_height=session_rec.viewport_height,
            created_at=session_rec.created_at.isoformat(),
            updated_at=session_rec.updated_at.isoformat(),
        )

    async def list_user_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[BrowserSessionSummary]:
        """List authenticated user's browser sessions with strict tenant isolation."""
        stmt = (
            select(BrowserSession)
            .where(BrowserSession.user_id == user_id)
            .order_by(desc(BrowserSession.created_at))
        )
        result = await db.execute(stmt)
        sessions = result.scalars().all()

        return [
            BrowserSessionSummary(
                id=s.id,
                user_id=s.user_id,
                title=s.title,
                current_url=s.current_url,
                status=s.status,
                viewport_width=s.viewport_width,
                viewport_height=s.viewport_height,
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
    ) -> BrowserSession:
        """Fetch session ensuring tenant isolation."""
        stmt = select(BrowserSession).where(
            BrowserSession.id == session_id,
            BrowserSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        session_rec = result.scalar_one_or_none()
        if not session_rec:
            raise EntityNotFoundError("BrowserSession", session_id)
        return session_rec

    async def navigate(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        request: NavigateRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> NavigateResponse:
        """Navigate browser to target URL with SSRF/loopback validation and audit logging."""
        session_rec = await self.get_session(db, user_id, session_id)

        nav_result = await self._agent.navigate(request.url)
        session_rec.current_url = nav_result["url"]

        action = BrowserAction(
            session_id=session_rec.id,
            action_type="NAVIGATE",
            target_selector=None,
            value=nav_result["url"],
            status="SUCCESS",
        )
        db.add(action)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="browser.navigate",
            resource_scope=f"browser_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={"url": nav_result["url"], "title": nav_result["title"]},
        )
        await db.commit()

        return NavigateResponse(
            session_id=session_rec.id,
            url=nav_result["url"],
            title=nav_result["title"],
            status_code=nav_result.get("status_code", 200),
            status=nav_result.get("status", "LOADED"),
        )

    async def read_page(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> ReadPageResponse:
        """Extract text and elements from active page wrapped in security delimiter tags."""
        session_rec = await self.get_session(db, user_id, session_id)

        data = await self._agent.read_page(session_rec.current_url)

        action = BrowserAction(
            session_id=session_rec.id,
            action_type="READ_PAGE",
            target_selector=None,
            value=session_rec.current_url,
            status="SUCCESS",
        )
        db.add(action)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="browser.read_page",
            resource_scope=f"browser_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "url": session_rec.current_url,
                "elements_count": len(data["elements"]),
            },
        )
        await db.commit()

        return ReadPageResponse(
            session_id=session_rec.id,
            url=session_rec.current_url,
            title=session_rec.title,
            content=data["wrapped_content"],
            raw_text=data["raw_text"],
            elements=data["elements"],
        )

    async def fill_form(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        request: FillFormRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> FillFormResponse:
        """Fill interactive form input."""
        session_rec = await self.get_session(db, user_id, session_id)

        success = await self._agent.fill_form(request.selector, request.value)

        action = BrowserAction(
            session_id=session_rec.id,
            action_type="FILL_FORM",
            target_selector=request.selector,
            value=request.value,
            status="SUCCESS" if success else "FAILED",
        )
        db.add(action)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="browser.fill_form",
            resource_scope=f"browser_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS" if success else "FAILED",
            details={"selector": request.selector},
        )
        await db.commit()

        return FillFormResponse(
            session_id=session_rec.id,
            selector=request.selector,
            value=request.value,
            success=success,
            status="FILLED" if success else "FAILED",
        )

    async def submit_form(
        self,
        db: AsyncSession,
        user: User,
        session_id: uuid.UUID,
        request: SubmitFormRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> SubmitFormResponse:
        """Submit form through Policy Broker approval gate (Consequential Action)."""
        session_rec = await self.get_session(db, user.id, session_id)

        # Evaluate consequential action with Policy Broker
        eval_result = await self._broker.evaluate_action(
            session=db,
            actor=user,
            tool_name="browser.submit_form",
            arguments={"session_id": str(session_id), "selector": request.selector},
            target_resource=f"browser_session:{session_rec.id}",
            approval_id=request.approval_id,
            session_id=session_id_auth,
        )

        if eval_result.decision != BrokerDecision.ALLOW:
            if eval_result.decision == BrokerDecision.REQUIRE_APPROVAL:
                action = BrowserAction(
                    session_id=session_rec.id,
                    action_type="SUBMIT_FORM",
                    target_selector=request.selector,
                    value=str(request.form_data) if request.form_data else None,
                    status="APPROVAL_REQUIRED",
                    approval_id=eval_result.approval_request.id if eval_result.approval_request else None,
                )
                db.add(action)
                await db.commit()
                raise PermissionDeniedError(
                    f"Approval required to submit form on page. Approval request ID: {action.approval_id}"
                )
            raise PermissionDeniedError(f"Action denied by Policy Broker: {eval_result.reason}")

        # Execute submission
        submit_res = await self._agent.submit_form(request.selector, request.form_data)
        if submit_res.get("new_url"):
            session_rec.current_url = submit_res["new_url"]

        action = BrowserAction(
            session_id=session_rec.id,
            action_type="SUBMIT_FORM",
            target_selector=request.selector,
            value=str(request.form_data) if request.form_data else None,
            status="SUCCESS",
            approval_id=request.approval_id,
        )
        db.add(action)

        await AuditService.record_event(
            session=db,
            user_id=user.id,
            session_id=session_id_auth,
            action_type="browser.submit_form",
            resource_scope=f"browser_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "selector": request.selector,
                "new_url": submit_res.get("new_url"),
                "approval_id": str(request.approval_id) if request.approval_id else None,
            },
        )
        await db.commit()

        return SubmitFormResponse(
            session_id=session_rec.id,
            selector=request.selector,
            status="SUCCESS",
            new_url=submit_res.get("new_url"),
            requires_approval=False,
            approval_request_id=request.approval_id,
            message="Form submitted successfully.",
        )

    async def capture_screenshot(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        request: CaptureScreenshotRequest,
        action_id: Optional[uuid.UUID] = None,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> ScreenshotResponse:
        """Capture visual base64 screenshot for human review and auditing."""
        session_rec = await self.get_session(db, user_id, session_id)

        img_b64 = await self._agent.capture_screenshot(
            width=session_rec.viewport_width,
            height=session_rec.viewport_height,
        )

        screenshot = BrowserScreenshot(
            session_id=session_rec.id,
            action_id=action_id,
            url=session_rec.current_url,
            image_base64=img_b64,
            width=session_rec.viewport_width,
            height=session_rec.viewport_height,
            caption=request.caption,
        )
        db.add(screenshot)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="browser.screenshot",
            resource_scope=f"browser_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={"caption": request.caption, "url": session_rec.current_url},
        )
        await db.commit()
        await db.refresh(screenshot)

        return ScreenshotResponse(
            id=screenshot.id,
            session_id=screenshot.session_id,
            action_id=screenshot.action_id,
            url=screenshot.url,
            image_base64=screenshot.image_base64,
            width=screenshot.width,
            height=screenshot.height,
            caption=screenshot.caption,
            created_at=screenshot.created_at.isoformat(),
        )

    async def list_screenshots(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> List[ScreenshotResponse]:
        """List captured screenshots for session."""
        session_rec = await self.get_session(db, user_id, session_id)

        stmt = (
            select(BrowserScreenshot)
            .where(BrowserScreenshot.session_id == session_rec.id)
            .order_by(desc(BrowserScreenshot.created_at))
        )
        result = await db.execute(stmt)
        screenshots = result.scalars().all()

        return [
            ScreenshotResponse(
                id=s.id,
                session_id=s.session_id,
                action_id=s.action_id,
                url=s.url,
                image_base64=s.image_base64,
                width=s.width,
                height=s.height,
                caption=s.caption,
                created_at=s.created_at.isoformat(),
            )
            for s in screenshots
        ]

    async def list_actions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> List[BrowserActionResponse]:
        """List recorded actions for session."""
        session_rec = await self.get_session(db, user_id, session_id)

        stmt = (
            select(BrowserAction)
            .where(BrowserAction.session_id == session_rec.id)
            .order_by(desc(BrowserAction.created_at))
        )
        result = await db.execute(stmt)
        actions = result.scalars().all()

        return [
            BrowserActionResponse(
                id=a.id,
                session_id=a.session_id,
                action_type=a.action_type,
                target_selector=a.target_selector,
                value=a.value,
                status=a.status,
                approval_id=a.approval_id,
                created_at=a.created_at.isoformat(),
            )
            for a in actions
        ]
