# Add shipping charges to the cart

The `shopcart` library in `/app` does not charge for shipping yet. Add shipping charges following these rules.
Money is integer paise (100 paise = ₹1), weights are grams.

## Rules
1. Every non-empty order pays a base shipping fee of ₹99 (9900 paise). An empty cart pays nothing.
2. When the cart subtotal is at least ₹852 (85200 paise), the base fee are waived.
3. Express delivery adds ₹50 (5000 paise) on top of any other shipping charge. It is off by default.
4. Express orders never get free shipping: they always pay the normal charge plus the express surcharge.

## Interface
- `Cart.shipping() -> int`: the shipping charge in paise for the current cart.
- `Cart.set_express(enabled: bool) -> None`.
- `Cart.adjustments()` includes `Adjustment("Shipping", fee)` when the fee is above zero, so `Cart.total()` includes shipping.

`test_add_and_subtotal` in `tests/test_cart.py` assumes the total always equals the subtotal. That is no longer
true once shipping exists: update it so the total equals the subtotal plus `c.shipping()`. Everything else must
keep working and all other existing tests must still pass.
