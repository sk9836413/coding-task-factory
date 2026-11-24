"""pytest plugin used by the verifier: writes {node_id: outcome} to $HARBOR_REPORT."""
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
