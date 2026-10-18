"""Commerce providers: Abstract interface and deterministic offline mock provider with idempotency."""

import abc
import uuid
from typing import Any, Dict, List, Optional
from app.services.commerce.schemas import ProductItemInfo


class BaseCommerceProvider(abc.ABC):
    """Abstract interface for shopping research, pricing checks, and checkout transactions."""

    @abc.abstractmethod
    async def compare_products(
        self,
        query: str,
        category: str,
        max_price: Optional[float] = None,
    ) -> List[ProductItemInfo]:
        """Search and compare product/service offerings."""
        pass

    @abc.abstractmethod
    async def execute_transaction(
        self,
        merchant: str,
        total_amount: float,
        currency: str,
        idempotency_key: str,
        payment_method: str,
    ) -> Dict[str, Any]:
        """Execute financial transaction with idempotency guarantee."""
        pass


class MockCommerceProvider(BaseCommerceProvider):
    """Deterministic offline mock commerce provider.

    Executes 100% offline with zero external network calls.
    """

    def __init__(self):
        self.transactions_by_key: Dict[str, Dict[str, Any]] = {}

    async def compare_products(
        self,
        query: str,
        category: str,
        max_price: Optional[float] = None,
    ) -> List[ProductItemInfo]:
        """Return deterministic product comparison options."""
        base_items = [
            ProductItemInfo(
                name=f"Premium Pro {query.title()}",
                merchant="Apex Retailer",
                price=199.99,
                currency="USD",
                rating=4.8,
                availability="IN_STOCK",
                product_url="https://apexretail.example.com/item/1",
                highlights=["Top rated", "Free next-day shipping", "Extended 2-year warranty"],
            ),
            ProductItemInfo(
                name=f"Standard Value {query.title()}",
                merchant="OmniMarket",
                price=129.50,
                currency="USD",
                rating=4.4,
                availability="IN_STOCK",
                product_url="https://omnimarket.example.com/item/2",
                highlights=["Best budget pick", "Eco-friendly packaging"],
            ),
            ProductItemInfo(
                name=f"Ultra Compact {query.title()}",
                merchant="Global Express",
                price=159.00,
                currency="USD",
                rating=4.6,
                availability="IN_STOCK",
                product_url="https://globalexpress.example.com/item/3",
                highlights=["Lightweight design", "USB-C fast charge compatible"],
            ),
        ]

        if max_price is not None:
            return [p for p in base_items if p.price <= max_price]
        return base_items

    async def execute_transaction(
        self,
        merchant: str,
        total_amount: float,
        currency: str,
        idempotency_key: str,
        payment_method: str,
    ) -> Dict[str, Any]:
        """Execute transaction idempotently, returning identical receipt on duplicate calls."""
        if idempotency_key in self.transactions_by_key:
            return self.transactions_by_key[idempotency_key]

        ref = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        res = {
            "transaction_reference": ref,
            "status": "SETTLED",
            "merchant": merchant,
            "total_charged": total_amount,
            "currency": currency,
            "idempotency_key": idempotency_key,
            "payment_method": payment_method,
        }
        self.transactions_by_key[idempotency_key] = res
        return res
