# Coding Task Factory (demo)

A reusable pipeline that turns a real codebase into **feature-development tasks for evaluating AI coding
systems**, packaged in [Harbor](https://www.harborframework.com/) task format and **validated before they ship**.
Built as a demo for the Innodata AI Hackathon, Track 1 (Coding Task Factory). Team **SKA**.

The real challenge repository is only shared after registration, so this demo runs on `sample_repo/`, a small
shopping-cart library (`shopcart`) with its own tests.

## What it does

```
sample repo ──> sample a feature spec ──> build task ──> package (Harbor) ──> validate ──> report
                (family + rules)          instruction      task.toml           fail before
                                          reference code   environment/        pass after
                                          feature tests    solution/solve.sh   stable re-run
                                          known-wrong      tests/test.sh       every known-wrong
                                          implementations                      version rejected
```

**One strategy, many tasks.** Each feature *family* is a parameterised spec. Changing the parameters changes the
behaviour the agent must implement, not just names:

| Family | Rules that vary between tasks |
|---|---|
| `promo` | percent or flat, category-only eligibility, minimum spend (on cart or on eligible items), cap, single use per customer |
| `shipping` | base fee, per-started-kg weight charge, free-shipping threshold, express surcharge, whether express keeps free shipping |
| `deals` | buy X get 1 free (with optional cap), or tiered % off on a product or a whole category |

Tasks in the same family must differ in at least two rules. The report also proves they are really different:
each task's reference solution is run against the other tasks' tests and must fail them.

**Independent oracle.** Expected values in the tests come from a small oracle written separately from the
reference implementation, so a bug in the generated code cannot also hide in its tests.

**Known-wrong implementations (mutants).** For every rule, the generator also writes a realistic wrong
implementation, for example "minimum spend uses `>` instead of `>=`", "first kilogram charged as extra weight",
"category quantity counted per line". A task is only accepted if its tests reject every one of them. If no test
scenario can expose a bug with this repo (for example rounding, because all catalog prices are whole rupees),
the generator says so instead of pretending.

**Existing behaviour is protected.** The repo's own tests are copied into `tests/regression/` so the agent cannot
edit them. When a feature intentionally changes old behaviour (shipping makes `total()` differ from
`subtotal()`), the family declares the exact test change, the instruction tells the agent about it, and the
verifier uses the updated test. The validator caught this conflict on the first run and rejected those tasks
until it was handled.

## Harbor task layout

```
shipping-01/
  instruction.md            the task given to the agent
  task.toml                 Harbor config (version, metadata, timeouts)
  environment/Dockerfile    python:3.12-slim + pytest; repo copied to /app
  environment/repo/         repository at the starting version
  solution/solve.sh         reference implementation (oracle agent)
  tests/test.sh             runs feature + regression tests, writes /logs/verifier/reward.txt (1 or 0)
  tests/test_feature.py     generated feature tests
  tests/regression/         the repo's original tests
  validation/mutants/       known-wrong implementations (used only by the validator)
  factory.json              family, rules, starting repo version, validation results
```

## Run it

```powershell
python -m venv .venv
.venv\Scripts\pip install pytest==8.4.1
.venv\Scripts\python -m factory generate --repo sample_repo --out out --n 9 --seed 7
.venv\Scripts\python -m factory validate out\tasks\promo-01
.venv\Scripts\python -m pytest -q tests
```

With Harbor and Docker installed, any generated task can also be run the official way:

```powershell
harbor run -p out/tasks/promo-01 -a oracle
```

## Results on the sample repo

| Seed | Tasks | Valid | Known-wrong versions rejected | Same-family pairs distinct |
|---|---|---|---|---|
| 7 | 9 | 9 | 28 / 28 | 9 / 9 |
| 11 | 9 | 9 | 33 / 33 | 9 / 9 |
| 23 | 9 | 9 | 32 / 32 | 9 / 9 |

A full run of 9 tasks takes about 100 seconds on a laptop. See `out/report.md` for the seed 7 run.

## Moving to the hackathon repository

- Replace `sample_repo` with the provided repo and write families for its domain. The `Repo` class, packager,
  validator, cross-check and report do not change.
- Map `task.toml` and the folder layout to the provided task interface once its spec is released.
- Next step: use the provided model APIs to propose new families and rule ideas from the codebase, keeping the
  oracle + mutant validation as the gate that decides what ships.

## Limits

- Validation runs locally with bash and pytest, mirroring `tests/test.sh`; it has not been run inside Harbor's
  Docker sandbox on this machine (Docker is not installed here).
- Families are written for this sample repo; a new repo needs its own families.
- No model API is used yet; task generation is template- and oracle-based.
