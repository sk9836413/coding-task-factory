from shopcart import Cart


def _deal(cart):
    return sum(a.amount for a in cart.adjustments() if a.label.startswith("Deal"))


def test_no_deal_below_group_size():
    c = Cart()
    c.add('SHIRT-M', 2)
    c.add('TEA-250', 1)
    assert c.deal_discount() == 0
    assert _deal(c) == 0
    assert c.total() == 183800


def test_one_free_item_per_group():
    c = Cart()
    c.add('SHIRT-M', 3)
    assert c.deal_discount() == 79900
    assert _deal(c) == -79900
    assert c.total() == 159800


def test_partial_group_gets_nothing_extra():
    c = Cart()
    c.add('SHIRT-M', 5)
    c.add('TEA-250', 2)
    assert c.deal_discount() == 79900
    assert _deal(c) == -79900
    assert c.total() == 367600


def test_free_items_are_capped():
    c = Cart()
    c.add('SHIRT-M', 6)
    assert c.deal_discount() == 79900
    assert _deal(c) == -79900
    assert c.total() == 399500
