"""Files copied verbatim into every task's tests/ folder."""

# pytest plugin: records one outcome per test node id into $HARBOR_REPORT (JSON).
REPORT_PLUGIN = '''"""pytest plugin used by the verifier: writes {node_id: outcome} to $HARBOR_REPORT."""
import json
import os

_outcomes = {}


def pytest_runtest_logreport(report):
    prev = _outcomes.get(report.nodeid)
    if report.failed:
        _outcomes[report.nodeid] = "failed"
    elif report.skipped and prev is None:
        _outcomes[report.nodeid] = "skipped"
    elif report.when == "call" and report.passed and prev != "failed":
        _outcomes[report.nodeid] = "passed"


def pytest_collectreport(report):
    if report.failed:
        _outcomes[report.nodeid or "<collection>"] = "error"


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("HARBOR_REPORT", "/logs/verifier/test_outcomes.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_outcomes, f, indent=0, sort_keys=True)
'''

# Grader: SWE-bench style. Any pass_to_pass failure -> 0.0; else share of fail_to_pass tests that pass.
GRADE = '''"""Compute the reward from test outcomes (Innodata Track 1 rules).

reward = 0.0 if any pass_to_pass test did not pass,
         otherwise (fail_to_pass tests passed) / (fail_to_pass tests).
"""
import json
import sys
from pathlib import Path

tests_dir, outcomes_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
f2p = json.loads((tests_dir / "fail_to_pass.json").read_text())
p2p = json.loads((tests_dir / "pass_to_pass.json").read_text())
outcomes = json.loads(outcomes_path.read_text()) if outcomes_path.exists() else {}

broken = [t for t in p2p if outcomes.get(t) != "passed"]
passed = [t for t in f2p if outcomes.get(t) == "passed"]
reward = 0.0 if broken else round(len(passed) / len(f2p), 4)
(out_dir / "reward.txt").write_text(f"{reward}\\n")
(out_dir / "grading.json").write_text(json.dumps({
    "reward": reward,
    "fail_to_pass": {"total": len(f2p), "passed": len(passed),
                     "failing": [t for t in f2p if t not in passed]},
    "pass_to_pass": {"total": len(p2p), "broken": broken[:50], "broken_count": len(broken)},
}, indent=2))
print(f"reward={reward} feature={len(passed)}/{len(f2p)} regression_broken={len(broken)}")
'''
