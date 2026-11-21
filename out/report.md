# Task factory run

- Repository: `sample_repo` at `sha256:74a426e496f4cc9c`
- Seed 7: 9 tasks generated, **9 valid**, in 124.1 s
- Known-wrong implementations rejected by the tests: **28/28**
- Same-family task pairs whose reference solutions fail each other's tests: **9/9**

| Task | Title | Difficulty | Untouched repo fails | Reference passes | Stable | Mutants killed | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| promo-01 | Add the THANKYOU promo code to the cart | medium | yes | yes | yes | 6/6 | 18 | valid |
| shipping-01 | Add shipping charges to the cart | medium | yes | yes | yes | 4/4 | 13 | valid |
| deals-01 | Add a buy 1 get 1 free deal on RICE-5K | medium | yes | yes | yes | 2/2 | 11 | valid |
| promo-02 | Add the WEEKEND promo code to the cart | medium | yes | yes | yes | 2/2 | 14 | valid |
| shipping-02 | Add shipping charges to the cart | easy | yes | yes | yes | 2/2 | 11 | valid |
| deals-02 | Add a buy 3 get 1 free deal on OIL-1L | medium | yes | yes | yes | 2/2 | 11 | valid |
| promo-03 | Add the FESTIVE promo code to the cart | medium | yes | yes | yes | 4/4 | 16 | valid |
| shipping-03 | Add shipping charges to the cart | medium | yes | yes | yes | 4/4 | 13 | valid |
| deals-03 | Add a buy 2 get 1 free deal on SHIRT-M | medium | yes | yes | yes | 2/2 | 11 | valid |

## Mutants per task

**promo-01**: killed: Codes are not upper-cased or trimmed before matching; killed: Minimum spend uses > instead of >=; killed: Minimum spend checked only when the code is applied, never re-checked; killed: Maximum discount cap not applied; killed: Same customer can reuse the code; killed: Code marked as used even when it gave no discount
  (no scenario could expose: round_half_up)

**shipping-01**: killed: Empty carts are charged shipping; killed: Weight charge counts whole kilograms instead of started kilograms; killed: The first kilogram is charged as extra weight; killed: Free-shipping threshold uses > instead of >=

**deals-01**: killed: Counts groups of X instead of X+1 for buy X get 1 free; killed: Free-item cap per order not applied

**promo-02**: killed: Codes are not upper-cased or trimmed before matching; killed: Discount applied to the whole cart instead of the eligible category
  (no scenario could expose: round_half_up)

**shipping-02**: killed: Empty carts are charged shipping; killed: Free-shipping threshold uses > instead of >=

**deals-02**: killed: Counts groups of X instead of X+1 for buy X get 1 free; killed: Free-item cap per order not applied

**promo-03**: killed: Codes are not upper-cased or trimmed before matching; killed: Minimum spend uses > instead of >=; killed: Minimum spend checked only when the code is applied, never re-checked; killed: Maximum discount cap not applied
  (no scenario could expose: round_half_up)

**shipping-03**: killed: Empty carts are charged shipping; killed: Free-shipping threshold uses > instead of >=; killed: Express surcharge never added; killed: Express orders get (or lose) free shipping against the rules

**deals-03**: killed: Counts groups of X instead of X+1 for buy X get 1 free; killed: Free-item cap per order not applied

## Distinctness (same family)

| A | B | A's solution fails B | B's solution fails A |
|---|---|---|---|
| promo-01 | promo-02 | True | True |
| promo-01 | promo-03 | True | True |
| shipping-01 | shipping-02 | True | True |
| shipping-01 | shipping-03 | True | True |
| deals-01 | deals-02 | True | True |
| deals-01 | deals-03 | True | True |
| promo-02 | promo-03 | True | True |
| shipping-02 | shipping-03 | True | True |
| deals-02 | deals-03 | True | True |
