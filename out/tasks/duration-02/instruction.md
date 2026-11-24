# Add a `Duration` parameter type to Click

Many command-line tools take time intervals such as `--timeout 90s` or `--every 1h30m`. Add a new parameter
type, `click.Duration`, that converts such a value into an `int` number of seconds.

## Interface
- `click.Duration(max_seconds: int | None = None)` in `src/click/types.py`, a subclass of `click.ParamType`,
  exported from the `click` package.
- `name` is `"duration"`. `to_info_dict()` includes `"max_seconds"`.
- `convert()` returns an `int` number of seconds. Invalid values fail through `self.fail(...)`, so a command line reports a usage
  error (exit code 2) like other Click types.

## Rules
1. Units (lowercase only): `d` = 86,400 s, `h` = 3,600 s, `m` = 60 s, `s` = 1 s. Any other unit, uppercase units, decimals, negative numbers and spaces inside the value are invalid.
2. A number without a unit is in `s`.
3. Only a single number with one unit is allowed; `1h30m` is invalid.
4. The duration must be greater than zero: `0s` fails with a message containing `must be greater than zero`.
5. `max_seconds` (optional, default `None`): a longer duration fails with a message containing `longer than the maximum of <max_seconds> seconds`. A duration equal to it is allowed.
6. Python values are accepted too: an `int` is a number of seconds and a `datetime.timedelta` is used as is; both go through the same zero and maximum checks.
7. Any other invalid value fails with a message containing `is not a valid duration`.

All existing tests must keep passing.
