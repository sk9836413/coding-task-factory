import click
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


def test_names_and_aliases_invoke_the_command():
    _ok('list', 'list')
    _ok('ls', 'list')
    _ok('l', 'list')
    _ok('rm', 'remove')
    _ok('show', 'show')


def test_unknown_names_are_rejected():
    _bad('x', 'No such command')
    _bad('lis-t', 'No such command')
    _bad('rmv', 'No such command')


def test_case_rule():
    _ok('LS', 'list')
    _ok('List', 'list')
    _ok('SHOW', 'show')


def test_unique_prefixes():
    _ok('re', 'remove')
    _ok('sh', 'show')
    _ok('lin', 'lint')


def test_ambiguous_prefix():
    _bad('li', 'Too many matches: lint, list')


def test_prefix_with_case():
    _ok('Sh', 'show')
    _ok('RE', 'remove')


def test_help_lists_commands():
    result = CliRunner().invoke(_cli(), ['--help'])
    assert result.exit_code == 0
    assert '(ls, l)' not in result.output
    assert 'remove' in result.output and 'lint' in result.output


def test_aliases_api():
    assert click.Command('x').aliases == []
    cmd = click.Command('x', aliases=('a', 'b'))
    assert cmd.aliases == ['a', 'b']
    assert 'aliases' not in cmd.to_info_dict(click.Context(cmd))
