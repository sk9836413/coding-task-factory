# Buy 3 get 1 free in the cart

Add a quantity deal to the `shopcart` library in `/app`. Money is integer paise (100 paise = ₹1).

## Rules
1. For product `OIL-1L` (price 18500 paise): for every 4 units in the cart, 1 unit is free (buy 3, get 1 free). Incomplete groups get nothing.
2. At most 2 free unit(s) per cart.
3. The deal applies automatically; there is nothing to switch on.

## Interface
- `Cart.deal_discount() -> int`: the deal discount in paise (0 when the deal does not apply).
- `Cart.adjustments()` includes `Adjustment("Deal: buy 3 get 1 free on OIL-1L", -discount)` when the discount is above zero (the label
  must start with `Deal`), so `Cart.total()` includes it.

Keep all existing behaviour working; the existing tests in `tests/` must still pass.
