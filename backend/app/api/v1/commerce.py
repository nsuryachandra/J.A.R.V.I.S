"""REST API router for Commerce, Booking, & External Actions under Policy Broker governance."""

import json
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.user import User
from app.services.commerce.schemas import (
    CompareProductsRequest,
    CompareProductsResponse,
    CreateOrderDraftRequest,
    ExecuteOrderRequest,
    ExecuteOrderResponse,
    OrderDraftResponse,
    OrderItem,
)
from app.services.commerce.service import CommerceService

router = APIRouter(prefix="/commerce", tags=["Commerce & External Actions"])
_commerce_service = CommerceService()


@router.post("/compare", response_model=CompareProductsResponse)
async def compare_products(
    payload: CompareProductsRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
) -> CompareProductsResponse:
    """Search, compare, and rank product, travel, or service offerings across merchants (SAFE action)."""
    try:
        return await _commerce_service.compare(payload)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/orders", response_model=OrderDraftResponse)
async def create_order_draft(
    payload: CreateOrderDraftRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> OrderDraftResponse:
    """Create an itemized order or booking draft (SAFE action, idempotent)."""
    current_user, auth_session_id = auth
    try:
        return await _commerce_service.create_order_draft(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/orders", response_model=List[OrderDraftResponse])
async def list_order_drafts(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[OrderDraftResponse]:
    """List all order and booking drafts for the authenticated user with tenant isolation."""
    current_user, _ = auth
    return await _commerce_service.list_orders(
        db=db,
        user_id=current_user.id,
    )


@router.get("/orders/{order_id}", response_model=OrderDraftResponse)
async def get_order_draft(
    order_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> OrderDraftResponse:
    """Retrieve a specific order or booking draft by ID."""
    current_user, _ = auth
    try:
        draft = await _commerce_service.get_order(
            db=db,
            user_id=current_user.id,
            order_id=order_id,
        )
        items_list = [OrderItem(**i) for i in json.loads(draft.items)]
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
            items=items_list,
            delivery_details=draft.delivery_details,
            booking_date=draft.booking_date.isoformat() if draft.booking_date else None,
            idempotency_key=draft.idempotency_key,
            approval_id=draft.approval_id,
            transaction_reference=draft.transaction_reference,
            executed_at=draft.executed_at.isoformat() if draft.executed_at else None,
            created_at=draft.created_at.isoformat(),
            updated_at=draft.updated_at.isoformat(),
        )
    except EntityNotFoundError as enf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(enf))


@router.post("/orders/{order_id}/execute", response_model=ExecuteOrderResponse)
async def execute_order(
    order_id: uuid.UUID,
    payload: ExecuteOrderRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ExecuteOrderResponse:
    """Execute purchase or booking under double confirmation and Policy Broker approval gates (CONSEQUENTIAL action)."""
    current_user, auth_session_id = auth
    try:
        return await _commerce_service.execute_order(
            db=db,
            user=current_user,
            order_id=order_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError as enf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(enf))
    except ValidationError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except PermissionDeniedError as pde:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pde))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))
