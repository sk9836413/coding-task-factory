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
    c.add('RICE-5K', 2)
    c.add('PEN-10', 3)
    assert _promo(c) == 0
    assert c.total() == 174800
    c.apply_code('WEEKEND')
    assert _promo(c) == -2250
    assert c.total() == 172550


def test_code_is_case_insensitive_and_trimmed():
    c = Cart('asha')
    c.add('RICE-5K', 2)
    c.add('PEN-10', 3)
    c.apply_code('  weekend ')
    assert _promo(c) == -2250
    assert c.total() == 172550


def test_unknown_code_rejected():
    c = Cart('asha')
    c.add('RICE-5K', 2)
    c.add('PEN-10', 3)
    with pytest.raises(shopcart.InvalidCode):
        c.apply_code('NOTAREALCODE')
    assert _promo(c) == 0
    assert c.total() == 174800


def test_one_code_per_order():
    c = Cart('asha')
    c.add('RICE-5K', 2)
    c.add('PEN-10', 3)
    c.apply_code('WEEKEND')
    with pytest.raises(shopcart.InvalidCode):
        c.apply_code('WEEKEND')
    assert _promo(c) == -2250
    assert c.total() == 172550


def test_remove_code():
    c = Cart('asha')
    c.add('RICE-5K', 2)
    c.add('PEN-10', 3)
    c.apply_code('WEEKEND')
    c.remove_code()
    assert _promo(c) == 0
    assert c.total() == 174800


def test_only_category_items_are_discounted():
    c = Cart('asha')
    c.add('RICE-5K', 2)
    c.add('PEN-10', 3)
    c.apply_code('WEEKEND')
    assert _promo(c) == -2250
    assert c.total() == 172550


def test_no_discount_without_eligible_items():
    c = Cart('asha')
    c.add('SHIRT-M', 3)
    c.add('BULB-9W', 2)
    c.apply_code('WEEKEND')
    assert _promo(c) == 0
    assert c.total() == 259500
