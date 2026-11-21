"""CLI.

  python -m factory generate --repo sample_repo --out out --n 6 --seed 7
  python -m factory validate out/tasks/promo-01
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .families import FAMILIES
from .pipeline import run
from .validate import validate


def main() -> None:
    ap = argparse.ArgumentParser(prog="factory", description="Coding Task Factory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="generate, package and validate tasks")
    g.add_argument("--repo", type=Path, default=Path("sample_repo"))
    g.add_argument("--out", type=Path, default=Path("out"))
    g.add_argument("--n", type=int, default=6)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--families", default=",".join(FAMILIES), help=f"comma list of {', '.join(FAMILIES)}")
    g.add_argument("--no-validate", action="store_true")
    v = sub.add_parser("validate", help="validate one Harbor task folder")
    v.add_argument("task", type=Path)
    a = ap.parse_args()

    if a.cmd == "generate":
        fams = [f.strip() for f in a.families.split(",") if f.strip()]
        unknown = set(fams) - set(FAMILIES)
        if unknown:
            ap.error(f"unknown families: {', '.join(sorted(unknown))}")
        rep = run(a.repo, a.out, a.n, a.seed, fams, not a.no_validate)
        print((a.out / "report.md").read_text(encoding="utf-8"))
        print(f"Tasks in {a.out / 'tasks'}  ({rep['valid']}/{rep['generated']} valid)")
    else:
        r = validate(a.task)
        print(json.dumps({k: r[k] for k in ("task_id", "checks", "mutation_score", "valid")}, indent=2))


if __name__ == "__main__":
    main()
