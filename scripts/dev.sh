#!/usr/bin/env bash
# Everything needed to build, run and test MetalArm on a Mac, in one place.
#
#   scripts/dev.sh setup        install every dependency (idempotent)
#   scripts/dev.sh up           start the stack (postgres, redis, backend, web)
#   scripts/dev.sh web          rebuild + restart the web image after a frontend edit
#   scripts/dev.sh backend      backend test suite (428 tests, ~2 min)
#   scripts/dev.sh frontend     frontend tier tests (fast, no stack needed)
#   scripts/dev.sh ios [filter] iOS tests on a booted simulator, CI-style
#   scripts/dev.sh e2e          browser end-to-end, both suites
#   scripts/dev.sh smoke        HTTP smoke test against the running stack
#   scripts/dev.sh unlimit      clear the signup rate limit (5 per IP per hour)
#   scripts/dev.sh record [what] record the demo: ios, web, or both
#
# The point of this file is that none of it has to be worked out twice: the
# environment variables the tests need, the simulator flags that stop xcodebuild
# hanging, and which changes need an image rebuild before they are visible.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

UI_URL="${METALARM_UI:-http://localhost:3000}"

# The compose stack publishes postgres on a non-default host port, and the
# in-container hostnames ("postgres", "redis") mean nothing from the host.
db_env() {
  set -a; . "$root/.env"; set +a
  export POSTGRES_HOST=localhost POSTGRES_PORT="${POSTGRES_HOST_PORT:-5434}"
  export REDIS_HOST=localhost REDIS_PORT="${REDIS_HOST_PORT:-6379}"
}

# An iPhone simulator that is actually BOOTED. xcodebuild will otherwise clone
# simulators to test in parallel, and a clone that is still booting fails with
# "Error resuming pid ... signal 19", then spends ten minutes in simctl
# diagnose before it says so. CI boots one and disables parallel testing for
# the same reason (.github/workflows/ios.yml).
booted_iphone() {
  local udid
  udid=$(xcrun simctl list devices available --json \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)["devices"]
best=None
for runtime, items in d.items():
    if "iOS" not in runtime: continue
    for dev in items:
        if not dev["name"].startswith("iPhone"): continue
        if dev["state"] == "Booted": print(dev["udid"]); raise SystemExit
        best = best or dev["udid"]
print(best or "")')
  [ -n "$udid" ] || { echo "No iPhone simulator available" >&2; exit 1; }
  xcrun simctl boot "$udid" 2>/dev/null || true
  xcrun simctl bootstatus "$udid" -b >/dev/null
  echo "$udid"
}

case "${1:-}" in
setup)
  echo "==> backend venv"
  [ -d backend/.venv ] || python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements-dev.txt
  echo "==> frontend venv"
  [ -d frontend/.venv ] || python3 -m venv frontend/.venv
  frontend/.venv/bin/pip install -q -r frontend/requirements-dev.txt
  echo "==> browser end-to-end"
  (cd scripts/e2e && npm install --silent)
  echo "==> simulator"
  booted_iphone >/dev/null && echo "    booted"
  echo "Done. 'scripts/dev.sh up' next."
  ;;
up)
  docker compose up -d
  ;;
web)
  # A frontend edit is invisible until the image is rebuilt: the stack serves
  # a compiled Reflex export, not the working tree.
  docker compose build frontend && docker compose up -d frontend
  ;;
backend)
  db_env
  cd backend && .venv/bin/python -m pytest -p no:warnings --color=no "${@:2}"
  ;;
frontend)
  frontend/.venv/bin/python -m pytest frontend/tests "${@:2}"
  ;;
ios)
  udid=$(booted_iphone)
  filter=()
  [ $# -gt 1 ] && filter=(-only-testing:"$2")
  set +e
  xcodebuild test -scheme MetalARM -project ios/MetalARM.xcodeproj \
    -destination "platform=iOS Simulator,id=$udid" \
    -parallel-testing-enabled NO "${filter[@]}" \
    CODE_SIGNING_ALLOWED=NO 2>&1 | tee /tmp/metalarm-ios.log \
    | grep -E "Test Case.*(passed|failed)|error:|Executed |\*\* TEST"
  code=${PIPESTATUS[0]}
  set -e
  echo "Full log: /tmp/metalarm-ios.log"
  exit "$code"
  ;;
e2e)
  cd scripts/e2e && node workout_e2e.mjs && node rank_up_e2e.mjs
  ;;
smoke)
  python3 scripts/smoke_test.py "${@:2}"
  ;;
record)
  # Videos land in ~/Desktop/MetalArm Recordings/<today>/, never over an
  # older take.
  what="${2:-both}"
  if [ "$what" = "web" ] || [ "$what" = "both" ]; then
    echo "==> web: the rank-up escalation"
    # The stack serves a compiled export, so record the CURRENT frontend.
    docker compose build frontend >/dev/null && docker compose up -d frontend >/dev/null
    # A just-restarted container answers the port before it can serve a page;
    # the recorder's first goto times out against it.
    for _ in $(seq 1 60); do
      curl -sfo /dev/null "$UI_URL/login" && break
      sleep 2
    done
    "$0" unlimit >/dev/null
    (cd scripts/e2e && node rank_up_reel.mjs)
  fi
  if [ "$what" = "ios" ] || [ "$what" = "both" ]; then
    echo "==> iOS: the full tour"
    scripts/record_tour.sh
  fi
  ;;
unlimit)
  set -a; . "$root/.env"; set +a
  docker exec metalarm-redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" \
    --scan --pattern 'ratelimit:signup-ip:*' 2>/dev/null \
    | while read -r key; do
        docker exec metalarm-redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" del "$key" >/dev/null
      done
  echo "Signup rate limit cleared."
  ;;
*)
  sed -n '2,20p' "$0"
  exit 1
  ;;
esac
