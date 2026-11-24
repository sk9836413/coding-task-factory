"""Family: a new `click.Duration` parameter type ("1h30m" -> seconds or timedelta) with varying rules."""
from __future__ import annotations

import random
import re

from ..common import Emitter, Mutant, TaskPackage, insert_after, insert_before
from ..repo import Repo

NAME = "duration"
ALL_UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def units(p: dict) -> dict[str, int]:
    return {u: v for u, v in ALL_UNITS.items() if u != "d" or p["days"]}


def sample(repo: Repo, rng: random.Random) -> dict:
    return {
        "days": rng.random() < 0.5,
        "compound": rng.random() < 0.6,
        "bare_unit": rng.choice(["s", "m"]),
        "output": rng.choice(["seconds", "timedelta"]),
        "positive_only": rng.random() < 0.5,
        "max_seconds": rng.choice([None, 3600, 12 * 3600, 7 * 86400]),
    }


def signature(p: dict) -> tuple:
    return tuple(sorted(p.items()))


# ---------------------------------------------------------------- oracle
def oracle(p: dict, text: str):
    """("ok", seconds) or ("bad", fragment)."""
    s = text.strip()
    table = units(p)
    if s.isdigit():
        seconds = int(s) * table[p["bare_unit"]]
    else:
        parts = re.findall(r"(\d+)([a-z]+)", s)
        if not parts or "".join(n + u for n, u in parts) != s:
            return ("bad", "is not a valid duration")
        if len(parts) > 1 and not p["compound"]:
            return ("bad", "is not a valid duration")
        order = list(table)
        last, seconds = -1, 0
        for n, u in parts:
            if u not in table or order.index(u) <= last:
                return ("bad", "is not a valid duration")
            last = order.index(u)
            seconds += int(n) * table[u]
    if p["positive_only"] and seconds <= 0:
        return ("bad", "must be greater than zero")
    if p["max_seconds"] is not None and seconds > p["max_seconds"]:
        return ("bad", f"longer than the maximum of {p['max_seconds']} seconds")
    return ("ok", seconds)


# ---------------------------------------------------------------- reference implementation (+ bug variants)
def _type_source(p: dict, bugs: frozenset) -> str:
    table = dict(units(p))
    if "days_rule_flipped" in bugs:
        table = dict(ALL_UNITS) if not p["days"] else {u: v for u, v in ALL_UNITS.items() if u != "d"}
    if "minutes_as_seconds" in bugs:
        table["m"] = 1
    bare = p["bare_unit"]
    if "bare_unit_wrong" in bugs:
        bare = "m" if bare == "s" else "s"
    compound = p["compound"] != ("compound_rule_flipped" in bugs)
    positive = p["positive_only"] != ("zero_rule_flipped" in bugs)
    timedelta_out = (p["output"] == "timedelta") != ("wrong_output_type" in bugs)
    op = ">=" if "max_inclusive_wrong" in bugs else ">"
    order_check = "" if "order_not_checked" in bugs else (
        "                    if index <= last:\n"
        "                        self.fail(invalid, param, ctx)\n\n")
    rows = "\n".join(f'        "{k}": {v},' for k, v in table.items())
    ret_type = "timedelta" if timedelta_out else "int"
    ret = "timedelta(seconds=seconds)" if timedelta_out else "seconds"
    compound_check = "" if compound else (
        "                if len(parts) > 1:\n"
        "                    self.fail(invalid, param, ctx)\n\n")
    positive_check = ("" if not positive else
                      "        if seconds <= 0:\n"
                      "            self.fail(\n"
                      '                _("{value!r} must be greater than zero.").format(value=value), param, ctx\n'
                      "            )\n\n")
    return f'''class Duration(ParamType[{ret_type}]):
    """Converts a duration such as ``90s``, ``15m`` or ``1h30m`` into
    {"a :class:`datetime.timedelta`" if timedelta_out else "a number of seconds"}.

    :param max_seconds: Reject durations longer than this many seconds.
    """

    name = "duration"
    _units = {{
{rows}
    }}

    def __init__(self, max_seconds: int | None = None) -> None:
        self.max_seconds = max_seconds

    def to_info_dict(self) -> dict[str, t.Any]:
        info_dict = super().to_info_dict()
        info_dict["max_seconds"] = self.max_seconds
        return info_dict

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> {ret_type}:
        if isinstance(value, timedelta):
            seconds = int(value.total_seconds())
        elif isinstance(value, int) and not isinstance(value, bool):
            seconds = value
        else:
            text = str(value).strip()
            invalid = _("{{value!r}} is not a valid duration.").format(value=value)

            if text.isdigit():
                seconds = int(text) * self._units["{bare}"]
            else:
                parts = re.findall(r"(\\d+)([a-z]+)", text)

                if not parts or "".join(n + u for n, u in parts) != text:
                    self.fail(invalid, param, ctx)

{compound_check}                order = list(self._units)
                last = -1
                seconds = 0

                for number, unit in parts:
                    if unit not in self._units:
                        self.fail(invalid, param, ctx)

                    index = order.index(unit)

{order_check}                    last = index
                    seconds += int(number) * self._units[unit]

{positive_check}        if self.max_seconds is not None and seconds {op} self.max_seconds:
            self.fail(
                _("{{value!r}} is longer than the maximum of {{max}} seconds.").format(
                    value=value, max=self.max_seconds
                ),
                param,
                ctx,
            )

        return {ret}

    def __repr__(self) -> str:
        return "Duration"


'''


def _files(repo: Repo, p: dict, bugs: frozenset = frozenset()) -> dict[str, str]:
    types = repo.read("src/click/types.py")
    types = insert_after(types, "import os\n", "import re\n", "import re")
    types = insert_after(types, "from datetime import datetime\n", "from datetime import timedelta\n", "timedelta")
    types = insert_before(types, "class FileInfoDict(ParamTypeInfoDict):", _type_source(p, bugs), "Duration class")
    init = repo.read("src/click/__init__.py")
    init = insert_after(init, "from .types import DateTime as DateTime\n", "from .types import Duration as Duration\n",
                        "export")
    return {"src/click/types.py": types, "src/click/__init__.py": init}


HEADER = '''import datetime

import click
from click.testing import CliRunner


def _run(value, **type_kwargs):
    @click.command()
    @click.option("--every", type=click.Duration(**type_kwargs), required=True)
    def cli(every):
        click.echo(f"value={every!r}")

    return CliRunner().invoke(cli, ["--every", value])


def _ok(value, expected, **type_kwargs):
    result = _run(value, **type_kwargs)
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"value={expected!r}"


def _bad(value, fragment, **type_kwargs):
    result = _run(value, **type_kwargs)
    assert result.exit_code == 2, result.output
    assert fragment in result.output, result.output
'''


def build(repo: Repo, p: dict) -> TaskPackage:
    kw = f"max_seconds={p['max_seconds']}" if p["max_seconds"] else ""
    em = Emitter(HEADER)
    td = p["output"] == "timedelta"

    def lit(seconds: int) -> str:
        return f"datetime.timedelta(seconds={seconds})" if td else str(seconds)

    def case(name: str, texts: list[str]) -> None:
        lines = []
        for text in texts:
            kind, val = oracle(p, text)
            extra = f", {kw}" if kw else ""
            lines.append(f"_ok({text!r}, {lit(val)}{extra})" if kind == "ok" else f"_bad({text!r}, {val!r}{extra})")
        em.test(name, lines)

    case("single_units", ["45s", "20m", "2h"])
    case("bare_number_uses_default_unit", ["90", "5"])
    case("days_unit", ["1d", "2d"])
    case("compound_values", ["1h30m", "2m5s", "1d2h"])
    case("units_must_go_from_largest_to_smallest", ["30m1h", "1h1h", "5s2m"])
    case("zero_duration", ["0s", "0"])
    case("invalid_values_are_rejected", ["abc", "1H", "1.5h", "-5s", "1 h", "h1", "1w"])
    if p["max_seconds"]:
        mx = p["max_seconds"]
        case("maximum_is_inclusive", [f"{mx}s", f"{mx + 1}s"])
    em.test("python_values_and_api", [
        "assert isinstance(click.Duration(), click.ParamType)",
        f"assert click.Duration({kw}).convert(30, None, None) == {lit(30)}",
        f"assert click.Duration({kw}).convert(datetime.timedelta(minutes=2), None, None) == {lit(120)}",
        "assert click.Duration().name == 'duration'",
        "assert click.Duration(max_seconds=9).to_info_dict()['max_seconds'] == 9",
    ])

    mutants = ["minutes_as_seconds", "bare_unit_wrong", "compound_rule_flipped", "days_rule_flipped",
               "zero_rule_flipped", "wrong_output_type"]
    if p["compound"]:
        mutants.append("order_not_checked")
    if p["max_seconds"]:
        mutants.append("max_inclusive_wrong")
    muts = [Mutant(b, BUGS[b], _files(repo, p, frozenset([b]))) for b in mutants]
    return TaskPackage(family=NAME, params=p, signature=signature(p), title="Add a Duration parameter type",
                       instruction=_instruction(p), solution=_files(repo, p), feature_tests=em.source(),
                       mutants=muts, difficulty="hard" if p["compound"] else "medium",
                       tags=["param-type", p["output"]] + (["compound"] if p["compound"] else []))


BUGS = {
    "minutes_as_seconds": "The m unit is counted as seconds",
    "bare_unit_wrong": "A bare number uses the wrong unit",
    "compound_rule_flipped": "Compound values (1h30m) accepted/rejected against the requirement",
    "days_rule_flipped": "The d unit accepted/rejected against the requirement",
    "zero_rule_flipped": "Zero durations accepted/rejected against the requirement",
    "wrong_output_type": "Returns seconds instead of timedelta, or the other way round",
    "order_not_checked": "Units out of order or repeated (30m1h, 1h1h) are accepted",
    "max_inclusive_wrong": "A duration equal to the maximum is rejected",
}


def _instruction(p: dict) -> str:
    table = units(p)
    unit_list = ", ".join(f"`{u}` = {v:,} s" for u, v in table.items())
    out = "a `datetime.timedelta`" if p["output"] == "timedelta" else "an `int` number of seconds"
    rules = [
        f"Units (lowercase only): {unit_list}. Any other unit, uppercase units, decimals, negative numbers and "
        "spaces inside the value are invalid.",
        f"A number without a unit is in `{p['bare_unit']}`.",
        ("Compound values are allowed (`1h30m`, `2m5s`). Units must appear from largest to smallest and each "
         "unit at most once, so `30m1h` and `1h1h` are invalid."
         if p["compound"] else "Only a single number with one unit is allowed; `1h30m` is invalid."),
        ("The duration must be greater than zero: `0s` fails with a message containing `must be greater than zero`."
         if p["positive_only"] else "A zero duration (`0s`) is allowed."),
        "`max_seconds` (optional, default `None`): a longer duration fails with a message containing "
        "`longer than the maximum of <max_seconds> seconds`. A duration equal to it is allowed.",
        "Python values are accepted too: an `int` is a number of seconds and a `datetime.timedelta` is used as is; "
        "both go through the same zero and maximum checks.",
        "Any other invalid value fails with a message containing `is not a valid duration`.",
    ]
    body = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    return f"""# Add a `Duration` parameter type to Click

Many command-line tools take time intervals such as `--timeout 90s` or `--every 1h30m`. Add a new parameter
type, `click.Duration`, that converts such a value into {out}.

## Interface
- `click.Duration(max_seconds: int | None = None)` in `src/click/types.py`, a subclass of `click.ParamType`,
  exported from the `click` package.
- `name` is `"duration"`. `to_info_dict()` includes `"max_seconds"`.
- `convert()` returns {out}. Invalid values fail through `self.fail(...)`, so a command line reports a usage
  error (exit code 2) like other Click types.

## Rules
{body}

All existing tests must keep passing.
"""
