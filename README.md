# MetalArm

Turn real goals, habits and gym workouts into RPG-style progression - quests,
workout tracking with personal records, XP, levels, ranks (E→S), a rewards
shop, and parties with a shared quest board.

Full-Python stack: **FastAPI** backend, **Reflex** frontend (compiles Python to
React/Next.js), Postgres, Redis, pgAdmin, all under Docker Compose.

> Visual direction is *inspired by* hunter-rank RPG aesthetics. All assets,
> copy, and art in this repo are original work - no copyrighted material.

> **Formerly LevelForge.** A few data-bearing identifiers deliberately keep
> the old name, because the existing data lives under them: the Docker volumes
> (`levelforge_postgres_data` etc., pinned in `docker-compose.yml`) and the
> Postgres role/database (`POSTGRES_USER` / `POSTGRES_DB` = `levelforge`).
> `LEVELFORGE_API_BASE_URL` is still read as a fallback for
> `METALARM_API_BASE_URL`.

---

## Quick start

```bash
cp .env.example .env
# Edit .env and replace every CHANGE_ME placeholder.
# Generate a real JWT secret:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose up -d --build
```

Schema migrations run automatically: the `migrate` service applies
`alembic upgrade head` and exits before the backend starts, so a fresh clone
comes up with a fully migrated database. It is idempotent, so it is safe on
every start.

Then check that it actually came up - don't assume:

```bash
docker compose ps
curl -s http://localhost:8000/health | python3 -m json.tool
```

A healthy response reports the **real** server versions it connected to:

```json
{
  "status": "ok",
  "service": "metalarm-api",
  "dependencies": {
    "postgres": {"connected": true, "server_version": "17.10"},
    "redis":    {"connected": true, "server_version": "8.10.1"}
  }
}
```

If a dependency is down, `/health` returns **503** and names it. It is never
hardcoded to "ok".

`/health` checks **readiness, not just liveness**: it also confirms the schema
is migrated to the revision this code expects. An un-migrated database answers
`SELECT 1` perfectly happily while every real query fails on a missing table,
so a connectivity-only check would report "ok" on a stack that cannot serve a
single request. When the schema is behind, the response is 503 and names the
fix:

```json
"schema": {
  "ready": false,
  "applied_revision": null,
  "expected_revision": "5dba70011569",
  "error": "database has never been migrated - run 'alembic upgrade head'"
}
```

## Services

| Service  | URL                     | Notes |
|---|---|---|
| Backend API | http://localhost:8000 | `/docs` for Swagger UI |
| Frontend    | http://localhost:3000 | Reflex (UI + state server, one port in prod) |
| pgAdmin     | http://localhost:5050 | Login with `PGADMIN_DEFAULT_EMAIL` / `PASSWORD` |
| Postgres    | `localhost:5434`      | Host port 5434; container-internal is 5432 |
| Redis       | `localhost:6379`      | |

Postgres, Redis and pgAdmin are published to **127.0.0.1 only**, not `0.0.0.0`,
so none of them is reachable from the LAN. Redis additionally requires a
password (`REDIS_PASSWORD`); without one it logs a warning that it "will accept
connections from any IP address on any network interface" and any process on
the machine could read the leaderboard cache.

**Why Postgres is on 5434:** the development machine runs a native macOS
Postgres on 5432. Change `POSTGRES_HOST_PORT` in `.env` if that isn't true for
you - the container-internal port stays 5432 either way, so the backend is
unaffected.

## Working on one half at a time

Every service is independently buildable, so a frontend problem never blocks
verifying the backend:

```bash
docker compose build backend
docker compose up -d postgres redis backend
docker compose logs -f backend

docker compose build frontend          # separately
```

## Local (non-Docker) development

```bash
# Backend
cd backend && python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # needs postgres+redis running

# Frontend
cd frontend && python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
reflex run                             # UI :3000, state server :8001
```

Reflex splits ports in dev but **requires a single port in prod** - the Docker
image serves both from 3000.

## Tests

The suite runs in its own container against a **separate** database that is
created and dropped per session, so it never touches development data. Test
dependencies live in the Dockerfile's `dev` stage and are absent from the
runtime image.

```bash
docker compose run --rm tests            # full suite
docker compose run --rm tests pytest tests/test_quests.py -v
```

There is also an end-to-end smoke test that drives a **running stack** over
real HTTP - every sprint's endpoints, plus ownership isolation - and cleans up
after itself:

```bash
docker compose up -d
python3 scripts/smoke_test.py
```

The two are complementary: pytest drives the app in-process for speed and
isolation, while the smoke test proves the deployed containers, network and
migrations actually serve requests.

### Browser end-to-end test

`scripts/e2e/` drives the real UI in your installed Chrome (headless, via
`playwright-core` - no browser download) against a running stack. It is the
only test that exercises Reflex's websocket events, hydration and the
client-side scripts: the full workout journey (log, PR moment, level-up,
edit, delete, refresh mid-workout, finish), routines, progress, the account
weight unit, profile and party boards - then sweeps every page at phone and
desktop width for errors and horizontal overflow, saving screenshots.

```bash
docker compose up -d
cd scripts/e2e && npm install && node workout_e2e.mjs      # screenshots -> $TMPDIR/metalarm-e2e
```

`CHROME_PATH=/path/to/chrome` overrides the browser. This is test tooling
only - the app itself still has no hand-written JS build.

## Database migrations

Alembic reads the database URL from the environment, never from `alembic.ini`,
so no credential is committed.

```bash
docker compose exec backend alembic current
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

`alembic check` reports whether the ORM models have drifted from the migrations:

```bash
docker compose exec backend alembic check      # "No new upgrade operations detected."
```

### After changing the XP curve

`level_progress.current_level` and `.rank` are **caches** of the curve in
`backend/app/core/leveling.py`; `total_xp` is the source of truth. Retuning the
curve leaves those columns stale until they are recomputed:

```bash
docker compose run --rm tests python -m scripts.recompute_progression --dry-run
docker compose run --rm tests python -m scripts.recompute_progression
```

### Exercise library

The workout module's shared exercise library is loaded by
`backend/scripts/import_exercises.py` from `backend/app/data/exercises.json`
(91 starter exercises). The `migrate` service runs it after every
`alembic upgrade head`; it upserts by slug, so repeat runs are a no-op. To load
a bigger dataset (JSON, or CSV with `;`-separated muscle groups):

```bash
docker compose run --rm tests python -m scripts.import_exercises --file path/to/big.csv --dry-run
docker compose run --rm tests python -m scripts.import_exercises --file path/to/big.csv
```

A bad row rejects the whole file. Exercises missing from the file are
reported, never deleted - workout history points at them.

Workout point values live only in `backend/app/core/workout_rules.py`. Awards
are snapshotted into the points ledger, so retuning never rewrites history.

## API contract

`docs/api-contract.md` is **generated** from the live OpenAPI spec - it cannot
silently drift from the code:

```bash
docker compose up -d backend
python3 scripts/generate_api_contract.py
```

The frontend reads that file as the source of truth for endpoint shapes.

## Notes for contributors

- **No hand-written JS/TS.** Reflex owns the Node/React build entirely.
  `frontend/reflex.lock/` (`package.json` + `bun.lock`) is **generated by
  Reflex and committed on purpose** for reproducible builds - never hand-edit
  it; change dependencies through Reflex.
  Why this is safe, given the predecessor project died on exactly this: the old
  break was npm's, where a macOS-generated `package-lock.json` pinned only the
  host's optional dep and `npm ci` in a Linux/musl container then failed on the
  missing `@rollup/rollup-linux-arm64-musl` (npm/cli#4828). Bun's lockfile
  records **all** platform variants (`linux-arm64-musl`, `linux-arm64-gnu`,
  `darwin-arm64`, `win32`, ...), so the same file resolves correctly on every
  platform. Verified: this lockfile was generated on macOS/arm64 and built
  cleanly inside the linux/arm64 container.
- **Do not use `passlib`.** It fails against `bcrypt>=5` and depends on the
  stdlib `crypt` module removed in Python 3.13+ (PEP 594). Use `bcrypt`
  directly; use `PyJWT` for tokens.
- Secrets come from `.env` only. `.env` is gitignored; commit `.env.example`
  with placeholders.
- `REFLEX_API_URL` is compiled into the JS bundle - changing it needs
  `docker compose build frontend`, not just a restart.
- **Inline scripts must not write text or classes into React-owned nodes.**
  The workout rest timer and clock (`components/rest_timer.py`) set only
  attributes React never manages, and CSS shows them via
  `content: attr(...)`. Writing `textContent` into server-rendered nodes
  before hydration throws React error #418 (hydration mismatch).

## Docs

- `docs/api-contract.md` - generated endpoint reference
- `docs/workouts-api.md` - gym workout module: behaviour, payload examples, and
  the rules the frontend must follow (frontend handoff)
- `docs/data-model.md` - the schema and why it is shaped that way
- `docs/progress-log.md` - session-by-session log; append an entry every session
