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
    _ok('1B', 1, max_bytes=2147483648)
    _ok('2KiB', 2048, max_bytes=2147483648)
    _ok('3MiB', 3145728, max_bytes=2147483648)
    _bad('4GiB', 'larger than the maximum of 2147483648 bytes', max_bytes=2147483648)
    _bad('5TiB', 'larger than the maximum of 2147483648 bytes', max_bytes=2147483648)


def test_bare_number_uses_default_unit():
    _ok('512', 524288, max_bytes=2147483648)
    _ok('3', 3072, max_bytes=2147483648)


def test_optional_space_between_number_and_unit():
    _ok('2 KiB', 2048, max_bytes=2147483648)
    _ok('  7 MiB  ', 7340032, max_bytes=2147483648)


def test_unit_case_rule():
    _ok('1kib', 1024, max_bytes=2147483648)
    _ok('1KIB', 1024, max_bytes=2147483648)
    _ok('4MiB', 4194304, max_bytes=2147483648)


def test_fractional_values():
    _ok('1.5MiB', 1572864, max_bytes=2147483648)
    _ok('0.25KiB', 256, max_bytes=2147483648)
    _ok('1.7B', 1, max_bytes=2147483648)


def test_invalid_values_are_rejected():
    _bad('abc', 'is not a valid size', max_bytes=2147483648)
    _bad('-1B', 'is not a valid size', max_bytes=2147483648)
    _bad('1 2B', 'is not a valid size', max_bytes=2147483648)
    _bad('1XB', 'is not a valid size', max_bytes=2147483648)
    _bad('1.B', 'is not a valid size', max_bytes=2147483648)


def test_units_of_the_other_system_are_rejected():
    _bad('1KB', 'is not a valid size', max_bytes=2147483648)
    _bad('2GB', 'is not a valid size', max_bytes=2147483648)


def test_maximum_is_inclusive():
    _ok('2147483648B', 2147483648, max_bytes=2147483648)
    _bad('2147483649B', 'larger than the maximum of 2147483648 bytes', max_bytes=2147483648)


def test_python_values_and_api():
    assert isinstance(click.ByteSize(), click.ParamType)
    assert click.ByteSize(max_bytes=2147483648).convert(4096, None, None) == 4096
    assert click.ByteSize().name == 'size'
    assert click.ByteSize(max_bytes=7).to_info_dict()['max_bytes'] == 7
