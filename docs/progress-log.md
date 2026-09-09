# LevelForge - Progress Log

Both agents append an entry at the end of **every** session: what changed,
what's blocked, what the other agent needs to know. Newest entries at the top.

Entry format:
```
## YYYY-MM-DD - <Agent> (<model>)
**Changed:** ...
**Verified:** ...   <- real command output only, never assumptions
**Blocked:** ...
**Other agent needs to know:** ...
```

---

## 2026-09-10 (2) - Backend Agent (Opus) - schema + first migration

**Changed**
- `docs/data-model.md` signed off -> **CONFIRMED**. Decisions: multi-party
  membership ALLOWED; native PG enums only for genuinely stable sets
  (`rank`, `quest_status`, `party_role`) with `recurrence` as VARCHAR+CHECK;
  email uniqueness via `email_normalized`, not CITEXT.
- ORM models added under `backend/app/models/` (10 tables). `alembic/env.py`
  now imports them so autogenerate can see them.
- `backend/app/core/leveling.py`: XP curve + rank thresholds, isolated so
  Section 11's open curve question stays cheap. PLACEHOLDER numbers.
- First migration: **`5dba70011569`**.

**Verified (real output)**
- `upgrade head` -> `downgrade base` -> `upgrade head` all clean; `alembic check`
  reports **no drift**, so models match the DB exactly.
- 10 tables, 3 enum types with correct lowercase values, 2 UNIQUE anti-farm
  constraints, 17 CHECK constraints - all confirmed present in `pg_constraint`.
- Guarantees tested by attempting what they forbid (all rolled back):
  double-completing a daily quest **blocked**; completing it the next day
  **succeeded**; case-variant email **blocked**; negative points **blocked**;
  `recurrence='monthly'` **blocked**; `xp_reward=999999` **blocked**;
  bogus enum value **blocked**.
- Backend image rebuilt; container reports `5dba70011569 (head)` and 10 models.
  All 5 services healthy; `/health` reports real PG 17.10 + Redis 8.10.1.

**Two bugs caught before shipping**
- `Enum(QuestStatus)` persists the member NAME (`ACTIVE`), not `.value`
  (`active`), diverging from `server_default` and failing the migration.
  Fixed via a shared `pg_enum()` helper using `values_callable`. Hidden by
  `Rank`, whose names equal its values.
- Autogenerate's `downgrade()` drops tables but **not** native enum types, so
  the next upgrade fails with `type "rank" already exists`. `downgrade()` now
  carries a hand-added `DROP TYPE IF EXISTS` loop.

**Also**
- Renaming the project folder broke both venvs (venv console scripts hardcode
  an absolute shebang). Both were recreated. If you move the repo again,
  recreate `backend/.venv` and `frontend/.venv`; Docker is unaffected.

**Blocked**
- Nothing.

**Other agent needs to know**
- **Frontend Agent:** the schema is settled, but **no API endpoints exist yet**
  beyond `/` and `/health` - `docs/api-contract.md` is still just those two.
  Sprint 2 UI must run against a stub until auth/quest endpoints land.
  Useful shapes to design against: a quest is completed **per period**, so the
  UI needs "done today" state rather than a boolean `completed`; XP is
  cumulative with level/rank derived; ranks are `E,D,C,B,A,S` lowercase-valued
  enums except rank which is uppercase.
- **Backend Agent (next):** Sprint 2 = auth (signup/login/JWT with bcrypt +
  PyJWT, never passlib) and quest CRUD, including `period_key` derivation in
  the user's timezone. Regenerate the contract after every endpoint change.

---

## 2026-09-10 - Setup / Backend Agent (Opus)

**Changed**
- Fresh `git init` (branch `main`). Scaffolded `backend/`, `frontend/`, `docs/`,
  `scripts/`, root `docker-compose.yml`, `.env.example`, `.gitignore`,
  `.dockerignore`.
- Backend: FastAPI app (`backend/app/`) with env-driven settings
  (`core/config.py`), SQLAlchemy engine + `DeclarativeBase` (`db/session.py`),
  Redis client (`db/redis_client.py`), and `/health`.
- Alembic wired to read the DB URL from the environment (`alembic/env.py`), so
  no credential is ever committed. **No migration authored yet** - that's the
  next task.
- Frontend: Reflex app with a placeholder Stat Panel. Plugins declared
  explicitly in `rxconfig.py` (theme moved to `RadixThemesPlugin`).
- Compose: 5 services, each independently buildable. `scripts/generate_api_contract.py`
  generates `docs/api-contract.md` from the live `/openapi.json`.

**Verified (real output)**
- All 5 services up; postgres/redis/backend report `(healthy)`.
- `GET /health` -> `200` with **real** values:
  `postgres.server_version 17.10`, `redis.server_version 8.10.1`.
- **Negative test:** stopped Postgres -> `/health` returned `503`
  `{"status":"degraded","postgres":{"connected":false,...}}` while Redis stayed
  `true`. Restarted Postgres -> recovered to `200` with no backend restart
  (`pool_pre_ping`). The health check is genuinely live, not hardcoded.
- `GET /` `200`, `/docs` `200`, `/openapi.json` `200`.
- Frontend `:3000` -> `200`, server-rendering real content (HUNTER / LEVEL /
  RANK / "Level up your life"), 8910 bytes.
- pgAdmin `:5050` -> `200`.
- `alembic current` connects (`PostgresqlImpl`), 0 revisions - as expected.
- `psql`: `levelforge` db as `levelforge` user, PostgreSQL 17.10 on **aarch64**
  (native arm64, no emulation). Redis SET/GET/DEL round-trip OK.

**Decisions worth knowing**
- **passlib is banned from this project.** It hard-fails against bcrypt>=5
  during backend detection and depends on stdlib `crypt`, removed in Python
  3.13+ (PEP 594). We call `bcrypt` directly. **PyJWT** replaces `python-jose`
  (both verified working on 3.14). Do not reintroduce passlib.
- **Reflex prod is single-port.** `reflex/reflex.py:358` rejects
  `frontend_port != backend_port` in prod/preview. Local dev = 3000 (UI) +
  8001 (state server); Docker prod = **3000 for both**.
- `REFLEX_API_URL` is baked into the JS bundle at **build** time. Changing it
  requires `docker compose build frontend`, not just a restart.
- Host `5432` is taken by a native macOS Postgres, so LevelForge's Postgres
  maps to host **5434**. Container-internal is still 5432.
- pgAdmin rejects `.local` emails (RFC 6762 special-use TLD). Default admin
  email is `admin@levelforge.dev`.
- The predecessor `fuelforge-*` containers were **stopped** (not removed);
  their volumes and data are intact.
- `frontend/reflex.lock/{package.json,bun.lock}` is Reflex-generated and **is
  committed** deliberately. Checked specifically because the predecessor died
  on a lockfile: `bun.lock` records every platform variant
  (`lightningcss-linux-arm64-musl`, `-linux-arm64-gnu`, `-darwin-arm64`,
  win32...), unlike npm's host-only pinning that caused
  `@rollup/rollup-linux-arm64-musl not found`. Generated on macOS/arm64, built
  clean in the linux/arm64 container. Do not hand-edit it.

**Blocked**
- Nothing.

**Other agent needs to know**
- **Frontend Agent:** the Reflex scaffold builds and runs in Docker; build on
  `frontend/levelforge/`. Keep animation code in `components/`, separate from
  state/data per Section 7. Read `docs/api-contract.md` for endpoint shapes -
  right now it only has `/` and `/health`, so Sprint 2 UI must run against a
  stub until auth/quest endpoints land.
- **Backend Agent (next session):** finalize the Section 5 schema, get it
  confirmed, then author the first Alembic migration. Sprint 2 = auth + quest
  CRUD. Regenerate the contract after every endpoint change.
