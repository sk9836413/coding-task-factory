from shopcart import Cart


def _ship(cart):
    return sum(a.amount for a in cart.adjustments() if a.label == "Shipping")


def test_empty_cart_has_no_shipping():
    c = Cart()
    assert c.shipping() == 0
    assert c.total() == 0


def test_base_fee_for_light_order():
    c = Cart()
    c.add('SHIRT-M', 1)
    c.add('BULB-9W', 2)
    assert c.shipping() == 4900
    assert _ship(c) == 4900
    assert c.total() == 104600


def test_free_shipping_threshold_is_inclusive():
    c = Cart()
    c.add('OIL-1L', 1)
    c.add('SOCK-3P', 3)
    assert c.shipping() == 0
    assert _ship(c) == 0
    assert c.total() == 108200


def test_shipping_becomes_free_when_threshold_reached():
    c = Cart()
    c.add('OIL-1L', 1)
    c.add('PEN-10', 2)
    assert c.shipping() == 4900
    assert _ship(c) == 4900
    assert c.total() == 53400
    c.add('OIL-1L', 4)
    assert c.shipping() == 0
    assert _ship(c) == 0
    assert c.total() == 122500
