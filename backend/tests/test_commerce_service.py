"""Unit and domain integration tests for Commerce, Booking, & External Actions."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.user import User
from app.services.approval_service import ApprovalService
from app.services.commerce.providers import MockCommerceProvider
from app.services.commerce.schemas import (
    CompareProductsRequest,
    CreateOrderDraftRequest,
    ExecuteOrderRequest,
    OrderItem,
)
from app.services.commerce.service import CommerceService


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


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create second user for tenant isolation testing."""
    u = User(
        id=uuid.uuid4(),
        email=f"comm_other_{uuid.uuid4().hex[:6]}@jarvis.ai",
        hashed_password="hashed_pw_test",
        timezone="Asia/Kolkata",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


class TestCommerceService:
    """Domain tests for product comparison, order/booking drafts, double confirmation, Policy Broker gating, and idempotency."""

    @pytest.fixture
    def mock_provider(self) -> MockCommerceProvider:
        return MockCommerceProvider()

    @pytest.fixture
    def commerce_service(self, mock_provider: MockCommerceProvider) -> CommerceService:
        return CommerceService(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_compare_products_safe_action(
        self,
        commerce_service: CommerceService,
    ):
        """Verify product comparison queries across merchants without requiring approvals."""
        comp_req = CompareProductsRequest(
            query="Ergonomic Mechanical Keyboard",
            category="Electronics",
            max_price=160.0,
        )
        res = await commerce_service.compare(comp_req)
        assert res.query == "Ergonomic Mechanical Keyboard"
        assert res.category == "Electronics"
        assert len(res.options) >= 2
        for opt in res.options:
            assert opt.price <= 160.0
            assert opt.availability == "IN_STOCK"
        assert "Ergonomic Mechanical Keyboard" in res.best_value_recommendation

    @pytest.mark.asyncio
    async def test_create_order_draft_and_idempotency(
        self,
        db_session: AsyncSession,
        user: User,
        commerce_service: CommerceService,
    ):
        """Verify draft creation accurately calculates subtotal, tax, and enforces idempotency."""
        items = [
            OrderItem(name="Ultra-Wide Monitor", quantity=1, unit_price=400.0, total_price=400.0),
            OrderItem(name="USB-C Docking Station", quantity=2, unit_price=50.0, total_price=100.0),
        ]
        draft_req = CreateOrderDraftRequest(
            order_type="PURCHASE",
            merchant="TechHub Superstore",
            title="Desk Setup Upgrade",
            currency="USD",
            items=items,
            delivery_details="Floor 4, Suite 402, Tech Park",
            idempotency_key="idemp_desk_upgrade_001",
        )

        draft1 = await commerce_service.create_order_draft(
            db=db_session,
            user_id=user.id,
            request=draft_req,
        )
        assert draft1.merchant == "TechHub Superstore"
        assert draft1.subtotal_amount == 500.0
        assert draft1.tax_amount == 40.0  # 8% tax
        assert draft1.total_amount == 540.0
        assert draft1.status == "DRAFT"
        assert draft1.idempotency_key == "idemp_desk_upgrade_001"

        # Calling again with same idempotency key returns the existing draft
        draft2 = await commerce_service.create_order_draft(
            db=db_session,
            user_id=user.id,
            request=draft_req,
        )
        assert draft2.id == draft1.id
        assert draft2.total_amount == 540.0

    @pytest.mark.asyncio
    async def test_execute_order_requires_double_confirmation(
        self,
        db_session: AsyncSession,
        user: User,
        commerce_service: CommerceService,
    ):
        """Verify execute_order rejects requests if confirmed_by_user is False."""
        items = [OrderItem(name="Flight Ticket SFO->JFK", quantity=1, unit_price=350.0, total_price=350.0)]
        draft_req = CreateOrderDraftRequest(
            order_type="FLIGHT_BOOKING",
            merchant="SkyWays Aero",
            title="SFO to JFK Flight",
            currency="USD",
            items=items,
            booking_date="2026-11-01T08:00:00Z",
            idempotency_key="idemp_flight_sfo_002",
        )
        draft = await commerce_service.create_order_draft(
            db=db_session,
            user_id=user.id,
            request=draft_req,
        )

        exec_req = ExecuteOrderRequest(
            confirmed_by_user=False,  # NOT confirmed!
        )
        with pytest.raises(ValidationError) as exc:
            await commerce_service.execute_order(
                db=db_session,
                user=user,
                order_id=draft.id,
                request=exec_req,
            )
        assert "Double-confirmation required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_execute_order_consequential_approval_gate_and_execution(
        self,
        db_session: AsyncSession,
        user: User,
        commerce_service: CommerceService,
    ):
        """Verify consequential action gating: 403 on unapproved checkout, succeeds when approved."""
        items = [OrderItem(name="Conference Pass", quantity=1, unit_price=250.0, total_price=250.0)]
        draft_req = CreateOrderDraftRequest(
            order_type="SERVICE_ORDER",
            merchant="AI Summit 2026",
            title="General Admission Ticket",
            currency="USD",
            items=items,
            idempotency_key="idemp_conf_pass_003",
        )
        draft = await commerce_service.create_order_draft(
            db=db_session,
            user_id=user.id,
            request=draft_req,
        )

        # 1. Attempt execute without approval token -> PermissionDeniedError and approval request created
        exec_req = ExecuteOrderRequest(
            confirmed_by_user=True,
            payment_method="CORPORATE_CARD",
        )
        with pytest.raises(PermissionDeniedError) as exc:
            await commerce_service.execute_order(
                db=db_session,
                user=user,
                order_id=draft.id,
                request=exec_req,
            )
        assert "Approval required to execute financial transaction" in str(exc.value)

        # Verify draft marked as APPROVAL_REQUIRED and linked to approval_id
        refreshed_draft = await commerce_service.get_order(db_session, user.id, draft.id)
        assert refreshed_draft.status == "APPROVAL_REQUIRED"
        assert refreshed_draft.approval_id is not None

        # 2. Approve via ApprovalService
        await ApprovalService.approve_request(
            session=db_session,
            approval_id=refreshed_draft.approval_id,
            user_id=user.id,
            approval_method="UI_CONFIRMATION",
        )

        # 3. Retry execute with approved approval_id
        exec_req_approved = ExecuteOrderRequest(
            approval_id=refreshed_draft.approval_id,
            confirmed_by_user=True,
            payment_method="CORPORATE_CARD",
        )
        res = await commerce_service.execute_order(
            db=db_session,
            user=user,
            order_id=draft.id,
            request=exec_req_approved,
        )
        assert res.status == "EXECUTED"
        assert res.total_charged == 270.0  # 250 + 20 tax (8%)
        assert res.currency == "USD"
        assert res.transaction_reference.startswith("TXN-")
        assert "Successfully charged" in res.receipt_summary

        # 4. Strict idempotency replay test: Re-executing already executed order returns receipt without recharging
        res_replay = await commerce_service.execute_order(
            db=db_session,
            user=user,
            order_id=draft.id,
            request=exec_req_approved,
        )
        assert res_replay.status == "EXECUTED"
        assert res_replay.transaction_reference == res.transaction_reference
        assert "previously executed" in res_replay.receipt_summary

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        db_session: AsyncSession,
        user: User,
        other_user: User,
        commerce_service: CommerceService,
    ):
        """Verify cross-tenant isolation: other_user cannot view or execute user's orders."""
        items = [OrderItem(name="Cloud Storage 1TB", quantity=1, unit_price=99.0, total_price=99.0)]
        draft_req = CreateOrderDraftRequest(
            order_type="PURCHASE",
            merchant="CloudCore",
            title="Storage Subscription",
            currency="USD",
            items=items,
            idempotency_key="idemp_storage_004",
        )
        draft = await commerce_service.create_order_draft(
            db=db_session,
            user_id=user.id,
            request=draft_req,
        )

        # User's list has 1 draft
        user_orders = await commerce_service.list_orders(db_session, user.id)
        assert any(o.id == draft.id for o in user_orders)

        # Other user's list has 0 drafts
        other_orders = await commerce_service.list_orders(db_session, other_user.id)
        assert not any(o.id == draft.id for o in other_orders)

        # Other user cannot get order
        with pytest.raises(EntityNotFoundError):
            await commerce_service.get_order(db_session, other_user.id, draft.id)

        # Other user cannot execute order
        with pytest.raises(EntityNotFoundError):
            await commerce_service.execute_order(
                db=db_session,
                user=other_user,
                order_id=draft.id,
                request=ExecuteOrderRequest(confirmed_by_user=True),
            )

    @pytest.mark.asyncio
    async def test_execute_order_with_tampered_or_foreign_approval_token(
        self,
        db_session: AsyncSession,
        user: User,
        other_user: User,
        commerce_service: CommerceService,
    ):
        """Verify tampering prevention: an approval granted for another action or user is rejected."""
        items = [OrderItem(name="Gift Card", quantity=1, unit_price=100.0, total_price=100.0)]
        draft_req = CreateOrderDraftRequest(
            order_type="PURCHASE",
            merchant="CardShop",
            title="Gift Card Order",
            currency="USD",
            items=items,
            idempotency_key="idemp_tamper_005",
        )
        draft = await commerce_service.create_order_draft(
            db=db_session,
            user_id=user.id,
            request=draft_req,
        )

        # Create an approval request for other_user for a completely different tool
        foreign_approval = await ApprovalService.create_request(
            session=db_session,
            user_id=other_user.id,
            tool_name="communication.send_message",
            tool_version="1.0.0",
            arguments={"recipient": "someone@example.com"},
            target_resource="message_draft:123",
            risk_class="CONSEQUENTIAL",
        )
        await ApprovalService.approve_request(
            session=db_session,
            approval_id=foreign_approval.id,
            user_id=other_user.id,
        )

        # Attempt to use foreign approval to execute user's commerce order
        with pytest.raises(PermissionDeniedError):
            await commerce_service.execute_order(
                db=db_session,
                user=user,
                order_id=draft.id,
                request=ExecuteOrderRequest(
                    approval_id=foreign_approval.id,
                    confirmed_by_user=True,
                ),
            )

