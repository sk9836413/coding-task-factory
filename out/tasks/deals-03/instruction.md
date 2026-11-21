# Buy 2 get 1 free in the cart

Add a quantity deal to the `shopcart` library in `/app`. Money is integer paise (100 paise = ₹1).

## Rules
1. For product `SHIRT-M` (price 79900 paise): for every 3 units in the cart, 1 unit is free (buy 2, get 1 free). Incomplete groups get nothing.
2. At most 1 free unit(s) per cart.
3. The deal applies automatically; there is nothing to switch on.

## Interface
- `Cart.deal_discount() -> int`: the deal discount in paise (0 when the deal does not apply).
- `Cart.adjustments()` includes `Adjustment("Deal: buy 2 get 1 free on SHIRT-M", -discount)` when the discount is above zero (the label
  must start with `Deal`), so `Cart.total()` includes it.

Keep all existing behaviour working; the existing tests in `tests/` must still pass.
