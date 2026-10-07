#!/usr/bin/env bash
# A brand-new demo database, migrated and seeded, for one take of the film.
#
#   scripts/demo/seed_fresh.sh <email> <password>
#
# Uses its OWN database (metalarm_demo), never the dev one, and recreates it
# every time: a take changes the account (a quest completed, a duel judged,
# the streak notice seen), so the next take must start from the same place.
# Leaves backend + frontend running against it.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
EMAIL="$1"; PASSWORD="$2"
export POSTGRES_DB=metalarm_demo
user=$(grep '^POSTGRES_USER=' .env | cut -d= -f2)

docker compose up -d postgres redis >/dev/null 2>&1
docker compose stop backend >/dev/null 2>&1 || true
docker compose exec -T postgres psql -U "$user" -d postgres -qc \
  "DROP DATABASE IF EXISTS metalarm_demo WITH (FORCE)" -c "CREATE DATABASE metalarm_demo" >/dev/null
# `up` reruns the migrate service (schema + library + seeds) before backend.
docker compose up -d backend frontend >/dev/null 2>&1
for _ in $(seq 1 60); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' localhost:8000/health)" = 200 ] && break
  sleep 3
done
scripts/dev.sh unlimit >/dev/null 2>&1 || true
docker compose run --rm -v "$root/backend/scripts:/app/scripts" backend \
  python -m scripts.seed_demo --email "$EMAIL" --password "$PASSWORD" 2>/dev/null | tail -1
