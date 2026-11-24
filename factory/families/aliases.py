"""Family: command aliases for click groups, with prefix matching, case rules and help display that vary."""
from __future__ import annotations

import random

from ..common import Emitter, Mutant, TaskPackage, insert_after, insert_before, replace_once
from ..repo import Repo

NAME = "aliases"
# The test CLI used by every task in this family: name -> aliases.
COMMANDS = {"list": ["ls", "l"], "lint": [], "remove": ["rm"], "show": []}


def sample(repo: Repo, rng: random.Random) -> dict:
    return {"prefix_matching": rng.random() < 0.5, "case_insensitive": rng.random() < 0.5,
            "show_in_help": rng.random() < 0.5}


def signature(p: dict) -> tuple:
    return tuple(sorted(p.items()))


# ---------------------------------------------------------------- oracle
def oracle(p: dict, token: str):
    """("ok", canonical command name) or ("bad", fragment)."""
    norm = (lambda s: s.lower()) if p["case_insensitive"] else (lambda s: s)
    if token in COMMANDS:
        return ("ok", token)
    for name, aliases in COMMANDS.items():
        if any(norm(n) == norm(token) for n in [name, *aliases]):
            return ("ok", name)
    if p["prefix_matching"]:
        matches = sorted(n for n in COMMANDS if norm(n).startswith(norm(token)))
        if len(matches) == 1:
            return ("ok", matches[0])
        if len(matches) > 1:
            return ("bad", f"Too many matches: {', '.join(matches)}")
    return ("bad", "No such command")


# ---------------------------------------------------------------- reference implementation (+ bug variants)
def _files(repo: Repo, p: dict, bugs: frozenset = frozenset()) -> dict[str, str]:
    core = repo.read("src/click/core.py")
    ci = p["case_insensitive"] != ("case_rule_flipped" in bugs)
    prefix = p["prefix_matching"] != ("prefix_rule_flipped" in bugs)
    show = p["show_in_help"] != ("help_rule_flipped" in bugs)

    core = replace_once(core, '''        hidden: bool = False,
        deprecated: bool | str = False,
    ) -> None:
        #: the name the command thinks it has.''', '''        hidden: bool = False,
        deprecated: bool | str = False,
        aliases: cabc.Sequence[str] | None = None,
    ) -> None:
        #: the name the command thinks it has.''', "Command signature")
    core = replace_once(core, '''        self.hidden = hidden
        self.deprecated = deprecated

    def to_info_dict(self, ctx: Context) -> dict[str, t.Any]:''', '''        self.hidden = hidden
        self.deprecated = deprecated
        #: Other names the command can be invoked by within a group.
        self.aliases: list[str] = list(aliases or [])

    def to_info_dict(self, ctx: Context) -> dict[str, t.Any]:''', "Command attribute")

    norm = "name.lower()" if ci else "name"
    lookup = [
        "    def get_command(self, ctx: Context, cmd_name: str) -> Command | None:",
        '        """Given a context and a command name, this returns a :class:`Command`',
        "        object if it exists or returns ``None``. Aliases are also checked.",
        '        """',
        "        cmd = self.commands.get(cmd_name)",
        "",
        "        if cmd is not None:",
        "            return cmd",
        "",
        f"        def norm(name: str) -> str:",
        f"            return {norm}",
        "",
        "        wanted = norm(cmd_name)",
        "",
    ]
    if "alias_not_resolved" in bugs:
        lookup += ["        for command in self.commands.values():",
                   "            if norm(command.name or \"\") == wanted:",
                   "                return command", ""]
    else:
        lookup += ["        for command in self.commands.values():",
                   "            names = [command.name or \"\", *getattr(command, \"aliases\", [])]",
                   "",
                   "            if any(norm(name) == wanted for name in names):",
                   "                return command", ""]
    if prefix:
        lookup += ["        matches = sorted(",
                   "            name for name in self.commands if norm(name).startswith(wanted)",
                   "        )", ""]
        if "ambiguous_prefix_picks_first" in bugs:
            lookup += ["        if matches:", "            return self.commands[matches[0]]", ""]
        else:
            lookup += ["        if len(matches) == 1:", "            return self.commands[matches[0]]", "",
                       "        if len(matches) > 1:",
                       "            raise UsageError(",
                       '                _("Too many matches: {names}").format(names=", ".join(matches)), ctx',
                       "            )", ""]
    lookup += ["        return None", ""]
    core = replace_once(core, '''    def get_command(self, ctx: Context, cmd_name: str) -> Command | None:
        """Given a context and a command name, this returns a :class:`Command`
        object if it exists or returns ``None``.
        """
        return self.commands.get(cmd_name)
''', "\n".join(lookup), "Group.get_command")

    if "alias_name_kept" not in bugs:
        core = insert_before(core, "        # If we don't find the command we want to show an error message\n", '''        # Report the registered name even when an alias or prefix was used.
        if cmd is not None:
            cmd_name = next(
                (key for key, value in self.commands.items() if value is cmd),
                cmd.name or cmd_name,
            )

''', "canonical name")
    if show:
        core = replace_once(core, "                rows.append((subcommand, help))\n", '''                if getattr(cmd, "aliases", None):
                    subcommand = f"{subcommand} ({', '.join(cmd.aliases)})"

                rows.append((subcommand, help))
''', "help rows")
    return {"src/click/core.py": core}


HEADER = '''import click
from click.testing import CliRunner


def _cli():
    @click.group()
    @click.pass_context
    def cli(ctx):
        click.echo(f"group sees {ctx.invoked_subcommand}")

    @cli.command("list", aliases=["ls", "l"], help="List items.")
    def list_items():
        click.echo("ran list")

    @cli.command("lint", help="Lint files.")
    def lint():
        click.echo("ran lint")

    @cli.command("remove", aliases=["rm"], help="Remove an item.")
    def remove():
        click.echo("ran remove")

    @cli.command("show", help="Show an item.")
    def show():
        click.echo("ran show")

    return cli


def _ok(token, canonical):
    result = CliRunner().invoke(_cli(), [token])
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [f"group sees {canonical}", f"ran {canonical}"]


def _bad(token, fragment):
    result = CliRunner().invoke(_cli(), [token])
    assert result.exit_code == 2, result.output
    assert fragment in result.output, result.output
'''


def build(repo: Repo, p: dict) -> TaskPackage:
    em = Emitter(HEADER)

    def case(name: str, tokens: list[str]) -> None:
        em.test(name, [f"_ok({tok!r}, {val!r})" if kind == "ok" else f"_bad({tok!r}, {val!r})"
                       for tok in tokens for kind, val in [oracle(p, tok)]])

    case("names_and_aliases_invoke_the_command", ["list", "ls", "l", "rm", "show"])
    case("unknown_names_are_rejected", ["x", "lis-t", "rmv"])
    case("case_rule", ["LS", "List", "SHOW"])
    case("unique_prefixes", ["re", "sh", "lin"])
    case("ambiguous_prefix", ["li"])
    case("prefix_with_case", ["Sh", "RE"])
    help_line = "list (ls, l)" if p["show_in_help"] else "(ls, l)"
    check = "in" if p["show_in_help"] else "not in"
    em.test("help_lists_commands", [
        "result = CliRunner().invoke(_cli(), ['--help'])",
        "assert result.exit_code == 0",
        f"assert {help_line!r} {check} result.output",
        "assert 'remove' in result.output and 'lint' in result.output",
    ])
    em.test("aliases_api", [
        "assert click.Command('x').aliases == []",
        "cmd = click.Command('x', aliases=('a', 'b'))",
        "assert cmd.aliases == ['a', 'b']",
        "assert 'aliases' not in cmd.to_info_dict(click.Context(cmd))",
    ])

    mutants = ["alias_not_resolved", "alias_name_kept", "case_rule_flipped", "prefix_rule_flipped",
               "help_rule_flipped"]
    if p["prefix_matching"]:
        mutants.append("ambiguous_prefix_picks_first")
    muts = [Mutant(b, BUGS[b], _files(repo, p, frozenset([b]))) for b in mutants]
    return TaskPackage(family=NAME, params=p, signature=signature(p), title="Add command aliases to Click groups",
                       instruction=_instruction(p), solution=_files(repo, p), feature_tests=em.source(),
                       mutants=muts, difficulty="hard" if p["prefix_matching"] else "medium",
                       tags=["group", "command-resolution"] + (["prefix-matching"] if p["prefix_matching"] else []))


BUGS = {
    "alias_not_resolved": "Aliases are stored but never used to find a command",
    "alias_name_kept": "The alias, not the registered name, is reported as the invoked subcommand",
    "case_rule_flipped": "Name matching is case-(in)sensitive against the requirement",
    "prefix_rule_flipped": "Prefix matching enabled/disabled against the requirement",
    "help_rule_flipped": "Aliases shown/hidden in help against the requirement",
    "ambiguous_prefix_picks_first": "An ambiguous prefix picks the first match instead of failing",
}


def _instruction(p: dict) -> str:
    rules = [
        "`click.Command` (and so `click.Group` and every command created with `@group.command(...)`) accepts a new "
        "keyword argument `aliases`, a sequence of strings, stored as a list on `command.aliases` (`[]` when not "
        "given). The output of `to_info_dict()` must not change.",
        "`Group.get_command(ctx, name)` finds a command by its registered name first, then by any command's "
        "aliases. Invoking `cli ls` runs the command registered as `list` when it has the alias `ls`.",
        "When a command is found through an alias (or a prefix), the group reports the registered name: "
        "`ctx.invoked_subcommand` is `list`, not `ls`.",
        ("Matching of names and aliases is case-insensitive (`LS`, `List`)." if p["case_insensitive"] else
         "Matching of names and aliases is case-sensitive: `LS` is not `ls`."),
    ]
    if p["prefix_matching"]:
        rules.append("If nothing matches exactly, a unique prefix of a registered command name selects that command "
                     "(`re` -> `remove`). Prefixes are not matched against aliases. If the prefix matches more than "
                     "one name, fail with a usage error whose message contains `Too many matches: ` followed by the "
                     "matching names, sorted and separated by `, ` (for example `Too many matches: lint, list`).")
    else:
        rules.append("There is no prefix matching: `re` does not select `remove`.")
    rules.append("Unknown names keep Click's existing `No such command` error (exit code 2).")
    rules.append("In the group's `--help` output, a command with aliases is listed as `list (ls, l)`, keeping the "
                 "alias order." if p["show_in_help"] else
                 "Aliases are not shown in `--help`; commands are listed by their registered names only.")
    body = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    return f"""# Add command aliases to Click groups

Users of large CLIs want short names: `tool ls` for `tool list`, `tool rm` for `tool remove`. Add alias
support to Click commands and groups in `src/click/core.py`.

## Rules
{body}

## Example
```python
@click.group()
def cli(): ...

@cli.command("list", aliases=["ls", "l"])
def list_items(): ...
```

All existing tests must keep passing.
"""
