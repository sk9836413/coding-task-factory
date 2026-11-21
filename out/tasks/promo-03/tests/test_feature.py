import pytest

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


def test_discount_applied():
    c = Cart('asha')
    c.add('TEA-250', 1)
    c.add('PEN-10', 3)
    assert _promo(c) == 0
    assert c.total() == 69000
    c.apply_code('FESTIVE')
    assert _promo(c) == -6900
    assert c.total() == 62100


def test_code_is_case_insensitive_and_trimmed():
    c = Cart('asha')
    c.add('TEA-250', 1)
    c.add('PEN-10', 3)
    c.apply_code('  festive ')
    assert _promo(c) == -6900
    assert c.total() == 62100


def test_unknown_code_rejected():
    c = Cart('asha')
    c.add('TEA-250', 1)
    c.add('PEN-10', 3)
    with pytest.raises(shopcart.InvalidCode):
        c.apply_code('NOTAREALCODE')
    assert _promo(c) == 0
    assert c.total() == 69000


def test_one_code_per_order():
    c = Cart('asha')
    c.add('TEA-250', 1)
    c.add('PEN-10', 3)
    c.apply_code('FESTIVE')
    with pytest.raises(shopcart.InvalidCode):
        c.apply_code('FESTIVE')
    assert _promo(c) == -6900
    assert c.total() == 62100


def test_remove_code():
    c = Cart('asha')
    c.add('TEA-250', 1)
    c.add('PEN-10', 3)
    c.apply_code('FESTIVE')
    c.remove_code()
    assert _promo(c) == 0
    assert c.total() == 69000


def test_minimum_spend_is_inclusive():
    c = Cart('asha')
    c.add('TEA-250', 2)
    c.add('PEN-10', 1)
    c.apply_code('FESTIVE')
    assert _promo(c) == -6300
    assert c.total() == 56700


def test_discount_starts_when_minimum_reached():
    c = Cart('asha')
    c.add('TEA-250', 1)
    c.add('BULB-9W', 1)
    c.apply_code('FESTIVE')
    assert _promo(c) == 0
    assert c.total() == 33900
    c.add('TEA-250', 2)
    assert _promo(c) == -8190
    assert c.total() == 73710


def test_discount_removed_when_cart_drops_below_minimum():
    c = Cart('asha')
    c.add('TEA-250', 1)
    c.add('PEN-10', 3)
    c.apply_code('FESTIVE')
    assert _promo(c) == -6900
    assert c.total() == 62100
    c.remove('TEA-250')
    assert _promo(c) == 0
    assert c.total() == 45000


def test_discount_is_capped():
    c = Cart('asha')
    c.add('FAN-TBL', 1)
    c.apply_code('FESTIVE')
    assert _promo(c) == -15000
    assert c.total() == 174900
