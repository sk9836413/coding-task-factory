"""Family: promo codes with eligibility rules, minimum spend, caps and single use per customer."""
from __future__ import annotations

import random

from ..common import (ADJ_ANCHOR, IMPORT_ANCHOR, INIT_ANCHOR, Emitter, Mutant, TaskPackage, basket_lines,
                      insert_before, replace_once, rupees)
from ..repo import Repo

NAME = "promo"
CODES = ["WELCOME", "FESTIVE", "THANKYOU", "WEEKEND", "FIRSTORDER", "MONSOON"]


# ---------------------------------------------------------------- sampling
def sample(repo: Repo, rng: random.Random) -> dict:
    p = {"code": rng.choice(CODES), "kind": rng.choice(["percent", "flat"])}
    if p["kind"] == "percent":
        p["pct"] = rng.choice([5, 10, 15, 20])
        p["cap"] = rng.choice([None, 15000, 30000])
    else:
        p["flat"] = rng.choice([5000, 10000, 25000])
        p["cap"] = None
    p["category"] = rng.choice([None] + repo.categories())
    p["threshold_on"] = "cart"
    p["min_subtotal"] = None
    if rng.random() < 0.7:
        if p["category"] and rng.random() < 0.5:
            p["threshold_on"] = "eligible"
        values = sorted({_basis(repo, p, b) for b in repo.baskets()} - {0})
        values = [v for v in values if 20000 <= v <= 150000]
        p["min_subtotal"] = rng.choice(values[len(values) // 4: 3 * len(values) // 4] or values)
    p["single_use"] = rng.random() < 0.5
    return p


def signature(p: dict) -> tuple:
    return tuple(sorted((k, v) for k, v in p.items() if k != "code"))


# ---------------------------------------------------------------- oracle (independent of the reference code)
def _base(repo: Repo, p: dict, basket: dict) -> int:
    return sum(repo.item(s).price * q for s, q in basket.items()
               if p["category"] is None or repo.item(s).category == p["category"])


def _sub(repo: Repo, basket: dict) -> int:
    return sum(repo.item(s).price * q for s, q in basket.items())


def _basis(repo: Repo, p: dict, basket: dict) -> int:
    return _base(repo, p, basket) if p["threshold_on"] == "eligible" else _sub(repo, basket)


def _discount(repo: Repo, p: dict, basket: dict, code_on: bool = True) -> int:
    base = _base(repo, p, basket)
    if not code_on or base <= 0:
        return 0
    if p["min_subtotal"] is not None and _basis(repo, p, basket) < p["min_subtotal"]:
        return 0
    if p["kind"] == "percent":
        d = base * p["pct"] // 100
        return min(d, p["cap"]) if p["cap"] else d
    return min(p["flat"], base)


class _Cart:
    def __init__(self, customer: str):
        self.customer, self.qty, self.code = customer, {}, None


class _Test:
    """Writes one test function while simulating the expected behaviour."""

    def __init__(self, repo: Repo, p: dict, used: set):
        self.repo, self.p, self.used, self.lines, self.c = repo, p, used, [], {}

    def cart(self, var: str, customer: str, basket: dict) -> "_Test":
        self.c[var] = _Cart(customer)
        self.lines.append(f"{var} = Cart({customer!r})")
        self.add(var, basket)
        return self

    def add(self, var: str, basket: dict) -> "_Test":
        for s, q in basket.items():
            self.c[var].qty[s] = self.c[var].qty.get(s, 0) + q
        self.lines += basket_lines(var, basket)
        return self

    def remove(self, var: str, sku: str) -> "_Test":
        del self.c[var].qty[sku]
        self.lines.append(f"{var}.remove({sku!r})")
        return self

    def apply(self, var: str, code: str) -> "_Test":
        st, norm = self.c[var], code.strip().upper()
        ok = norm == self.p["code"] and st.code is None and not (
            self.p["single_use"] and (st.customer, norm) in self.used)
        if ok:
            st.code = norm
            self.lines.append(f"{var}.apply_code({code!r})")
        else:
            self.lines += ["with pytest.raises(shopcart.InvalidCode):", f"    {var}.apply_code({code!r})"]
        return self

    def remove_code(self, var: str) -> "_Test":
        self.c[var].code = None
        self.lines.append(f"{var}.remove_code()")
        return self

    def _d(self, var: str) -> int:
        st = self.c[var]
        return _discount(self.repo, self.p, st.qty, st.code is not None)

    def check(self, var: str) -> "_Test":
        d, sub = self._d(var), _sub(self.repo, self.c[var].qty)
        self.lines += [f"assert _promo({var}) == {-d}", f"assert {var}.total() == {max(0, sub - d)}"]
        return self

    def checkout(self, var: str) -> "_Test":
        st, d = self.c[var], self._d(var)
        self.lines.append(f"assert {var}.checkout() == {max(0, _sub(self.repo, st.qty) - d)}")
        if st.code and d > 0:
            self.used.add((st.customer, st.code))
        return self


# ---------------------------------------------------------------- reference implementation (+ bug variants)
def _cart_source(repo: Repo, p: dict, bugs: frozenset = frozenset()) -> str:
    src = repo.read("shopcart/cart.py")
    code, cat = p["code"], p["category"]
    module = f'\nPROMO_CODE = "{code}"\n\n\nclass InvalidCode(ValueError):\n    """Raised when a promo code cannot be applied."""\n'
    if p["single_use"]:
        module += ("\n\n_USED_CODES: set[tuple[str, str]] = set()\n\n\ndef reset_code_usage() -> None:\n"
                   '    """Forget which customers have used which codes."""\n    _USED_CODES.clear()\n')
    src = replace_once(src, IMPORT_ANCHOR, IMPORT_ANCHOR + module, "module constants")
    src = replace_once(src, INIT_ANCHOR, INIT_ANCHOR + "        self._code: str | None = None\n", "init")

    basis = "base" if p["threshold_on"] == "eligible" else "self.subtotal()"
    if "wrong_basis" in bugs:
        basis = "self.subtotal()" if basis == "base" else "base"
    op = ">" if "threshold_strict" in bugs else ">="
    norm = "code" if "no_normalize" in bugs else "code.strip().upper()"
    m = [
        "    def apply_code(self, code: str) -> None:",
        f"        code = {norm}",
        "        if code != PROMO_CODE:",
        '            raise InvalidCode(f"Unknown code: {code}")',
        "        if self._code is not None:",
        '            raise InvalidCode("Only one code can be used per order")',
    ]
    if p["single_use"] and "single_use_not_enforced" not in bugs:
        m += ["        if (self.customer_id, code) in _USED_CODES:",
              '            raise InvalidCode("This code has already been used")']
    if p["min_subtotal"] is not None and "apply_time_check" in bugs:
        m += ["        base = self._promo_base()",
              f"        if not ({basis} {op} {p['min_subtotal']}):",
              '            raise InvalidCode("Minimum spend not reached")']
    m += ["        self._code = code", "",
          "    def remove_code(self) -> None:", "        self._code = None", "",
          "    def _promo_base(self) -> int:"]
    if cat and "ignore_category" not in bugs:
        m.append(f'        return sum(l.total for l in self.lines() if l.product.category == "{cat}")')
    else:
        m.append("        return self.subtotal()")
    m += ["", "    def _promo_discount(self) -> int:",
          "        if self._code is None:", "            return 0",
          "        base = self._promo_base()", "        if base <= 0:", "            return 0"]
    if p["min_subtotal"] is not None and "apply_time_check" not in bugs:
        m += [f"        if not ({basis} {op} {p['min_subtotal']}):", "            return 0"]
    if p["kind"] == "percent":
        m.append(f"        discount = round(base * {p['pct']} / 100)" if "round_half_up" in bugs
                 else f"        discount = base * {p['pct']} // 100")
        if p["cap"] and "ignore_cap" not in bugs:
            m.append(f"        discount = min(discount, {p['cap']})")
    else:
        m.append(f"        discount = {p['flat']}" if "flat_exceeds_base" in bugs
                 else f"        discount = min({p['flat']}, base)")
    m += ["        return discount", ""]
    if p["single_use"]:
        cond = "self._code is not None" if "burn_without_discount" in bugs \
            else "self._code is not None and self._promo_discount() > 0"
        m += ["    def checkout(self) -> int:", '        """Place the order and return the amount charged."""',
              "        total = self.total()", f"        if {cond}:",
              "            _USED_CODES.add((self.customer_id, self._code))", "        return total", ""]
    new_adj = ("    def adjustments(self) -> list[Adjustment]:\n"
               "        discount = self._promo_discount()\n"
               '        return [Adjustment(f"Promo {self._code}", -discount)] if discount else []\n')
    src = insert_before(src, ADJ_ANCHOR, "\n".join(m) + "\n", "methods")
    return replace_once(src, ADJ_ANCHOR, new_adj, "adjustments")


def _init_source(repo: Repo, p: dict) -> str:
    src = repo.read("shopcart/__init__.py")
    extra = ", InvalidCode" + (", reset_code_usage" if p["single_use"] else "")
    src = replace_once(src, "from .cart import Adjustment, Cart, LineItem",
                       f"from .cart import Adjustment, Cart{extra}, LineItem", "init import")
    names = '"InvalidCode", ' + ('"reset_code_usage", ' if p["single_use"] else "")
    return replace_once(src, '__all__ = ["Adjustment", "Cart",', f'__all__ = ["Adjustment", "Cart", {names}',
                        "init all")


# ---------------------------------------------------------------- task build
def build(repo: Repo, p: dict) -> TaskPackage:
    rng = random.Random(repr(signature(p)))
    baskets = repo.baskets()
    rng.shuffle(baskets)
    base = lambda b: _base(repo, p, b)
    basis = lambda b: _basis(repo, p, b)
    meets = lambda b: p["min_subtotal"] is None or basis(b) >= p["min_subtotal"]
    uncapped = lambda b: base(b) * p.get("pct", 0) // 100
    under_cap = lambda b: not p["cap"] or uncapped(b) < p["cap"]

    def pick(pred, prefer=None):
        good = [b for b in baskets if pred(b)]
        if prefer:
            good = [b for b in good if prefer(b)] or good
        return good[0] if good else None

    rounding = lambda b: p["kind"] == "percent" and (base(b) * p["pct"]) % 100 >= 50
    main = pick(lambda b: base(b) > 0 and meets(b) and under_cap(b), rounding)
    if main is None:
        raise ValueError("no basket gets a discount")

    used: set = set()
    em = Emitter(HEADER)
    tests = []

    def t() -> _Test:
        used.clear()
        x = _Test(repo, p, used)
        tests.append(x)
        return x

    em.test("discount_applied", t().cart("c", "asha", main).check("c").apply("c", p["code"]).check("c").lines)
    em.test("code_is_case_insensitive_and_trimmed",
            t().cart("c", "asha", main).apply("c", f"  {p['code'].lower()} ").check("c").lines)
    em.test("unknown_code_rejected", t().cart("c", "asha", main).apply("c", "NOTAREALCODE").check("c").lines)
    em.test("one_code_per_order", t().cart("c", "asha", main).apply("c", p["code"]).apply("c", p["code"]).check("c").lines)
    em.test("remove_code", t().cart("c", "asha", main).apply("c", p["code"]).remove_code("c").check("c").lines)

    mutants = ["no_normalize"]
    skipped = []
    if p["min_subtotal"] is not None:
        exact = pick(lambda b: base(b) > 0 and basis(b) == p["min_subtotal"] and under_cap(b))
        if exact:
            em.test("minimum_spend_is_inclusive", t().cart("c", "asha", exact).apply("c", p["code"]).check("c").lines)
            mutants.append("threshold_strict")
        else:
            skipped.append("threshold_strict")
        low = pick(lambda b: base(b) > 0 and basis(b) < p["min_subtotal"])
        if low:
            sku = next(s for s in low if p["category"] is None or repo.item(s).category == p["category"])
            k = 1
            while basis({**low, sku: low[sku] + k}) < p["min_subtotal"]:
                k += 1
            em.test("discount_starts_when_minimum_reached",
                    t().cart("c", "asha", low).apply("c", p["code"]).check("c").add("c", {sku: k}).check("c").lines)
            mutants.append("apply_time_check")
        else:
            skipped.append("apply_time_check")
        drop = pick(lambda b: len(b) == 2 and meets(b) and base(b) > 0 and any(
            basis({s: q for s, q in b.items() if s != r}) < p["min_subtotal"] for r in b))
        if drop:
            r = next(r for r in drop if basis({s: q for s, q in drop.items() if s != r}) < p["min_subtotal"])
            em.test("discount_removed_when_cart_drops_below_minimum",
                    t().cart("c", "asha", drop).apply("c", p["code"]).check("c").remove("c", r).check("c").lines)
    if p["category"]:
        cat = p["category"]
        mixed = pick(lambda b: meets(b) and 0 < base(b) < _sub(repo, b) and _discount(repo, p, b) != _discount(
            repo, {**p, "category": None}, b))
        if mixed:
            em.test("only_category_items_are_discounted",
                    t().cart("c", "asha", mixed).apply("c", p["code"]).check("c").lines)
        none = pick(lambda b: base(b) == 0 and _sub(repo, b) >= (p["min_subtotal"] or 0))
        if none:
            em.test("no_discount_without_eligible_items",
                    t().cart("c", "asha", none).apply("c", p["code"]).check("c").lines)
        (mutants if (mixed or none) else skipped).append("ignore_category")
        if p["min_subtotal"] is not None:
            flip = {**p, "threshold_on": "cart" if p["threshold_on"] == "eligible" else "eligible"}
            split = pick(lambda b: base(b) > 0 and _discount(repo, p, b) != _discount(repo, flip, b))
            if split:
                em.test("minimum_spend_basis", t().cart("c", "asha", split).apply("c", p["code"]).check("c").lines)
                mutants.append("wrong_basis")
            else:
                skipped.append("wrong_basis")
    if p["cap"]:
        big = pick(lambda b: meets(b) and uncapped(b) > p["cap"])
        if big:
            em.test("discount_is_capped", t().cart("c", "asha", big).apply("c", p["code"]).check("c").lines)
            mutants.append("ignore_cap")
        else:
            skipped.append("ignore_cap")
    if p["kind"] == "flat" and p["category"]:
        small = pick(lambda b: meets(b) and 0 < base(b) < p["flat"])
        if small:
            em.test("flat_discount_never_exceeds_eligible_amount",
                    t().cart("c", "asha", small).add("c", {}).apply("c", p["code"]).check("c").lines)
            mutants.append("flat_exceeds_base")
        else:
            skipped.append("flat_exceeds_base")
    if p["kind"] == "percent":
        (mutants if rounding(main) else skipped).append("round_half_up")
    if p["single_use"]:
        x = t().cart("a1", "asha", main).apply("a1", p["code"]).checkout("a1")
        x.cart("a2", "asha", main).apply("a2", p["code"]).check("a2")
        x.cart("b1", "ravi", main).apply("b1", p["code"]).check("b1")
        em.test("code_is_single_use_per_customer", x.lines)
        mutants.append("single_use_not_enforced")
        if p["min_subtotal"] is not None:
            low = pick(lambda b: base(b) > 0 and basis(b) < p["min_subtotal"])
            if low:
                x = t().cart("a1", "asha", low).apply("a1", p["code"]).checkout("a1")
                x.cart("a2", "asha", main).apply("a2", p["code"]).check("a2")
                em.test("code_not_used_up_when_it_gave_no_discount", x.lines)
                mutants.append("burn_without_discount")
            else:
                skipped.append("burn_without_discount")

    solution = {"shopcart/cart.py": _cart_source(repo, p), "shopcart/__init__.py": _init_source(repo, p)}
    muts = [Mutant(b, BUGS[b], {"shopcart/cart.py": _cart_source(repo, p, frozenset([b])),
                                "shopcart/__init__.py": solution["shopcart/__init__.py"]}) for b in mutants]
    example_d = _discount(repo, p, main)
    example = ", ".join(f"{q} x {s}" for s, q in main.items())
    return TaskPackage(
        family=NAME, params=p, signature=signature(p),
        title=f"Add the {p['code']} promo code to the cart",
        instruction=_instruction(p, example, _sub(repo, main), example_d),
        solution=solution, feature_tests=em.source(), mutants=muts, skipped_mutants=skipped,
        difficulty="hard" if (p["single_use"] and p["min_subtotal"] and p["category"]) else "medium",
        tags=["promo-code", p["kind"]] + (["category-rule"] if p["category"] else []) +
             (["minimum-spend"] if p["min_subtotal"] else []) + (["single-use"] if p["single_use"] else []),
    )


BUGS = {
    "no_normalize": "Codes are not upper-cased or trimmed before matching",
    "threshold_strict": "Minimum spend uses > instead of >=",
    "apply_time_check": "Minimum spend checked only when the code is applied, never re-checked",
    "ignore_category": "Discount applied to the whole cart instead of the eligible category",
    "wrong_basis": "Minimum spend measured on the wrong amount (cart vs eligible items)",
    "ignore_cap": "Maximum discount cap not applied",
    "flat_exceeds_base": "Flat discount can exceed the eligible amount",
    "round_half_up": "Percentage discount rounded instead of rounded down",
    "single_use_not_enforced": "Same customer can reuse the code",
    "burn_without_discount": "Code marked as used even when it gave no discount",
}

HEADER = '''import pytest

import shopcart
from shopcart import Cart


@pytest.fixture(autouse=True)
def _fresh_usage():
    reset = getattr(shopcart, "reset_code_usage", None)
    if reset:
        reset()
    yield


def _promo(cart):
    return sum(a.amount for a in cart.adjustments() if a.label.startswith("Promo"))
'''


def _instruction(p: dict, example: str, ex_sub: int, ex_d: int) -> str:
    code, cat = p["code"], p["category"]
    eligible = f"the total of items in the `{cat}` category" if cat else "the cart subtotal"
    if p["kind"] == "percent":
        amount = f"{p['pct']}% of the eligible amount, rounded down to the nearest paisa"
    else:
        amount = f"a flat {rupees(p['flat'])} off, but never more than the eligible amount"
    rules = [
        f"The code is `{code}`. Matching ignores upper/lower case and spaces around the code.",
        f"The discount is {amount}.",
        f"The eligible amount is {eligible}.",
    ]
    if p["min_subtotal"] is not None:
        on = "the eligible amount" if p["threshold_on"] == "eligible" else "the cart subtotal"
        rules.append(f"The discount only applies while {on} is at least {rupees(p['min_subtotal'])} "
                     f"({p['min_subtotal']} paise). The code can be applied before that; the discount appears and "
                     "disappears as the cart changes.")
    if p["cap"]:
        rules.append(f"The discount is never more than {rupees(p['cap'])} ({p['cap']} paise).")
    rules.append("Only one code per cart. Applying a code while one is already applied raises `InvalidCode`.")
    rules.append("Unknown codes raise `InvalidCode`.")
    if p["single_use"]:
        rules.append("Each customer (`customer_id`) can use the code once. It counts as used when `checkout()` is "
                     "called on a cart where the code gave a discount above zero. After that, applying it for the "
                     "same customer raises `InvalidCode`. Other customers are not affected.")
    iface = [
        "`shopcart.InvalidCode`: new exception, subclass of `ValueError`, importable from `shopcart`.",
        "`Cart.apply_code(code: str) -> None` and `Cart.remove_code() -> None`.",
        f"`Cart.adjustments()` includes `Adjustment(\"Promo {code}\", -discount)` while the discount is above zero, "
        "and no promo adjustment otherwise. `Cart.total()` already sums adjustments.",
    ]
    if p["single_use"]:
        iface.append("`Cart.checkout() -> int` returns the amount charged (same as `total()`).")
        iface.append("`shopcart.reset_code_usage() -> None` forgets all recorded code usage.")
    body = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    ifc = "\n".join(f"- {x}" for x in iface)
    return f"""# Add the {code} promo code to the cart

Marketing wants customers to be able to enter the promo code `{code}` at checkout. The repository in
`/app` is the `shopcart` library. Money is always integer paise (100 paise = ₹1).

## Rules
{body}

## Interface
{ifc}

## Example
A cart with {example} has a subtotal of {ex_sub} paise. After `apply_code("{code}")` the promo adjustment is
{-ex_d} and `total()` is {ex_sub - ex_d}.

Keep all existing behaviour working; the existing tests in `tests/` must still pass.
"""
