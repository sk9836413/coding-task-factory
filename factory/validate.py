"""Validates a Harbor task folder the same way Harbor would grade it, but locally (no Docker needed).

Checks:
  repo_ok        the original repo passes its own tests
  rejects_start  the verifier gives reward 0 on the untouched repo (the task is not already solved)
  solvable       after solution/solve.sh the verifier gives reward 1
  stable         the solved repo gets reward 1 again on a second run (no flaky tests)
  mutants        every known wrong implementation gets reward 0 (tests catch bad behaviour)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASH = shutil.which("bash") or "bash"


def _env(ws: Path) -> dict:
    env = dict(os.environ)
    env.update(APP_DIR=(ws / "app").as_posix(), TESTS_DIR=(ws / "tests").as_posix(),
               LOGS_DIR=(ws / "logs").as_posix(), PYTHON=Path(sys.executable).as_posix())
    return env


def _workspace(task: Path, files: dict[str, str] | None = None) -> Path:
    ws = Path(tempfile.mkdtemp(prefix="tf-"))
    shutil.copytree(task / "environment" / "repo", ws / "app")
    shutil.copytree(task / "tests", ws / "tests")
    (ws / "logs").mkdir()
    for rel, content in (files or {}).items():
        (ws / "app" / rel).write_text(content, encoding="utf-8", newline="\n")
    return ws


def _verify(ws: Path) -> tuple[int, str]:
    subprocess.run([BASH, (ws / "tests" / "test.sh").as_posix()], env=_env(ws), capture_output=True, timeout=180)
    reward_file = ws / "logs" / "verifier" / "reward.txt"
    reward = int(reward_file.read_text().strip()) if reward_file.exists() else -1
    log = (ws / "logs" / "verifier" / "pytest.log")
    summary = log.read_text(errors="replace").strip().splitlines()[-1] if log.exists() else "no log"
    return reward, summary


def _counts(summary: str) -> dict:
    return {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|error)", summary)}


def load_mutants(task: Path) -> list:
    """Read validation/mutants/<name>/... back into Mutant objects."""
    from .common import Mutant
    meta = json.loads((task / "factory.json").read_text(encoding="utf-8"))
    desc = {m["name"]: m["description"] for m in meta.get("mutants", [])}
    out = []
    root = task / "validation" / "mutants"
    for d in sorted(root.iterdir()) if root.exists() else []:
        files = {p.relative_to(d).as_posix(): p.read_text(encoding="utf-8") for p in d.rglob("*") if p.is_file()}
        out.append(Mutant(d.name, desc.get(d.name, ""), files))
    return out


def validate(task: Path, mutants: list | None = None) -> dict:
    task = Path(task)
    if mutants is None:
        mutants = load_mutants(task)
    res: dict = {"task_id": task.name, "checks": {}, "mutants": []}
    c = res["checks"]

    ws = _workspace(task)
    try:
        # The untouched repo must pass its own original tests (the verifier's copy may be intentionally updated).
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                           cwd=ws / "app", env={**_env(ws), "PYTHONPATH": (ws / "app").as_posix()},
                           capture_output=True, text=True, timeout=180)
        c["repo_ok"] = r.returncode == 0
        reward, summary = _verify(ws)
        n = _counts(summary)
        c["rejects_start"] = reward == 0
        res["start_summary"] = summary
        res["feature_tests_failing_at_start"] = n.get("failed", 0) + n.get("error", 0)

        sh = subprocess.run([BASH, (task / "solution" / "solve.sh").as_posix()], env=_env(ws), capture_output=True,
                            text=True, timeout=60)
        c["solution_applies"] = sh.returncode == 0
        reward, summary = _verify(ws)
        c["solvable"] = reward == 1
        res["solved_summary"] = summary
        res["tests_total"] = sum(_counts(summary).values())
        c["stable"] = _verify(ws)[0] == 1
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    for m in mutants or []:
        mws = _workspace(task, m.files)
        try:
            reward, summary = _verify(mws)
        finally:
            shutil.rmtree(mws, ignore_errors=True)
        res["mutants"].append({"name": m.name, "description": m.description, "killed": reward == 0,
                               "summary": summary})
    killed = sum(m["killed"] for m in res["mutants"])
    res["mutation_score"] = f"{killed}/{len(res['mutants'])}"
    c["all_mutants_killed"] = killed == len(res["mutants"])
    res["valid"] = all(c.values())
    return res


def cross_check(task_a: Path, task_b: Path) -> bool:
    """True if A's reference solution FAILS B's tests, i.e. the two tasks really ask for different behaviour."""
    ws = _workspace(task_b)
    try:
        subprocess.run([BASH, (Path(task_a) / "solution" / "solve.sh").as_posix()], env=_env(ws),
                       capture_output=True, timeout=60)
        return _verify(ws)[0] == 0
    finally:
        shutil.rmtree(ws, ignore_errors=True)


if __name__ == "__main__":
    print(json.dumps(validate(Path(sys.argv[1])), indent=2))
