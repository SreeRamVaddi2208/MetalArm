# MetalArm Data Model - CONFIRMED

> **STATUS: CONFIRMED and MIGRATED.** Signed off 2026-09-10; implemented in
> Alembic revision `5dba70011569`. Verified against Postgres 17 with a full
> upgrade -> downgrade -> upgrade cycle, and `alembic check` reports no drift.
> Changes from here need a new migration, not an edit to this file.

Conventions applied throughout:

- **UUID primary keys** (`gen_random_uuid()`), not sequential integers. Parties,
  invite codes, and leaderboards expose IDs to other users; sequential IDs would
  leak user counts and allow enumeration.
- **`TIMESTAMPTZ` everywhere**, never naive timestamps. A habit app is entirely
  about *when* something happened, and daily resets are timezone-sensitive.
- **`created_at` / `updated_at`** on every mutable table, server-defaulted.
- **Native Postgres enums for genuinely stable state sets only** (confirmed
  decision): `rank` (E-S is a fixed ladder), `quest_status` (active/archived),
  `party_role` (owner/member - ownership is structural). Sets we expect to grow
  use `VARCHAR + CHECK`: `recurrence`, since "monthly" / "every N days" are
  plausible additions and `ALTER TYPE ... ADD VALUE` cannot be used in the same
  transaction that adds it, which fights Alembic's transactional migrations.
- **Email uniqueness via a lowercased `email_normalized` column** (confirmed
  decision), not `CITEXT` - no Postgres extension required.

---

## 1. `users`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | CITEXT UNIQUE NOT NULL | case-insensitive: `A@b.com` == `a@b.com` |
| `password_hash` | TEXT NOT NULL | bcrypt (never passlib - see README) |
| `display_name` | VARCHAR(50) NOT NULL | shown on leaderboards |
| `timezone` | VARCHAR(64) NOT NULL DEFAULT `'UTC'` | IANA name, e.g. `America/New_York` |
| `is_active` | BOOL NOT NULL DEFAULT true | soft deactivation |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**Why `timezone` is not optional.** A "daily" quest resets at the user's
midnight, not the server's. Without this column, someone in IST gets their day
rolled over mid-afternoon. It's far cheaper to add now than to backfill once
completion history exists.

`CITEXT` needs `CREATE EXTENSION citext`, which the first migration will
include. The alternative is storing a lowercased `email_normalized` column.

---

## 2. `level_progress` (1:1 with user)

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID PK, FK users ON DELETE CASCADE | |
| `total_xp` | BIGINT NOT NULL DEFAULT 0 | **source of truth** |
| `current_level` | INT NOT NULL DEFAULT 1 | derived, cached |
| `rank` | ENUM(E,D,C,B,A,S) NOT NULL DEFAULT 'E' | derived, cached |
| `points_balance` | INT NOT NULL DEFAULT 0, CHECK >= 0 | rewards wallet |
| `current_streak` / `longest_streak` | INT NOT NULL DEFAULT 0 | |
| `last_completed_on` | DATE NULL | in the user's local date |

**The one structural choice worth arguing about:** the brief's sketch stores
`current_xp`. I'm proposing `total_xp` as the stored truth, with `current_level`
and `rank` as *cached derivations* recomputed on every XP change.

Reason: if `current_level` and `current_xp` are both authoritative, they can
drift, and retuning the XP curve later (Section 11 explicitly leaves the curve
open) silently corrupts everyone's progress. With cumulative `total_xp`, the
curve is pure presentation logic - retuning it re-derives every user correctly
and is reversible. The cached columns exist only so the leaderboard doesn't
recompute a curve for every row.

The curve lives in **one module** (`app/core/leveling.py`), so Section 11's open
question stays cheap to answer later.

---

## 3. `quests` (personal)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `owner_id` | UUID FK users ON DELETE CASCADE, INDEXED | |
| `title` | VARCHAR(140) NOT NULL | |
| `description` | TEXT NULL | |
| `xp_reward` | INT NOT NULL CHECK (0..10000) | bounded: stops a self-made 1e9 XP quest |
| `points_reward` | INT NOT NULL DEFAULT 0 CHECK >= 0 | |
| `recurrence` | ENUM(none, daily, weekly) NOT NULL | |
| `status` | ENUM(active, archived) NOT NULL DEFAULT 'active' | |
| `due_at` | TIMESTAMPTZ NULL | |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

Note `status` has **no `completed` value** - see below.

---

## 4. `quest_completions` - the significant addition

**This table is not in the Section 5 sketch, and I think its absence is a bug
in the sketch rather than an omission for brevity.**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `quest_id` | UUID FK quests ON DELETE CASCADE | |
| `user_id` | UUID FK users ON DELETE CASCADE | |
| `period_key` | VARCHAR(16) NOT NULL | `'2026-09-10'` daily, `'2026-W37'` weekly, `'once'` one-off |
| `completed_at` | TIMESTAMPTZ NOT NULL | |
| `xp_awarded` / `points_awarded` | INT NOT NULL | **snapshot** of the reward at completion time |

> **UNIQUE (`quest_id`, `user_id`, `period_key`)**

The sketch models completion as `Quest.status`, which cannot express a daily
quest: a single status field has no way to say "done today, not done
yesterday." Worse, without the unique constraint a user can farm unlimited XP
by double-tapping the complete button - and that is a *race*, so an app-level
"did they already complete it?" check does not close it. Only a DB constraint
does.

`period_key` is computed from `completed_at` in the **user's** timezone, which
is what makes `users.timezone` load-bearing.

Rewards are **snapshotted** into the completion row so that editing a quest's
XP later doesn't silently rewrite history - the XP ledger stays reconstructible,
and `total_xp` becomes auditable as `SUM(xp_awarded)`.

---

## 5. `reward_items` / `reward_redemptions`

`reward_items`: `id`, `owner_id` (FK users, indexed), `title`, `point_cost`
(INT CHECK > 0), `is_active` BOOL, timestamps.

`reward_redemptions`: `id`, `reward_item_id` (FK, ON DELETE RESTRICT),
`user_id` (FK), `points_spent` INT (snapshotted), `redeemed_at`.

Redemption debits `level_progress.points_balance` **in the same transaction** as
the redemption insert, with `CHECK (points_balance >= 0)` as the backstop
against concurrent double-spend. `ON DELETE RESTRICT` on the item so deleting a
reward can't erase spend history.

---

## 6. `parties` / `party_memberships`

`parties`: `id`, `name` VARCHAR(60), `invite_code` VARCHAR(10) UNIQUE NOT NULL
(indexed - it's the lookup key), `owner_id` FK users, `max_members` INT NOT NULL
DEFAULT 8, `is_active` BOOL, timestamps.

`party_memberships`: PK (`party_id`, `user_id`), `role` ENUM(owner, member),
`joined_at`. Index on `user_id` for "my parties".

Proposed defaults, all reversible:
- **Freely created and dissolved.** Dissolve = `is_active = false`, retaining
  history rather than cascading away everyone's completions.
- **Max 8 members**, stored per-party rather than hardcoded, so it's tunable
  without a migration.
- **A user may join multiple parties.** Say so if you'd rather cap it at one -
  that's a partial unique index, trivial now and painful later.
- Invite code is a random 8-char base32 (no `0/O/1/I`), regenerable by the owner.

---

## 7. `party_quests` / `party_quest_completions`

`party_quests` mirrors `quests` but is keyed to `party_id` with a `created_by`
FK, and is visible to all members.

`party_quest_completions` mirrors `quest_completions`, with
**UNIQUE (`party_quest_id`, `user_id`, `period_key`)** - each member may
complete a shared quest once per period, and each completion contributes to
both their personal `total_xp` and the party total.

Party XP total is **derived** (`SUM` over completions), optionally cached on
`parties.total_xp` in Sprint 5 when the Redis leaderboard lands. Redis holds the
sorted set for ranking; Postgres stays the source of truth, so a Redis flush
costs a rebuild, never data.

---

## Resolved decisions

1. **Multi-party membership: ALLOWED.** A user may belong to several parties.
   Capping it later is a partial unique index on `user_id`.
2. **Enums:** native PG enums for stable sets, `VARCHAR + CHECK` for
   `recurrence`. See the conventions above.
3. **Email:** `email_normalized` column, not `CITEXT`.

Still open, and deliberately **not blocking** anything:

4. XP curve and rank cutoffs (Section 11) - isolated in
   `app/core/leveling.py`. Because `total_xp` is the stored truth, retuning
   re-derives every user rather than corrupting stored progress.
5. WebSockets vs polling (Section 11) - no schema impact either way.

---

## Verification performed against Postgres 17

Each guarantee was tested by attempting the thing it forbids, not by assuming
the constraint works:

| # | Attempt | Result |
|---|---|---|
| 1 | Complete a daily quest for `2026-09-10` | succeeded |
| 2 | Complete the SAME quest again that day | **blocked** - `uq_quest_completion_period` |
| 3 | Complete it on `2026-09-11` | succeeded - recurrence works |
| 4 | Register `TEST@example.com` over `Test@Example.com` | **blocked** - `ix_users_email_normalized` |
| 5 | Set `points_balance = -5` | **blocked** - `ck_progress_points_non_negative` |
| 6 | `recurrence = 'monthly'` | **blocked** - `ck_quests_recurrence` |
| 7 | `xp_reward = 999999` | **blocked** - `ck_quests_xp_reward_range` |
| 8 | `status = 'finished'` | **blocked** - invalid enum value |

Test rows were rolled back; the database holds no fixture data.

## Two bugs this caught before they shipped

**SQLAlchemy enum name/value mismatch.** `Enum(QuestStatus)` persists the member
NAME (`ACTIVE`) by default, not `.value` (`active`), which diverged from
`server_default='active'` and failed the migration with
`invalid input value for enum quest_status: "active"`. Fixed with a shared
`pg_enum()` helper using `values_callable`. This is easy to miss because `Rank`
(names == values) works either way - it would have hidden until the first quest
was created.

**Autogenerate does not drop enum types on downgrade.** `drop_table` leaves
`rank` / `quest_status` / `party_role` behind, so the next upgrade fails with
`type "rank" already exists`. The migration's `downgrade()` carries a
hand-added `DROP TYPE IF EXISTS` loop, marked as such.

---

# Gym workout module (Alembic `085f917f46f8`)

Implements the brief's "Shared data contract" in `backend/app/models/workout.py`.
Every field the brief lists is present; the **+** additions below are what the
implementation needed on top. All vocabularies are `VARCHAR + CHECK`
(`app/models/workout_enums.py`), not native enums - every one of them is
expected to grow. No native types means `downgrade()` needs no hand-added
`DROP TYPE`.

| Table | Brief fields | + Additions (why) |
|---|---|---|
| `exercises` | name, category, primary_muscle_groups[], equipment, is_custom, created_by_user_id | **slug** (import upsert key, library only) · **name_key** (normalised name carrying uniqueness - same pattern as `email_normalized`) · **instructions**, **media_url** (Lyfta-shaped library) · **is_archived** (a used custom exercise is hidden, never deleted) |
| `routines` / `routine_exercises` | user_id, name, ordered exercise_id + target sets/reps/weight | **notes** · **position** + UNIQUE(routine_id, position) · **rest_seconds** (seeds the client rest timer) |
| `workout_sessions` | user_id, started_at, ended_at, routine_id, status | **name**, **notes** · **qualified** (was it a real workout - gates bonus + streak) · **week_key** (ISO week in the user's tz, so the streak is a GROUP BY) · **points_credited** (shop points credited at finish, snapshotted) |
| `set_entries` | session_id, exercise_id, set_number, weight, reps, rpe, is_warmup, is_pr, completed_at | weight stored as **weight_kg** (lb converted on input) · **user_id** (denormalised: one index scan for an exercise's history) · **duration_seconds**, **distance_m** (cardio) · **client_set_id** (idempotent retries) |
| `personal_records` | user_id, exercise_id, record_type, value, achieved_at, session_id | **weight_kg** (qualifier for rep PRs) · **previous_value** ("beat it by 5 kg") · **is_baseline** (first log, no bonus) · **set_id**. Rows are record-setting *events*; the current PR is the best row, and all rows are rebuildable from sets (`personal_records.replay`) |
| `points_ledger` | user_id, source_type, source_id, points, created_at | source **reversal** (append-only undo) · **session_id** · **period_key** (streak week) · **reason** (human label) |
| `body_measurements` | user_id, metric, value, unit, recorded_at | **label** (required for custom metrics) |

## Constraints doing the anti-farming work

As with quests, the database - not a Python check - is the authority wherever
a race is possible:

- `uq_workout_sessions_one_active` - partial UNIQUE(user_id) WHERE in_progress.
  One live workout per user, so parallel sessions cannot multiply the caps.
- `uq_set_entries_client_id` - UNIQUE(session_id, client_set_id). A retried
  submit resolves to the original set.
- `uq_points_ledger_once` - partial UNIQUE(source_type, source_id) for
  session_completed / streak_bonus / reversal. A session cannot be paid twice
  and an award cannot be reversed twice.
- `uq_points_ledger_streak_week` - one streak bonus per user per ISO week.
- `ck_points_ledger_sign` - only reversals are negative, and they always are.
- CHECK bounds on weight (≤1000 kg), reps, RPE, duration, distance - absurd
  inputs cannot mint records.

Set-level awards are serialised by the existing `level_progress` row lock
(every write path takes it first), which is what makes the per-session caps
race-free.

## Deliberate FK choice

Foreign keys onto `exercises` use NO ACTION, not RESTRICT: deleting a user
cascades to their custom exercises and to the sets referencing them in one
statement, and RESTRICT is checked mid-cascade while NO ACTION waits until the
end of the statement.

## Verified

`alembic check` reports no drift; `upgrade` → `downgrade -1` → `upgrade` is
clean; the importer loaded 91 library exercises and a second run reported 91
unchanged.
