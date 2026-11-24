"""Local mirror of Harbor's validation matrix, plus `harbor lint`.

Harbor runs (in Docker):
  harbor run -p <task> -a nop    -> expected reward 0.0
  harbor run -p <task> -a oracle -> expected reward 1.0
This module reproduces the same flow with the task's own scripts on a scratch clone at base_commit:
  agent phase  : nothing (nop) or solution/solve.sh (oracle)
  collect hook : git add -A && git diff --cached --binary <base> > /logs/artifacts/agent.patch
  verifier     : tests/test.sh in a *fresh* clone, which applies the patch, restores tests, runs pytest, grades.
Extra checks: every known-wrong implementation (validation/mutants/*.patch) must be caught by the feature
tests, and the oracle must be stable on a second run.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .repo import Repo, git

BASH = shutil.which("bash") or "bash"


def _env(**paths: Path) -> dict:
    env = dict(os.environ)
    env.update({k: v.as_posix() for k, v in paths.items()})
    env["PYTHON"] = Path(sys.executable).as_posix()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATHSEP"] = os.pathsep  # test.sh defaults to ":" (Linux, as in Harbor's containers)
    return env


def _verify(repo: Repo, task: Path, agent_patch: str | None) -> dict:
    """Fresh verifier container equivalent: returns grading.json."""
    ws = repo.scratch()
    try:
        tests, logs = ws / "tests", ws / "logs"
        shutil.copytree(task / "tests", tests)
        (logs / "artifacts").mkdir(parents=True)
        if agent_patch:
            (logs / "artifacts" / "agent.patch").write_text(agent_patch, encoding="utf-8", newline="\n")
        subprocess.run([BASH, (tests / "test.sh").as_posix()], capture_output=True, timeout=1200,
                       env=_env(APP_DIR=ws / "app", TESTS_DIR=tests, LOGS_DIR=logs))
        grading = logs / "verifier" / "grading.json"
        if not grading.exists():
            apply_log = logs / "verifier" / "apply.log"
            reward_file = logs / "verifier" / "reward.txt"
            return {"reward": float(reward_file.read_text()) if reward_file.exists() else None,
                    "note": apply_log.read_text(errors="replace") if apply_log.exists() else "no grading output"}
        return json.loads(grading.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def _agent_phase(repo: Repo, task: Path, oracle: bool) -> str:
    """Agent container equivalent: run solve.sh (oracle) or nothing (nop), then the collect hook."""
    ws = repo.scratch()
    try:
        app = ws / "app"
        if oracle:
            r = subprocess.run([BASH, (task / "solution" / "solve.sh").as_posix()], capture_output=True, text=True,
                               env=_env(APP_DIR=app, SOLUTION_DIR=task / "solution"), timeout=120)
            if r.returncode != 0:
                raise RuntimeError(f"solve.sh failed: {r.stderr.strip()}")
        git("add", "-A", cwd=app)
        return git("diff", "--cached", "--binary", repo.base, cwd=app)
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def _feature_only(repo: Repo, task: Path, patch: str) -> tuple[int, int]:
    """Runs just the feature tests against a patch: (failed, total)."""
    ws = repo.scratch()
    try:
        app = ws / "app"
        pf = ws / "p.patch"
        pf.write_text(patch, encoding="utf-8", newline="\n")
        git("apply", "--whitespace=nowarn", str(pf), cwd=app)
        shutil.copy(task / "tests" / "test_task_feature.py", app / "tests" / "test_task_feature.py")
        out = ws / "o.json"
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "harbor_report",
                        "tests/test_task_feature.py"], cwd=app, capture_output=True, timeout=600,
                       env={**_env(), "PYTHONPATH": os.pathsep.join([str(app / "src"), str(task / "tests")]),
                            "HARBOR_REPORT": str(out)})
        res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        return sum(v != "passed" for v in res.values()), len(res)
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def harbor_lint(task: Path) -> dict:
    exe = shutil.which("harbor") or str(Path(sys.executable).with_name("harbor.exe" if os.name == "nt" else "harbor"))
    r = subprocess.run([exe, "lint", "--json", str(task)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    try:
        findings = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        findings = [{"rule": "lint-output", "message": (r.stdout + r.stderr)[-500:]}]
    return {"ok": not findings, "findings": findings}


def validate(repo: Repo, task: Path, run_mutants: bool = True) -> dict:
    task = Path(task).resolve()
    res: dict = {"task_id": task.name, "checks": {}}
    c = res["checks"]

    nop = _verify(repo, task, _agent_phase(repo, task, oracle=False))
    res["nop"] = nop
    c["nop_reward_0"] = nop.get("reward") == 0.0
    c["nop_regression_intact"] = nop.get("pass_to_pass", {}).get("broken_count") == 0

    agent_patch = _agent_phase(repo, task, oracle=True)
    oracle = _verify(repo, task, agent_patch)
    res["oracle"] = oracle
    c["oracle_reward_1"] = oracle.get("reward") == 1.0

    failed, total = _feature_only(repo, task, agent_patch)
    c["oracle_stable"] = failed == 0 and total > 0

    res["mutants"] = []
    if run_mutants:
        for mp in sorted((task / "validation" / "mutants").glob("*.patch")):
            failed, total = _feature_only(repo, task, mp.read_text(encoding="utf-8"))
            res["mutants"].append({"name": mp.stem, "killed": failed > 0, "failed_tests": failed, "tests": total})
        c["all_mutants_killed"] = all(m["killed"] for m in res["mutants"])
    killed = sum(m["killed"] for m in res["mutants"])
    res["mutation_score"] = f"{killed}/{len(res['mutants'])}"

    lint = harbor_lint(task)
    res["harbor_lint"] = lint
    c["harbor_lint_clean"] = lint["ok"]
    res["valid"] = all(c.values())
    return res
