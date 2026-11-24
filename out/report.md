# Task factory run

- Repository: `pallets/click` at `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1` (tag `8.5.1`)
- Existing tests passing at the base commit (pass_to_pass): 2356
- Seed 7: 5 tasks generated, **5 valid**, in 472.5 s
- Known-wrong implementations caught by the feature tests: **35/35**
- Same-family task pairs whose reference solutions fail each other's tests: **2/2**

| Task | Title | nop reward | oracle reward | Regression intact (nop) | Stable | Mutants caught | harbor lint | Status |
|---|---|---|---|---|---|---|---|---|
| bytesize-01 | Add a ByteSize parameter type | 0.0 | 1.0 | yes | yes | 8/8 | yes | valid |
| duration-01 | Add a Duration parameter type | 0.0 | 1.0 | yes | yes | 8/8 | yes | valid |
| aliases-01 | Add command aliases to Click groups | 0.0 | 1.0 | yes | yes | 6/6 | yes | valid |
| bytesize-02 | Add a ByteSize parameter type | 0.0 | 1.0 | yes | yes | 6/6 | yes | valid |
| duration-02 | Add a Duration parameter type | 0.0 | 1.0 | yes | yes | 7/7 | yes | valid |

## Rules per task

- **bytesize-01**: system=binary, case_sensitive=False, allow_fraction=True, default_unit=KiB, max_bytes=2147483648
- **duration-01**: days=False, compound=True, bare_unit=s, output=timedelta, positive_only=True, max_seconds=3600
- **aliases-01**: prefix_matching=True, case_insensitive=True, show_in_help=False
- **bytesize-02**: system=decimal, case_sensitive=False, allow_fraction=False, default_unit=B, max_bytes=50000000000
- **duration-02**: days=True, compound=False, bare_unit=s, output=seconds, positive_only=True, max_seconds=3600

## Mutants

- **bytesize-01**: binary_uses_1000 (caught), case_rule_flipped (caught), cross_system_accepted (caught), default_unit_ignored (caught), fraction_rule_flipped (caught), max_inclusive_wrong (caught), rounds_instead_of_floor (caught), space_not_allowed (caught)
- **duration-01**: bare_unit_wrong (caught), compound_rule_flipped (caught), days_rule_flipped (caught), max_inclusive_wrong (caught), minutes_as_seconds (caught), order_not_checked (caught), wrong_output_type (caught), zero_rule_flipped (caught)
- **aliases-01**: alias_name_kept (caught), alias_not_resolved (caught), ambiguous_prefix_picks_first (caught), case_rule_flipped (caught), help_rule_flipped (caught), prefix_rule_flipped (caught)
- **bytesize-02**: case_rule_flipped (caught), cross_system_accepted (caught), decimal_uses_1024 (caught), fraction_rule_flipped (caught), max_inclusive_wrong (caught), space_not_allowed (caught)
- **duration-02**: bare_unit_wrong (caught), compound_rule_flipped (caught), days_rule_flipped (caught), max_inclusive_wrong (caught), minutes_as_seconds (caught), wrong_output_type (caught), zero_rule_flipped (caught)

## Distinctness (same family)

| A | B | A's solution fails B | B's solution fails A |
|---|---|---|---|
| bytesize-01 | bytesize-02 | True | True |
| duration-01 | duration-02 | True | True |
