"""The target repository at its pinned base commit: reading files, scratch clones, patches, baseline tests."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import assets


def git(*args: str, cwd: Path, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


class Repo:
    """A local clone of pallets/click (or another allowed repo) checked out at a pinned base commit."""

    def __init__(self, path: Path, base: str, url: str = "https://github.com/pallets/click.git",
                 name: str = "pallets/click", license: str = "BSD-3-Clause"):
        self.path = Path(path).resolve()
        self.url, self.name, self.license = url, name, license
        if not (self.path / ".git").exists():
            raise SystemExit(f"{self.path} is not a git clone. Run scripts/setup.ps1 (or setup.sh) first.")
        self.base = git("rev-parse", f"{base}^{{commit}}", cwd=self.path).strip()
        if not re.fullmatch(r"[0-9a-f]{40}", self.base):
            raise SystemExit(f"Could not resolve base commit {base!r}")
        self.tag = git("describe", "--tags", "--exact-match", self.base, cwd=self.path, check=False).strip() or None

    def read(self, rel: str) -> str:
        """File content at the base commit, regardless of what is checked out."""
        return git("show", f"{self.base}:{rel}", cwd=self.path)

    def scratch(self) -> Path:
        """A throwaway clone at the base commit (shares objects, so it is fast)."""
        d = Path(tempfile.mkdtemp(prefix="tf-click-"))
        git("clone", "--quiet", "--shared", "--no-checkout", str(self.path), str(d / "app"), cwd=d)
        git("-c", "advice.detachedHead=false", "checkout", "--quiet", self.base, cwd=d / "app")
        return d

    def patch_for(self, files: dict[str, str]) -> str:
        """Unified diff (base -> files) that `git apply` accepts."""
        d = self.scratch()
        try:
            app = d / "app"
            for rel, content in files.items():
                p = app / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8", newline="\n")
            git("add", "-A", cwd=app)
            return git("diff", "--cached", "--binary", self.base, cwd=app)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def baseline_tests(self, python: str, cache_dir: Path) -> list[str]:
        """Node ids of every test that passes at the base commit (the pass_to_pass list)."""
        cache = cache_dir / f"pass_to_pass-{self.base[:12]}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        d = self.scratch()
        try:
            app, tests = d / "app", d / "tests"
            tests.mkdir()
            (tests / "harbor_report.py").write_text(assets.REPORT_PLUGIN, encoding="utf-8", newline="\n")
            env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(app / "src"), str(tests)]),
                   "HARBOR_REPORT": str(d / "report.json"), "PYTHONDONTWRITEBYTECODE": "1"}
            subprocess.run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "harbor_report", "tests"],
                           cwd=app, env=env, capture_output=True, timeout=900)
            outcomes = json.loads((d / "report.json").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(d, ignore_errors=True)
        passed = sorted(n for n, o in outcomes.items() if o == "passed")
        if not passed:
            raise SystemExit("No tests passed at the base commit; check the Python environment.")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(passed, indent=0), encoding="utf-8")
        return passed
