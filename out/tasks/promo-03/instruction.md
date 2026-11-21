# Add the FESTIVE promo code to the cart

Marketing wants customers to be able to enter the promo code `FESTIVE` at checkout. The repository in
`/app` is the `shopcart` library. Money is always integer paise (100 paise = ₹1).

## Rules
1. The code is `FESTIVE`. Matching ignores upper/lower case and spaces around the code.
2. The discount is 10% of the eligible amount, rounded down to the nearest paisa.
3. The eligible amount is the cart subtotal.
4. The discount only applies while the cart subtotal is at least ₹630 (63000 paise). The code can be applied before that; the discount appears and disappears as the cart changes.
5. The discount is never more than ₹150 (15000 paise).
6. Only one code per cart. Applying a code while one is already applied raises `InvalidCode`.
7. Unknown codes raise `InvalidCode`.

## Interface
- `shopcart.InvalidCode`: new exception, subclass of `ValueError`, importable from `shopcart`.
- `Cart.apply_code(code: str) -> None` and `Cart.remove_code() -> None`.
- `Cart.adjustments()` includes `Adjustment("Promo FESTIVE", -discount)` while the discount is above zero, and no promo adjustment otherwise. `Cart.total()` already sums adjustments.

## Example
A cart with 1 x TEA-250, 3 x PEN-10 has a subtotal of 69000 paise. After `apply_code("FESTIVE")` the promo adjustment is
-6900 and `total()` is 62100.

Keep all existing behaviour working; the existing tests in `tests/` must still pass.
