from shopcart import Cart


def _deal(cart):
    return sum(a.amount for a in cart.adjustments() if a.label.startswith("Deal"))


def test_no_deal_below_group_size():
    c = Cart()
    c.add('OIL-1L', 3)
    c.add('TEA-250', 1)
    assert c.deal_discount() == 0
    assert _deal(c) == 0
    assert c.total() == 79500


def test_one_free_item_per_group():
    c = Cart()
    c.add('OIL-1L', 4)
    assert c.deal_discount() == 18500
    assert _deal(c) == -18500
    assert c.total() == 55500


def test_partial_group_gets_nothing_extra():
    c = Cart()
    c.add('OIL-1L', 7)
    c.add('TEA-250', 2)
    assert c.deal_discount() == 18500
    assert _deal(c) == -18500
    assert c.total() == 159000


def test_free_items_are_capped():
    c = Cart()
    c.add('OIL-1L', 12)
    assert c.deal_discount() == 37000
    assert _deal(c) == -37000
    assert c.total() == 185000
