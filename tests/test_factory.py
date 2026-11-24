"""Fast checks of the factory itself (the full nop/oracle/mutant validation runs in `python -m factory generate`)."""
import json
import random
import tomllib
from pathlib import Path

import pytest

from factory.common import replace_once
from factory.families import FAMILIES, aliases, bytesize, duration
from factory.harbor import write_task
from factory.pipeline import _distance, generate
from factory.repo import Repo, git

ROOT = Path(__file__).resolve().parent.parent
BASE = "cf19179e8e2fd54c601378cec9e0d21bb12b6fb1"


@pytest.fixture(scope="module")
def repo():
    path = ROOT / "work" / "click"
    if not (path / ".git").exists():
        pytest.skip("run scripts/setup first (clones pallets/click into work/click)")
    return Repo(path, BASE)


def test_base_commit_is_pinned_release(repo):
    assert repo.base == BASE and len(repo.base) == 40
    assert repo.tag == "8.5.1"


def test_features_do_not_exist_upstream(repo):
    types = repo.read("src/click/types.py")
    core = repo.read("src/click/core.py")
    assert "class ByteSize" not in types and "class Duration" not in types
    assert "aliases" not in core


def test_bytesize_oracle():
    p = {"system": "both", "case_sensitive": False, "allow_fraction": True, "default_unit": "KiB",
         "max_bytes": 10 * 2**30}
    assert bytesize.oracle(p, "1.5MB") == ("ok", 1_500_000)
    assert bytesize.oracle(p, "2 kib") == ("ok", 2048)
    assert bytesize.oracle(p, "3") == ("ok", 3072)
    assert bytesize.oracle(p, "1.7B") == ("ok", 1)
    assert bytesize.oracle(p, f"{10 * 2**30 + 1}B")[0] == "bad"
    assert bytesize.oracle({**p, "allow_fraction": False}, "1.5MB") == ("bad", "fractional sizes are not allowed")


def test_duration_oracle():
    p = {"days": True, "compound": True, "bare_unit": "m", "output": "seconds", "positive_only": True,
         "max_seconds": None}
    assert duration.oracle(p, "1h30m") == ("ok", 5400)
    assert duration.oracle(p, "90") == ("ok", 5400)
    assert duration.oracle(p, "30m1h")[0] == "bad"
    assert duration.oracle(p, "0s") == ("bad", "must be greater than zero")
    assert duration.oracle({**p, "days": False}, "1d")[0] == "bad"


def test_aliases_oracle():
    p = {"prefix_matching": True, "case_insensitive": True, "show_in_help": True}
    assert aliases.oracle(p, "ls") == ("ok", "list")
    assert aliases.oracle(p, "RE") == ("ok", "remove")
    assert aliases.oracle(p, "li") == ("bad", "Too many matches: lint, list")
    assert aliases.oracle({**p, "prefix_matching": False}, "re") == ("bad", "No such command")


def test_generation_is_deterministic_and_varied(repo):
    one = generate(repo, 5, 7, list(FAMILIES))
    two = generate(repo, 5, 7, list(FAMILIES))
    assert [t.signature for t in one] == [t.signature for t in two]
    assert len({t.signature for t in one}) == 5
    assert {t.family for t in one} == set(FAMILIES)
    for a in one:
        for b in one:
            if a is not b and a.family == b.family:
                assert _distance(a.signature, b.signature) >= 2


def test_package_layout_and_harbor_schema(repo, tmp_path):
    from harbor.models.task.config import TaskConfig

    t = bytesize.build(repo, bytesize.sample(repo, random.Random(1)))
    t.task_id = "layout-01"
    d = write_task(t, repo, tmp_path, ["tests/test_basic.py::test_basic_functionality"],
                   ["tests/test_task_feature.py::test_x"])
    for rel in ["instruction.md", "task.toml", "environment/Dockerfile", "solution/solve.sh",
                "solution/solution.patch", "tests/test.sh", "tests/test_task_feature.py", "tests/fail_to_pass.json",
                "tests/pass_to_pass.json", "tests/grade.py", "tests/harbor_report.py"]:
        assert (d / rel).exists(), rel
    raw = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))
    cfg = TaskConfig.model_validate(raw)
    assert cfg.metadata["base_commit"] == BASE
    assert raw["verifier"]["environment_mode"] == "separate"
    assert BASE in (d / "environment" / "Dockerfile").read_text()
    assert json.loads((d / "tests" / "fail_to_pass.json").read_text()) == ["tests/test_task_feature.py::test_x"]


def test_solution_patch_applies_to_base(repo, tmp_path):
    t = duration.build(repo, duration.sample(repo, random.Random(3)))
    patch = tmp_path / "s.patch"
    patch.write_text(repo.patch_for(t.solution), encoding="utf-8", newline="\n")
    ws = repo.scratch()
    git("apply", "--check", str(patch), cwd=ws / "app")


def test_edit_anchor_missing_is_an_error():
    with pytest.raises(ValueError):
        replace_once("abc", "zzz", "y", "missing")
