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

## 2026-09-10 (3) - Backend Agent (Opus) - Sprint 2: auth + quest CRUD

**Changed**
- Committed the Sprint 1.5 schema work that was sitting staged (`de17a20`).
- **Auth:** `core/security.py` (bcrypt + PyJWT), `api/deps.py`
  (`get_current_user`), `api/routes/auth.py`. Endpoints: `POST /auth/signup`,
  `POST /auth/login` (JSON - use this from Reflex), `POST /auth/token`
  (form-encoded, only so /docs' Authorize button works), `GET /auth/me`.
- **Quests:** `api/routes/quests.py` - list/create/get/patch/delete plus
  `POST /quests/{id}/complete`. All mounted under **`/api/v1`**.
- `core/periods.py` derives `period_key` in the USER's timezone;
  `core/progression.py` applies XP/points/level/rank/streak.
- **Tests:** 66 pytest tests under `backend/tests/`. New Dockerfile `dev`
  stage + profiled `tests` compose service: `docker compose run --rm tests`.
- `docs/api-contract.md` regenerated from the live app: **11 endpoints**.

**Verified (real output)**
- `66 passed` in 9.97s. All 5 services `(healthy)`; `/health` 200 with real
  PG 17.10 + Redis 8.10.1; `/`, `/docs`, `/openapi.json`, `:3000`, `:5050` all
  responding. `alembic check` still reports no drift (no model changes).
- **Concurrency, the important one:** 20 simultaneous completions of one quest
  -> `{409: 19, 200: 1}`, exactly 500 XP awarded (not 10,000), exactly 1
  completion row. The lost-update and XP-farming races are genuinely closed.
- **Ownership:** user B gets 404 (not 403) on A's quest for GET/PATCH/DELETE/
  complete, and earns 0 XP from it. B's board shows 0 of A's quests.
- **Timezones:** same instant, `America/New_York` -> `2026-09-09` and
  `Asia/Tokyo` -> `2026-09-10`. Moving a user across that boundary lets the
  daily quest be completed again and extends the streak to 2 - both rows
  coexist under the UNIQUE constraint, exactly as intended.
- **Token attacks all rejected:** wrong secret, `alg=none`, expired (distinct
  message, deliberately), garbage, valid-signature-but-deleted-user, absent.
- Unknown-email vs wrong-password login differ by **2.8%** in latency
  (176.1ms vs 171.3ms) and return byte-identical bodies - no enumeration
  oracle. Our `JWT_SECRET_KEY` is 64 bytes.
- `alembic check` clean; contract generator is idempotent apart from its
  timestamp line; runtime image confirmed to contain **no** pytest/httpx.

**Three bugs caught before shipping**
- `EmailStr` needs the separate **`email-validator`** package; without it
  every schema using it fails at IMPORT time. Now pinned (`2.3.0`).
- The new Dockerfile `dev` stage is the LAST stage, and Docker builds the last
  stage by default - the shipped backend image would have silently gained
  pytest. Compose now pins `target: runtime` explicitly.
- In `conftest.py`, `import app.models` rebinds the name `app` from the
  FastAPI instance to the package, so `app.dependency_overrides` raised
  AttributeError. Use `from app import models` instead.

**Decisions worth knowing**
- **bcrypt 5.0 RAISES past 72 bytes** (it does not truncate). Password length
  is validated in BYTES at the schema layer, so 30 emoji (120 bytes) is a
  clean 422 rather than a 500. Truncating instead would make every password
  sharing a 72-byte prefix open the same account.
- Completion order is: lock `level_progress` FOR UPDATE -> insert completion
  -> apply XP -> commit. Same lock order for every writer, so no deadlock, and
  the UNIQUE constraint (not a Python pre-check) is what stops double-awards.
- `xp_awarded` is snapshotted at completion time - raising a quest's reward
  later does not rewrite history.
- Deleting a quest cascades its completions but does NOT claw back XP:
  `total_xp` is cumulative and the XP was earned. Archive to keep the trail.
- Access tokens only, no refresh tokens yet. `jti` is in the payload so a
  Redis denylist can revoke individual tokens later.
- Test emails must not use `.test`/`.local` - email-validator rejects RFC 6761
  special-use TLDs, the same trap pgAdmin hit in Sprint 1.
- **Known edge case, not a bug:** a user who changes timezone can re-complete
  a daily quest in the overlap. Inherent to per-user-timezone periods; flagging
  rather than fixing, since the alternative (server-fixed days) is worse.

**Blocked**
- Nothing.

**Other agent needs to know**
- **Frontend Agent: real endpoints now exist.** Regenerated
  `docs/api-contract.md` has all 11 with full request/response schemas. The
  stub is no longer needed for auth or quests.
  - Base path is **`/api/v1`**. Log in via `POST /api/v1/auth/login` with JSON
    `{email, password}` -> `{access_token, token_type, expires_in}`. Send it
    as `Authorization: Bearer <token>`. Tokens last 60 min by default; on
    expiry you get 401 with detail `"Token has expired"` - re-login on that.
  - A quest is **never** "completed" outright. Render from
    `completed_in_current_period` + `current_period_key`, both returned per
    quest and computed in the user's timezone.
  - `POST /quests/{id}/complete` returns `progression` carrying
    **`leveled_up`** and **`ranked_up`** booleans plus before/after level and
    rank - drive the Section 7 level-up animation off those directly, no
    diffing needed. A repeat completion is a **409**, which the UI should
    treat as "already done this period", not an error state.
  - Signup takes an IANA `timezone` (e.g. `America/New_York`); an unknown zone
    is a 422. This drives daily resets and streaks, so collect it at signup.
- **Backend Agent (next):** Sprint 3 = XP curve + rank thresholds. The numbers
  in `core/leveling.py` are still PLACEHOLDERS and Section 11's curve question
  is still open - settle it with the user before tuning. Retuning is safe:
  `total_xp` is the source of truth and level/rank are re-derived.

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
