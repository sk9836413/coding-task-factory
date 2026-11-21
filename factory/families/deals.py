"""Family: quantity deals, either "buy X get 1 free" on a product or tiered % off on a product or category."""
from __future__ import annotations

import random

from ..common import ADJ_ANCHOR, Emitter, Mutant, TaskPackage, basket_lines, insert_before, replace_once
from ..repo import Repo

NAME = "deals"


def sample(repo: Repo, rng: random.Random) -> dict:
    cheapish = [i.sku for i in repo.catalog() if i.price <= 80000]
    if rng.random() < 0.5:
        return {"kind": "bxgy", "sku": rng.choice(cheapish), "x": rng.choice([1, 2, 3]),
                "max_free": rng.choice([None, 1, 2])}
    if rng.random() < 0.5:
        target = ("sku", rng.choice(cheapish))
    else:
        cats = [c for c in repo.categories() if sum(i.category == c for i in repo.catalog()) >= 2]
        target = ("category", rng.choice(cats))
    return {"kind": "tiered", "target": target, "n": rng.choice([3, 4, 5]), "pct": rng.choice([10, 15, 20])}


def signature(p: dict) -> tuple:
    return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in p.items()))


def _label(p: dict) -> str:
    if p["kind"] == "bxgy":
        return f"Deal: buy {p['x']} get 1 free on {p['sku']}"
    return f"Deal: {p['pct']}% off {p['n']}+ {p['target'][1]}"


def _discount(repo: Repo, p: dict, b: dict) -> int:
    """Independent oracle."""
    if p["kind"] == "bxgy":
        q = b.get(p["sku"], 0)
        free = q // (p["x"] + 1)
        if p["max_free"] is not None:
            free = min(free, p["max_free"])
        return free * repo.item(p["sku"]).price
    kind, val = p["target"]
    hit = {s: q for s, q in b.items() if (s == val if kind == "sku" else repo.item(s).category == val)}
    if sum(hit.values()) < p["n"]:
        return 0
    return sum(repo.item(s).price * q for s, q in hit.items()) * p["pct"] // 100


def _cart_source(repo: Repo, p: dict, bugs: frozenset = frozenset()) -> str:
    src = repo.read("shopcart/cart.py")
    m = ["    def deal_discount(self) -> int:", '        """Discount from the active quantity deal, in paise."""']
    if p["kind"] == "bxgy":
        group = p["x"] if "group_off_by_one" in bugs else p["x"] + 1
        price = repo.item(p["sku"]).price
        m += [f'        free = self.quantity("{p["sku"]}") // {group}']
        if p["max_free"] is not None and "ignore_max" not in bugs:
            m.append(f"        free = min(free, {p['max_free']})")
        m.append(f"        return free * {price}")
    else:
        kind, val = p["target"]
        match = f'l.product.sku == "{val}"' if kind == "sku" else f'l.product.category == "{val}"'
        m += [f"        hit = [l for l in self.lines() if {match}]"]
        op = ">" if "tier_strict" in bugs else ">="
        if "count_per_line" in bugs:
            m += [f"        hit = [l for l in hit if l.quantity {op} {p['n']}]",
                  "        if not hit:", "            return 0"]
        else:
            m += [f"        if not sum(l.quantity for l in hit) {op} {p['n']}:", "            return 0"]
        m.append(f"        return round(sum(l.total for l in hit) * {p['pct']} / 100)" if "round_half_up" in bugs
                 else f"        return sum(l.total for l in hit) * {p['pct']} // 100")
    m.append("")
    new_adj = ("    def adjustments(self) -> list[Adjustment]:\n        d = self.deal_discount()\n"
               f'        return [Adjustment("{_label(p)}", -d)] if d else []\n')
    src = insert_before(src, ADJ_ANCHOR, "\n".join(m) + "\n", "methods")
    return replace_once(src, ADJ_ANCHOR, new_adj, "adjustments")


def build(repo: Repo, p: dict) -> TaskPackage:
    em = Emitter(HEADER)
    mutants, skipped = [], []

    def case(name: str, basket: dict) -> None:
        d = _discount(repo, p, basket)
        sub = sum(repo.item(s).price * q for s, q in basket.items())
        em.test(name, ["c = Cart()"] + basket_lines("c", basket) +
                [f"assert c.deal_discount() == {d}", f"assert _deal(c) == {-d}", f"assert c.total() == {sub - d}"])

    other = next(i.sku for i in repo.catalog() if i.sku != p.get("sku") and (
        p["kind"] == "bxgy" or (p["target"][0] == "sku" and i.sku != p["target"][1]) or
        (p["target"][0] == "category" and i.category != p["target"][1])))
    if p["kind"] == "bxgy":
        s, x = p["sku"], p["x"]
        case("no_deal_below_group_size", {s: x, other: 1})
        case("one_free_item_per_group", {s: x + 1})
        case("partial_group_gets_nothing_extra", {s: 2 * x + 1, other: 2})
        mutants.append("group_off_by_one")
        if p["max_free"] is not None:
            case("free_items_are_capped", {s: (x + 1) * (p["max_free"] + 1)})
            mutants.append("ignore_max")
    else:
        kind, val = p["target"]
        n = p["n"]
        if kind == "sku":
            case("no_discount_below_tier", {val: n - 1, other: 1})
            case("discount_at_tier", {val: n})
            case("discount_above_tier", {val: n + 2, other: 1})
        else:
            skus = [i.sku for i in repo.catalog() if i.category == val]
            case("no_discount_below_tier", {skus[0]: n - 1, other: 2})
            case("discount_at_tier", {skus[0]: n})
            case("quantities_across_the_category_add_up", {skus[0]: n - 1, skus[1]: 1})
            mutants.append("count_per_line")
        mutants.append("tier_strict")
        rb = next(({val if kind == "sku" else skus[0]: q} for q in range(n, n + 12)
                   if (repo.item(val if kind == "sku" else skus[0]).price * q * p["pct"]) % 100 >= 50), None)
        if rb:
            case("discount_rounds_down", rb)
            mutants.append("round_half_up")
        else:
            skipped.append("round_half_up")

    solution = {"shopcart/cart.py": _cart_source(repo, p)}
    muts = [Mutant(b, BUGS[b], {"shopcart/cart.py": _cart_source(repo, p, frozenset([b]))}) for b in mutants]
    title = (f"Add a buy {p['x']} get 1 free deal on {p['sku']}" if p["kind"] == "bxgy"
             else f"Add {p['pct']}% off for {p['n']} or more {p['target'][1]}")
    return TaskPackage(family=NAME, params=p, signature=signature(p), title=title, instruction=_instruction(repo, p),
                       solution=solution, feature_tests=em.source(), mutants=muts, skipped_mutants=skipped,
                       difficulty="easy" if p["kind"] == "bxgy" and p["max_free"] is None else "medium",
                       tags=["quantity-deal", p["kind"]])


BUGS = {
    "group_off_by_one": "Counts groups of X instead of X+1 for buy X get 1 free",
    "ignore_max": "Free-item cap per order not applied",
    "tier_strict": "Tier starts above N instead of at N",
    "count_per_line": "Category quantity counted per product line instead of across the category",
    "round_half_up": "Percentage rounded instead of rounded down",
}

HEADER = '''from shopcart import Cart


def _deal(cart):
    return sum(a.amount for a in cart.adjustments() if a.label.startswith("Deal"))
'''


def _instruction(repo: Repo, p: dict) -> str:
    if p["kind"] == "bxgy":
        it = repo.item(p["sku"])
        rules = [f"For product `{p['sku']}` (price {it.price} paise): for every {p['x'] + 1} units in the cart, "
                 f"1 unit is free (buy {p['x']}, get 1 free). Incomplete groups get nothing."]
        if p["max_free"] is not None:
            rules.append(f"At most {p['max_free']} free unit(s) per cart.")
    else:
        kind, val = p["target"]
        what = f"product `{val}`" if kind == "sku" else f"products in the `{val}` category (counted together)"
        rules = [f"When the cart holds {p['n']} or more units of {what}, those units get {p['pct']}% off.",
                 "The discount is the percentage of the matching line totals, rounded down to the nearest paisa.",
                 "Other products are never discounted."]
    rules.append("The deal applies automatically; there is nothing to switch on.")
    body = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    return f"""# {"Buy " + str(p["x"]) + " get 1 free" if p["kind"] == "bxgy" else "Quantity discount"} in the cart

Add a quantity deal to the `shopcart` library in `/app`. Money is integer paise (100 paise = ₹1).

## Rules
{body}

## Interface
- `Cart.deal_discount() -> int`: the deal discount in paise (0 when the deal does not apply).
- `Cart.adjustments()` includes `Adjustment("{_label(p)}", -discount)` when the discount is above zero (the label
  must start with `Deal`), so `Cart.total()` includes it.

Keep all existing behaviour working; the existing tests in `tests/` must still pass.
"""
