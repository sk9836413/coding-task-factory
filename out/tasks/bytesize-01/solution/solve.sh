#!/bin/bash
# Oracle: apply the reference implementation.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
SOLUTION_DIR="${SOLUTION_DIR:-/solution}"
git -C "$APP_DIR" apply --whitespace=nowarn "$SOLUTION_DIR/solution.patch"
