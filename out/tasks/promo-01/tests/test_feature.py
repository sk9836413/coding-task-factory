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
    c.add('RICE-5K', 1)
    c.add('PEN-10', 3)
    assert _promo(c) == 0
    assert c.total() == 109900
    c.apply_code('THANKYOU')
    assert _promo(c) == -21980
    assert c.total() == 87920


def test_code_is_case_insensitive_and_trimmed():
    c = Cart('asha')
    c.add('RICE-5K', 1)
    c.add('PEN-10', 3)
    c.apply_code('  thankyou ')
    assert _promo(c) == -21980
    assert c.total() == 87920


def test_unknown_code_rejected():
    c = Cart('asha')
    c.add('RICE-5K', 1)
    c.add('PEN-10', 3)
    with pytest.raises(shopcart.InvalidCode):
        c.apply_code('NOTAREALCODE')
    assert _promo(c) == 0
    assert c.total() == 109900


def test_one_code_per_order():
    c = Cart('asha')
    c.add('RICE-5K', 1)
    c.add('PEN-10', 3)
    c.apply_code('THANKYOU')
    with pytest.raises(shopcart.InvalidCode):
        c.apply_code('THANKYOU')
    assert _promo(c) == -21980
    assert c.total() == 87920


def test_remove_code():
    c = Cart('asha')
    c.add('RICE-5K', 1)
    c.add('PEN-10', 3)
    c.apply_code('THANKYOU')
    c.remove_code()
    assert _promo(c) == 0
    assert c.total() == 109900


def test_minimum_spend_is_inclusive():
    c = Cart('asha')
    c.add('OIL-1L', 3)
    c.add('BULB-9W', 1)
    c.apply_code('THANKYOU')
    assert _promo(c) == -13080
    assert c.total() == 52320


def test_discount_starts_when_minimum_reached():
    c = Cart('asha')
    c.add('BULB-9W', 1)
    c.add('PEN-10', 1)
    c.apply_code('THANKYOU')
    assert _promo(c) == 0
    assert c.total() == 24900
    c.add('BULB-9W', 5)
    assert _promo(c) == -14880
    assert c.total() == 59520


def test_discount_removed_when_cart_drops_below_minimum():
    c = Cart('asha')
    c.add('BULB-9W', 2)
    c.add('FAN-TBL', 1)
    c.apply_code('THANKYOU')
    assert _promo(c) == -30000
    assert c.total() == 179700
    c.remove('FAN-TBL')
    assert _promo(c) == 0
    assert c.total() == 19800


def test_discount_is_capped():
    c = Cart('asha')
    c.add('BULB-9W', 2)
    c.add('FAN-TBL', 1)
    c.apply_code('THANKYOU')
    assert _promo(c) == -30000
    assert c.total() == 179700


def test_code_is_single_use_per_customer():
    a1 = Cart('asha')
    a1.add('RICE-5K', 1)
    a1.add('PEN-10', 3)
    a1.apply_code('THANKYOU')
    assert a1.checkout() == 87920
    a2 = Cart('asha')
    a2.add('RICE-5K', 1)
    a2.add('PEN-10', 3)
    with pytest.raises(shopcart.InvalidCode):
        a2.apply_code('THANKYOU')
    assert _promo(a2) == 0
    assert a2.total() == 109900
    b1 = Cart('ravi')
    b1.add('RICE-5K', 1)
    b1.add('PEN-10', 3)
    b1.apply_code('THANKYOU')
    assert _promo(b1) == -21980
    assert b1.total() == 87920


def test_code_not_used_up_when_it_gave_no_discount():
    a1 = Cart('asha')
    a1.add('BULB-9W', 1)
    a1.add('PEN-10', 1)
    a1.apply_code('THANKYOU')
    assert a1.checkout() == 24900
    a2 = Cart('asha')
    a2.add('RICE-5K', 1)
    a2.add('PEN-10', 3)
    a2.apply_code('THANKYOU')
    assert _promo(a2) == -21980
    assert a2.total() == 87920
