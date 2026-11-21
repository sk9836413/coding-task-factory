# Add the WEEKEND promo code to the cart

Marketing wants customers to be able to enter the promo code `WEEKEND` at checkout. The repository in
`/app` is the `shopcart` library. Money is always integer paise (100 paise = ₹1).

## Rules
1. The code is `WEEKEND`. Matching ignores upper/lower case and spaces around the code.
2. The discount is 5% of the eligible amount, rounded down to the nearest paisa.
3. The eligible amount is the total of items in the `stationery` category.
4. Only one code per cart. Applying a code while one is already applied raises `InvalidCode`.
5. Unknown codes raise `InvalidCode`.

## Interface
- `shopcart.InvalidCode`: new exception, subclass of `ValueError`, importable from `shopcart`.
- `Cart.apply_code(code: str) -> None` and `Cart.remove_code() -> None`.
- `Cart.adjustments()` includes `Adjustment("Promo WEEKEND", -discount)` while the discount is above zero, and no promo adjustment otherwise. `Cart.total()` already sums adjustments.

## Example
A cart with 2 x RICE-5K, 3 x PEN-10 has a subtotal of 174800 paise. After `apply_code("WEEKEND")` the promo adjustment is
-2250 and `total()` is 172550.

Keep all existing behaviour working; the existing tests in `tests/` must still pass.
