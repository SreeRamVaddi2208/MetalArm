# Gym Workout Module - API Reference (frontend handoff)

> Hand-written companion to the generated `docs/api-contract.md`. The contract
> is the source of truth for **field shapes**; this file explains **behaviour**:
> what to call when, what each flag means, and which rules the UI must never
> re-implement. Backend Agent owns it. If you need something that is not here,
> ask for it - do not invent an endpoint or compute a value client-side.

**Frontend status:** implemented in Reflex - pages `frontend/metalarm/pages/`
`workout.py`, `routines.py`, `progress.py`; state in `frontend/metalarm/state/`
(`workout.py`, `picker.py`, `routines.py`, `progress.py`).

All paths are under `/api/v1` and need `Authorization: Bearer <token>`, the
same as every other endpoint. Another user's session, set, routine, custom
exercise or measurement is always **404**, never 403.

---

## The rules the UI must follow

1. **Never compute points, XP, PRs or streaks.** Every number comes from a
   response. No request accepts a point value; sending one is silently ignored.
2. **Celebrate from the response, not a diff.** Logging a set returns
   `pr_events` and `progression.leveled_up` / `ranked_up` directly.
3. **Rehydrate on load.** Call `GET /workouts/sessions/active` on page load. A
   refresh mid-workout loses nothing: the session lives on the server.
4. **Send a `client_set_id`** (a fresh UUID per submit tap). A retry or
   double-tap with the same id returns the original set with
   `is_duplicate: true` and awards nothing twice.
5. **Weights come back in kg.** You may submit `unit: "lb"`, and the server
   converts. Convert back for display if the user prefers pounds.

## How points reach the game layer

| Moment | XP / level bar | Shop points (wallet) |
|---|---|---|
| Log a set | moves immediately (`progression`) | not yet |
| Edit / delete a set | adjusted immediately (can go down) | not yet |
| Finish | session + streak bonus added | **whole session credited** (`points_credited`) |
| Abandon | everything from the session reversed | nothing |

Show `session_points` from each set response as the live in-workout counter.
Shop points arrive at finish because sets can still be edited until then.

---

## Exercise library

| Method | Path | Notes |
|---|---|---|
| GET | `/exercises` | Library + the user's own. Query: `q` (name contains), `category`, `equipment`, `muscle`, `custom_only`, `include_archived`, `limit` (≤200), `offset`. |
| GET | `/exercises/meta` | Allowed `categories`, `equipment`, `muscle_groups`, `weight_units`, `measurement_metrics`, `measurement_units`. Build filter chips from this - don't hardcode them. |
| POST | `/exercises` | Create a custom exercise: `{name, category, primary_muscle_groups[], equipment, instructions?, media_url?}`. 409 on a duplicate name (case- and space-insensitive). |
| GET/PATCH | `/exercises/{id}` | PATCH only on your own custom exercises. **403** for library exercises. |
| DELETE | `/exercises/{id}` | Returns `{"archived": bool}`. A custom exercise that is used anywhere is **archived** (hidden from the picker) instead of deleted. |
| GET | `/exercises/{id}/history` | Chart data, one point per completed session, oldest first: `top_weight_kg`, `top_weight_reps`, `best_est_1rm`, `volume_kg`, `working_sets`, `total_reps`. `limit` ≤365. |
| GET | `/exercises/{id}/last-performance` | Ghost values for an exercise added mid-workout: the last completed session's `sets`. Empty list if never done. |

## Routines

| Method | Path | Notes |
|---|---|---|
| GET | `/routines` | Most recently edited first. |
| POST | `/routines` | `{name, notes?, exercises: [{exercise_id, target_sets?, target_reps?, target_weight_kg?, rest_seconds?}]}`. The list order is the routine order. |
| GET | `/routines/{id}` | |
| PUT | `/routines/{id}` | **Full replace**, same body as POST. |
| DELETE | `/routines/{id}` | 204. Workouts started from it keep their history. |

An unknown, archived, or other user's exercise id in a routine → **422**.
Use `rest_seconds` to seed the client-side rest timer.

## Training paths

| Method | Path | Notes |
|---|---|---|
| GET | `/training-categories` | The three paths - athletic, bodybuilder, powerlifter - with tagline, rep range, load, volume, rest and emphasis tags. Render the cards from this; do not hardcode the copy. |

The path itself is `users.character_class`, set with
`PATCH /auth/me {"character_class": "athlete"}` and cleared with `""`. `/auth/me`
returns `character_class_set_at`: **null means never asked**, which is how the
app knows whether to put the question up; declining writes the timestamp with an
empty path.

A path decides what is SUGGESTED - the ready-made workout below is ordered by it
(`matches_your_path`) - and which character stats are highlighted. It never
affects points, XP, records, streaks or a leaderboard.

## Ready-made workouts

| Method | Path | Notes |
|---|---|---|
| GET | `/workouts/presets` | The three styles. Each slot carries its whole exercise, `media_url` included, so the UI can show a demo of the movement. The workout matching the caller's training path comes **first**, flagged `matches_your_path`; `category_label` is what to print ("Athletic"), `category` is what is stored ("athlete"). |

`POST /workouts/sessions {"preset_slug": "..."}` starts one. Send `preset_slug`
or `routine_id`, never both (**422**); an unknown slug is a **404**.

Presets are definitions in `backend/app/data/workout_presets.json`, not rows.
Starting one materialises the user's own routine from it - once, reused after
that - because a session takes its targets, its planned order and its ghost
values from a routine. The copy is a normal routine afterwards: listed, and
editable.

**Demos are links, not files.** A demo is whatever `media_url` the exercise
carries (`backend/app/data/exercises.json`, loaded by
`scripts/import_exercises.py`, which runs on every deploy). Adding clips is
editing that file - no client release. An exercise with no link shows a
placeholder of the same size, so nothing jumps as links are filled in.

## Workout sessions

| Method | Path | Notes |
|---|---|---|
| POST | `/workouts/sessions` | `{routine_id?, name?}` → `SessionOut`. **409** if a workout is already live (the detail contains its id). |
| GET | `/workouts/sessions/active` | `{"session": SessionOut \| null}`. Always 200. |
| GET | `/workouts/sessions` | History, newest first. `status`, `limit` (≤100), `before` (ISO datetime cursor = last row's `started_at`). |
| GET | `/workouts/sessions/{id}` | `SessionOut`. |
| POST | `/workouts/sessions/{id}/sets` | Log a set → `SetLogResponse` (201). |
| PATCH | `/workouts/sessions/{id}/sets/{set_id}` | Fix a set → `SetLogResponse`. Any of `weight`+`unit`, `reps`, `rpe`, `is_warmup`, `duration_seconds`, `distance_m`. |
| DELETE | `/workouts/sessions/{id}/sets/{set_id}` | → `{points_awarded (negative), session_points, progression}`. |
| POST | `/workouts/sessions/{id}/finish` | → `FinishResponse`, the summary screen. |
| POST | `/workouts/sessions/{id}/abandon` | → `{session, points_reversed, progression}`. |

### `SessionOut` - render the live workout from this

```json
{
  "id": "…", "name": "Push day", "status": "in_progress", "routine_id": "…",
  "started_at": "…", "ended_at": null, "duration_seconds": 1260,
  "working_sets": 7, "total_volume_kg": 3150.0, "points_total": 64,
  "points_credited": 0, "qualified": null,
  "exercises": [
    {
      "exercise": { "id": "…", "name": "Barbell Bench Press", "primary_muscle_groups": ["chest","triceps","shoulders"], "…": "…" },
      "target": { "target_sets": 3, "target_reps": 5, "target_weight_kg": 100.0, "rest_seconds": 180 },
      "sets":          [ { "id": "…", "set_number": 1, "weight_kg": 100.0, "reps": 5, "rpe": 8.0, "is_warmup": false, "is_pr": true, "…": "…" } ],
      "previous_sets": [ { "set_number": 1, "weight_kg": 97.5, "reps": 5, "…": "…" } ]
    }
  ]
}
```

A session started from a routine lists the routine's exercises (with `target`)
before any sets exist. `previous_sets` holds the **ghost values** (the last
completed session's sets for that exercise).

### Logging a set

Request - one tap, minimal fields:

```json
{ "exercise_id": "…", "weight": 100, "unit": "kg", "reps": 5,
  "rpe": 8, "is_warmup": false, "client_set_id": "8d7f…" }
```

- Strength: `reps` (plus `weight`; `0` for bodyweight).
- Cardio / timed holds: `duration_seconds` and/or `distance_m` (`reps` may be null).
- At least one of `reps`, `duration_seconds` or `distance_m` is required (otherwise 422).

Response (`SetLogResponse`):

```json
{
  "set": { "id": "…", "set_number": 2, "weight_kg": 110.0, "reps": 5, "is_pr": true, "…": "…" },
  "pr_events": [
    { "record_type": "max_weight", "value": 110.0, "weight_kg": 110.0, "previous_value": 100.0,
      "is_baseline": false, "bonus_awarded": true, "exercise_name": "Barbell Bench Press", "…": "…" },
    { "record_type": "est_1rm", "value": 128.33, "previous_value": 116.67,
      "is_baseline": false, "bonus_awarded": false, "…": "…" }
  ],
  "awards": [
    { "source_type": "set_logged", "points": 2, "reason": "Set logged" },
    { "source_type": "pr_achieved", "points": 50, "reason": "New PR: max_weight" }
  ],
  "points_awarded": 52, "session_points": 66, "set_cap_reached": false,
  "progression": { "total_xp": 1840, "level_before": 9, "level_after": 10,
                   "leveled_up": true, "ranked_up": false, "rank_after": "D", "…": "…" },
  "is_duplicate": false
}
```

**How to read `pr_events`, the PR celebration:**

| Condition | Meaning | Suggested UI |
|---|---|---|
| any event with `bonus_awarded: true` | a real PR that paid the PR bonus | **The big moment.** Lead with that event: "+10 kg on Bench". |
| events, none paid, `is_baseline: false` | a genuine record that earned no bonus (a lighter-weight rep PR, a second PR on the same exercise this session, or a tiny improvement) | smaller "new record" beat |
| all events `is_baseline: true` | first time this exercise was ever logged | "first log", no fanfare |
| `[]` | nothing broken | nothing |

`record_type` values: `max_weight`, `max_reps_at_weight` (value = reps,
`weight_kg` = the weight), `est_1rm`, `max_volume` (finish only).

`set.is_pr` is true only when the set beat an existing record. A first-ever
baseline set has `pr_events` (all `is_baseline: true`) but `is_pr: false`.

### Finishing - `FinishResponse`

```json
{
  "session": { "duration_seconds": 3480, "working_sets": 18, "total_volume_kg": 9120.0, "pr_count": 2, "…": "…" },
  "qualified": true,
  "awards": [
    { "source_type": "session_completed", "points": 36, "reason": "Workout completed" },
    { "source_type": "streak_bonus", "points": 20, "reason": "2-week streak" }
  ],
  "breakdown": { "set_points": 36, "pr_bonus": 50, "session_bonus": 36,
                 "streak_bonus": 20, "reversals": -2, "total": 140 },
  "points_credited": 140,
  "pr_events": [ "…every record set this session, including max_volume…" ],
  "streak": { "weeks": 2, "this_week_sessions": 3, "target": 3,
              "this_week_done": true, "sessions_to_go": 0 },
  "progression": { "leveled_up": false, "…": "…" }
}
```

`qualified: false` means the workout was too short (under 10 minutes or fewer
than 3 working sets). It still completes and keeps its set points, but gets no
session bonus and doesn't count toward the streak. Say so on the summary rather
than showing a silent zero.

### 409s the UI should expect

| When | Detail |
|---|---|
| Starting while one is live | "A workout is already in progress (…id…) - finish or abandon it first" |
| Any change to a finished/abandoned workout | "This workout is already completed" / "…abandoned" |
| Logging to a workout open > 6 hours | "…open for over 6 hours - finish or abandon it…" |
| Logging an archived exercise | "That exercise has been archived" |

## Records, points, streak

| Method | Path | Notes |
|---|---|---|
| GET | `/workouts/records` | Current PRs; optional `exercise_id`. One row per type per exercise, **except** `max_reps_at_weight`, which returns the best reps at each weight (several rows). |
| GET | `/workouts/points` | `{total_points, this_week_points, sessions_completed, streak}`. |
| GET | `/workouts/points/ledger` | Newest first, `limit` ≤200, `before` cursor. Undoing an award adds a negative `reversal` row; no row is ever edited. |

The **weekly streak** counts consecutive ISO weeks (in the user's timezone) that
each contain `target` qualifying workouts. The current week doesn't break it
while in progress: show `sessions_to_go` ("1 more workout keeps your streak").
A qualifying workout also advances the app-wide **daily** streak on the Stat
Panel (the one that gates A/S rank), exactly like completing a quest.

## Account preference, profile, and the party workout board

| Method | Path | Notes |
|---|---|---|
| PATCH | `/auth/me` | `{weight_unit: "kg" \| "lb"}` → `MeOut`. The display unit lives on the account (`weight_unit` is on `/auth/me` and `/profile`), so it follows the user across devices. |
| GET | `/profile` | `stats` now also carries `workouts_completed`, `workout_prs` (sets that beat a record), `total_volume_kg`, `longest_workout_streak` (weeks). Six workout badges join the list: `first_workout`, `ten_workouts`, `fifty_workouts`, `first_pr`, `prs_25`, `workout_streak_4`. |
| GET | `/parties/{id}/workout-leaderboard` | `?period=week\|all`. Members ranked by workout points from the ledger, with `workouts` finished in the window. `week` is the viewer's current ISO week. Members only (404 otherwise). |

## Body measurements

| Method | Path | Notes |
|---|---|---|
| GET | `/body-measurements` | Newest first. `metric`, `limit` ≤500. |
| POST | `/body-measurements` | `{metric: weight\|body_fat\|custom, value, unit, label?, recorded_at?}`. `weight` → `kg`/`lb`; `body_fat` → `percent`; `custom` requires `label`. |
| DELETE | `/body-measurements/{id}` | 204. |

Measurements never earn points.

---

## Current point values (placeholders - brief Section 7)

All in `backend/app/core/workout_rules.py`, and only there. Shown so the UI
copy can make sense; **never hardcode them** - render what responses say.

| Rule | Value |
|---|---|
| Working set | 2 pts, capped at 50 per workout; warm-ups 0 |
| Finished workout (≥10 min, ≥3 working sets) | 25 × up to 1.5 (duration and set count), so 25-38 |
| PR bonus | 50; one per exercise per workout, three per workout; first-ever log and <1% gains excluded |
| Weekly streak (3 workouts/week) | 10 × streak weeks, max 100, paid once per week |
| 1 workout point | = 1 XP **and** 1 shop point |
