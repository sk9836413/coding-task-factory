# Coding Task Factory (Innodata AI Hackathon, Track 1)

An automated pipeline that reads **pallets/click** at a pinned release commit and produces realistic
**feature-development tasks** for evaluating AI coding systems, packaged for **Harbor 0.25** and validated
before they ship. Team **SKA**.

| | |
|---|---|
| Repository | [pallets/click](https://github.com/pallets/click) (Python, pytest) |
| Base commit | `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1` (tag `8.5.1`); all 2,356 existing tests pass there |
| Harbor | 0.25.x, task schema 1.4, separate verifier container |
| Output | 5 task packages in [`out/tasks`](out/tasks), report in [`out/report.md`](out/report.md) |

## Quick start

```bash
# Linux / macOS            # Windows PowerShell
bash scripts/setup.sh      # .\scripts\setup.ps1
.venv/bin/python -m factory generate --n 5 --seed 7          # .venv\Scripts\python -m factory generate --n 5 --seed 7
.venv/bin/python -m pytest -q tests                          # the factory's own tests
```

With Docker running, every generated task can be checked the official way:

```bash
harbor run -p out/tasks/bytesize-01 -a nop    -k 1 -o jobs --no-delete -y   # expected reward 0.0
harbor run -p out/tasks/bytesize-01 -a oracle -k 1 -o jobs --no-delete -y   # expected reward 1.0
```

## What a task looks like

```
bytesize-01/
  instruction.md              requirements + exact interface; the only file the agent sees
  task.toml                   schema 1.4; [metadata] repository, base_commit (40 chars), base_tag, license
  environment/Dockerfile      python:3.12-slim pinned by digest; clones click and checks out base_commit
  solution/solution.patch     reference implementation as a git patch
  solution/solve.sh           oracle: git apply solution.patch
  tests/test.sh               verifier (see below)
  tests/test_task_feature.py  generated feature tests
  tests/fail_to_pass.json     feature test ids
  tests/pass_to_pass.json     the 2,356 existing test ids that pass at base_commit
  tests/grade.py              reward: 0.0 if any pass_to_pass test fails, else share of fail_to_pass passing
  validation/mutants/*.patch  known-wrong implementations (used only by the local validator)
  factory.json                provenance: family, rules, base commit, validation results
```

**Verifier flow (separate container).** After the agent finishes, a `[[verifier.collect]]` hook saves the
agent's work as `git diff --cached --binary <base_commit>` into `/logs/artifacts/agent.patch`. Harbor
uploads it into a fresh verifier container built from the same Dockerfile. `tests/test.sh` applies the
patch, restores the repository's original `tests/` from `base_commit` (so existing tests cannot be edited
away), adds the feature tests, runs pytest with a small reporting plugin, and `grade.py` writes
`/logs/verifier/reward.txt` using the Track 1 formula.

## How tasks are generated

The pipeline has **three feature families**. Each is a parameterised specification; changing the parameters
changes the behaviour the agent must implement, not just names. Tasks in the same family must differ in at
least two rules, and a cross-check proves it: each task's reference solution is run against its siblings'
tests and must fail them.

| Family | Feature (new in click) | Rules that vary |
|---|---|---|
| `bytesize` | `click.ByteSize` parameter type: `10MiB`, `1.5 GB` -> bytes | decimal / binary / both unit systems, case sensitivity, fractions allowed, default unit, maximum |
| `duration` | `click.Duration` parameter type: `1h30m` -> seconds or `timedelta` | days unit, compound values with ordering rules, bare-number unit, output type, zero allowed, maximum |
| `aliases` | Command aliases for groups: `@cli.command("list", aliases=["ls"])` | prefix matching with ambiguity errors, case sensitivity, aliases shown in `--help` |

For each task the family produces:

1. **Requirements** (`instruction.md`) with the exact interface and every rule.
2. **Reference implementation**, written into click's own files (`src/click/types.py`, `__init__.py`,
   `core.py`) with anchored edits that fail loudly if the code they expect is not there; exported as a git
   patch against `base_commit`.
3. **Feature tests** whose expected values come from an **independent oracle** written separately from the
   reference code, so a bug in the generated code cannot also hide in its tests.
4. **Mutants**: one realistic wrong implementation per rule (for example "KiB uses 1000", "`30m1h` accepted",
   "alias reported instead of the registered name"). A task is accepted only if its tests catch every one.

## Validation

`python -m factory generate` validates every task before accepting it:

| Check | How |
|---|---|
| nop reward 0.0, regression intact | Same agent/collect/verifier flow as Harbor, with no agent change |
| oracle reward 1.0 | `solve.sh` in an agent clone -> collect hook -> `test.sh` in a fresh clone |
| Stable | Feature tests re-run on the oracle patch |
| Mutants caught | Each `validation/mutants/*.patch` must fail at least one feature test |
| Harbor schema and lint | `harbor lint` (Harbor 0.25.0) on every package; `TaskConfig` parsing in the factory's tests |
| Distinct tasks | Cross-check of reference solutions between same-family tasks |

### Results (seed 7, `out/`)

| Task | Feature | nop | oracle | Mutants caught | harbor lint |
|---|---|---|---|---|---|
| bytesize-01 | `ByteSize`: binary units, case-insensitive, fractions, default KiB, max 2 GiB | 0.0 | 1.0 | 8/8 | clean |
| duration-01 | `Duration`: compound values, no days, timedelta output, > 0, max 1 h | 0.0 | 1.0 | 8/8 | clean |
| aliases-01 | Aliases: prefix matching, case-insensitive, hidden in help | 0.0 | 1.0 | 6/6 | clean |
| bytesize-02 | `ByteSize`: decimal units, case-insensitive, no fractions, max 50 GB | 0.0 | 1.0 | 6/6 | clean |
| duration-02 | `Duration`: single unit, days allowed, seconds output, > 0, max 1 h | 0.0 | 1.0 | 7/7 | clean |

- 5 of 5 tasks valid; all 2,356 existing tests stay green under nop and oracle; 35 of 35 known-wrong
  implementations caught; both same-family pairs proven distinct. A full run takes about 8 minutes.
- Full details: [`out/report.md`](out/report.md) and [`out/report.json`](out/report.json).

### Failure cases the validator caught (and how they were fixed)

These were caught automatically by the regression gate while building the pipeline; no task output was
edited by hand.

1. **`ByteSize` broke `tests/test_imports.py::test_light_imports`.** The first reference implementation
   imported `decimal`; click restricts which modules it loads on import. Fixed by using exact integer
   arithmetic for fractional sizes.
2. **Aliases broke 4 tests in `tests/test_info_dict.py`.** The first version added `"aliases"` to
   `Command.to_info_dict()`, whose exact output those tests pin. The requirement now says `to_info_dict()`
   must not change, and a feature test checks it.
3. **`_` shadowing.** A `number.partition(".")` unpacked into `_`, which is click's gettext function, so
   error messages crashed. Caught by the feature tests; renamed.

## Design decisions and assumptions

- **Feature work only.** Every task adds behaviour that does not exist in click 8.5.1 (checked in the
  factory's tests). No bug-fix tasks, and every task starts from the unmodified release commit.
- **Templates + oracle instead of free-form generation.** Model-generated code and tests can share the same
  misunderstanding. Writing expected values from a separate oracle and gating on mutants makes every shipped
  task provably solvable and its tests provably strict.
- **Separate verifier.** The agent never sees `tests/` or `solution/`; the verifier rebuilds a clean
  checkout, so changes to existing tests or test infrastructure cannot raise the reward.
- **Reward** follows the Track 1 rules: any regression failure gives 0.0, otherwise the share of feature
  tests that pass.

## Tools and models

- Python 3.12, pytest 8.4.1, Harbor 0.25.0, git, uv. No model API is called by the pipeline itself.
- AI coding assistants were used while writing this pipeline, as the hackathon rules allow.

## Limits

- The official `harbor run` nop/oracle checks need Docker. On the development laptop Docker is not
  installed, so the same scripts were run locally against fresh git checkouts at `base_commit`
  (the validator mirrors Harbor's agent -> collect -> separate-verifier flow). Run the two `harbor run`
  commands above on a machine with Docker to confirm.
- Families are written for click; each new repository needs its own families. The packager, verifier,
  grader, validator and report are repository-independent.
- The current pipeline does not call a model API; using the event's models to propose new families and
  rule ideas, with the same oracle + mutant gate, is the next step.
