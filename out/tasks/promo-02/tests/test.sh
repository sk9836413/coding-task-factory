#!/bin/bash
# Verifier: feature tests + the repo's original tests. Reward 1 only if all pass.
APP_DIR="${APP_DIR:-/app}"
TESTS_DIR="${TESTS_DIR:-/tests}"
LOGS_DIR="${LOGS_DIR:-/logs}"
PYTHON="${PYTHON:-python}"
mkdir -p "$LOGS_DIR/verifier"
cd "$APP_DIR"
PYTHONPATH="$APP_DIR" PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m pytest -q -p no:cacheprovider \
  "$TESTS_DIR/test_feature.py" "$TESTS_DIR/regression" > "$LOGS_DIR/verifier/pytest.log" 2>&1
if [ $? -eq 0 ]; then
  echo 1 > "$LOGS_DIR/verifier/reward.txt"
else
  echo 0 > "$LOGS_DIR/verifier/reward.txt"
fi
