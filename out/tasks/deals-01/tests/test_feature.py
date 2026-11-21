from shopcart import Cart


def _deal(cart):
    return sum(a.amount for a in cart.adjustments() if a.label.startswith("Deal"))


def test_no_deal_below_group_size():
    c = Cart()
    c.add('RICE-5K', 1)
    c.add('TEA-250', 1)
    assert c.deal_discount() == 0
    assert _deal(c) == 0
    assert c.total() == 88900


def test_one_free_item_per_group():
    c = Cart()
    c.add('RICE-5K', 2)
    assert c.deal_discount() == 64900
    assert _deal(c) == -64900
    assert c.total() == 64900


def test_partial_group_gets_nothing_extra():
    c = Cart()
    c.add('RICE-5K', 3)
    c.add('TEA-250', 2)
    assert c.deal_discount() == 64900
    assert _deal(c) == -64900
    assert c.total() == 177800


def test_free_items_are_capped():
    c = Cart()
    c.add('RICE-5K', 6)
    assert c.deal_discount() == 129800
    assert _deal(c) == -129800
    assert c.total() == 259600
