"""End-to-end checks of the factory on the sample repo. Each test builds a task, writes it in Harbor format and
validates it locally (fail before, pass after, stable, all known-wrong implementations rejected)."""
import random
import tomllib
from pathlib import Path

import pytest

from factory.families import deals, promo, shipping
from factory.harbor import write_task
from factory.pipeline import generate
from factory.repo import Repo
from factory.validate import cross_check, load_mutants, validate

ROOT = Path(__file__).resolve().parent.parent
REPO = Repo(ROOT / "sample_repo")


def _package(task, tmp_path, task_id):
    task.task_id = task_id
    return write_task(task, REPO, tmp_path)


def _assert_valid(d, task):
    r = validate(d, task.mutants)
    assert r["checks"] == {k: True for k in r["checks"]}, r
    assert r["mutants"], "every task should ship at least one known-wrong implementation"
    return r


def test_harbor_layout(tmp_path):
    t = promo.build(REPO, promo.sample(REPO, random.Random(1)))
    d = _package(t, tmp_path, "layout")
    for rel in ["instruction.md", "task.toml", "environment/Dockerfile", "environment/repo/shopcart/cart.py",
                "solution/solve.sh", "tests/test.sh", "tests/test_feature.py", "tests/regression/test_cart.py",
                "factory.json"]:
        assert (d / rel).exists(), rel
    cfg = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))
    assert cfg["version"] == "1.0" and cfg["verifier"]["timeout_sec"] > 0
    assert "reward.txt" in (d / "tests/test.sh").read_text()
    assert len(load_mutants(d)) == len(t.mutants)


def test_promo_with_every_rule(tmp_path):
    p = {"code": "FESTIVE", "kind": "percent", "pct": 10, "cap": 15000, "category": "grocery",
         "threshold_on": "eligible", "min_subtotal": 64900, "single_use": True}
    t = promo.build(REPO, p)
    r = _assert_valid(_package(t, tmp_path, "promo-all"), t)
    assert {m["name"] for m in r["mutants"]} >= {"threshold_strict", "apply_time_check", "ignore_category",
                                                  "single_use_not_enforced", "burn_without_discount"}


def test_flat_promo(tmp_path):
    p = {"code": "WELCOME", "kind": "flat", "flat": 25000, "cap": None, "category": "stationery",
         "threshold_on": "cart", "min_subtotal": None, "single_use": False}
    t = promo.build(REPO, p)
    r = _assert_valid(_package(t, tmp_path, "promo-flat"), t)
    assert "flat_exceeds_base" in {m["name"] for m in r["mutants"]}


def test_shipping_express_and_weight(tmp_path):
    p = {"base_fee": 4900, "per_kg": 2000, "express": 10000, "free_above": 79900, "express_free": False}
    t = shipping.build(REPO, p)
    r = _assert_valid(_package(t, tmp_path, "ship-express"), t)
    assert {"weight_floor", "express_ignored", "express_free_wrong"} <= {m["name"] for m in r["mutants"]}


def test_category_tiered_deal(tmp_path):
    p = {"kind": "tiered", "target": ("category", "grocery"), "n": 3, "pct": 15}
    t = deals.build(REPO, p)
    r = _assert_valid(_package(t, tmp_path, "deal-cat"), t)
    assert "count_per_line" in {m["name"] for m in r["mutants"]}


def test_untouched_repo_is_rejected_and_tasks_are_distinct(tmp_path):
    a = deals.build(REPO, {"kind": "bxgy", "sku": "TEA-250", "x": 2, "max_free": None})
    b = deals.build(REPO, {"kind": "bxgy", "sku": "TEA-250", "x": 3, "max_free": 1})
    da, db = _package(a, tmp_path, "a"), _package(b, tmp_path, "b")
    assert validate(da, [])["checks"]["rejects_start"]
    assert cross_check(da, db) and cross_check(db, da)


def test_generation_is_deterministic_and_varied():
    one = [t.signature for t in generate(REPO, 6, 5, ["promo", "shipping", "deals"])]
    two = [t.signature for t in generate(REPO, 6, 5, ["promo", "shipping", "deals"])]
    assert one == two and len(set(one)) == 6


def test_edit_anchor_missing_is_an_error(tmp_path):
    src = REPO.read("shopcart/cart.py")
    from factory.common import replace_once
    with pytest.raises(ValueError):
        replace_once(src, "def does_not_exist", "x", "missing")
