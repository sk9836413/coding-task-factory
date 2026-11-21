from __future__ import annotations

from dataclasses import dataclass

from .catalog import CATALOG, Product


@dataclass(frozen=True)
class LineItem:
    product: Product
    quantity: int

    @property
    def total(self) -> int:
        return self.product.price * self.quantity


@dataclass(frozen=True)
class Adjustment:
    """A change to the order total. Discounts are negative, charges are positive."""
    label: str
    amount: int


class Cart:
    def __init__(self, customer_id: str = "guest"):
        self.customer_id = customer_id
        self._qty: dict[str, int] = {}
        self._express = False

    def add(self, sku: str, quantity: int = 1) -> None:
        if sku not in CATALOG:
            raise KeyError(f"Unknown SKU: {sku}")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        self._qty[sku] = self._qty.get(sku, 0) + quantity

    def remove(self, sku: str, quantity: int | None = None) -> None:
        if sku not in self._qty:
            raise KeyError(f"{sku} is not in the cart")
        if quantity is None or quantity >= self._qty[sku]:
            del self._qty[sku]
        elif quantity <= 0:
            raise ValueError("Quantity must be positive")
        else:
            self._qty[sku] -= quantity

    def quantity(self, sku: str) -> int:
        return self._qty.get(sku, 0)

    def lines(self) -> list[LineItem]:
        return [LineItem(CATALOG[sku], q) for sku, q in sorted(self._qty.items())]

    def subtotal(self) -> int:
        return sum(line.total for line in self.lines())

    def weight_g(self) -> int:
        return sum(line.product.weight_g * line.quantity for line in self.lines())

    def shipping(self) -> int:
        """Shipping charge in paise."""
        if not self._qty:
            return 0
        fee = 4000
        extra = max(0, self.weight_g() - 1000)
        fee += -(-extra // 1000) * 2000
        if self.subtotal() > 85200:
            fee = 0
        return fee

    def adjustments(self) -> list[Adjustment]:
        fee = self.shipping()
        return [Adjustment("Shipping", fee)] if fee else []

    def total(self) -> int:
        return max(0, self.subtotal() + sum(a.amount for a in self.adjustments()))
