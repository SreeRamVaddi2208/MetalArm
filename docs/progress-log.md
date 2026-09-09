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

## 2026-09-10 (5) - Backend Agent (Opus) - Sprint 4: rewards wallet + shop

**Changed**
- Rewards shop live under **`/api/v1/rewards`**, using the `reward_items` /
  `reward_redemptions` tables that have sat unused since Sprint 1.5. No schema
  change was needed and `alembic check` still reports no drift.
- Endpoints: `GET/POST /rewards`, `GET/PATCH/DELETE /rewards/{id}`,
  **`POST /rewards/{id}/redeem`**, `GET /rewards/wallet`,
  `GET /rewards/redemptions`.
- Points are EARNED on quest completion (Sprint 2) and SPENT here. The spend
  path mirrors the completion path exactly: lock `level_progress` FOR UPDATE,
  then check balance, then insert + debit in one transaction.
- Contract regenerated: **19 endpoints, 22 schemas**. 118 tests (was 92).

**Verified (real output)**
- `118 passed`. All 5 services healthy, `/health` 200, `alembic check` clean.
- **Double-spend race closed.** 20 simultaneous redeems of an 80-point reward
  against a 100-point balance -> `{409: 19, 200: 1}`, final balance **20**,
  exactly **1** redemption row. Same shape as the Sprint 2 completion race.
- **CHECK is a genuine backstop**, not decoration: a raw
  `UPDATE level_progress SET points_balance = -1` in psql, bypassing the app
  entirely, is rejected by `ck_progress_points_non_negative`.
- Deleting a redeemed reward returns a clean **409** naming the count and
  pointing at deactivation - not a 500 from the FK. Deactivating instead works
  and the ledger survives.
- Sequential overdraw guard: five 30-point redeems against 100 points give
  `[200, 200, 200, 409, 409]`, balance 10.
- Repricing a reward after redemption leaves `points_spent` at the price
  actually paid.

**Design decisions worth knowing**
- **`ON DELETE RESTRICT` is load-bearing.** A reward with redemption history
  cannot be deleted, because that would erase the record of points already
  spent. The app checks first and returns a 409 explaining the alternative;
  deactivation (`PATCH is_active=false`) hides it from the shop and keeps the
  ledger. This is the opposite of quests, which hard-delete and cascade.
- `point_cost >= 1` is enforced in the schema as well as the DB - a zero-cost
  reward is a free infinite loop.
- `affordable` and `times_redeemed` are computed per request; the counts come
  from ONE grouped query, so the shop's cost does not grow per reward.
- Redemption is **not reversible** - there is no un-redeem or refund endpoint.
  Nothing in the brief calls for one; flagging in case that is wanted later.

**One bug caught before shipping**
- FastAPI matches routes in DECLARATION order, so `/rewards/wallet` and
  `/rewards/redemptions` declared after `/rewards/{reward_id}` would be parsed
  as UUIDs and 422. They are declared first, with a comment saying why, and a
  parametrized regression test pins it.

**A real asymmetry the frontend must not paper over**
- `GET /rewards/wallet` returns `points_balance`, `total_points_earned` and
  `total_points_spent`. **They do not always reconcile.** Deleting a quest
  cascades its completions away, so `total_points_earned` drops while the
  balance correctly does not - the points were genuinely earned and may
  already be spent. Verified: earn 100, spend 80, delete the earning quest ->
  `balance=20, earned=0, spent=80`.
  **Render `points_balance`. Never render `earned - spent` as the balance, and
  do not treat a mismatch as corruption.** Redemptions never vanish this way
  (their FK is RESTRICT); only the earned side can.

**Blocked**
- Nothing.

**Other agent needs to know**
- **Frontend Agent - the Rewards Shop has real endpoints.** Sprint 4 is the
  first sprint the brief has us building the same feature together, so:
  - `GET /rewards` returns the shop, cheapest first, deactivated items hidden
    (`?include_inactive=true` to see them). Each item carries **`affordable`**
    (already compared against the caller's balance - just disable the button)
    and `times_redeemed`.
  - `POST /rewards/{id}/redeem` returns `{redemption, points_balance}`, so the
    wallet display can update without a second call. **409 is the expected,
    non-exceptional response** for insufficient points and for a deactivated
    reward - the `detail` string is written to be shown to the user.
  - Deleting a redeemed reward is a **409 by design**; offer "deactivate"
    in the UI rather than surfacing it as a failure.
  - Balance also appears on `GET /auth/me` as `progress.points_balance`, so a
    combined Stat Panel does not need the wallet call.
- **Backend Agent (next):** Sprint 5 = Party/Guild + Redis leaderboard. The
  `parties` / `party_memberships` / `party_quests` / `party_quest_completions`
  tables already exist and are unused. Redis is up and healthy but the app has
  never actually used it beyond the health check. Note Section 11's open
  question on **real-time vs periodic refresh** for the shared board and
  leaderboard, and on **party size limits / dissolution** - both need settling
  with the user before building.

---

## 2026-09-10 (4) - Backend Agent (Opus) - Sprint 3: XP curve + rank thresholds

**Changed**
- **Section 11's curve question is now SETTLED with the user.** Curve
  retuned from the placeholder `BASE=50, EXPONENT=1.5` to **`BASE=40,
  EXPONENT=1.25`**, ranks moved from `1/10/20/35/50/75` to
  **`1/8/18/30/45/65`**. Pacing at a realistic ~268 XP/day:
  D ~6 days, C ~6 weeks, B ~4.4 months, A ~11 months, **S ~2.1 years**
  (was 9.8 years, which made the top half of the ladder dead content).
- **Rank now honours "level AND consistency"** (Section 2), which the previous
  implementation did not - it keyed off level alone. E-B stay level-only;
  **A requires a 14-day streak and S a 30-day streak.** A lapsed user falls
  back to the highest rank they still qualify for (S -> B), never to E:
  level and total_xp are never lost, only the top badge.
- `leveling.py` gains `rank_for(level, streak)`, `rank_by_level(level)`,
  `effective_streak()`, `streak_is_active()`, `next_rank_requirement()`.
  `rank_for_level()` is gone - all call sites updated.
- `GET /auth/me` progression payload extended for the Stat Panel:
  `streak_is_active`, `rank_by_level`, `next_rank`, `next_rank_level`,
  `next_rank_streak`. Contract regenerated.
- New `backend/scripts/recompute_progression.py` (with `--dry-run`).
- 92 tests (was 66).

**Verified (real output)**
- `92 passed`. Backend rebuilt, all services healthy, `/health` 200.
- Curve matches the agreed table exactly (D 1,647 XP -> S 209,559 XP);
  `level_for_xp(xp_for_level(n)) == n` for n in 1..300.
- **Streak gate demonstrated live** on one user at level 65, varying only the
  last-completion date:
  `today -> S`, `1 day ago -> S` (grace), `2 days ago -> B`, `10 days -> B`.
  Throughout, `rank_by_level` still reports `S` and `next_rank` reports `A`,
  so the UI can say "rebuild your streak to reclaim it". Level 65 and
  total_xp never changed.
- **Recompute verified on seeded stale rows**, not just an empty table: two
  users with identical XP cached as the old curve's level 34/rank B both moved
  to level 65; the active one became **S**, the 10-days-dormant one stayed
  **B**. `--dry-run` wrote nothing; a second run reported `0 of 2` (idempotent).
- One quest at 150 XP now takes a new user to **level 3** - the early reward
  loop the curve choice was made for.

**Two design problems found and fixed**
- **`current_streak` is frozen while a user is away.** Nothing runs on a
  dormant user's behalf, so gating rank on the stored counter would have meant
  a lapsed user keeps S forever - the exact outcome the gate exists to prevent.
  Streak is now derived at READ time via `effective_streak()`, which returns 0
  once `last_completed_on` is more than `STREAK_GRACE_DAYS` (1) behind the
  user's local date.
- **`ranked_up` fired on demotions.** It compared `rank_after != rank_before`,
  so losing a streak would have triggered the celebratory rank-up animation.
  It now compares ladder positions and is true only on promotion.

**Also**
- `xp_for_level` was O(n) and `level_for_xp` O(n^2) (a re-summed loop inside a
  linear scan). Replaced with a cumulative table built once at import plus a
  bisect lookup: 10,000 `level_for_xp` calls now take **1.2 ms**. This matters
  once Sprint 5's leaderboard derives a level per row.
- Container-run DB tooling lives in `backend/scripts/` (needs app imports and
  the compose network); host-run HTTP tooling stays in root `scripts/`.
  Invoke as a module - `python -m scripts.recompute_progression` - because
  `python scripts/x.py` puts the script's own directory on `sys.path`, not the
  working directory, so `app` fails to import.

**Blocked**
- Nothing.

**Other agent needs to know**
- **Frontend Agent - the Stat Panel now has real data to bind to.**
  `GET /api/v1/auth/me` -> `progress` carries everything the panel needs:
  - XP bar: `xp_into_level` / `xp_for_next_level` (both 0 at MAX_LEVEL = full).
  - Rank badge: **`rank`** is the rank actually held. **`rank_by_level`** is
    what the level alone earned. **When these differ, the user has earned the
    higher rank but needs a streak to hold it** - surface that ("14-day streak
    to claim A"), don't just render the lower badge.
  - Next rank: `next_rank`, `next_rank_level`, `next_rank_streak`, all `null`
    at the top of the ladder. Never hardcode a threshold - they will move.
  - Streak: `current_streak` is the EFFECTIVE value and reads **0** once
    lapsed; `streak_is_active` says whether it is live. `longest_streak` is
    the all-time best and never decreases.
  - `ranked_up` on a completion is now true **only on promotion**, so it is
    safe to drive the Sprint 6 rank-up animation directly off it.
- **Backend Agent (next):** Sprint 4 = Reward Points wallet + Rewards Shop
  (`reward_items`, `reward_redemptions` already exist in the schema, unused).
  `points_balance` has a `>= 0` CHECK as a double-spend backstop; debit in the
  same transaction as the redemption insert, and take the `level_progress`
  row lock first, exactly as the completion path does.
- If you ever change a number in `app/core/leveling.py`, the cached
  `current_level` / `rank` columns go stale until you run
  `docker compose run --rm tests python -m scripts.recompute_progression`.

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
