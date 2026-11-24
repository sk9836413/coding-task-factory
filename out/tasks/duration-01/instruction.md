# Add a `Duration` parameter type to Click

Many command-line tools take time intervals such as `--timeout 90s` or `--every 1h30m`. Add a new parameter
type, `click.Duration`, that converts such a value into a `datetime.timedelta`.

## Interface
- `click.Duration(max_seconds: int | None = None)` in `src/click/types.py`, a subclass of `click.ParamType`,
  exported from the `click` package.
- `name` is `"duration"`. `to_info_dict()` includes `"max_seconds"`.
- `convert()` returns a `datetime.timedelta`. Invalid values fail through `self.fail(...)`, so a command line reports a usage
  error (exit code 2) like other Click types.

## Rules
1. Units (lowercase only): `h` = 3,600 s, `m` = 60 s, `s` = 1 s. Any other unit, uppercase units, decimals, negative numbers and spaces inside the value are invalid.
2. A number without a unit is in `s`.
3. Compound values are allowed (`1h30m`, `2m5s`). Units must appear from largest to smallest and each unit at most once, so `30m1h` and `1h1h` are invalid.
4. The duration must be greater than zero: `0s` fails with a message containing `must be greater than zero`.
5. `max_seconds` (optional, default `None`): a longer duration fails with a message containing `longer than the maximum of <max_seconds> seconds`. A duration equal to it is allowed.
6. Python values are accepted too: an `int` is a number of seconds and a `datetime.timedelta` is used as is; both go through the same zero and maximum checks.
7. Any other invalid value fails with a message containing `is not a valid duration`.

All existing tests must keep passing.
