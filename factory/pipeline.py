"""Generate -> package -> validate -> cross-check -> report."""
from __future__ import annotations

import json
import random
import shutil
import time
from itertools import combinations
from pathlib import Path

from .families import FAMILIES
from .harbor import write_task
from .repo import Repo
from .validate import cross_check, validate


def _distance(a: tuple, b: tuple) -> int:
    da, db = dict(a), dict(b)
    return sum(da.get(k) != db.get(k) for k in set(da) | set(db))


def generate(repo: Repo, n: int, seed: int, families: list[str]) -> list:
    """Sample n tasks round-robin over families. Tasks in the same family must differ in at least 2 rules."""
    rng = random.Random(seed)
    tasks, sigs = [], {f: [] for f in families}
    attempts = 0
    while len(tasks) < n and attempts < n * 60:
        fam = families[len(tasks) % len(families)]
        attempts += 1
        mod = FAMILIES[fam]
        params = mod.sample(repo, rng)
        sig = mod.signature(params)
        if any(_distance(sig, s) < 2 for s in sigs[fam]):
            continue
        try:
            task = mod.build(repo, params)
        except ValueError:
            continue
        sigs[fam].append(sig)
        task.task_id = f"{fam}-{sum(t.family == fam for t in tasks) + 1:02d}"
        tasks.append(task)
    return tasks


def run(repo_path: Path, out: Path, n: int = 6, seed: int = 7, families: list[str] | None = None,
        do_validate: bool = True) -> dict:
    t0 = time.time()
    repo = Repo(repo_path)
    families = families or list(FAMILIES)
    if out.exists():
        shutil.rmtree(out)
    (out / "tasks").mkdir(parents=True)
    tasks = generate(repo, n, seed, families)
    dirs = {t.task_id: write_task(t, repo, out / "tasks") for t in tasks}

    results = []
    if do_validate:
        for t in tasks:
            r = validate(dirs[t.task_id], t.mutants)
            r.update(family=t.family, title=t.title, skipped_mutants=t.skipped_mutants, difficulty=t.difficulty)
            results.append(r)
            meta_p = dirs[t.task_id] / "factory.json"
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            meta["validation"] = r
            meta_p.write_text(json.dumps(meta, indent=2, default=list), encoding="utf-8", newline="\n")
        rejected = out / "rejected"
        for r in results:
            if not r["valid"]:
                rejected.mkdir(exist_ok=True)
                shutil.move(str(dirs[r["task_id"]]), str(rejected / r["task_id"]))

    pairs = []
    valid_ids = {r["task_id"] for r in results if r["valid"]} if do_validate else set(dirs)
    for a, b in combinations([t for t in tasks if t.task_id in valid_ids], 2):
        if a.family != b.family:
            continue
        pairs.append({"a": a.task_id, "b": b.task_id,
                      "a_solution_fails_b": cross_check(dirs[a.task_id], dirs[b.task_id]),
                      "b_solution_fails_a": cross_check(dirs[b.task_id], dirs[a.task_id])})

    report = {"repo": repo.path.name, "repo_version": repo.version(), "seed": seed, "requested": n,
              "generated": len(tasks), "valid": len(valid_ids), "seconds": round(time.time() - t0, 1),
              "tasks": results, "distinctness": pairs,
              "params": {t.task_id: t.params for t in tasks}}
    (out / "report.json").write_text(json.dumps(report, indent=2, default=list), encoding="utf-8", newline="\n")
    (out / "report.md").write_text(_markdown(report, tasks), encoding="utf-8", newline="\n")
    return report


def _markdown(rep: dict, tasks: list) -> str:
    rows = []
    for r in rep["tasks"]:
        c = r["checks"]
        ok = lambda k: "yes" if c.get(k) else "**NO**"
        rows.append(f"| {r['task_id']} | {r['title']} | {r['difficulty']} | {ok('rejects_start')} | "
                    f"{ok('solvable')} | {ok('stable')} | {r['mutation_score']} | {r['tests_total']} | "
                    f"{'valid' if r['valid'] else 'REJECTED'} |")
    total_m = sum(len(r["mutants"]) for r in rep["tasks"])
    killed = sum(m["killed"] for r in rep["tasks"] for m in r["mutants"])
    distinct = sum(p["a_solution_fails_b"] and p["b_solution_fails_a"] for p in rep["distinctness"])
    lines = [
        "# Task factory run", "",
        f"- Repository: `{rep['repo']}` at `{rep['repo_version']}`",
        f"- Seed {rep['seed']}: {rep['generated']} tasks generated, **{rep['valid']} valid**, in {rep['seconds']} s",
        f"- Known-wrong implementations rejected by the tests: **{killed}/{total_m}**",
        f"- Same-family task pairs whose reference solutions fail each other's tests: **{distinct}/{len(rep['distinctness'])}**",
        "",
        "| Task | Title | Difficulty | Untouched repo fails | Reference passes | Stable | Mutants killed | Tests | Status |",
        "|---|---|---|---|---|---|---|---|---|",
        *rows, "", "## Mutants per task", "",
    ]
    for r in rep["tasks"]:
        lines.append(f"**{r['task_id']}**: " + "; ".join(
            f"{'killed' if m['killed'] else 'SURVIVED'}: {m['description']}" for m in r["mutants"]))
        if r["skipped_mutants"]:
            lines.append(f"  (no scenario could expose: {', '.join(r['skipped_mutants'])})")
        lines.append("")
    lines += ["## Distinctness (same family)", "", "| A | B | A's solution fails B | B's solution fails A |",
              "|---|---|---|---|"]
    lines += [f"| {p['a']} | {p['b']} | {p['a_solution_fails_b']} | {p['b_solution_fails_a']} |"
              for p in rep["distinctness"]]
    return "\n".join(lines) + "\n"
