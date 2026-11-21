import pytest

from shopcart import CATALOG, Cart


def test_empty_cart():
    c = Cart()
    assert c.lines() == [] and c.subtotal() == 0 and c.total() == 0


def test_add_and_subtotal():
    c = Cart()
    c.add("TEA-250", 2)
    c.add("BULB-9W")
    assert c.quantity("TEA-250") == 2
    assert c.subtotal() == 2 * 24000 + 9900
    assert c.total() == c.subtotal() + c.shipping()


def test_add_same_sku_accumulates():
    c = Cart()
    c.add("PEN-10")
    c.add("PEN-10", 3)
    assert c.quantity("PEN-10") == 4


def test_remove_partial_and_full():
    c = Cart()
    c.add("SOCK-3P", 3)
    c.remove("SOCK-3P", 1)
    assert c.quantity("SOCK-3P") == 2
    c.remove("SOCK-3P")
    assert c.quantity("SOCK-3P") == 0 and c.subtotal() == 0


def test_invalid_input():
    c = Cart()
    with pytest.raises(KeyError):
        c.add("NOPE")
    with pytest.raises(ValueError):
        c.add("TEA-250", 0)
    with pytest.raises(KeyError):
        c.remove("TEA-250")


def test_weight_and_lines_sorted():
    c = Cart()
    c.add("RICE-5K")
    c.add("FAN-TBL")
    assert c.weight_g() == 5100 + 3200
    assert [l.product.sku for l in c.lines()] == ["FAN-TBL", "RICE-5K"]


def test_catalog_prices_are_paise():
    assert all(isinstance(p.price, int) and p.price > 0 for p in CATALOG.values())
