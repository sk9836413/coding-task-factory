# Add command aliases to Click groups

Users of large CLIs want short names: `tool ls` for `tool list`, `tool rm` for `tool remove`. Add alias
support to Click commands and groups in `src/click/core.py`.

## Rules
1. `click.Command` (and so `click.Group` and every command created with `@group.command(...)`) accepts a new keyword argument `aliases`, a sequence of strings, stored as a list on `command.aliases` (`[]` when not given). The output of `to_info_dict()` must not change.
2. `Group.get_command(ctx, name)` finds a command by its registered name first, then by any command's aliases. Invoking `cli ls` runs the command registered as `list` when it has the alias `ls`.
3. When a command is found through an alias (or a prefix), the group reports the registered name: `ctx.invoked_subcommand` is `list`, not `ls`.
4. Matching of names and aliases is case-insensitive (`LS`, `List`).
5. If nothing matches exactly, a unique prefix of a registered command name selects that command (`re` -> `remove`). Prefixes are not matched against aliases. If the prefix matches more than one name, fail with a usage error whose message contains `Too many matches: ` followed by the matching names, sorted and separated by `, ` (for example `Too many matches: lint, list`).
6. Unknown names keep Click's existing `No such command` error (exit code 2).
7. Aliases are not shown in `--help`; commands are listed by their registered names only.

## Example
```python
@click.group()
def cli(): ...

@cli.command("list", aliases=["ls", "l"])
def list_items(): ...
```

All existing tests must keep passing.
