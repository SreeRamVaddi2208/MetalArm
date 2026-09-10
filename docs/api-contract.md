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
- **Generated:** 2026-09-10 08:09 UTC
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

JSON login - the endpoint the Reflex frontend uses.

*Tags:* `auth`

*Request body* (`application/json`): `LoginRequest`

| Status | Description |
|---|---|
| `200` | Successful Response |
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

### `GET /api/v1/profile`

**Read Profile**

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

#### `Body_login_form_api_v1_auth_token_post`

| Field | Type | Required |
|---|---|---|
| `grant_type` | `string | null` | no |
| `username` | `string` | yes |
| `password` | `string` | yes |
| `scope` | `string` | no |
| `client_id` | `string | null` | no |
| `client_secret` | `string | null` | no |

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

#### `HTTPValidationError`

| Field | Type | Required |
|---|---|---|
| `detail` | `ValidationError[]` | no |

#### `JoinRequest`

| Field | Type | Required |
|---|---|---|
| `invite_code` | `string` | yes |

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

#### `LoginRequest`

| Field | Type | Required |
|---|---|---|
| `email` | `string` | yes |
| `password` | `string` | yes |

#### `MeOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `email` | `string` | yes |
| `display_name` | `string` | yes |
| `timezone` | `string` | yes |
| `created_at` | `string` | yes |
| `progress` | `ProgressOut` | yes |

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

#### `SignupRequest`

| Field | Type | Required |
|---|---|---|
| `email` | `string` | yes |
| `password` | `string` | yes |
| `display_name` | `string` | yes |
| `timezone` | `string` | no |

#### `TokenResponse`

| Field | Type | Required |
|---|---|---|
| `access_token` | `string` | yes |
| `token_type` | `string` | no |
| `expires_in` | `integer` | yes |

#### `UserOut`

| Field | Type | Required |
|---|---|---|
| `id` | `string` | yes |
| `email` | `string` | yes |
| `display_name` | `string` | yes |
| `timezone` | `string` | yes |
| `created_at` | `string` | yes |

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
