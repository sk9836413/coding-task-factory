"""Family: shipping charges with free-shipping thresholds, weight charges and express delivery."""
from __future__ import annotations

import random

from ..common import ADJ_ANCHOR, INIT_ANCHOR, Emitter, Mutant, TaskPackage, basket_lines, insert_before, \
    replace_once, rupees
from ..repo import Repo

NAME = "shipping"


def sample(repo: Repo, rng: random.Random) -> dict:
    p = {"base_fee": rng.choice([4000, 4900, 9900]),
         "per_kg": rng.choice([None, 1000, 2000]),
         "express": rng.choice([None, 5000, 10000]),
         "free_above": None, "express_free": False}
    if rng.random() < 0.75:
        values = sorted({_sub(repo, b) for b in repo.baskets()})
        values = [v for v in values if 40000 <= v <= 160000]
        p["free_above"] = rng.choice(values[len(values) // 4: 3 * len(values) // 4] or values)
    if p["express"] and p["free_above"]:
        p["express_free"] = rng.random() < 0.5
    return p


def signature(p: dict) -> tuple:
    return tuple(sorted(p.items()))


def _sub(repo: Repo, b: dict) -> int:
    return sum(repo.item(s).price * q for s, q in b.items())


def _weight(repo: Repo, b: dict) -> int:
    return sum(repo.item(s).weight_g * q for s, q in b.items())


def _fee(repo: Repo, p: dict, b: dict, express: bool) -> int:
    """Independent oracle for the expected shipping charge."""
    if not b:
        return 0
    fee = p["base_fee"]
    if p["per_kg"]:
        extra = max(0, _weight(repo, b) - 1000)
        fee += ((extra + 999) // 1000) * p["per_kg"]
    if p["free_above"] is not None and _sub(repo, b) >= p["free_above"] and (not express or p["express_free"]):
        fee = 0
    if express and p["express"]:
        fee += p["express"]
    return fee


class _Test:
    def __init__(self, repo: Repo, p: dict):
        self.repo, self.p, self.lines, self.qty, self.express = repo, p, [], {}, False

    def cart(self, basket: dict) -> "_Test":
        self.lines.append("c = Cart()")
        return self.add(basket)

    def add(self, basket: dict) -> "_Test":
        for s, q in basket.items():
            self.qty[s] = self.qty.get(s, 0) + q
        self.lines += basket_lines("c", basket)
        return self

    def set_express(self, on: bool) -> "_Test":
        self.express = on
        self.lines.append(f"c.set_express({on})")
        return self

    def check(self) -> "_Test":
        f, sub = _fee(self.repo, self.p, self.qty, self.express), _sub(self.repo, self.qty)
        self.lines += [f"assert c.shipping() == {f}", f"assert _ship(c) == {f}", f"assert c.total() == {sub + f}"]
        return self


def _cart_source(repo: Repo, p: dict, bugs: frozenset = frozenset()) -> str:
    src = repo.read("shopcart/cart.py")
    src = replace_once(src, INIT_ANCHOR, INIT_ANCHOR + "        self._express = False\n", "init")
    m = []
    if p["express"]:
        m += ["    def set_express(self, enabled: bool) -> None:", "        self._express = bool(enabled)", ""]
    m += ["    def shipping(self) -> int:", '        """Shipping charge in paise."""']
    if "empty_charged" not in bugs:
        m += ["        if not self._qty:", "            return 0"]
    m.append(f"        fee = {p['base_fee']}")
    if p["per_kg"]:
        if "weight_includes_first_kg" in bugs:
            m.append("        extra = self.weight_g()")
        else:
            m.append("        extra = max(0, self.weight_g() - 1000)")
        m.append(f"        fee += (extra // 1000) * {p['per_kg']}" if "weight_floor" in bugs
                 else f"        fee += -(-extra // 1000) * {p['per_kg']}")
    if p["free_above"] is not None:
        op = ">" if "free_strict" in bugs else ">="
        cond = f"self.subtotal() {op} {p['free_above']}"
        if p["express"]:
            keeps_free = p["express_free"] != ("express_free_wrong" in bugs)
            if not keeps_free:
                cond += " and not self._express"
        m += [f"        if {cond}:", "            fee = 0"]
    if p["express"] and "express_ignored" not in bugs:
        m += ["        if self._express:", f"            fee += {p['express']}"]
    m += ["        return fee", ""]
    new_adj = ("    def adjustments(self) -> list[Adjustment]:\n        fee = self.shipping()\n"
               '        return [Adjustment("Shipping", fee)] if fee else []\n')
    src = insert_before(src, ADJ_ANCHOR, "\n".join(m) + "\n", "methods")
    return replace_once(src, ADJ_ANCHOR, new_adj, "adjustments")


def build(repo: Repo, p: dict) -> TaskPackage:
    rng = random.Random(repr(signature(p)))
    baskets = repo.baskets()
    rng.shuffle(baskets)
    sub = lambda b: _sub(repo, b)
    w = lambda b: _weight(repo, b)
    below = lambda b: p["free_above"] is None or sub(b) < p["free_above"]

    def pick(pred):
        return next((b for b in baskets if pred(b)), None)

    em = Emitter(HEADER)
    mutants, skipped = [], []
    em.test("empty_cart_has_no_shipping", ["c = Cart()", "assert c.shipping() == 0", "assert c.total() == 0"])
    mutants.append("empty_charged")
    light = pick(lambda b: below(b) and w(b) <= 1000)
    if light:
        em.test("base_fee_for_light_order", _Test(repo, p).cart(light).check().lines)
    if p["per_kg"]:
        heavy = pick(lambda b: below(b) and w(b) > 1000 and (w(b) - 1000) % 1000 != 0)
        if heavy:
            em.test("weight_charge_per_started_kg", _Test(repo, p).cart(heavy).check().lines)
            mutants.append("weight_floor")
        else:
            skipped.append("weight_floor")
        mid = pick(lambda b: below(b) and 0 < w(b) <= 1000) or pick(
            lambda b: below(b) and w(b) > 1000 and (w(b) // 1000) != -(-(w(b) - 1000) // 1000))
        if mid:
            em.test("first_kg_included_in_base_fee", _Test(repo, p).cart(mid).check().lines)
            mutants.append("weight_includes_first_kg")
        else:
            skipped.append("weight_includes_first_kg")
    if p["free_above"] is not None:
        exact = pick(lambda b: sub(b) == p["free_above"])
        if exact:
            em.test("free_shipping_threshold_is_inclusive", _Test(repo, p).cart(exact).check().lines)
            mutants.append("free_strict")
        else:
            skipped.append("free_strict")
        under = pick(lambda b: sub(b) < p["free_above"])
        if under:
            sku = next(iter(under))
            k = 1
            while sub({**under, sku: under[sku] + k}) < p["free_above"]:
                k += 1
            em.test("shipping_becomes_free_when_threshold_reached",
                    _Test(repo, p).cart(under).check().add({sku: k}).check().lines)
    if p["express"]:
        any_b = light or pick(below)
        em.test("express_adds_surcharge", _Test(repo, p).cart(any_b).check().set_express(True).check()
                .set_express(False).check().lines)
        mutants.append("express_ignored")
        if p["free_above"] is not None:
            big = pick(lambda b: sub(b) >= p["free_above"])
            em.test("express_and_free_shipping", _Test(repo, p).cart(big).check().set_express(True).check().lines)
            mutants.append("express_free_wrong")

    solution = {"shopcart/cart.py": _cart_source(repo, p)}
    muts = [Mutant(b, BUGS[b], {"shopcart/cart.py": _cart_source(repo, p, frozenset([b]))}) for b in mutants]
    return TaskPackage(
        family=NAME, params=p, signature=signature(p), title="Add shipping charges to the cart",
        regression_edits={"tests/test_cart.py": [("assert c.total() == c.subtotal()",
                                                  "assert c.total() == c.subtotal() + c.shipping()")]},
        instruction=_instruction(p), solution=solution, feature_tests=em.source(), mutants=muts,
        skipped_mutants=skipped, difficulty="medium" if (p["per_kg"] or p["express"]) else "easy",
        tags=["shipping"] + (["weight"] if p["per_kg"] else []) + (["express"] if p["express"] else []) +
             (["free-threshold"] if p["free_above"] else []))


BUGS = {
    "empty_charged": "Empty carts are charged shipping",
    "weight_floor": "Weight charge counts whole kilograms instead of started kilograms",
    "weight_includes_first_kg": "The first kilogram is charged as extra weight",
    "free_strict": "Free-shipping threshold uses > instead of >=",
    "express_ignored": "Express surcharge never added",
    "express_free_wrong": "Express orders get (or lose) free shipping against the rules",
}

HEADER = '''from shopcart import Cart


def _ship(cart):
    return sum(a.amount for a in cart.adjustments() if a.label == "Shipping")
'''


def _instruction(p: dict) -> str:
    rules = [f"Every non-empty order pays a base shipping fee of {rupees(p['base_fee'])} ({p['base_fee']} paise). "
             "An empty cart pays nothing."]
    if p["per_kg"]:
        rules.append(f"The base fee covers the first 1 kg (1000 g) of `Cart.weight_g()`. Each started kilogram above "
                     f"that adds {rupees(p['per_kg'])} ({p['per_kg']} paise). For example 2,050 g costs 2 extra kg.")
    if p["free_above"] is not None:
        waived = "the base fee" + (" and the weight charge" if p["per_kg"] else "")
        rules.append(f"When the cart subtotal is at least {rupees(p['free_above'])} ({p['free_above']} paise), "
                     f"{waived} are waived.")
    if p["express"]:
        rules.append(f"Express delivery adds {rupees(p['express'])} ({p['express']} paise) on top of any other "
                     "shipping charge. It is off by default.")
        if p["free_above"] is not None:
            rules.append("Express orders still get free standard shipping when they qualify; only the express "
                         "surcharge is paid." if p["express_free"] else
                         "Express orders never get free shipping: they always pay the normal charge plus the "
                         "express surcharge.")
    iface = ["`Cart.shipping() -> int`: the shipping charge in paise for the current cart."]
    if p["express"]:
        iface.append("`Cart.set_express(enabled: bool) -> None`.")
    iface.append('`Cart.adjustments()` includes `Adjustment("Shipping", fee)` when the fee is above zero, so '
                 "`Cart.total()` includes shipping.")
    body = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    ifc = "\n".join(f"- {x}" for x in iface)
    return f"""# Add shipping charges to the cart

The `shopcart` library in `/app` does not charge for shipping yet. Add shipping charges following these rules.
Money is integer paise (100 paise = ₹1), weights are grams.

## Rules
{body}

## Interface
{ifc}

`test_add_and_subtotal` in `tests/test_cart.py` assumes the total always equals the subtotal. That is no longer
true once shipping exists: update it so the total equals the subtotal plus `c.shipping()`. Everything else must
keep working and all other existing tests must still pass.
"""
