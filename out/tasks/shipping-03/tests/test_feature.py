from shopcart import Cart


def _ship(cart):
    return sum(a.amount for a in cart.adjustments() if a.label == "Shipping")


def test_empty_cart_has_no_shipping():
    c = Cart()
    assert c.shipping() == 0
    assert c.total() == 0


def test_base_fee_for_light_order():
    c = Cart()
    c.add('SOCK-3P', 2)
    c.add('BULB-9W', 1)
    assert c.shipping() == 9900
    assert _ship(c) == 9900
    assert c.total() == 79600


def test_free_shipping_threshold_is_inclusive():
    c = Cart()
    c.add('OIL-1L', 3)
    c.add('BULB-9W', 3)
    assert c.shipping() == 0
    assert _ship(c) == 0
    assert c.total() == 85200


def test_shipping_becomes_free_when_threshold_reached():
    c = Cart()
    c.add('SOCK-3P', 2)
    c.add('BULB-9W', 1)
    assert c.shipping() == 9900
    assert _ship(c) == 9900
    assert c.total() == 79600
    c.add('SOCK-3P', 1)
    assert c.shipping() == 0
    assert _ship(c) == 0
    assert c.total() == 99600


def test_express_adds_surcharge():
    c = Cart()
    c.add('SOCK-3P', 2)
    c.add('BULB-9W', 1)
    assert c.shipping() == 9900
    assert _ship(c) == 9900
    assert c.total() == 79600
    c.set_express(True)
    assert c.shipping() == 14900
    assert _ship(c) == 14900
    assert c.total() == 84600
    c.set_express(False)
    assert c.shipping() == 9900
    assert _ship(c) == 9900
    assert c.total() == 79600


def test_express_and_free_shipping():
    c = Cart()
    c.add('RICE-5K', 1)
    c.add('SHIRT-M', 1)
    assert c.shipping() == 0
    assert _ship(c) == 0
    assert c.total() == 144800
    c.set_express(True)
    assert c.shipping() == 14900
    assert _ship(c) == 14900
    assert c.total() == 159700
