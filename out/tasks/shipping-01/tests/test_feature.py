from shopcart import Cart


def _ship(cart):
    return sum(a.amount for a in cart.adjustments() if a.label == "Shipping")


def test_empty_cart_has_no_shipping():
    c = Cart()
    assert c.shipping() == 0
    assert c.total() == 0


def test_base_fee_for_light_order():
    c = Cart()
    c.add('BULB-9W', 3)
    c.add('PEN-10', 3)
    assert c.shipping() == 4000
    assert _ship(c) == 4000
    assert c.total() == 78700


def test_weight_charge_per_started_kg():
    c = Cart()
    c.add('OIL-1L', 3)
    assert c.shipping() == 8000
    assert _ship(c) == 8000
    assert c.total() == 63500


def test_first_kg_included_in_base_fee():
    c = Cart()
    c.add('BULB-9W', 3)
    c.add('PEN-10', 3)
    assert c.shipping() == 4000
    assert _ship(c) == 4000
    assert c.total() == 78700


def test_free_shipping_threshold_is_inclusive():
    c = Cart()
    c.add('OIL-1L', 3)
    c.add('BULB-9W', 3)
    assert c.shipping() == 0
    assert _ship(c) == 0
    assert c.total() == 85200


def test_shipping_becomes_free_when_threshold_reached():
    c = Cart()
    c.add('BULB-9W', 3)
    c.add('PEN-10', 3)
    assert c.shipping() == 4000
    assert _ship(c) == 4000
    assert c.total() == 78700
    c.add('BULB-9W', 2)
    assert c.shipping() == 0
    assert _ship(c) == 0
    assert c.total() == 94500
