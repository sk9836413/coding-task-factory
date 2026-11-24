"""Writes a TaskPackage as a Harbor 0.25 task (task.toml schema 1.4).

<task>/
  instruction.md                the only file the agent sees
  task.toml                     metadata: repository, base_commit (40 chars), license; separate verifier
  environment/Dockerfile        pinned python image, click cloned at base_commit, editable install
  solution/solve.sh             applies solution/solution.patch (oracle agent)
  solution/solution.patch       reference implementation as a git patch
  tests/test.sh                 verifier: apply the agent's patch to a clean checkout, restore original tests,
                                run feature + regression tests, grade
  tests/test_task_feature.py    generated feature tests (copied to tests/ in the repo during verification)
  tests/fail_to_pass.json       feature test ids (must go from failing to passing)
  tests/pass_to_pass.json       existing test ids that pass at base_commit (must keep passing)
  tests/grade.py, tests/harbor_report.py   grading helpers
  validation/mutants/*.patch    known-wrong implementations, used only by the local validator
  factory.json                  provenance and validation results
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import assets
from .common import TaskPackage
from .repo import Repo

PYTHON_IMAGE = "python:3.12-slim@sha256:37fc60d303cb9294d3718b5b48998a0210bb1c73611c1399ef5eb7964c0536e5"
PYTEST = "pytest==8.4.1"


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _toml_list(xs: list[str]) -> str:
    return "[" + ", ".join(_toml_str(x) for x in xs) + "]"


def task_toml(task: TaskPackage, repo: Repo) -> str:
    collect = (f"mkdir -p /logs/artifacts && cd /app && git add -A && "
               f"git diff --cached --binary {repo.base} > /logs/artifacts/agent.patch")
    return f'''schema_version = "1.4"
artifacts = []

[task]
name = {_toml_str("ska/click-" + task.task_id)}
version = "1.0.0"
description = {_toml_str(task.title)}
keywords = {_toml_list(["click", "python", "feature-development", task.family] + task.tags)}

[[task.authors]]
name = "Team SKA"

[metadata]
repository = {_toml_str(repo.name)}
repository_url = {_toml_str(repo.url.removesuffix(".git"))}
base_commit = {_toml_str(repo.base)}
base_tag = {_toml_str(repo.tag or "")}
license = {_toml_str(repo.license)}
task_type = "feature-development"
family = {_toml_str(task.family)}
difficulty = {_toml_str(task.difficulty)}
generator = "Task Factory by Team SKA"

[verifier]
timeout_sec = 900.0
environment_mode = "separate"

[[verifier.collect]]
command = {_toml_str(collect)}
timeout_sec = 120.0

[agent]
timeout_sec = 1800.0

[environment]
build_timeout_sec = 900.0
'''


def dockerfile(repo: Repo) -> str:
    return f"""FROM {PYTHON_IMAGE}
RUN apt-get update \\
 && apt-get install -y --no-install-recommends git \\
 && rm -rf /var/lib/apt/lists/*
RUN git clone {repo.url} /app \\
 && git -C /app -c advice.detachedHead=false checkout --quiet {repo.base} \\
 && git -C /app config user.email "agent@example.com" \\
 && git -C /app config user.name "agent"
WORKDIR /app
RUN pip install --no-cache-dir {PYTEST} \\
 && pip install --no-cache-dir -e /app
"""


SOLVE_SH = """#!/bin/bash
# Oracle: apply the reference implementation.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
SOLUTION_DIR="${SOLUTION_DIR:-/solution}"
git -C "$APP_DIR" apply --whitespace=nowarn "$SOLUTION_DIR/solution.patch"
"""


def test_sh(repo: Repo) -> str:
    return f"""#!/bin/bash
# Verifier (runs in a fresh container at base_commit):
#   1. apply the agent's work (collected as /logs/artifacts/agent.patch),
#   2. restore the repository's original tests so they cannot be edited away,
#   3. run feature + regression tests, 4. grade (tests/grade.py).
APP_DIR="${{APP_DIR:-/app}}"
TESTS_DIR="${{TESTS_DIR:-/tests}}"
LOGS_DIR="${{LOGS_DIR:-/logs}}"
PYTHON="${{PYTHON:-python}}"
BASE_COMMIT="{repo.base}"
OUT="$LOGS_DIR/verifier"
mkdir -p "$OUT"
cd "$APP_DIR" || {{ echo 0.0 > "$OUT/reward.txt"; exit 0; }}

PATCH="$LOGS_DIR/artifacts/agent.patch"
if [ -s "$PATCH" ]; then
  if ! git apply --whitespace=nowarn "$PATCH" 2> "$OUT/apply.log"; then
    echo "agent patch did not apply" | tee -a "$OUT/apply.log"
    echo 0.0 > "$OUT/reward.txt"
    exit 0
  fi
fi
git checkout --quiet "$BASE_COMMIT" -- tests
cp "$TESTS_DIR/test_task_feature.py" tests/test_task_feature.py

HARBOR_REPORT="$OUT/test_outcomes.json" PYTHONPATH="$APP_DIR/src${{PATHSEP:-:}}$TESTS_DIR" PYTHONDONTWRITEBYTECODE=1 \\
  "$PYTHON" -m pytest -q -p no:cacheprovider -p harbor_report tests > "$OUT/pytest.log" 2>&1
"$PYTHON" "$TESTS_DIR/grade.py" "$TESTS_DIR" "$OUT/test_outcomes.json" "$OUT"
"""


def write_task(task: TaskPackage, repo: Repo, out_dir: Path, pass_to_pass: list[str],
               fail_to_pass: list[str]) -> Path:
    d = out_dir / task.task_id
    if d.exists():
        shutil.rmtree(d)

    def w(rel: str, text: str) -> None:
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    w("instruction.md", task.instruction)
    w("task.toml", task_toml(task, repo))
    w("environment/Dockerfile", dockerfile(repo))
    w("solution/solve.sh", SOLVE_SH)
    w("solution/solution.patch", repo.patch_for(task.solution))
    w("tests/test.sh", test_sh(repo))
    w("tests/test_task_feature.py", task.feature_tests)
    w("tests/fail_to_pass.json", json.dumps(fail_to_pass, indent=1))
    w("tests/pass_to_pass.json", json.dumps(pass_to_pass, indent=0))
    w("tests/grade.py", assets.GRADE)
    w("tests/harbor_report.py", assets.REPORT_PLUGIN)
    for m in task.mutants:
        w(f"validation/mutants/{m.name}.patch", repo.patch_for(m.files))
    meta = {"task_id": task.task_id, "title": task.title, "family": task.family, "params": task.params,
            "signature": [list(x) for x in task.signature], "repository": repo.name, "base_commit": repo.base,
            "base_tag": repo.tag, "fail_to_pass": len(fail_to_pass), "pass_to_pass": len(pass_to_pass),
            "mutants": [{"name": m.name, "description": m.description} for m in task.mutants],
            "skipped_mutants": task.skipped_mutants}
    w("factory.json", json.dumps(meta, indent=2, default=list))
    return d
