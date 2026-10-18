"""Pydantic schemas and contracts for Commerce, Booking, & External Actions."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductItemInfo(BaseModel):
    """Product or booking option comparison item."""

    name: str
    merchant: str
    price: float
    currency: str = "USD"
    rating: Optional[float] = None
    availability: str = "IN_STOCK"
    product_url: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)


class CompareProductsRequest(BaseModel):
    """Payload to search and compare products, travel, or services."""

    query: str = Field(min_length=1, max_length=255)
    category: str = Field(default="General", max_length=128)
    max_price: Optional[float] = Field(default=None, ge=0.0)


class CompareProductsResponse(BaseModel):
    """Product comparison result matrix."""

    query: str
    category: str
    options: List[ProductItemInfo] = Field(default_factory=list)
    best_value_recommendation: str


class OrderItem(BaseModel):
    """Line item in a shopping cart or booking."""

    name: str
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(ge=0.0)
    total_price: float = Field(ge=0.0)
    product_url: Optional[str] = None


class CreateOrderDraftRequest(BaseModel):
    """Payload to prepare an order or booking draft (SAFE action)."""

    order_type: str = Field(
        default="PURCHASE",
        description="'PURCHASE', 'FLIGHT_BOOKING', 'HOTEL_BOOKING', or 'SERVICE_ORDER'",
    )
    merchant: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    currency: str = Field(default="USD", max_length=8)
    items: List[OrderItem] = Field(min_length=1)
    delivery_details: Optional[str] = Field(default=None, max_length=512)
    booking_date: Optional[str] = None
    idempotency_key: str = Field(
        min_length=8,
        max_length=128,
        description="Unique client-supplied idempotency key to prevent double charging",
    )


class OrderDraftResponse(BaseModel):
    """Structured response for an order or booking draft."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    order_type: str
    merchant: str
    title: str
    currency: str
    subtotal_amount: float
    tax_amount: float
    total_amount: float
    status: str
    items: List[OrderItem] = Field(default_factory=list)
    delivery_details: Optional[str] = None
    booking_date: Optional[str] = None
    idempotency_key: str
    approval_id: Optional[uuid.UUID] = None
    transaction_reference: Optional[str] = None
    executed_at: Optional[str] = None
    created_at: str
    updated_at: str


class ExecuteOrderRequest(BaseModel):
    """Payload to authorize and execute purchase under double confirmation."""

    approval_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Approval token ID granting permission for transaction",
    )
    confirmed_by_user: bool = Field(
        default=False,
        description="Mandatory double-confirmation flag verifying user explicitly reviewed cart totals",
    )
    payment_method: str = Field(default="CARD_ON_FILE", max_length=64)


class ExecuteOrderResponse(BaseModel):
    """Receipt and execution response."""

    order_id: uuid.UUID
    status: str
    transaction_reference: str
    total_charged: float
    currency: str
    receipt_summary: str
