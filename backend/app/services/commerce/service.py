"""Domain service for Commerce, Booking, & External Actions under Policy Broker governance."""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from dateutil import parser as date_parser
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.base import utcnow
from app.models.commerce import OrderDraft
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.commerce.commerce_agent import CommerceAgent
from app.services.commerce.providers import BaseCommerceProvider
from app.services.commerce.schemas import (
    CompareProductsRequest,
    CompareProductsResponse,
    CreateOrderDraftRequest,
    ExecuteOrderRequest,
    ExecuteOrderResponse,
    OrderDraftResponse,
    OrderItem,
)
from app.services.policy_broker import BrokerDecision, PolicyBroker


class CommerceService:
    """Service orchestrating product comparison, order/booking drafts, double confirmation, and checkouts."""

    def __init__(
        self,
        broker: Optional[PolicyBroker] = None,
        provider: Optional[BaseCommerceProvider] = None,
    ):
        self._broker = broker or PolicyBroker()
        self._agent = CommerceAgent(provider=provider)

    @property
    def agent(self) -> CommerceAgent:
        return self._agent

    async def compare(self, request: CompareProductsRequest) -> CompareProductsResponse:
        """Compare product or booking options across merchants (SAFE action)."""
        return await self._agent.compare_offerings(
            query=request.query,
            category=request.category,
            max_price=request.max_price,
        )

    async def create_order_draft(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: CreateOrderDraftRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> OrderDraftResponse:
        """Prepare an order or travel booking draft with itemized breakdown (SAFE action)."""
        # Idempotency check: if draft with same idempotency_key exists for user, return existing
        existing_stmt = select(OrderDraft).where(
            OrderDraft.user_id == user_id,
            OrderDraft.idempotency_key == request.idempotency_key,
        )
        existing_res = await db.execute(existing_stmt)
        existing = existing_res.scalar_one_or_none()
        if existing:
            items_list = [OrderItem(**i) for i in json.loads(existing.items)]
            return OrderDraftResponse(
                id=existing.id,
                user_id=existing.user_id,
                order_type=existing.order_type,
                merchant=existing.merchant,
                title=existing.title,
                currency=existing.currency,
                subtotal_amount=existing.subtotal_amount,
                tax_amount=existing.tax_amount,
                total_amount=existing.total_amount,
                status=existing.status,
                items=items_list,
                delivery_details=existing.delivery_details,
                booking_date=existing.booking_date.isoformat() if existing.booking_date else None,
                idempotency_key=existing.idempotency_key,
                approval_id=existing.approval_id,
                transaction_reference=existing.transaction_reference,
                executed_at=existing.executed_at.isoformat() if existing.executed_at else None,
                created_at=existing.created_at.isoformat(),
                updated_at=existing.updated_at.isoformat(),
            )

        subtotal, tax, total = self._agent.calculate_totals(request.items)

        parsed_booking_date = None
        if request.booking_date:
            try:
                parsed_booking_date = date_parser.parse(request.booking_date)
            except Exception:
                parsed_booking_date = None

        draft = OrderDraft(
            user_id=user_id,
            order_type=request.order_type.upper(),
            merchant=request.merchant,
            title=request.title,
            currency=request.currency.upper(),
            subtotal_amount=subtotal,
            tax_amount=tax,
            total_amount=total,
            status="DRAFT",
            items=json.dumps([item.model_dump() for item in request.items]),
            delivery_details=request.delivery_details,
            booking_date=parsed_booking_date,
            idempotency_key=request.idempotency_key,
        )
        db.add(draft)
        await db.commit()
        await db.refresh(draft)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="commerce.draft_create",
            resource_scope=f"order_draft:{draft.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "merchant": draft.merchant,
                "order_type": draft.order_type,
                "total_amount": draft.total_amount,
                "currency": draft.currency,
            },
        )
        await db.commit()

        return OrderDraftResponse(
            id=draft.id,
            user_id=draft.user_id,
            order_type=draft.order_type,
            merchant=draft.merchant,
            title=draft.title,
            currency=draft.currency,
            subtotal_amount=draft.subtotal_amount,
            tax_amount=draft.tax_amount,
            total_amount=draft.total_amount,
            status=draft.status,
            items=request.items,
            delivery_details=draft.delivery_details,
            booking_date=draft.booking_date.isoformat() if draft.booking_date else None,
            idempotency_key=draft.idempotency_key,
            approval_id=draft.approval_id,
            transaction_reference=draft.transaction_reference,
            executed_at=draft.executed_at.isoformat() if draft.executed_at else None,
            created_at=draft.created_at.isoformat(),
            updated_at=draft.updated_at.isoformat(),
        )

    async def list_orders(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[OrderDraftResponse]:
        """List user's order and booking drafts with tenant isolation."""
        stmt = (
            select(OrderDraft)
            .where(OrderDraft.user_id == user_id)
            .order_by(desc(OrderDraft.created_at))
        )
        result = await db.execute(stmt)
        drafts = result.scalars().all()

        out: List[OrderDraftResponse] = []
        for d in drafts:
            items_list = [OrderItem(**i) for i in json.loads(d.items)]
            out.append(
                OrderDraftResponse(
                    id=d.id,
                    user_id=d.user_id,
                    order_type=d.order_type,
                    merchant=d.merchant,
                    title=d.title,
                    currency=d.currency,
                    subtotal_amount=d.subtotal_amount,
                    tax_amount=d.tax_amount,
                    total_amount=d.total_amount,
                    status=d.status,
                    items=items_list,
                    delivery_details=d.delivery_details,
                    booking_date=d.booking_date.isoformat() if d.booking_date else None,
                    idempotency_key=d.idempotency_key,
                    approval_id=d.approval_id,
                    transaction_reference=d.transaction_reference,
                    executed_at=d.executed_at.isoformat() if d.executed_at else None,
                    created_at=d.created_at.isoformat(),
                    updated_at=d.updated_at.isoformat(),
                )
            )
        return out

    async def get_order(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> OrderDraft:
        """Fetch single order draft ensuring tenant isolation."""
        stmt = select(OrderDraft).where(
            OrderDraft.id == order_id,
            OrderDraft.user_id == user_id,
        )
        result = await db.execute(stmt)
        draft = result.scalar_one_or_none()
        if not draft:
            raise EntityNotFoundError("OrderDraft", order_id)
        return draft

    async def execute_order(
        self,
        db: AsyncSession,
        user: User,
        order_id: uuid.UUID,
        request: ExecuteOrderRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> ExecuteOrderResponse:
        """Execute purchase or booking under double confirmation and Policy Broker approval gates."""
        order = await self.get_order(db, user.id, order_id)

        # Idempotency replay check: if already executed, return settled receipt directly
        if order.status == "EXECUTED":
            return ExecuteOrderResponse(
                order_id=order.id,
                status=order.status,
                transaction_reference=order.transaction_reference or "PREVIOUSLY_SETTLED",
                total_charged=order.total_amount,
                currency=order.currency,
                receipt_summary=(
                    f"Transaction previously executed and settled for {order.currency} {order.total_amount:.2f} "
                    f"at {order.merchant}. Reference: {order.transaction_reference}."
                ),
            )

        # 1. Double confirmation verification
        if not request.confirmed_by_user:
            raise ValidationError(
                "Double-confirmation required: user must explicitly review cart totals and confirm purchase intent."
            )

        # 2. Consequential action policy evaluation
        eval_result = await self._broker.evaluate_action(
            session=db,
            actor=user,
            tool_name="commerce.execute_order",
            arguments={
                "order_id": str(order.id),
                "merchant": order.merchant,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "idempotency_key": order.idempotency_key,
            },
            target_resource=f"order_draft:{order.id}",
            approval_id=request.approval_id,
            session_id=session_id_auth,
        )

        if eval_result.decision != BrokerDecision.ALLOW:
            if eval_result.decision == BrokerDecision.REQUIRE_APPROVAL:
                order.status = "APPROVAL_REQUIRED"
                if eval_result.approval_request:
                    order.approval_id = eval_result.approval_request.id
                await db.commit()
                raise PermissionDeniedError(
                    f"Approval required to execute financial transaction of {order.currency} {order.total_amount:.2f} "
                    f"at {order.merchant}. Approval request ID: {order.approval_id}"
                )
            raise PermissionDeniedError(f"Action denied by Policy Broker: {eval_result.reason}")

        # 3. Execute financial transaction via provider
        txn_res = await self._agent.execute_checkout(
            merchant=order.merchant,
            total_amount=order.total_amount,
            currency=order.currency,
            idempotency_key=order.idempotency_key,
            payment_method=request.payment_method,
        )

        order.status = "EXECUTED"
        order.transaction_reference = txn_res["transaction_reference"]
        order.executed_at = utcnow()
        order.approval_id = request.approval_id

        await AuditService.record_event(
            session=db,
            user_id=user.id,
            session_id=session_id_auth,
            action_type="commerce.order_execute",
            resource_scope=f"order_draft:{order.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "merchant": order.merchant,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "transaction_reference": order.transaction_reference,
                "idempotency_key": order.idempotency_key,
                "approval_id": str(request.approval_id) if request.approval_id else None,
            },
        )
        await db.commit()

        receipt = (
            f"Successfully charged {order.currency} {order.total_amount:.2f} at {order.merchant}. "
            f"Order Reference: {order.transaction_reference}. Payment method: {request.payment_method}."
        )

        return ExecuteOrderResponse(
            order_id=order.id,
            status=order.status,
            transaction_reference=order.transaction_reference,
            total_charged=order.total_amount,
            currency=order.currency,
            receipt_summary=receipt,
        )
