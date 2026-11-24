import datetime

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


def test_single_units():
    _ok('45s', datetime.timedelta(seconds=45), max_seconds=3600)
    _ok('20m', datetime.timedelta(seconds=1200), max_seconds=3600)
    _bad('2h', 'longer than the maximum of 3600 seconds', max_seconds=3600)


def test_bare_number_uses_default_unit():
    _ok('90', datetime.timedelta(seconds=90), max_seconds=3600)
    _ok('5', datetime.timedelta(seconds=5), max_seconds=3600)


def test_days_unit():
    _bad('1d', 'is not a valid duration', max_seconds=3600)
    _bad('2d', 'is not a valid duration', max_seconds=3600)


def test_compound_values():
    _bad('1h30m', 'longer than the maximum of 3600 seconds', max_seconds=3600)
    _ok('2m5s', datetime.timedelta(seconds=125), max_seconds=3600)
    _bad('1d2h', 'is not a valid duration', max_seconds=3600)


def test_units_must_go_from_largest_to_smallest():
    _bad('30m1h', 'is not a valid duration', max_seconds=3600)
    _bad('1h1h', 'is not a valid duration', max_seconds=3600)
    _bad('5s2m', 'is not a valid duration', max_seconds=3600)


def test_zero_duration():
    _bad('0s', 'must be greater than zero', max_seconds=3600)
    _bad('0', 'must be greater than zero', max_seconds=3600)


def test_invalid_values_are_rejected():
    _bad('abc', 'is not a valid duration', max_seconds=3600)
    _bad('1H', 'is not a valid duration', max_seconds=3600)
    _bad('1.5h', 'is not a valid duration', max_seconds=3600)
    _bad('-5s', 'is not a valid duration', max_seconds=3600)
    _bad('1 h', 'is not a valid duration', max_seconds=3600)
    _bad('h1', 'is not a valid duration', max_seconds=3600)
    _bad('1w', 'is not a valid duration', max_seconds=3600)


def test_maximum_is_inclusive():
    _ok('3600s', datetime.timedelta(seconds=3600), max_seconds=3600)
    _bad('3601s', 'longer than the maximum of 3600 seconds', max_seconds=3600)


def test_python_values_and_api():
    assert isinstance(click.Duration(), click.ParamType)
    assert click.Duration(max_seconds=3600).convert(30, None, None) == datetime.timedelta(seconds=30)
    assert click.Duration(max_seconds=3600).convert(datetime.timedelta(minutes=2), None, None) == datetime.timedelta(seconds=120)
    assert click.Duration().name == 'duration'
    assert click.Duration(max_seconds=9).to_info_dict()['max_seconds'] == 9
