"""Generate -> package (Harbor 0.25) -> validate -> cross-check -> report."""
from __future__ import annotations

import json
import random
import re
import shutil
import sys
import time
from itertools import combinations
from pathlib import Path

from .families import FAMILIES
from .harbor import write_task
from .repo import Repo
from .validate import _feature_only, validate

ROOT = Path(__file__).resolve().parent.parent


def _distance(a: tuple, b: tuple) -> int:
    da, db = dict(a), dict(b)
    return sum(da.get(k) != db.get(k) for k in set(da) | set(db))


def generate(repo: Repo, n: int, seed: int, families: list[str]) -> list:
    """Sample n tasks round-robin over families. Tasks in the same family must differ in at least 2 rules."""
    rng = random.Random(seed)
    tasks, sigs = [], {f: [] for f in families}
    attempts = 0
    while len(tasks) < n and attempts < n * 80:
        fam = families[len(tasks) % len(families)]
        attempts += 1
        mod = FAMILIES[fam]
        params = mod.sample(repo, rng)
        sig = mod.signature(params)
        if any(_distance(sig, s) < 2 for s in sigs[fam]):
            continue
        task = mod.build(repo, params)
        sigs[fam].append(sig)
        task.task_id = f"{fam}-{sum(t.family == fam for t in tasks) + 1:02d}"
        tasks.append(task)
    return tasks


def run(repo: Repo, out: Path, n: int = 5, seed: int = 7, families: list[str] | None = None,
        do_validate: bool = True, log=print) -> dict:
    t0 = time.time()
    out = Path(out).resolve()
    families = families or list(FAMILIES)
    if out.exists():
        shutil.rmtree(out)
    (out / "tasks").mkdir(parents=True)
    log(f"Repository {repo.name} at {repo.base} ({repo.tag or 'no tag'})")
    p2p = repo.baseline_tests(sys.executable, ROOT / ".cache")
    log(f"Baseline: {len(p2p)} existing tests pass at the base commit (pass_to_pass)")
    tasks = generate(repo, n, seed, families)
    dirs = {}
    for t in tasks:
        f2p = [f"tests/test_task_feature.py::{m}" for m in re.findall(r"^def (test_\w+)\(", t.feature_tests, re.M)]
        dirs[t.task_id] = write_task(t, repo, out / "tasks", p2p, f2p)
        log(f"  packaged {t.task_id}: {t.title} ({len(f2p)} feature tests, {len(t.mutants)} mutants)")

    results = []
    if do_validate:
        for t in tasks:
            log(f"  validating {t.task_id} (nop, oracle, mutants, harbor lint) ...")
            r = validate(repo, dirs[t.task_id])
            r.update(family=t.family, title=t.title, difficulty=t.difficulty, params=t.params)
            results.append(r)
            meta_p = dirs[t.task_id] / "factory.json"
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            meta["validation"] = {k: r[k] for k in ("checks", "mutation_score", "valid", "mutants")}
            meta["validation"]["nop_reward"] = r["nop"].get("reward")
            meta["validation"]["oracle_reward"] = r["oracle"].get("reward")
            meta_p.write_text(json.dumps(meta, indent=2, default=list), encoding="utf-8", newline="\n")
            log(f"    nop={r['nop'].get('reward')} oracle={r['oracle'].get('reward')} "
                f"mutants={r['mutation_score']} lint={'clean' if r['checks']['harbor_lint_clean'] else 'FINDINGS'} "
                f"-> {'VALID' if r['valid'] else 'REJECTED'}")
        for r in results:
            if not r["valid"]:
                rej = out / "rejected"
                rej.mkdir(exist_ok=True)
                shutil.move(str(dirs[r["task_id"]]), str(rej / r["task_id"]))

    valid_ids = {r["task_id"] for r in results if r["valid"]} if do_validate else set(dirs)
    pairs = []
    for a, b in combinations([t for t in tasks if t.task_id in valid_ids and t.family], 2):
        if a.family != b.family:
            continue
        a_patch = (dirs[a.task_id] / "solution" / "solution.patch").read_text(encoding="utf-8")
        b_patch = (dirs[b.task_id] / "solution" / "solution.patch").read_text(encoding="utf-8")
        pairs.append({"a": a.task_id, "b": b.task_id,
                      "a_solution_fails_b": _feature_only(repo, dirs[b.task_id], a_patch)[0] > 0,
                      "b_solution_fails_a": _feature_only(repo, dirs[a.task_id], b_patch)[0] > 0})

    report = {"repository": repo.name, "base_commit": repo.base, "base_tag": repo.tag, "seed": seed,
              "requested": n, "generated": len(tasks), "valid": len(valid_ids), "pass_to_pass": len(p2p),
              "seconds": round(time.time() - t0, 1), "tasks": results, "distinctness": pairs}
    (out / "report.json").write_text(json.dumps(report, indent=2, default=list), encoding="utf-8", newline="\n")
    (out / "report.md").write_text(markdown(report), encoding="utf-8", newline="\n")
    return report


def markdown(rep: dict) -> str:
    rows = []
    for r in rep["tasks"]:
        c = r["checks"]
        y = lambda k: "yes" if c.get(k) else "**NO**"
        rows.append(f"| {r['task_id']} | {r['title']} | {r['nop'].get('reward')} | {r['oracle'].get('reward')} | "
                    f"{y('nop_regression_intact')} | {y('oracle_stable')} | {r['mutation_score']} | "
                    f"{y('harbor_lint_clean')} | {'valid' if r['valid'] else 'REJECTED'} |")
    total_m = sum(len(r["mutants"]) for r in rep["tasks"])
    killed = sum(m["killed"] for r in rep["tasks"] for m in r["mutants"])
    distinct = sum(p["a_solution_fails_b"] and p["b_solution_fails_a"] for p in rep["distinctness"])
    lines = [
        "# Task factory run", "",
        f"- Repository: `{rep['repository']}` at `{rep['base_commit']}` (tag `{rep['base_tag']}`)",
        f"- Existing tests passing at the base commit (pass_to_pass): {rep['pass_to_pass']}",
        f"- Seed {rep['seed']}: {rep['generated']} tasks generated, **{rep['valid']} valid**, in {rep['seconds']} s",
        f"- Known-wrong implementations caught by the feature tests: **{killed}/{total_m}**",
        f"- Same-family task pairs whose reference solutions fail each other's tests: "
        f"**{distinct}/{len(rep['distinctness'])}**", "",
        "| Task | Title | nop reward | oracle reward | Regression intact (nop) | Stable | Mutants caught | "
        "harbor lint | Status |",
        "|---|---|---|---|---|---|---|---|---|", *rows, "", "## Rules per task", "",
    ]
    for r in rep["tasks"]:
        lines.append(f"- **{r['task_id']}**: " + ", ".join(f"{k}={v}" for k, v in r["params"].items()))
    lines += ["", "## Mutants", ""]
    for r in rep["tasks"]:
        lines.append(f"- **{r['task_id']}**: " + ", ".join(
            f"{m['name']} ({'caught' if m['killed'] else 'SURVIVED'})" for m in r["mutants"]))
    lines += ["", "## Distinctness (same family)", "", "| A | B | A's solution fails B | B's solution fails A |",
              "|---|---|---|---|"]
    lines += [f"| {p['a']} | {p['b']} | {p['a_solution_fails_b']} | {p['b_solution_fails_a']} |"
              for p in rep["distinctness"]]
    return "\n".join(lines) + "\n"
