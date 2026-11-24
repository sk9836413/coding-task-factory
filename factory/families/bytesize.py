"""Family: a new `click.ByteSize` parameter type ("10MiB", "1.5 GB" -> bytes) with varying rules."""
from __future__ import annotations

import random
from fractions import Fraction

from ..common import Emitter, Mutant, TaskPackage, insert_after, insert_before
from ..repo import Repo

NAME = "bytesize"
DEC = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12}
BIN = {"B": 1, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30, "TiB": 2**40}


def units(p: dict) -> dict[str, int]:
    return {"decimal": DEC, "binary": BIN, "both": {**DEC, **BIN}}[p["system"]]


def sample(repo: Repo, rng: random.Random) -> dict:
    system = rng.choice(["decimal", "binary", "both"])
    p = {"system": system, "case_sensitive": rng.random() < 0.5, "allow_fraction": rng.random() < 0.5,
         "default_unit": "B", "max_bytes": None}
    if rng.random() < 0.5:
        p["default_unit"] = {"decimal": "KB", "binary": "KiB", "both": rng.choice(["KB", "KiB"])}[system]
    if rng.random() < 0.6:
        big = "GiB" if system == "binary" else "GB" if system == "decimal" else rng.choice(["GB", "GiB"])
        p["max_bytes"] = rng.choice([2, 10, 50]) * units(p)[big]
    return p


def signature(p: dict) -> tuple:
    return tuple(sorted(p.items()))


# ---------------------------------------------------------------- oracle (independent of the reference code)
def oracle(p: dict, text: str):
    """Returns ("ok", bytes) or ("bad", fragment-of-error-message)."""
    import re
    s = text.strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?) ?([A-Za-z]*)", s)
    if not m:
        return ("bad", "is not a valid size")
    num, unit = m.groups()
    table = units(p)
    if unit == "":
        factor = table[p["default_unit"]]
    else:
        match = [k for k in table if (k == unit if p["case_sensitive"] else k.lower() == unit.lower())]
        if not match:
            return ("bad", "is not a valid size")
        factor = table[match[0]]
    if "." in num and not p["allow_fraction"]:
        return ("bad", "fractional sizes are not allowed")
    size = int(Fraction(num) * factor)  # floor for non-negative values
    if p["max_bytes"] is not None and size > p["max_bytes"]:
        return ("bad", f"larger than the maximum of {p['max_bytes']} bytes")
    return ("ok", size)


# ---------------------------------------------------------------- reference implementation (+ bug variants)
def _type_source(p: dict, bugs: frozenset) -> str:
    table = dict(units(p))
    if "binary_uses_1000" in bugs:
        table = {k: (1000 ** ["B", "KiB", "MiB", "GiB", "TiB"].index(k) if k in BIN and k != "B" else v)
                 for k, v in table.items()}
    if "decimal_uses_1024" in bugs:
        table = {k: (1024 ** ["B", "KB", "MB", "GB", "TB"].index(k) if k in DEC and k != "B" else v)
                 for k, v in table.items()}
    if "cross_system_accepted" in bugs:
        table = {**DEC, **BIN}
    case_sensitive = p["case_sensitive"] != ("case_rule_flipped" in bugs)
    allow_fraction = p["allow_fraction"] != ("fraction_rule_flipped" in bugs)
    pattern = r"(\d+(?:\.\d+)?)([A-Za-z]*)" if "space_not_allowed" in bugs else r"(\d+(?:\.\d+)?) ?([A-Za-z]*)"
    default = "B" if "default_unit_ignored" in bugs else p["default_unit"]
    op = ">=" if "max_inclusive_wrong" in bugs else ">"
    # Exact integer arithmetic (no float, no decimal import: click keeps its import footprint small).
    to_int = ("(2 * whole * factor + scale) // (2 * scale)" if "rounds_instead_of_floor" in bugs
              else "whole * factor // scale")
    rows = "\n".join(f'        "{k}": {v},' for k, v in table.items())
    lookup = ("                factor = self._units.get(unit)" if case_sensitive else
              "                factor = {k.lower(): v for k, v in self._units.items()}.get(unit.lower())")
    frac = ("" if allow_fraction else
            '            if "." in number:\n'
            "                self.fail(\n"
            '                    _("{value!r} is not a valid size: fractional sizes are not allowed.").format(\n'
            "                        value=value\n"
            "                    ),\n"
            "                    param,\n"
            "                    ctx,\n"
            "                )\n\n")
    return f'''class ByteSize(ParamType[int]):
    """Converts a human-readable size such as ``10MiB`` or ``1.5 GB`` into a
    number of bytes.

    :param max_bytes: Reject sizes larger than this many bytes.
    """

    name = "size"
    _units = {{
{rows}
    }}
    _default_unit = "{default}"

    def __init__(self, max_bytes: int | None = None) -> None:
        self.max_bytes = max_bytes

    def to_info_dict(self) -> dict[str, t.Any]:
        info_dict = super().to_info_dict()
        info_dict["max_bytes"] = self.max_bytes
        return info_dict

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> int:
        if isinstance(value, int) and not isinstance(value, bool):
            size = value
        else:
            match = re.fullmatch(r"{pattern}", str(value).strip())

            if match is None:
                self.fail(
                    _("{{value!r}} is not a valid size.").format(value=value), param, ctx
                )

            number, unit = match.groups()

            if not unit:
                factor = self._units[self._default_unit]
            else:
{lookup}

            if factor is None:
                self.fail(
                    _("{{value!r}} is not a valid size.").format(value=value), param, ctx
                )

{frac}            int_part, _dot, frac_part = number.partition(".")
            whole = int(int_part + frac_part)
            scale = 10 ** len(frac_part)
            size = {to_int}

        if self.max_bytes is not None and size {op} self.max_bytes:
            self.fail(
                _("{{value!r}} is larger than the maximum of {{max}} bytes.").format(
                    value=value, max=self.max_bytes
                ),
                param,
                ctx,
            )

        return size

    def __repr__(self) -> str:
        return "ByteSize"


'''


def _files(repo: Repo, p: dict, bugs: frozenset = frozenset()) -> dict[str, str]:
    types = repo.read("src/click/types.py")
    types = insert_after(types, "import os\n", "import re\n", "import re")
    types = insert_before(types, "class FileInfoDict(ParamTypeInfoDict):", _type_source(p, bugs), "ByteSize class")
    init = repo.read("src/click/__init__.py")
    init = insert_after(init, "from .types import BOOL as BOOL\n", "from .types import ByteSize as ByteSize\n", "export")
    return {"src/click/types.py": types, "src/click/__init__.py": init}


# ---------------------------------------------------------------- tests
HEADER = '''import click
from click.testing import CliRunner


def _run(value, **type_kwargs):
    @click.command()
    @click.option("--size", type=click.ByteSize(**type_kwargs), required=True)
    def cli(size):
        click.echo(f"bytes={size!r}")

    return CliRunner().invoke(cli, ["--size", value])


def _ok(value, expected, **type_kwargs):
    result = _run(value, **type_kwargs)
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"bytes={expected!r}"


def _bad(value, fragment, **type_kwargs):
    result = _run(value, **type_kwargs)
    assert result.exit_code == 2, result.output
    assert fragment in result.output, result.output
'''


def build(repo: Repo, p: dict) -> TaskPackage:
    table = units(p)
    kw = f"max_bytes={p['max_bytes']}" if p["max_bytes"] else ""
    em = Emitter(HEADER)

    def case(name: str, texts: list[str]) -> None:
        lines = []
        for text in texts:
            kind, val = oracle(p, text)
            args = f"{text!r}, {val!r}" + (f", {kw}" if kw else "")
            lines.append(f"_ok({args})" if kind == "ok" else f"_bad({args})")
        em.test(name, lines)

    names = list(table)
    big_units = [u for u in names if u != "B"]
    case("every_unit_is_converted", [f"{i + 1}{u}" for i, u in enumerate(names)])
    case("bare_number_uses_default_unit", ["512", "3"])
    case("optional_space_between_number_and_unit", [f"2 {big_units[0]}", f"  7 {big_units[1]}  "])
    case("unit_case_rule", [f"1{big_units[0].lower()}", f"1{big_units[0].upper()}", f"4{big_units[1]}"])
    case("fractional_values", [f"1.5{big_units[1]}", f"0.25{big_units[0]}", "1.7B"])
    case("invalid_values_are_rejected", ["abc", "-1B", "1 2B", "1XB", "1.B"])
    other = [u for u in (BIN if p["system"] == "decimal" else DEC) if u != "B"] if p["system"] != "both" else []
    if other:
        case("units_of_the_other_system_are_rejected", [f"1{other[0]}", f"2{other[2]}"])
    if p["max_bytes"]:
        mx = p["max_bytes"]
        case("maximum_is_inclusive", [f"{mx}B", f"{mx + 1}B"])
    em.test("python_values_and_api", [
        "assert isinstance(click.ByteSize(), click.ParamType)",
        f"assert click.ByteSize({kw}).convert(4096, None, None) == 4096",
        "assert click.ByteSize().name == 'size'",
        "assert click.ByteSize(max_bytes=7).to_info_dict()['max_bytes'] == 7",
    ])

    mutants = ["case_rule_flipped", "fraction_rule_flipped", "space_not_allowed"]
    if p["system"] in ("binary", "both"):
        mutants.append("binary_uses_1000")
    if p["system"] in ("decimal", "both"):
        mutants.append("decimal_uses_1024")
    if p["system"] != "both":
        mutants.append("cross_system_accepted")
    if p["allow_fraction"]:
        mutants.append("rounds_instead_of_floor")
    if p["default_unit"] != "B":
        mutants.append("default_unit_ignored")
    if p["max_bytes"]:
        mutants.append("max_inclusive_wrong")
    muts = [Mutant(b, BUGS[b], _files(repo, p, frozenset([b]))) for b in mutants]
    return TaskPackage(family=NAME, params=p, signature=signature(p), title="Add a ByteSize parameter type",
                       instruction=_instruction(p), solution=_files(repo, p), feature_tests=em.source(),
                       mutants=muts, difficulty="medium",
                       tags=["param-type", p["system"]] + (["max"] if p["max_bytes"] else []))


BUGS = {
    "case_rule_flipped": "Unit case sensitivity is the opposite of the requirement",
    "fraction_rule_flipped": "Fractional numbers accepted/rejected against the requirement",
    "space_not_allowed": "A space between the number and the unit is rejected",
    "binary_uses_1000": "Binary units (KiB, MiB, ...) use powers of 1000",
    "decimal_uses_1024": "Decimal units (KB, MB, ...) use powers of 1024",
    "cross_system_accepted": "Units from the other unit system are accepted",
    "rounds_instead_of_floor": "Fractional byte counts are rounded instead of rounded down",
    "default_unit_ignored": "A bare number is treated as bytes instead of the default unit",
    "max_inclusive_wrong": "A size equal to the maximum is rejected",
}


def _instruction(p: dict) -> str:
    table = units(p)
    unit_list = ", ".join(f"`{u}` = {v:,}" for u, v in table.items())
    system = {"decimal": "decimal (SI) units only", "binary": "binary (IEC) units only",
              "both": "both decimal (SI) and binary (IEC) units"}[p["system"]]
    # Examples use this task's own units, so they never contradict rule 1.
    small, medium = [u for u in table if u != "B"][:2]
    rules = [
        f"Accept {system}: {unit_list} bytes. Any other unit is invalid.",
        (f"Unit names are case-sensitive: only the exact spellings above are valid (`{small.lower()}` is invalid)."
         if p["case_sensitive"] else
         f"Unit names are case-insensitive (`{small.lower()}`, `{small.upper()}` and `{small}` mean the same unit)."),
        f"A number without a unit is in `{p['default_unit']}`.",
        "The value may have surrounding whitespace and at most one space between the number and the unit "
        f"(`2 {small}`). Negative numbers are invalid.",
        (f"Fractional numbers are allowed (`1.5{medium}`); the result is rounded down to a whole number of bytes."
         if p["allow_fraction"] else
         "Fractional numbers are not allowed: fail with a message containing `fractional sizes are not allowed`."),
        "Python `int` values (for example an option default) are returned unchanged, but are still checked "
        "against `max_bytes`.",
        "`max_bytes` (optional, default `None`): a size larger than `max_bytes` fails with a message containing "
        "`larger than the maximum of <max_bytes> bytes`. A size equal to it is allowed.",
        "Any other invalid value fails with a message containing `is not a valid size`.",
    ]
    body = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    return f"""# Add a `ByteSize` parameter type to Click

Command-line tools often take sizes such as cache limits or upload limits. Add a new parameter type,
`click.ByteSize`, that converts a human-readable size into an integer number of bytes.

## Interface
- `click.ByteSize(max_bytes: int | None = None)` in `src/click/types.py`, a subclass of `click.ParamType`,
  exported from the `click` package.
- `name` is `"size"`. `to_info_dict()` includes `"max_bytes"`.
- `convert()` returns an `int`. Invalid values fail through `self.fail(...)`, so a command line reports a
  usage error (exit code 2) like other Click types.

## Rules
{body}

## Example
```python
@click.command()
@click.option("--cache", type=click.ByteSize(max_bytes=...))
def cli(cache): ...
```

All existing tests must keep passing.
"""
