# Add shipping charges to the cart

The `shopcart` library in `/app` does not charge for shipping yet. Add shipping charges following these rules.
Money is integer paise (100 paise = ₹1), weights are grams.

## Rules
1. Every non-empty order pays a base shipping fee of ₹40 (4000 paise). An empty cart pays nothing.
2. The base fee covers the first 1 kg (1000 g) of `Cart.weight_g()`. Each started kilogram above that adds ₹20 (2000 paise). For example 2,050 g costs 2 extra kg.
3. When the cart subtotal is at least ₹852 (85200 paise), the base fee and the weight charge are waived.

## Interface
- `Cart.shipping() -> int`: the shipping charge in paise for the current cart.
- `Cart.adjustments()` includes `Adjustment("Shipping", fee)` when the fee is above zero, so `Cart.total()` includes shipping.

`test_add_and_subtotal` in `tests/test_cart.py` assumes the total always equals the subtotal. That is no longer
true once shipping exists: update it so the total equals the subtotal plus `c.shipping()`. Everything else must
keep working and all other existing tests must still pass.
