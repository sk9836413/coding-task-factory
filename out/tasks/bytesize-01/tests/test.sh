#!/bin/bash
# Verifier (runs in a fresh container at base_commit):
#   1. apply the agent's work (collected as /logs/artifacts/agent.patch),
#   2. restore the repository's original tests so they cannot be edited away,
#   3. run feature + regression tests, 4. grade (tests/grade.py).
APP_DIR="${APP_DIR:-/app}"
TESTS_DIR="${TESTS_DIR:-/tests}"
LOGS_DIR="${LOGS_DIR:-/logs}"
PYTHON="${PYTHON:-python}"
BASE_COMMIT="cf19179e8e2fd54c601378cec9e0d21bb12b6fb1"
OUT="$LOGS_DIR/verifier"
mkdir -p "$OUT"
cd "$APP_DIR" || { echo 0.0 > "$OUT/reward.txt"; exit 0; }

PATCH="$LOGS_DIR/artifacts/agent.patch"
if [ -s "$PATCH" ]; then
  if ! git apply --whitespace=nowarn "$PATCH" 2> "$OUT/apply.log"; then
    echo "agent patch did not apply" | tee -a "$OUT/apply.log"
    echo 0.0 > "$OUT/reward.txt"
    exit 0
  fi
fi
git checkout --quiet "$BASE_COMMIT" -- tests
cp "$TESTS_DIR/test_task_feature.py" tests/test_task_feature.py

HARBOR_REPORT="$OUT/test_outcomes.json" PYTHONPATH="$APP_DIR/src${PATHSEP:-:}$TESTS_DIR" PYTHONDONTWRITEBYTECODE=1 \
  "$PYTHON" -m pytest -q -p no:cacheprovider -p harbor_report tests > "$OUT/pytest.log" 2>&1
"$PYTHON" "$TESTS_DIR/grade.py" "$TESTS_DIR" "$OUT/test_outcomes.json" "$OUT"
