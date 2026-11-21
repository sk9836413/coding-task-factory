#!/bin/bash
# Reference solution: writes the changed files.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/shopcart"
cat > "$APP_DIR/shopcart/__init__.py" <<'TASKFACTORY_EOF'
"""shopcart: a tiny shopping-cart library. Money is always integer paise (100 paise = 1 rupee)."""
from .cart import Adjustment, Cart, InvalidCode, LineItem
from .catalog import CATALOG, Product

__all__ = ["Adjustment", "Cart", "InvalidCode",  "LineItem", "CATALOG", "Product"]
TASKFACTORY_EOF
mkdir -p "$APP_DIR/shopcart"
cat > "$APP_DIR/shopcart/cart.py" <<'TASKFACTORY_EOF'
from __future__ import annotations

from dataclasses import dataclass

from .catalog import CATALOG, Product

PROMO_CODE = "FESTIVE"


class InvalidCode(ValueError):
    """Raised when a promo code cannot be applied."""


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
        self._code: str | None = None

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

    def apply_code(self, code: str) -> None:
        code = code.strip().upper()
        if code != PROMO_CODE:
            raise InvalidCode(f"Unknown code: {code}")
        if self._code is not None:
            raise InvalidCode("Only one code can be used per order")
        self._code = code

    def remove_code(self) -> None:
        self._code = None

    def _promo_base(self) -> int:
        return self.subtotal()

    def _promo_discount(self) -> int:
        if self._code is None:
            return 0
        base = self._promo_base()
        if base <= 0:
            return 0
        if not (self.subtotal() >= 63000):
            return 0
        discount = base * 10 // 100
        discount = min(discount, 15000)
        return discount

    def adjustments(self) -> list[Adjustment]:
        discount = self._promo_discount()
        return [Adjustment(f"Promo {self._code}", -discount)] if discount else []

    def total(self) -> int:
        return max(0, self.subtotal() + sum(a.amount for a in self.adjustments()))
TASKFACTORY_EOF
