"""Writes a TaskPackage to disk in Harbor task format.

my-task/
  instruction.md            what the agent is asked to do
  task.toml                 Harbor config
  environment/Dockerfile    python:3.12-slim + pytest, repo snapshot copied to /app
  environment/repo/         the repository at the starting version
  solution/solve.sh         reference implementation (writes the changed files)
  tests/test.sh             runs feature + regression tests, writes /logs/verifier/reward.txt
  tests/test_feature.py     generated feature tests
  tests/regression/         the repo's own tests, copied so the agent cannot edit them
  validation/mutants/       known-wrong implementations the tests must reject (not shipped to the agent)
  factory.json              provenance: family, params, repo version, validation results
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .common import TaskPackage
from .repo import Repo

EOF_MARK = "TASKFACTORY_EOF"

TEST_SH = """#!/bin/bash
# Verifier: feature tests + the repo's original tests. Reward 1 only if all pass.
APP_DIR="${APP_DIR:-/app}"
TESTS_DIR="${TESTS_DIR:-/tests}"
LOGS_DIR="${LOGS_DIR:-/logs}"
PYTHON="${PYTHON:-python}"
mkdir -p "$LOGS_DIR/verifier"
cd "$APP_DIR"
PYTHONPATH="$APP_DIR" PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m pytest -q -p no:cacheprovider \\
  "$TESTS_DIR/test_feature.py" "$TESTS_DIR/regression" > "$LOGS_DIR/verifier/pytest.log" 2>&1
if [ $? -eq 0 ]; then
  echo 1 > "$LOGS_DIR/verifier/reward.txt"
else
  echo 0 > "$LOGS_DIR/verifier/reward.txt"
fi
"""

DOCKERFILE = """FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.4.1
WORKDIR /app
COPY repo/ /app/
"""


def _toml_list(xs: list[str]) -> str:
    return "[" + ", ".join(json.dumps(x) for x in xs) + "]"


def solve_sh(files: dict[str, str]) -> str:
    out = ["#!/bin/bash", "# Reference solution: writes the changed files.", "set -euo pipefail",
           'APP_DIR="${APP_DIR:-/app}"']
    for rel, content in sorted(files.items()):
        if EOF_MARK in content:
            raise ValueError("file content contains the heredoc marker")
        parent = str(Path(rel).parent.as_posix())
        if parent != ".":
            out.append(f'mkdir -p "$APP_DIR/{parent}"')
        out.append(f"cat > \"$APP_DIR/{rel}\" <<'{EOF_MARK}'\n{content.rstrip()}\n{EOF_MARK}")
    return "\n".join(out) + "\n"


def write_task(task: TaskPackage, repo: Repo, out_dir: Path, regression_dir: str = "tests") -> Path:
    d = out_dir / task.task_id
    if d.exists():
        shutil.rmtree(d)
    (d / "environment").mkdir(parents=True)
    (d / "solution").mkdir()
    (d / "tests" / "regression").mkdir(parents=True)

    def w(rel: str, text: str) -> None:
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    w("instruction.md", task.instruction)
    w("task.toml", f'''version = "1.0"

[metadata]
author_name = "Team SKA"
author_email = ""
difficulty = "{task.difficulty}"
difficulty_explanation = "Feature development in an existing Python codebase; {len(task.mutants)} known wrong implementations must be rejected by the tests"
category = "software-engineering"
tags = {_toml_list(["python", "feature-development", task.family] + task.tags)}

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = 900.0

[environment]
build_timeout_sec = 600.0
''')
    w("environment/Dockerfile", DOCKERFILE)
    for rel in repo.files():
        w(f"environment/repo/{rel}", repo.read(rel))
    for rel in repo.files():
        if rel.startswith(regression_dir + "/") and rel.endswith(".py"):
            text = repo.read(rel)
            for old, new in task.regression_edits.get(rel, []):
                if text.count(old) != 1:
                    raise ValueError(f"regression edit anchor not found once in {rel}: {old!r}")
                text = text.replace(old, new)
            w(f"tests/regression/{Path(rel).name}", text)
    w("solution/solve.sh", solve_sh(task.solution))
    w("tests/test.sh", TEST_SH)
    w("tests/test_feature.py", task.feature_tests)
    meta = {"task_id": task.task_id, "title": task.title, "family": task.family, "params": task.params,
            "signature": [list(x) for x in task.signature], "repo_version": repo.version(),
            "mutants": [{"name": m.name, "description": m.description} for m in task.mutants],
            "skipped_mutants": task.skipped_mutants}
    for m in task.mutants:  # known-wrong implementations, kept outside anything the agent or verifier sees
        for rel, content in m.files.items():
            w(f"validation/mutants/{m.name}/{rel}", content)
    w("factory.json", json.dumps(meta, indent=2, default=list))
    return d
