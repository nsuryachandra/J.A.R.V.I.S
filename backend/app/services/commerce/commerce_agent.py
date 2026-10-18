"""Commerce & Booking Agent coordinator for product comparison, cart calculations, and transactions."""

from typing import Any, Dict, List, Optional, Tuple
from app.services.commerce.providers import BaseCommerceProvider, MockCommerceProvider
from app.services.commerce.schemas import (
    CompareProductsResponse,
    OrderItem,
    ProductItemInfo,
)


class CommerceAgent:
    """Agent orchestrating product comparisons, double-confirmation cart summaries, and checkouts."""

    def __init__(self, provider: Optional[BaseCommerceProvider] = None):
        self._provider = provider or MockCommerceProvider()

    @property
    def provider(self) -> BaseCommerceProvider:
        return self._provider

    async def compare_offerings(
        self,
        query: str,
        category: str = "General",
        max_price: Optional[float] = None,
    ) -> CompareProductsResponse:
        """Compare options and identify best-value recommendation."""
        options = await self._provider.compare_products(query, category, max_price)
        best_pick = options[0].name if options else "None found"
        recommendation = (
            f"Based on price-to-rating analysis for '{query}', '{best_pick}' offers the optimal "
            "balance of verified customer ratings, warranty coverage, and total delivered price."
        )

        return CompareProductsResponse(
            query=query,
            category=category,
            options=options,
            best_value_recommendation=recommendation,
        )

    def calculate_totals(
        self,
        items: List[OrderItem],
        tax_rate: float = 0.08,
    ) -> Tuple[float, float, float]:
        """Compute subtotal, estimated tax, and total amount with 2-decimal precision."""
        subtotal = sum(item.quantity * item.unit_price for item in items)
        tax = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax, 2)
        return round(subtotal, 2), tax, total

    async def execute_checkout(
        self,
        merchant: str,
        total_amount: float,
        currency: str,
        idempotency_key: str,
        payment_method: str = "CARD_ON_FILE",
    ) -> Dict[str, Any]:
        """Execute purchase transaction through active provider."""
        return await self._provider.execute_transaction(
            merchant=merchant,
            total_amount=total_amount,
            currency=currency,
            idempotency_key=idempotency_key,
            payment_method=payment_method,
        )
