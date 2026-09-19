# MetalArm API Contract

> **GENERATED FILE - do not hand-edit.**
> Regenerate with `python scripts/generate_api_contract.py` while the
> backend is running. Backend Agent owns this file.
>
> **Frontend Agent:** treat this as the single source of truth for
> endpoint shapes. Never invent an endpoint. If something you need is
> missing, ask Backend Agent to add it and regenerate - do not guess.

- **API title:** MetalArm API
- **API version:** 0.1.0
- **Generated:** 2026-09-19 18:07 UTC
- **Source:** `http://localhost:8000/openapi.json`

---

## Endpoints

### `GET /`

**Root**

*Tags:* `system`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `POST /api/v1/auth/login`

**Login**

JSON login - the endpoint the Reflex frontend and the iOS app use.

*Tags:* `auth`

*Request body* (`application/json`): `LoginRequest`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/auth/logout`

**Logout**

Sign out of this device only: its access and refresh tokens stop
working, every other device stays signed in.

Send the refresh token in the body - it is still valid after the access
token has expired. A bearer access token alone also works.

*Tags:* `auth`

*Request body* (`application/json`): `LogoutRequest | null`

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/auth/logout-all`

**Logout Everywhere**

Sign out on every device: every access and refresh token issued so far
stops working.

*Tags:* `auth`

| Status | Description |
|---|---|
| `204` | Successful Response |

---

### `DELETE /api/v1/auth/me`

**Delete Account**

Permanently delete the account and everything it owns.

Required by the App Store for any app that offers account creation. Every
user-owned table (device sessions included) cascades on users.id. Parties
are handled first: one the user owns goes to its longest-serving member
instead of being deleted with its owner.

*Tags:* `auth`

*Request body* (`application/json`): `DeleteAccountRequest`

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/auth/me`

**Read Me**

The signed-in user plus progression - what the Stat Panel renders.

*Tags:* `auth`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `PATCH /api/v1/auth/me`

**Update Me**

Update account preferences: the workout weight unit and the cosmetic
character class.

Stored on the account rather than in the browser, so the choice follows
the user across devices.

*Tags:* `auth`

*Request body* (`application/json`): `MeUpdate`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/auth/refresh`

**Refresh**

Swap a refresh token for a new access + refresh pair on the same device
session. Fails once that device has signed out, or once the user has signed
out everywhere (token_version bumped).

*Tags:* `auth`

*Request body* (`application/json`): `RefreshRequest`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/auth/signup`

**Signup**

Create an account and its progression row.

Both rows are written in one transaction: a User without LevelProgress
would break every progression read path, and there is no valid state in
which one exists without the other.

*Tags:* `auth`

*Request body* (`application/json`): `SignupRequest`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/auth/token`

**Login Form**

OAuth2 password-flow login, form-encoded.

Exists so /docs' Authorize button works for manual testing. Identical
semantics to /login; OAuth2 mandates the field be named `username`, which
here carries the email.

*Tags:* `auth`

*Request body* (`application/x-www-form-urlencoded`): `Body_login_form_api_v1_auth_token_post`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/body-measurements`

**List Measurements**

Newest first.

*Tags:* `body`

| Param | In | Type | Required |
|---|---|---|---|
| `metric` | query | `MeasurementMetric | null` | no |
| `limit` | query | `integer` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/body-measurements`

**Create Measurement**

*Tags:* `body`

*Request body* (`application/json`): `BodyMeasurementCreate`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE /api/v1/body-measurements/{measurement_id}`

**Delete Measurement**

*Tags:* `body`

| Param | In | Type | Required |
|---|---|---|---|
| `measurement_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `PUT /api/v1/devices/push-token`

**Register Push Token**

Register this device's APNs token, or refresh it.

Idempotent: the app sends it on every launch, because iOS can hand out a
new token at any time. A token already registered - to this account or
another one signed in earlier on the same phone - moves to this account
and this sign-in session.

*Tags:* `devices`

*Request body* (`application/json`): `PushDeviceRegister`

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `DELETE /api/v1/devices/push-token/{token}`

**Unregister Push Token**

Stop notifying this device - the user turned notifications off.

Succeeds whether or not the token was registered, so a retry is harmless,
and only ever removes the caller's own token.

*Tags:* `devices`

| Param | In | Type | Required |
|---|---|---|---|
| `token` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/exercises`

**List Exercises**

Search the library plus the caller's own exercises, by name.

*Tags:* `exercises`

| Param | In | Type | Required |
|---|---|---|---|
| `q` | query | `string | null` | no |
| `category` | query | `ExerciseCategory | null` | no |
| `equipment` | query | `Equipment | null` | no |
| `muscle` | query | `MuscleGroup | null` | no |
| `custom_only` | query | `boolean` | no |
| `include_archived` | query | `boolean` | no |
| `limit` | query | `integer` | no |
| `offset` | query | `integer` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/exercises`

**Create Exercise**

*Tags:* `exercises`

*Request body* (`application/json`): `ExerciseCreate`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/exercises/meta`

**Exercise Meta**

The allowed vocabularies, for filter chips and pickers.

*Tags:* `exercises`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `DELETE /api/v1/exercises/{exercise_id}`

**Delete Exercise**

Delete a custom exercise - or archive it, if any set or routine still
references it, so history is never orphaned.

*Tags:* `exercises`

| Param | In | Type | Required |
|---|---|---|---|
| `exercise_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/exercises/{exercise_id}`

**Read Exercise**

*Tags:* `exercises`

| Param | In | Type | Required |
|---|---|---|---|
| `exercise_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PATCH /api/v1/exercises/{exercise_id}`

**Update Exercise**

*Tags:* `exercises`

| Param | In | Type | Required |
|---|---|---|---|
| `exercise_id` | path | `string` | yes |

*Request body* (`application/json`): `ExerciseUpdate`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/exercises/{exercise_id}/history`

**Exercise History**

Per completed session: top weight, best estimated 1RM, volume. Oldest
first, ready to plot.

*Tags:* `exercises`

| Param | In | Type | Required |
|---|---|---|---|
| `exercise_id` | path | `string` | yes |
| `limit` | query | `integer` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/exercises/{exercise_id}/last-performance`

**Last Performance**

The previous completed session's sets - ghost values for an exercise
added mid-workout. Empty `sets` when it has never been done.

*Tags:* `exercises`

| Param | In | Type | Required |
|---|---|---|---|
| `exercise_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/leagues/current`

**Current League**

This week's league. The placement is created on first access, which is
also when last week's result is judged (app/core/leagues.py) - so leagues
need no scheduled job. Standings are the points ledger summed over the ISO
week in UTC, never a stored score.

*Tags:* `leagues`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `GET /api/v1/parties`

**List Parties**

Every party the caller belongs to.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `include_dissolved` | query | `boolean` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/parties`

**Create Party**

Create a party and join it as owner, in one transaction.

A party with no members would be unreachable - nobody could see it or use
its invite code - so the owner's membership is not a separate step.

*Tags:* `parties`

*Request body* (`application/json`): `PartyCreate`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/parties/join`

**Join Party**

Join by invite code.

The party row is locked FOR UPDATE before the headcount is read: checking
the cap without the lock is a race, and two simultaneous joins into a
9-of-10 party would both see room and both insert.

*Tags:* `parties`

*Request body* (`application/json`): `JoinRequest`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE /api/v1/parties/{party_id}`

**Dissolve Party**

Dissolve a party (owner only).

Soft: is_active=false, never a row delete. Members keep the XP they earned
and the completion history stays reconstructible - deleting would cascade
party_quests and their completions away, silently rewriting the record of
work people actually did.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/parties/{party_id}`

**Get Party**

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PATCH /api/v1/parties/{party_id}`

**Update Party**

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

*Request body* (`application/json`): `PartyUpdate`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/parties/{party_id}/leaderboard`

**Party Leaderboard**

Ranked party members by XP contributed to this party.

Served from the Redis sorted set, which falls back to Postgres and rebuilds
on a miss - so a cache flush costs a rebuild, never data.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |
| `limit` | query | `integer` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/parties/{party_id}/leave`

**Leave Party**

Leave a party.

When the OWNER leaves, the party is handed to the longest-serving remaining
member rather than orphaned - an ownerless party could never be renamed,
have its invite rotated, or be dissolved. If nobody remains, the party is
dissolved instead of being left empty and unreachable.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/parties/{party_id}/members`

**List Members**

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/parties/{party_id}/quests`

**List Party Quests**

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |
| `include_inactive` | query | `boolean` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/parties/{party_id}/quests`

**Create Party Quest**

Any member may add to the shared board.

Deliberately not owner-only: a shared quest board that only one person can
write to is a to-do list handed down, not a party.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

*Request body* (`application/json`): `PartyQuestCreate`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE /api/v1/parties/{party_id}/quests/{quest_id}`

**Delete Party Quest**

Deactivate a shared quest.

Soft, like dissolving a party: a hard delete would cascade away the
completion rows that back every member's contributed XP, silently changing
the leaderboard.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |
| `quest_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `PATCH /api/v1/parties/{party_id}/quests/{quest_id}`

**Update Party Quest**

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |
| `quest_id` | path | `string` | yes |

*Request body* (`application/json`): `PartyQuestUpdate`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/parties/{party_id}/quests/{quest_id}/complete`

**Complete Party Quest**

Complete a shared quest for the current period.

Same transaction shape as a personal completion, and for the same reasons:
lock level_progress FOR UPDATE first (consistent lock order across every
writer, so no deadlock), then let
UNIQUE(party_quest_id, user_id, period_key) - not a Python pre-check - be
what actually stops double-awarding.

The award lands in BOTH places: the member's personal total_xp and their
party contribution. Because a non-member cannot reach this endpoint, party
XP counts only what was earned while a member, with no extra bookkeeping.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |
| `quest_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/parties/{party_id}/raid`

**Party Raid**

This week's party boss: its HP, what the party has dealt, what it healed
on idle days, and who hit it hardest. Members only - an outsider gets 404,
as for every party read. The rules are in app/core/raids.py.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/parties/{party_id}/rotate-invite`

**Rotate Invite**

Issue a fresh invite code, invalidating the old one.

The only way to revoke a leaked link: the code IS the capability, so
rotating it is what stops further joins.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/parties/{party_id}/workout-leaderboard`

**Party Workout Leaderboard**

Friends' competition for the gym module: members ranked by workout
points from the points ledger.

Unlike the XP board above, this counts ALL of each member's workout points,
not only what was earned for the party - training is personal, and the
point is to compare it. `week` is the current ISO week in the VIEWER's
timezone (the same boundary GET /workouts/points uses), so everyone on one
board is compared over one window. A week's total cannot read negative:
a reversal landing this week of an award from last week is clamped at 0.

*Tags:* `parties`

| Param | In | Type | Required |
|---|---|---|---|
| `party_id` | path | `string` | yes |
| `period` | query | `string` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/profile`

**Read Profile**

*Tags:* `profile`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `GET /api/v1/profile/character`

**Character**

The character sheet: Strength, Endurance and Discipline, each 0-100 with
the number behind it (app/core/character.py). The class only marks which
stats are highlighted - it never changes a score.

*Tags:* `profile`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `GET /api/v1/profile/trials`

**Rank Trial Status**

The strength trials that gate ranks B, A and S: each lift's target at
the user's latest bodyweight, their best so far, and whether it is passed
(app/core/rank_trials.py). Targets are null until a bodyweight is logged.

*Tags:* `profile`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `GET /api/v1/quests`

**List Quests**

The caller's quest board, newest first.

*Tags:* `quests`

| Param | In | Type | Required |
|---|---|---|---|
| `status` | query | `QuestStatus` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/quests`

**Create Quest**

*Tags:* `quests`

*Request body* (`application/json`): `QuestCreate`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE /api/v1/quests/{quest_id}`

**Delete Quest**

Hard-delete a quest and its completion rows (FK ON DELETE CASCADE).

Already-earned XP is NOT clawed back - total_xp is cumulative and the XP
was legitimately earned. Callers wanting to keep the audit trail should
PATCH status='archived' instead.

*Tags:* `quests`

| Param | In | Type | Required |
|---|---|---|---|
| `quest_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/quests/{quest_id}`

**Get Quest**

*Tags:* `quests`

| Param | In | Type | Required |
|---|---|---|---|
| `quest_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PATCH /api/v1/quests/{quest_id}`

**Update Quest**

Partial update.

Editing xp_reward does NOT rewrite past awards: quest_completions snapshots
xp_awarded at completion time, so history stays auditable and a user can't
retroactively inflate earned XP by raising a quest's reward.

*Tags:* `quests`

| Param | In | Type | Required |
|---|---|---|---|
| `quest_id` | path | `string` | yes |

*Request body* (`application/json`): `QuestUpdate`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/quests/{quest_id}/complete`

**Complete Quest**

Complete a quest for the current period, awarding XP and points.

Ordering inside the transaction is deliberate:

1. Lock level_progress FOR UPDATE. Every writer takes this lock first, so
   concurrent completions serialize per user and no award is lost - and
   because the order is consistent, no deadlock is possible.
2. Insert the completion. UNIQUE(quest_id, user_id, period_key) is what
   actually prevents double-awarding; checking "already completed?" in
   Python first would still race between the check and the insert.
3. Apply XP/points/streak, then commit both together. If the insert fails,
   the whole transaction rolls back and no XP is granted.

*Tags:* `quests`

| Param | In | Type | Required |
|---|---|---|---|
| `quest_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/rewards`

**List Rewards**

*Tags:* `rewards`

| Param | In | Type | Required |
|---|---|---|---|
| `include_inactive` | query | `boolean` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/rewards`

**Create Reward**

*Tags:* `rewards`

*Request body* (`application/json`): `RewardCreate`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/rewards/redemptions`

**List Redemptions**

Spend history, newest first.

*Tags:* `rewards`

| Param | In | Type | Required |
|---|---|---|---|
| `limit` | query | `integer` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/rewards/wallet`

**Read Wallet**

Balance plus lifetime earned/spent totals.

Earned counts quests AND finished workouts (credited at finish - see
routes/workouts.py), so earned - spent reconciles with the balance.

*Tags:* `rewards`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `DELETE /api/v1/rewards/{reward_id}`

**Delete Reward**

Delete a reward that has never been redeemed.

The redemption FK is ON DELETE RESTRICT so that deleting a reward cannot
erase the record of points already spent on it. Once there is history the
reward can only be DEACTIVATED (PATCH is_active=false), which hides it from
the shop while leaving the ledger intact.

*Tags:* `rewards`

| Param | In | Type | Required |
|---|---|---|---|
| `reward_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/rewards/{reward_id}`

**Get Reward**

*Tags:* `rewards`

| Param | In | Type | Required |
|---|---|---|---|
| `reward_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PATCH /api/v1/rewards/{reward_id}`

**Update Reward**

Partial update.

Repricing does NOT rewrite spend history: points_spent is snapshotted on
the redemption row, so past redemptions keep the price actually paid.

*Tags:* `rewards`

| Param | In | Type | Required |
|---|---|---|---|
| `reward_id` | path | `string` | yes |

*Request body* (`application/json`): `RewardUpdate`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/rewards/{reward_id}/redeem`

**Redeem Reward**

Spend points on a reward.

Same transaction shape as completing a quest, and for the same reason:

1. Lock level_progress FOR UPDATE *before* reading the balance. Checking
   the balance without the lock is a race - two concurrent redeems both
   read 100, both spend 80, and the user gets 160 points of rewards for
   100 points. The lock is taken in the same order as the completion path,
   so the two cannot deadlock against each other.
2. Insert the redemption and debit in the same transaction, so points can
   never leave the wallet without a matching ledger row.
3. CHECK (points_balance >= 0) is the backstop if the guard above is ever
   bypassed.

*Tags:* `rewards`

| Param | In | Type | Required |
|---|---|---|---|
| `reward_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/routines`

**List Routines**

*Tags:* `routines`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `POST /api/v1/routines`

**Create Routine**

*Tags:* `routines`

*Request body* (`application/json`): `RoutineIn`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE /api/v1/routines/{routine_id}`

**Delete Routine**

Workouts started from it keep their history (routine_id is SET NULL).

*Tags:* `routines`

| Param | In | Type | Required |
|---|---|---|---|
| `routine_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/routines/{routine_id}`

**Read Routine**

*Tags:* `routines`

| Param | In | Type | Required |
|---|---|---|---|
| `routine_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT /api/v1/routines/{routine_id}`

**Replace Routine**

Full replace. The ordered exercise list is swapped as a whole.

*Tags:* `routines`

| Param | In | Type | Required |
|---|---|---|---|
| `routine_id` | path | `string` | yes |

*Request body* (`application/json`): `RoutineIn`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/workouts/import`

**Import Workouts**

Import history from a Strong or Hevy CSV export (app/core/importer.py).
The same file twice imports once, and workouts already in the history are
skipped. Imported workouts count for records, rank trials and charts, and
pay a little XP - never shop points, streaks, raids or leaderboard places.
422 when the file isn't an export that can be read.

*Tags:* `workouts`

*Request body* (`application/json`): `WorkoutImportIn`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/workouts/points`

**Points Summary**

Workout points totals and the weekly streak.

*Tags:* `workouts`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `GET /api/v1/workouts/points/ledger`

**List Ledger**

The points ledger, newest first. Reversals appear as their own negative
rows - nothing is ever edited or removed.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `limit` | query | `integer` | no |
| `before` | query | `string | null` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/workouts/records`

**List Records**

Current personal records. One row per record type per exercise, except
rep records, which return every undominated (weight, reps) point - "best
reps at each weight" is a list, not a single number.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `exercise_id` | query | `string | null` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/workouts/sessions`

**List Sessions**

Workout history, newest first.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `status` | query | `SessionStatus | null` | no |
| `limit` | query | `integer` | no |
| `before` | query | `string | null` | no |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/workouts/sessions`

**Start Session**

Start a workout, blank or from a routine. 409 if one is already live -
finish or abandon it first (GET /workouts/sessions/active returns it).

*Tags:* `workouts`

*Request body* (`application/json`): `SessionStart`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `GET /api/v1/workouts/sessions/active`

**Read Active Session**

The in-progress workout, or `session: null`. What the UI calls on load
to rehydrate a workout after a refresh.

*Tags:* `workouts`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `GET /api/v1/workouts/sessions/{session_id}`

**Read Session**

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `session_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/workouts/sessions/{session_id}/abandon`

**Abandon Session**

Discard a live workout. Every award it earned is reversed and its sets
stop counting toward records - otherwise log-then-abandon would be a way to
bank XP without ever finishing a workout.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `session_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/workouts/sessions/{session_id}/finish`

**Finish Session**

Finish a workout: judge session-volume records, pay the session and
streak bonuses, and credit the session's points to the wallet.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `session_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST /api/v1/workouts/sessions/{session_id}/sets`

**Log Set**

Log a set. Records and points are settled before this returns, so the
response alone tells the UI whether to celebrate a PR or a level-up.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `session_id` | path | `string` | yes |

*Request body* (`application/json`): `SetCreate`

| Status | Description |
|---|---|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE /api/v1/workouts/sessions/{session_id}/sets/{set_id}`

**Delete Set**

Remove a set from a live workout. Its awards are reversed and the
exercise's records rebuilt without it.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `session_id` | path | `string` | yes |
| `set_id` | path | `string` | yes |

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PATCH /api/v1/workouts/sessions/{session_id}/sets/{set_id}`

**Update Set**

Fix a typo in a set while the workout is live.

Implemented as reverse-then-re-award: the set's standing awards are
reversed, the exercise's records are rebuilt from history, and the edited
set is judged afresh. Other sets' awards are not revisited.

*Tags:* `workouts`

| Param | In | Type | Required |
|---|---|---|---|
| `session_id` | path | `string` | yes |
| `set_id` | path | `string` | yes |

*Request body* (`application/json`): `SetUpdate`

| Status | Description |
|---|---|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET /health`

**Health**

Liveness + dependency readiness.

Returns 200 only when Postgres AND Redis both genuinely respond;
otherwise 503 with per-dependency detail.

*Tags:* `system`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

## Schemas

#### `AbandonResponse`

| Field | Type | Required |
|---|---|---|
| `session` | `SessionSummaryOut` | yes |
| `points_reversed` | `integer` | yes |
| `progression` | `ProgressionDeltaOut` | yes |

#### `ActiveSessionOut`

| Field | Type | Required |
|---|---|---|
| `session` | `SessionOut | null` | yes |

#### `AwardOut`

| Field | Type | Required |
|---|---|---|
| `source_type` | `string` | yes |
| `points` | `integer` | yes |
| `reason` | `string` | yes |

#### `BadgeOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `name` | `string` | yes |
| `description` | `string` | yes |
| `icon` | `string` | yes |
| `earned` | `boolean` | yes |
| `progress` | `integer` | yes |
| `target` | `integer` | yes |
| `percent` | `integer` | yes |

#### `BodyMeasurementCreate`

| Field | Type | Required |
|---|---|---|
| `metric` | `MeasurementMetric` | yes |
| `label` | `string | null` | no |
| `value` | `number` | yes |
| `unit` | `MeasurementUnit` | yes |
| `recorded_at` | `string | null` | no |

#### `BodyMeasurementOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `metric` | `string` | yes |
| `label` | `string | null` | yes |
| `value` | `number` | yes |
| `unit` | `string` | yes |
| `recorded_at` | `string` | yes |

#### `Body_login_form_api_v1_auth_token_post`

| Field | Type | Required |
|---|---|---|
| `grant_type` | `string | null` | no |
| `username` | `string` | yes |
| `password` | `string` | yes |
| `scope` | `string` | no |
| `client_id` | `string | null` | no |
| `client_secret` | `string | null` | no |

#### `CharacterClass`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `CharacterOut`

| Field | Type | Required |
|---|---|---|
| `character_class` | `string` | yes |
| `class_label` | `string` | yes |
| `stats` | `StatOut[]` | yes |

#### `CompleteQuestResponse`

| Field | Type | Required |
|---|---|---|
| `completion` | `CompletionOut` | yes |
| `progression` | `ProgressionDeltaOut` | yes |

#### `CompletionOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `quest_id` | `string` | yes |
| `period_key` | `string` | yes |
| `completed_at` | `string` | yes |
| `xp_awarded` | `integer` | yes |
| `points_awarded` | `integer` | yes |

#### `DeleteAccountRequest`

| Field | Type | Required |
|---|---|---|
| `password` | `string` | yes |

#### `Equipment`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `ExerciseCategory`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `ExerciseCreate`

| Field | Type | Required |
|---|---|---|
| `name` | `string` | yes |
| `category` | `ExerciseCategory` | yes |
| `primary_muscle_groups` | `MuscleGroup[]` | yes |
| `equipment` | `Equipment` | yes |
| `instructions` | `string | null` | no |
| `media_url` | `string | null` | no |

#### `ExerciseDeleteOut`

| Field | Type | Required |
|---|---|---|
| `archived` | `boolean` | yes |

#### `ExerciseHistoryPoint`

| Field | Type | Required |
|---|---|---|
| `session_id` | `string` | yes |
| `performed_at` | `string` | yes |
| `top_weight_kg` | `number | null` | yes |
| `top_weight_reps` | `integer | null` | yes |
| `best_est_1rm` | `number | null` | yes |
| `volume_kg` | `number` | yes |
| `working_sets` | `integer` | yes |
| `total_reps` | `integer` | yes |

#### `ExerciseMetaOut`

| Field | Type | Required |
|---|---|---|
| `categories` | `string[]` | yes |
| `equipment` | `string[]` | yes |
| `muscle_groups` | `string[]` | yes |
| `weight_units` | `string[]` | yes |
| `measurement_metrics` | `string[]` | yes |
| `measurement_units` | `string[]` | yes |

#### `ExerciseOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `name` | `string` | yes |
| `slug` | `string | null` | yes |
| `category` | `string` | yes |
| `primary_muscle_groups` | `string[]` | yes |
| `equipment` | `string` | yes |
| `instructions` | `string | null` | yes |
| `media_url` | `string | null` | yes |
| `is_custom` | `boolean` | yes |
| `is_archived` | `boolean` | yes |

#### `ExerciseUpdate`

| Field | Type | Required |
|---|---|---|
| `name` | `string | null` | no |
| `category` | `ExerciseCategory | null` | no |
| `primary_muscle_groups` | `MuscleGroup[] | null` | no |
| `equipment` | `Equipment | null` | no |
| `instructions` | `string | null` | no |
| `media_url` | `string | null` | no |

#### `FinishResponse`

| Field | Type | Required |
|---|---|---|
| `session` | `SessionSummaryOut` | yes |
| `qualified` | `boolean` | yes |
| `awards` | `AwardOut[]` | yes |
| `breakdown` | `PointsBreakdownOut` | yes |
| `points_credited` | `integer` | yes |
| `pr_events` | `PrEventOut[]` | yes |
| `streak` | `StreakOut` | yes |
| `progression` | `ProgressionDeltaOut` | yes |
| `raids` | `RaidHitOut[]` | no |

#### `HTTPValidationError`

| Field | Type | Required |
|---|---|---|
| `detail` | `ValidationError[]` | no |

#### `HintOut`

| Field | Type | Required |
|---|---|---|
| `kind` | `string` | yes |
| `text` | `string` | yes |
| `target_weight_kg` | `number | null` | yes |
| `target_reps` | `integer | null` | yes |

#### `JoinRequest`

| Field | Type | Required |
|---|---|---|
| `invite_code` | `string` | yes |

#### `LastPerformanceOut`

| Field | Type | Required |
|---|---|---|
| `exercise_id` | `string` | yes |
| `session_id` | `string | null` | yes |
| `performed_at` | `string | null` | yes |
| `sets` | `SetOut[]` | yes |
| `hint` | `HintOut | null` | no |

#### `LeaderboardEntry`

| Field | Type | Required |
|---|---|---|
| `position` | `integer` | yes |
| `user_id` | `string` | yes |
| `display_name` | `string` | yes |
| `party_xp` | `integer` | yes |
| `level` | `integer` | yes |
| `rank` | `string` | yes |
| `is_me` | `boolean` | yes |

#### `LeaderboardOut`

| Field | Type | Required |
|---|---|---|
| `party_id` | `string` | yes |
| `total_party_xp` | `integer` | yes |
| `entries` | `LeaderboardEntry[]` | yes |

#### `LeagueEntryOut`

| Field | Type | Required |
|---|---|---|
| `position` | `integer` | yes |
| `user_id` | `string` | yes |
| `display_name` | `string` | yes |
| `points` | `integer` | yes |
| `level` | `integer` | yes |
| `rank` | `string` | yes |
| `is_me` | `boolean` | yes |

#### `LeagueOut`

| Field | Type | Required |
|---|---|---|
| `week_key` | `string` | yes |
| `division` | `integer` | yes |
| `division_label` | `string` | yes |
| `group_no` | `integer` | yes |
| `ends_at` | `string` | yes |
| `promoted_from` | `integer | null` | yes |
| `promote_cutoff` | `integer` | yes |
| `demote_cutoff` | `integer` | yes |
| `entries` | `LeagueEntryOut[]` | yes |

#### `LedgerEntryOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `source_type` | `string` | yes |
| `source_id` | `string` | yes |
| `points` | `integer` | yes |
| `reason` | `string` | yes |
| `session_id` | `string | null` | yes |
| `created_at` | `string` | yes |

#### `LifetimeStats`

| Field | Type | Required |
|---|---|---|
| `quests_completed` | `integer` | yes |
| `party_quests_completed` | `integer` | yes |
| `rewards_redeemed` | `integer` | yes |
| `points_earned` | `integer` | yes |
| `points_spent` | `integer` | yes |
| `parties_joined` | `integer` | yes |
| `party_xp_contributed` | `integer` | yes |
| `member_since` | `string` | yes |
| `workouts_completed` | `integer` | no |
| `workout_prs` | `integer` | no |
| `total_volume_kg` | `number` | no |
| `longest_workout_streak` | `integer` | no |

#### `LoginRequest`

| Field | Type | Required |
|---|---|---|
| `email` | `string` | yes |
| `password` | `string` | yes |

#### `LogoutRequest`

| Field | Type | Required |
|---|---|---|
| `refresh_token` | `string` | yes |

#### `MeOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `email` | `string` | yes |
| `display_name` | `string` | yes |
| `timezone` | `string` | yes |
| `created_at` | `string` | yes |
| `weight_unit` | `string` | no |
| `character_class` | `string` | no |
| `progress` | `ProgressOut` | yes |

#### `MeUpdate`

| Field | Type | Required |
|---|---|---|
| `weight_unit` | `WeightUnit | null` | no |
| `character_class` | `CharacterClass | string | null` | no |

#### `MeasurementMetric`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `MeasurementUnit`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `MemberOut`

| Field | Type | Required |
|---|---|---|
| `user_id` | `string` | yes |
| `display_name` | `string` | yes |
| `role` | `string` | yes |
| `joined_at` | `string` | yes |
| `level` | `integer` | yes |
| `rank` | `string` | yes |
| `party_xp` | `integer` | yes |

#### `MuscleGroup`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `PartyCreate`

| Field | Type | Required |
|---|---|---|
| `name` | `string` | yes |
| `max_members` | `integer` | no |

#### `PartyOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `name` | `string` | yes |
| `owner_id` | `string` | yes |
| `max_members` | `integer` | yes |
| `member_count` | `integer` | yes |
| `is_active` | `boolean` | yes |
| `created_at` | `string` | yes |
| `my_role` | `string` | yes |
| `invite_code` | `string | null` | no |
| `total_party_xp` | `integer` | no |

#### `PartyQuestCompleteResponse`

| Field | Type | Required |
|---|---|---|
| `xp_awarded` | `integer` | yes |
| `points_awarded` | `integer` | yes |
| `total_xp` | `integer` | yes |
| `level_before` | `integer` | yes |
| `level_after` | `integer` | yes |
| `rank_before` | `string` | yes |
| `rank_after` | `string` | yes |
| `current_streak` | `integer` | yes |
| `longest_streak` | `integer` | yes |
| `leveled_up` | `boolean` | yes |
| `ranked_up` | `boolean` | yes |
| `party_xp_contributed` | `integer` | yes |
| `total_party_xp` | `integer` | yes |

#### `PartyQuestCreate`

| Field | Type | Required |
|---|---|---|
| `title` | `string` | yes |
| `description` | `string | null` | no |
| `xp_reward` | `integer` | no |
| `points_reward` | `integer` | no |
| `recurrence` | `Recurrence` | no |
| `due_at` | `string | null` | no |

#### `PartyQuestOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `party_id` | `string` | yes |
| `title` | `string` | yes |
| `description` | `string | null` | yes |
| `xp_reward` | `integer` | yes |
| `points_reward` | `integer` | yes |
| `recurrence` | `string` | yes |
| `is_active` | `boolean` | yes |
| `due_at` | `string | null` | yes |
| `created_at` | `string` | yes |
| `current_period_key` | `string` | yes |
| `completed_in_current_period` | `boolean` | yes |
| `completed_by_count` | `integer` | yes |

#### `PartyQuestUpdate`

| Field | Type | Required |
|---|---|---|
| `title` | `string | null` | no |
| `description` | `string | null` | no |
| `xp_reward` | `integer | null` | no |
| `points_reward` | `integer | null` | no |
| `recurrence` | `Recurrence | null` | no |
| `is_active` | `boolean | null` | no |
| `due_at` | `string | null` | no |

#### `PartyUpdate`

| Field | Type | Required |
|---|---|---|
| `name` | `string | null` | no |

#### `PointsBreakdownOut`

| Field | Type | Required |
|---|---|---|
| `set_points` | `integer` | yes |
| `pr_bonus` | `integer` | yes |
| `session_bonus` | `integer` | yes |
| `streak_bonus` | `integer` | yes |
| `reversals` | `integer` | yes |
| `total` | `integer` | yes |

#### `PointsSummaryOut`

| Field | Type | Required |
|---|---|---|
| `total_points` | `integer` | yes |
| `this_week_points` | `integer` | yes |
| `sessions_completed` | `integer` | yes |
| `streak` | `StreakOut` | yes |

#### `PrEventOut`

| Field | Type | Required |
|---|---|---|
| `exercise_id` | `string` | yes |
| `exercise_name` | `string` | yes |
| `record_type` | `string` | yes |
| `value` | `number` | yes |
| `weight_kg` | `number | null` | yes |
| `previous_value` | `number | null` | yes |
| `is_baseline` | `boolean` | yes |
| `bonus_awarded` | `boolean` | yes |
| `set_id` | `string | null` | yes |

#### `ProfileOut`

| Field | Type | Required |
|---|---|---|
| `user` | `UserOut` | yes |
| `progress` | `ProgressOut` | yes |
| `stats` | `LifetimeStats` | yes |
| `badges` | `BadgeOut[]` | yes |
| `badges_earned` | `integer` | yes |
| `badges_total` | `integer` | yes |

#### `ProgressOut`

| Field | Type | Required |
|---|---|---|
| `total_xp` | `integer` | yes |
| `current_level` | `integer` | yes |
| `points_balance` | `integer` | yes |
| `longest_streak` | `integer` | yes |
| `last_completed_on` | `string | null` | yes |
| `xp_into_level` | `integer` | yes |
| `xp_for_next_level` | `integer` | yes |
| `current_streak` | `integer` | yes |
| `streak_is_active` | `boolean` | yes |
| `rank` | `string` | yes |
| `rank_by_level` | `string` | yes |
| `next_rank` | `string | null` | yes |
| `next_rank_level` | `integer | null` | yes |
| `next_rank_streak` | `integer | null` | yes |
| `next_rank_trial` | `string | null` | no |
| `trials_passed` | `string` | no |

#### `ProgressionDeltaOut`

| Field | Type | Required |
|---|---|---|
| `xp_awarded` | `integer` | yes |
| `points_awarded` | `integer` | yes |
| `total_xp` | `integer` | yes |
| `level_before` | `integer` | yes |
| `level_after` | `integer` | yes |
| `rank_before` | `string` | yes |
| `rank_after` | `string` | yes |
| `current_streak` | `integer` | yes |
| `longest_streak` | `integer` | yes |
| `leveled_up` | `boolean` | yes |
| `ranked_up` | `boolean` | yes |

#### `PushDeviceRegister`

| Field | Type | Required |
|---|---|---|
| `token` | `string` | yes |
| `environment` | `PushEnvironment` | yes |

#### `PushEnvironment`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `QuestCreate`

| Field | Type | Required |
|---|---|---|
| `title` | `string` | yes |
| `description` | `string | null` | no |
| `xp_reward` | `integer` | no |
| `points_reward` | `integer` | no |
| `recurrence` | `Recurrence` | no |
| `due_at` | `string | null` | no |

#### `QuestOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `title` | `string` | yes |
| `description` | `string | null` | yes |
| `xp_reward` | `integer` | yes |
| `points_reward` | `integer` | yes |
| `recurrence` | `string` | yes |
| `status` | `string` | yes |
| `due_at` | `string | null` | yes |
| `created_at` | `string` | yes |
| `current_period_key` | `string` | yes |
| `completed_in_current_period` | `boolean` | yes |

#### `QuestStatus`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `QuestUpdate`

| Field | Type | Required |
|---|---|---|
| `title` | `string | null` | no |
| `description` | `string | null` | no |
| `xp_reward` | `integer | null` | no |
| `points_reward` | `integer | null` | no |
| `recurrence` | `Recurrence | null` | no |
| `status` | `QuestStatus | null` | no |
| `due_at` | `string | null` | no |

#### `RaidHitOut`

| Field | Type | Required |
|---|---|---|
| `party_id` | `string` | yes |
| `party_name` | `string` | yes |
| `boss_name` | `string` | yes |
| `damage` | `integer` | yes |
| `hp_remaining` | `integer` | yes |
| `defeated` | `boolean` | yes |
| `defeated_now` | `boolean` | yes |

#### `RaidHitterOut`

| Field | Type | Required |
|---|---|---|
| `user_id` | `string` | yes |
| `display_name` | `string` | yes |
| `damage` | `integer` | yes |
| `hits` | `integer` | yes |
| `is_me` | `boolean` | yes |

#### `RaidOut`

| Field | Type | Required |
|---|---|---|
| `party_id` | `string` | yes |
| `week_key` | `string` | yes |
| `name` | `string` | yes |
| `max_hp` | `integer` | yes |
| `hp_remaining` | `integer` | yes |
| `damage_dealt` | `integer` | yes |
| `healed` | `integer` | yes |
| `idle_days` | `integer` | yes |
| `defeated` | `boolean` | yes |
| `defeated_at` | `string | null` | yes |
| `ends_at` | `string` | yes |
| `hitters` | `RaidHitterOut[]` | yes |

#### `RecordOut`

| Field | Type | Required |
|---|---|---|
| `exercise_id` | `string` | yes |
| `exercise_name` | `string` | yes |
| `record_type` | `string` | yes |
| `value` | `number` | yes |
| `weight_kg` | `number | null` | yes |
| `achieved_at` | `string` | yes |
| `session_id` | `string` | yes |
| `set_id` | `string | null` | yes |

#### `Recurrence`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `RedeemResponse`

| Field | Type | Required |
|---|---|---|
| `redemption` | `RedemptionOut` | yes |
| `points_balance` | `integer` | yes |

#### `RedemptionOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `reward_item_id` | `string` | yes |
| `reward_title` | `string` | yes |
| `points_spent` | `integer` | yes |
| `redeemed_at` | `string` | yes |

#### `RefreshRequest`

| Field | Type | Required |
|---|---|---|
| `refresh_token` | `string` | yes |

#### `RewardCreate`

| Field | Type | Required |
|---|---|---|
| `title` | `string` | yes |
| `point_cost` | `integer` | yes |

#### `RewardOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `title` | `string` | yes |
| `point_cost` | `integer` | yes |
| `is_active` | `boolean` | yes |
| `created_at` | `string` | yes |
| `affordable` | `boolean` | yes |
| `times_redeemed` | `integer` | yes |

#### `RewardUpdate`

| Field | Type | Required |
|---|---|---|
| `title` | `string | null` | no |
| `point_cost` | `integer | null` | no |
| `is_active` | `boolean | null` | no |

#### `RoutineExerciseIn`

| Field | Type | Required |
|---|---|---|
| `exercise_id` | `string` | yes |
| `target_sets` | `integer | null` | no |
| `target_reps` | `integer | null` | no |
| `target_weight_kg` | `number | null` | no |
| `rest_seconds` | `integer | null` | no |

#### `RoutineExerciseOut`

| Field | Type | Required |
|---|---|---|
| `position` | `integer` | yes |
| `exercise` | `ExerciseOut` | yes |
| `target_sets` | `integer | null` | yes |
| `target_reps` | `integer | null` | yes |
| `target_weight_kg` | `number | null` | yes |
| `rest_seconds` | `integer | null` | yes |

#### `RoutineIn`

| Field | Type | Required |
|---|---|---|
| `name` | `string` | yes |
| `notes` | `string | null` | no |
| `exercises` | `RoutineExerciseIn[]` | no |

#### `RoutineOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `name` | `string` | yes |
| `notes` | `string | null` | yes |
| `exercises` | `RoutineExerciseOut[]` | yes |
| `created_at` | `string` | yes |
| `updated_at` | `string` | yes |

#### `SessionExerciseOut`

| Field | Type | Required |
|---|---|---|
| `exercise` | `ExerciseOut` | yes |
| `hint` | `HintOut | null` | no |
| `target` | `SessionTargetOut | null` | yes |
| `sets` | `SetOut[]` | yes |
| `previous_sets` | `SetOut[]` | yes |

#### `SessionOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `name` | `string | null` | yes |
| `status` | `string` | yes |
| `routine_id` | `string | null` | yes |
| `started_at` | `string` | yes |
| `ended_at` | `string | null` | yes |
| `duration_seconds` | `integer` | yes |
| `working_sets` | `integer` | yes |
| `total_volume_kg` | `number` | yes |
| `points_total` | `integer` | yes |
| `points_credited` | `integer` | yes |
| `qualified` | `boolean | null` | yes |
| `exercises` | `SessionExerciseOut[]` | yes |

#### `SessionStart`

| Field | Type | Required |
|---|---|---|
| `routine_id` | `string | null` | no |
| `name` | `string | null` | no |

#### `SessionStatus`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `SessionSummaryOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `name` | `string | null` | yes |
| `status` | `string` | yes |
| `started_at` | `string` | yes |
| `ended_at` | `string | null` | yes |
| `duration_seconds` | `integer` | yes |
| `working_sets` | `integer` | yes |
| `exercise_count` | `integer` | yes |
| `total_volume_kg` | `number` | yes |
| `points_total` | `integer` | yes |
| `pr_count` | `integer` | yes |

#### `SessionTargetOut`

| Field | Type | Required |
|---|---|---|
| `target_sets` | `integer | null` | yes |
| `target_reps` | `integer | null` | yes |
| `target_weight_kg` | `number | null` | yes |
| `rest_seconds` | `integer | null` | yes |

#### `SetCreate`

| Field | Type | Required |
|---|---|---|
| `weight` | `number` | no |
| `unit` | `WeightUnit` | no |
| `reps` | `integer | null` | no |
| `rpe` | `number | null` | no |
| `is_warmup` | `boolean` | no |
| `duration_seconds` | `integer | null` | no |
| `distance_m` | `number | null` | no |
| `exercise_id` | `string` | yes |
| `client_set_id` | `string | null` | no |

#### `SetDeleteResponse`

| Field | Type | Required |
|---|---|---|
| `points_awarded` | `integer` | yes |
| `session_points` | `integer` | yes |
| `progression` | `ProgressionDeltaOut` | yes |

#### `SetLogResponse`

| Field | Type | Required |
|---|---|---|
| `set` | `SetOut` | yes |
| `pr_events` | `PrEventOut[]` | yes |
| `awards` | `AwardOut[]` | yes |
| `points_awarded` | `integer` | yes |
| `session_points` | `integer` | yes |
| `set_cap_reached` | `boolean` | yes |
| `progression` | `ProgressionDeltaOut` | yes |
| `is_duplicate` | `boolean` | no |

#### `SetOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `session_id` | `string` | yes |
| `exercise_id` | `string` | yes |
| `set_number` | `integer` | yes |
| `weight_kg` | `number` | yes |
| `reps` | `integer | null` | yes |
| `rpe` | `number | null` | yes |
| `is_warmup` | `boolean` | yes |
| `is_pr` | `boolean` | yes |
| `duration_seconds` | `integer | null` | yes |
| `distance_m` | `number | null` | yes |
| `completed_at` | `string` | yes |

#### `SetUpdate`

| Field | Type | Required |
|---|---|---|
| `weight` | `number | null` | no |
| `unit` | `WeightUnit` | no |
| `reps` | `integer | null` | no |
| `rpe` | `number | null` | no |
| `is_warmup` | `boolean | null` | no |
| `duration_seconds` | `integer | null` | no |
| `distance_m` | `number | null` | no |

#### `SignupRequest`

| Field | Type | Required |
|---|---|---|
| `email` | `string` | yes |
| `password` | `string` | yes |
| `display_name` | `string` | yes |
| `timezone` | `string` | no |

#### `StatOut`

| Field | Type | Required |
|---|---|---|
| `key` | `string` | yes |
| `label` | `string` | yes |
| `value` | `integer` | yes |
| `detail` | `string` | yes |
| `highlighted` | `boolean` | yes |

#### `StreakOut`

| Field | Type | Required |
|---|---|---|
| `weeks` | `integer` | yes |
| `this_week_sessions` | `integer` | yes |
| `target` | `integer` | yes |
| `this_week_done` | `boolean` | yes |
| `sessions_to_go` | `integer` | yes |

#### `TokenResponse`

| Field | Type | Required |
|---|---|---|
| `access_token` | `string` | yes |
| `token_type` | `string` | no |
| `expires_in` | `integer` | yes |
| `refresh_token` | `string` | yes |
| `refresh_expires_in` | `integer` | yes |

#### `TrialOut`

| Field | Type | Required |
|---|---|---|
| `rank` | `string` | yes |
| `lift` | `string` | yes |
| `description` | `string` | yes |
| `multiplier` | `number` | yes |
| `target_kg` | `number | null` | yes |
| `best_kg` | `number | null` | yes |
| `passed` | `boolean` | yes |

#### `UserOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `email` | `string` | yes |
| `display_name` | `string` | yes |
| `timezone` | `string` | yes |
| `created_at` | `string` | yes |
| `weight_unit` | `string` | no |
| `character_class` | `string` | no |

#### `ValidationError`

| Field | Type | Required |
|---|---|---|
| `loc` | `string | integer[]` | yes |
| `msg` | `string` | yes |
| `type` | `string` | yes |
| `input` | `object` | no |
| `ctx` | `object` | no |

#### `WalletOut`

| Field | Type | Required |
|---|---|---|
| `points_balance` | `integer` | yes |
| `total_points_earned` | `integer` | yes |
| `total_points_spent` | `integer` | yes |

#### `WeightUnit`

| Field | Type | Required |
|---|---|---|
| _(no properties)_ | | |

#### `WorkoutImportIn`

| Field | Type | Required |
|---|---|---|
| `csv` | `string` | yes |
| `unit` | `WeightUnit | null` | no |

#### `WorkoutImportOut`

| Field | Type | Required |
|---|---|---|
| `source` | `string` | yes |
| `workouts_imported` | `integer` | yes |
| `sets_imported` | `integer` | yes |
| `workouts_skipped` | `integer` | yes |
| `rows_skipped` | `integer` | yes |
| `exercises_created` | `string[]` | yes |
| `xp_awarded` | `integer` | yes |
| `duplicate` | `boolean` | yes |
| `progression` | `ProgressionDeltaOut | null` | yes |

#### `WorkoutLeaderboardEntry`

| Field | Type | Required |
|---|---|---|
| `position` | `integer` | yes |
| `user_id` | `string` | yes |
| `display_name` | `string` | yes |
| `points` | `integer` | yes |
| `workouts` | `integer` | yes |
| `level` | `integer` | yes |
| `rank` | `string` | yes |
| `is_me` | `boolean` | yes |

#### `WorkoutLeaderboardOut`

| Field | Type | Required |
|---|---|---|
| `party_id` | `string` | yes |
| `period` | `string` | yes |
| `period_start` | `string | null` | yes |
| `entries` | `WorkoutLeaderboardEntry[]` | yes |
