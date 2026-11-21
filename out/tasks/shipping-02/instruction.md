# Add shipping charges to the cart

The `shopcart` library in `/app` does not charge for shipping yet. Add shipping charges following these rules.
Money is integer paise (100 paise = ₹1), weights are grams.

## Rules
1. Every non-empty order pays a base shipping fee of ₹49 (4900 paise). An empty cart pays nothing.
2. When the cart subtotal is at least ₹1,082 (108200 paise), the base fee are waived.

## Interface
- `Cart.shipping() -> int`: the shipping charge in paise for the current cart.
- `Cart.adjustments()` includes `Adjustment("Shipping", fee)` when the fee is above zero, so `Cart.total()` includes shipping.

`test_add_and_subtotal` in `tests/test_cart.py` assumes the total always equals the subtotal. That is no longer
true once shipping exists: update it so the total equals the subtotal plus `c.shipping()`. Everything else must
keep working and all other existing tests must still pass.
