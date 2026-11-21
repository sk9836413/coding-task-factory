from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: int  # paise
    category: str
    weight_g: int


CATALOG: dict[str, Product] = {p.sku: p for p in [
    Product("TEA-250", "Assam Tea 250 g", 24000, "grocery", 260),
    Product("RICE-5K", "Basmati Rice 5 kg", 64900, "grocery", 5100),
    Product("OIL-1L", "Mustard Oil 1 L", 18500, "grocery", 950),
    Product("SHIRT-M", "Cotton Shirt M", 79900, "apparel", 300),
    Product("SOCK-3P", "Socks, pack of 3", 29900, "apparel", 150),
    Product("BULB-9W", "LED Bulb 9 W", 9900, "home", 80),
    Product("FAN-TBL", "Table Fan", 189900, "home", 3200),
    Product("PEN-10", "Gel Pens, pack of 10", 15000, "stationery", 120),
]}
