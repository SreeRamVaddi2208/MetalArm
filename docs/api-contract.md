# LevelForge API Contract

> **GENERATED FILE - do not hand-edit.**
> Regenerate with `python scripts/generate_api_contract.py` while the
> backend is running. Backend Agent owns this file.
>
> **Frontend Agent:** treat this as the single source of truth for
> endpoint shapes. Never invent an endpoint. If something you need is
> missing, ask Backend Agent to add it and regenerate - do not guess.

- **API title:** LevelForge API
- **API version:** 0.1.0
- **Generated:** 2026-09-09 22:21 UTC
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

#### `ValidationError`

| Field | Type | Required |
|---|---|---|
| `loc` | `string | integer[]` | yes |
| `msg` | `string` | yes |
| `type` | `string` | yes |
| `input` | `object` | no |
| `ctx` | `object` | no |
