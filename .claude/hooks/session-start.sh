#!/bin/bash
# SessionStart hook for Claude Code on the web: installs the backend and
# frontend Python deps, and starts a local Postgres + Redis with the same
# credentials CI uses (.github/workflows/ci.yml), so `pytest` works in
# backend/ and frontend/ without Docker.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$root"

# --- Python: the same 3.14 as CI, one venv per app --------------------------
# The image's uv only knows 3.14.0rc2, which pydantic rejects; a newer uv
# (run through uvx, cached after the first session) fetches a final release.
uv() { uvx --quiet --from 'uv>=0.9' uv "$@"; }
uv python install --quiet 3.14
python="$(uv python find 3.14)"
for app in backend frontend; do
  if ! "$app/.venv/bin/python" -c 'import sys; assert sys.version_info >= (3, 14) and sys.version_info.releaselevel == "final"' 2>/dev/null; then
    uv venv --quiet --clear --python "$python" "$app/.venv"
  fi
  uv pip install --quiet --python "$app/.venv/bin/python" -r "$app/requirements-dev.txt"
done

# --- Postgres + Redis, credentials matching CI ------------------------------
export POSTGRES_USER=metalarm POSTGRES_PASSWORD=ci-postgres-password POSTGRES_DB=metalarm
pg_version="$(ls /usr/lib/postgresql | sort -n | tail -1)"
pg_ctlcluster "$pg_version" main status >/dev/null 2>&1 || pg_ctlcluster "$pg_version" main start
for _ in $(seq 30); do pg_isready -q -h localhost && break; sleep 1; done
su postgres -c "psql -qtAc \"SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'\"" | grep -q 1 \
  || su postgres -c "psql -qc \"CREATE ROLE $POSTGRES_USER LOGIN SUPERUSER PASSWORD '$POSTGRES_PASSWORD'\""
su postgres -c "psql -qtAc \"SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'\"" | grep -q 1 \
  || su postgres -c "createdb -O $POSTGRES_USER $POSTGRES_DB"

redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes >/dev/null

# --- Environment for the rest of the session --------------------------------
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  cat >> "$CLAUDE_ENV_FILE" <<ENV
export POSTGRES_USER=$POSTGRES_USER
export POSTGRES_PASSWORD=$POSTGRES_PASSWORD
export POSTGRES_DB=$POSTGRES_DB
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export REDIS_HOST=localhost
export REDIS_PORT=6379
export JWT_SECRET_KEY=local-only-secret-not-used-anywhere-else-0123456789abcdef
export LOG_LEVEL=warning
ENV
fi
