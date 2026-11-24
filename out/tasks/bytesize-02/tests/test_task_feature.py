import click
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


def test_every_unit_is_converted():
    _ok('1B', 1, max_bytes=50000000000)
    _ok('2KB', 2000, max_bytes=50000000000)
    _ok('3MB', 3000000, max_bytes=50000000000)
    _ok('4GB', 4000000000, max_bytes=50000000000)
    _bad('5TB', 'larger than the maximum of 50000000000 bytes', max_bytes=50000000000)


def test_bare_number_uses_default_unit():
    _ok('512', 512, max_bytes=50000000000)
    _ok('3', 3, max_bytes=50000000000)


def test_optional_space_between_number_and_unit():
    _ok('2 KB', 2000, max_bytes=50000000000)
    _ok('  7 MB  ', 7000000, max_bytes=50000000000)


def test_unit_case_rule():
    _ok('1kb', 1000, max_bytes=50000000000)
    _ok('1KB', 1000, max_bytes=50000000000)
    _ok('4MB', 4000000, max_bytes=50000000000)


def test_fractional_values():
    _bad('1.5MB', 'fractional sizes are not allowed', max_bytes=50000000000)
    _bad('0.25KB', 'fractional sizes are not allowed', max_bytes=50000000000)
    _bad('1.7B', 'fractional sizes are not allowed', max_bytes=50000000000)


def test_invalid_values_are_rejected():
    _bad('abc', 'is not a valid size', max_bytes=50000000000)
    _bad('-1B', 'is not a valid size', max_bytes=50000000000)
    _bad('1 2B', 'is not a valid size', max_bytes=50000000000)
    _bad('1XB', 'is not a valid size', max_bytes=50000000000)
    _bad('1.B', 'is not a valid size', max_bytes=50000000000)


def test_units_of_the_other_system_are_rejected():
    _bad('1KiB', 'is not a valid size', max_bytes=50000000000)
    _bad('2GiB', 'is not a valid size', max_bytes=50000000000)


def test_maximum_is_inclusive():
    _ok('50000000000B', 50000000000, max_bytes=50000000000)
    _bad('50000000001B', 'larger than the maximum of 50000000000 bytes', max_bytes=50000000000)


def test_python_values_and_api():
    assert isinstance(click.ByteSize(), click.ParamType)
    assert click.ByteSize(max_bytes=50000000000).convert(4096, None, None) == 4096
    assert click.ByteSize().name == 'size'
    assert click.ByteSize(max_bytes=7).to_info_dict()['max_bytes'] == 7
