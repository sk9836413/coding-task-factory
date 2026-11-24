"""Shared pieces: the task package model, source-editing helpers and the test-file emitter."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mutant:
    name: str
    description: str
    files: dict[str, str]  # repo-relative path -> full file content (a deliberately wrong implementation)


@dataclass
class TaskPackage:
    family: str
    params: dict
    signature: tuple
    title: str
    instruction: str
    solution: dict[str, str]  # repo-relative path -> full new file content (reference implementation)
    feature_tests: str  # pytest module placed at tests/test_task_feature.py during verification
    mutants: list[Mutant] = field(default_factory=list)
    skipped_mutants: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    tags: list[str] = field(default_factory=list)
    task_id: str = ""


def replace_once(src: str, old: str, new: str, what: str) -> str:
    n = src.count(old)
    if n != 1:
        raise ValueError(f"Cannot apply edit '{what}': anchor found {n} times")
    return src.replace(old, new)


def insert_after(src: str, anchor: str, text: str, what: str) -> str:
    return replace_once(src, anchor, anchor + text, what)


def insert_before(src: str, anchor: str, text: str, what: str) -> str:
    return replace_once(src, anchor, text + anchor, what)


class Emitter:
    """Builds a pytest module. Families append test functions whose expected values come from their oracle."""

    def __init__(self, header: str):
        self.parts = [header.rstrip() + "\n"]
        self.names: list[str] = []

    def test(self, name: str, lines: list[str]) -> None:
        base, i = name, 2
        while name in self.names:
            name, i = f"{base}_{i}", i + 1
        self.names.append(name)
        body = "\n".join("    " + l for l in lines) or "    pass"
        self.parts.append(f"\n\ndef test_{name}():\n{body}\n")

    def source(self) -> str:
        return "".join(self.parts)

    def node_ids(self, path: str = "tests/test_task_feature.py") -> list[str]:
        return [f"{path}::test_{n}" for n in self.names]
