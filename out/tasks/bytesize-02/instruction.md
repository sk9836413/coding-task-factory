# Add a `ByteSize` parameter type to Click

Command-line tools often take sizes such as cache limits or upload limits. Add a new parameter type,
`click.ByteSize`, that converts a human-readable size into an integer number of bytes.

## Interface
- `click.ByteSize(max_bytes: int | None = None)` in `src/click/types.py`, a subclass of `click.ParamType`,
  exported from the `click` package.
- `name` is `"size"`. `to_info_dict()` includes `"max_bytes"`.
- `convert()` returns an `int`. Invalid values fail through `self.fail(...)`, so a command line reports a
  usage error (exit code 2) like other Click types.

## Rules
1. Accept decimal (SI) units only: `B` = 1, `KB` = 1,000, `MB` = 1,000,000, `GB` = 1,000,000,000, `TB` = 1,000,000,000,000 bytes. Any other unit is invalid.
2. Unit names are case-insensitive (`kb`, `KB` and `Kb` mean the same unit).
3. A number without a unit is in `B`.
4. The value may have surrounding whitespace and at most one space between the number and the unit (`2 KB`). Negative numbers are invalid.
5. Fractional numbers are not allowed: fail with a message containing `fractional sizes are not allowed`.
6. Python `int` values (for example an option default) are returned unchanged, but are still checked against `max_bytes`.
7. `max_bytes` (optional, default `None`): a size larger than `max_bytes` fails with a message containing `larger than the maximum of <max_bytes> bytes`. A size equal to it is allowed.
8. Any other invalid value fails with a message containing `is not a valid size`.

## Example
```python
@click.command()
@click.option("--cache", type=click.ByteSize(max_bytes=...))
def cli(cache): ...
```

All existing tests must keep passing.
