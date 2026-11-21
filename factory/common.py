"""Shared pieces: the task package model, source-editing helpers and the test-script emitter."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mutant:
    name: str
    description: str
    files: dict[str, str]  # path -> full file content


@dataclass
class TaskPackage:
    family: str
    params: dict
    signature: tuple
    title: str
    instruction: str
    solution: dict[str, str]  # path -> full new file content (reference implementation)
    feature_tests: str
    mutants: list[Mutant] = field(default_factory=list)
    skipped_mutants: list[str] = field(default_factory=list)  # bugs no scenario could expose
    # Existing tests the feature intentionally changes: {test file: [(old, new), ...]}. The verifier uses the
    # updated copy and the instruction tells the agent to update the test too.
    regression_edits: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    difficulty: str = "medium"
    tags: list[str] = field(default_factory=list)
    task_id: str = ""


def replace_once(src: str, old: str, new: str, what: str) -> str:
    n = src.count(old)
    if n != 1:
        raise ValueError(f"Cannot apply edit '{what}': anchor found {n} times")
    return src.replace(old, new)


def insert_before(src: str, anchor: str, text: str, what: str) -> str:
    return replace_once(src, anchor, text + anchor, what)


ADJ_ANCHOR = "    def adjustments(self) -> list[Adjustment]:\n        return []\n"
INIT_ANCHOR = "        self._qty: dict[str, int] = {}\n"
IMPORT_ANCHOR = "from .catalog import CATALOG, Product\n"


def rupees(paise: int) -> str:
    return f"₹{paise // 100:,}" + (f".{paise % 100:02d}" if paise % 100 else "")


class Emitter:
    """Builds a pytest file. Families append test functions with lines computed by their oracle."""

    def __init__(self, header: str):
        self.parts = [header.rstrip() + "\n"]
        self.names: set[str] = set()

    def test(self, name: str, lines: list[str]) -> None:
        base, i = name, 2
        while name in self.names:
            name, i = f"{base}_{i}", i + 1
        self.names.add(name)
        body = "\n".join("    " + l for l in lines) or "    pass"
        self.parts.append(f"\n\ndef test_{name}():\n{body}\n")

    def source(self) -> str:
        return "".join(self.parts)


def basket_lines(var: str, basket: dict[str, int]) -> list[str]:
    return [f"{var}.add({sku!r}, {q})" for sku, q in basket.items()]
