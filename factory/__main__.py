"""CLI.

  python -m factory generate --repo work/click --base 8.5.1 --out out --n 5 --seed 7
  python -m factory validate out/tasks/bytesize-01 --repo work/click --base 8.5.1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .families import FAMILIES
from .pipeline import run
from .repo import Repo
from .validate import validate

DEFAULT_REPO = Path("work/click")
DEFAULT_BASE = "cf19179e8e2fd54c601378cec9e0d21bb12b6fb1"  # click 8.5.1


def main() -> None:
    ap = argparse.ArgumentParser(prog="factory", description="Coding Task Factory for pallets/click (Harbor 0.25)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="generate, package and validate tasks")
    g.add_argument("--repo", type=Path, default=DEFAULT_REPO, help="local clone of pallets/click")
    g.add_argument("--base", default=DEFAULT_BASE, help="base commit or tag (default: click 8.5.1)")
    g.add_argument("--out", type=Path, default=Path("out"))
    g.add_argument("--n", type=int, default=5)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--families", default=",".join(FAMILIES), help=f"comma list of {', '.join(FAMILIES)}")
    g.add_argument("--no-validate", action="store_true")
    v = sub.add_parser("validate", help="validate one Harbor task folder")
    v.add_argument("task", type=Path)
    v.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    v.add_argument("--base", default=DEFAULT_BASE)
    a = ap.parse_args()

    repo = Repo(a.repo, a.base)
    if a.cmd == "generate":
        fams = [f.strip() for f in a.families.split(",") if f.strip()]
        unknown = set(fams) - set(FAMILIES)
        if unknown:
            ap.error(f"unknown families: {', '.join(sorted(unknown))}")
        rep = run(repo, a.out, a.n, a.seed, fams, not a.no_validate)
        print()
        print((a.out / "report.md").read_text(encoding="utf-8"))
        print(f"Tasks in {a.out / 'tasks'}  ({rep['valid']}/{rep['generated']} valid)")
    else:
        r = validate(repo, a.task)
        print(json.dumps({k: r[k] for k in ("task_id", "checks", "mutation_score", "valid")}, indent=2))


if __name__ == "__main__":
    main()
