"""Read-only view of the target repository: version, files, and its product catalog."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".venv"}


@dataclass(frozen=True)
class Item:
    sku: str
    price: int
    category: str
    weight_g: int


class Repo:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        if not (self.path / "shopcart" / "cart.py").exists():
            raise SystemExit(f"{self.path} does not look like the shopcart repo (shopcart/cart.py missing)")
        self._catalog: list[Item] | None = None

    def files(self) -> list[str]:
        out = []
        for p in sorted(self.path.rglob("*")):
            if p.is_file() and not (set(p.relative_to(self.path).parts) & SKIP_DIRS):
                out.append(p.relative_to(self.path).as_posix())
        return out

    def read(self, rel: str) -> str:
        return (self.path / rel).read_text(encoding="utf-8")

    def version(self) -> str:
        """Git commit if the repo is a git checkout, otherwise a content hash of all files."""
        if (self.path / ".git").exists():
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.path, capture_output=True, text=True)
            if sha.returncode == 0:
                return "git:" + sha.stdout.strip()
        h = hashlib.sha256()
        for rel in self.files():
            h.update(rel.encode())
            h.update((self.path / rel).read_bytes().replace(b"\r\n", b"\n"))
        return "sha256:" + h.hexdigest()[:16]

    def catalog(self) -> list[Item]:
        """Load the catalog by importing the repo in a separate process (keeps this process clean)."""
        if self._catalog is None:
            code = ("import json; from shopcart.catalog import CATALOG; "
                    "print(json.dumps([[p.sku, p.price, p.category, p.weight_g] for p in CATALOG.values()]))")
            r = subprocess.run([sys.executable, "-c", code], cwd=self.path, capture_output=True, text=True, check=True)
            self._catalog = [Item(*row) for row in json.loads(r.stdout)]
        return self._catalog

    def categories(self) -> list[str]:
        return sorted({i.category for i in self.catalog()})

    def baskets(self, max_qty: int = 3) -> list[dict[str, int]]:
        """Small baskets (1 or 2 distinct SKUs, quantity 1..max_qty) used to build test scenarios."""
        skus = [i.sku for i in self.catalog()]
        out = [{s: q} for s in skus for q in range(1, max_qty + 1)]
        for a, b in combinations(skus, 2):
            for qa, qb in product(range(1, max_qty + 1), repeat=2):
                out.append({a: qa, b: qb})
        return out

    def item(self, sku: str) -> Item:
        return next(i for i in self.catalog() if i.sku == sku)
