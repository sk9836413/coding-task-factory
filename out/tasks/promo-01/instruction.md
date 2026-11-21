# Add the THANKYOU promo code to the cart

Marketing wants customers to be able to enter the promo code `THANKYOU` at checkout. The repository in
`/app` is the `shopcart` library. Money is always integer paise (100 paise = ₹1).

## Rules
1. The code is `THANKYOU`. Matching ignores upper/lower case and spaces around the code.
2. The discount is 20% of the eligible amount, rounded down to the nearest paisa.
3. The eligible amount is the cart subtotal.
4. The discount only applies while the cart subtotal is at least ₹654 (65400 paise). The code can be applied before that; the discount appears and disappears as the cart changes.
5. The discount is never more than ₹300 (30000 paise).
6. Only one code per cart. Applying a code while one is already applied raises `InvalidCode`.
7. Unknown codes raise `InvalidCode`.
8. Each customer (`customer_id`) can use the code once. It counts as used when `checkout()` is called on a cart where the code gave a discount above zero. After that, applying it for the same customer raises `InvalidCode`. Other customers are not affected.

## Interface
- `shopcart.InvalidCode`: new exception, subclass of `ValueError`, importable from `shopcart`.
- `Cart.apply_code(code: str) -> None` and `Cart.remove_code() -> None`.
- `Cart.adjustments()` includes `Adjustment("Promo THANKYOU", -discount)` while the discount is above zero, and no promo adjustment otherwise. `Cart.total()` already sums adjustments.
- `Cart.checkout() -> int` returns the amount charged (same as `total()`).
- `shopcart.reset_code_usage() -> None` forgets all recorded code usage.

## Example
A cart with 1 x RICE-5K, 3 x PEN-10 has a subtotal of 109900 paise. After `apply_code("THANKYOU")` the promo adjustment is
-21980 and `total()` is 87920.

Keep all existing behaviour working; the existing tests in `tests/` must still pass.
