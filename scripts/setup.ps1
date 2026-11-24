# One-time setup on Windows (PowerShell). Needs: git, uv (https://docs.astral.sh/uv/).
# Creates .venv (Python 3.12) with Harbor 0.25 and pytest, and clones pallets/click at the pinned base commit.
$ErrorActionPreference = "Stop"
$Base = "cf19179e8e2fd54c601378cec9e0d21bb12b6fb1"  # click 8.5.1

uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt

if (-not (Test-Path work\click\.git)) {
    git clone https://github.com/pallets/click.git work\click
}
git -C work\click -c advice.detachedHead=false checkout --quiet $Base
git -C work\click log -1 --format="click at %H %d"
