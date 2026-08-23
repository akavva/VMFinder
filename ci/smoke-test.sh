#!/usr/bin/env bash
# Boots a built binary against a throwaway configuration and asserts it
# serves HTTP 200 on port 5000.
#
# The configured vCenter (127.0.0.1) is deliberately unreachable: this
# asserts the app still boots and serves with zero reachable vCenters, which
# is both the state a first-time user is in and something the app must never
# regress on. VMFINDER_HOME is pointed at a scratch dir so a real
# ~/.config/vmfinder is never touched.
#
# Usage: ci/smoke-test.sh [path-to-binary]     (default: dist/vmfinder)
set -uo pipefail
cd "$(dirname "$0")/.."

BINARY="${1:-dist/vmfinder}"
PYTHON="${PYTHON:-python3}"

VMFINDER_HOME="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/vmfinder-smoke-home"
rm -rf "$VMFINDER_HOME"
mkdir -p "$VMFINDER_HOME"
export VMFINDER_HOME

VMFINDER_ADMIN_HASH="$("$PYTHON" -c "import hashlib; print(hashlib.sha256(b'ci-test-password').hexdigest())")"
export VMFINDER_ADMIN_HASH
export VC1_NAME=CI-TestVC
export VC1_IP=127.0.0.1
export VC1_USER=ci-user
export VC1_PASS=ci-pass
export VC1_PORT=443

stdout_log="$VMFINDER_HOME/stdout.log"
stderr_log="$VMFINDER_HOME/stderr.log"

"$BINARY" > "$stdout_log" 2> "$stderr_log" &
pid=$!

ok=0
for _ in $(seq 1 20); do
    sleep 1
    status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:5000/ || true)"
    if [ "$status" = "200" ]; then
        ok=1
        break
    fi
done

kill -9 "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true

echo "----- stdout -----"
cat "$stdout_log" 2>/dev/null || true
echo "----- stderr -----"
cat "$stderr_log" 2>/dev/null || true

if [ "$ok" != "1" ]; then
    echo "FAIL: $BINARY did not respond with HTTP 200 on port 5000 within 20 seconds"
    exit 1
fi

echo "Smoke test passed: $BINARY served HTTP 200 on port 5000"
