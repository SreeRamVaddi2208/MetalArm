# MetalArm (formerly LevelForge) - Progress Log

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

## 2026-09-14 (17) - Opus - grey identity: palette, app icon, level-up celebration

**Changed**
- One grey, machined-steel palette in both apps (`ios/MetalARM/Theme/Theme.swift`,
  `frontend/metalarm/theme.py`, identical values): near-black ground `#0B0B0C`,
  graphite panels, text `#F2F2F4` / muted `#A8A8B0` / faint `#7C7C84`, white and
  silver as the only accents. Red `#E5484D` is kept only for errors and
  destructive actions. Ranks are told apart by brightness (E dark grey to S white).
- iOS tokens renamed from colours to roles (`fire` -> `accent`, `violet`/`gold`
  -> `silver`, `green` -> `success`, new `danger`, `borderStrong`); primary
  buttons are white with near-black text; the XP bar is white to silver.
- Web: ~25 hard-coded hex values moved onto new tokens (`FIELD`, `ON_ACCENT`,
  `SUCCESS_BG`, `WARNING_BG`, `DANGER_BG`, `VEIL`).
- App icon: a faceted-steel flexing arm resting on a polished "MA", on
  near-black with a soft silver light. Source `scripts/icon/metalarm-icon.svg`;
  `node scripts/icon/render_icon.mjs` renders the iOS icon (plus the iOS 18
  tinted variant, now in `Contents.json`) and the web `favicon.png` /
  `apple-touch-icon.png`, all opaque. The web app links both in `rx.App`.
- Level-up celebration on iOS (`Views/LevelUpView.swift`): shown over the
  summary for every level-up or rank-up in the FinishResponse. The new level
  punches in, silver rings burst, 24 metal sparks fly, and a success haptic plays;
  rank-up is bigger (extra ring, double heavy haptic). Reduce Motion gives a
  fade; VoiceOver announces the level. Tap or Continue to dismiss.
- Web level-up overlay restyled in silver with sparks and a shine sweep;
  reduced-motion still collapses it to a fade.
- Mock backend: `-UITestLevelUp` makes finishing a workout level up (14 -> 15);
  new UI test `testLevelUpCelebration`.

**Verified (real output)**
- iOS `xcodebuild test` with the live tour on the iPhone 17 Pro Max: **TEST SUCCEEDED**,
  MetalARMTests 35 passed, MetalARMUITests 7 passed (including `testLevelUpCelebration`).
- `scripts/e2e` against the rebuilt web image: **ALL PASSED (72)**, level-up moment included.
- `/favicon.png` and `/apple-touch-icon.png` return 200 and both `<link>` tags are in the page.
- Icons are 1024x1024 (180 and 64 for the web) with `hasAlpha: no`.
- No old accent colour values remain in `frontend/`, `ios/` or `scripts/`.

**Blocked**
- Nothing.

**Other agent needs to know**
- Use `Theme.accent`/`silver`/`danger` (iOS) and `theme.ACCENT`/`ON_ACCENT`/
  `DANGER` (web); no raw colour values outside the two theme files.

---

## 2026-09-14 (16) - Opus - iOS app uses the design fonts

**Changed**
- Bundled the design's typefaces in the iOS app, the same pair the web app
  uses: Space Grotesk (headings, numbers, buttons) and Manrope (body). Static
  400/500/600/700 TTFs cut from the google/fonts variable sources with
  `fontTools varLib.instancer`, in `ios/MetalARM/Fonts/` with both SIL Open
  Font Licences, registered under `UIAppFonts` in `Info.plist`.
- `Theme.display` now uses Space Grotesk; the new `Theme.body` (Manrope)
  replaces all 69 `.font(.system(size:))` calls in the views. Requests
  heavier than bold map to Bold (the heaviest bundled face).
- New `FontTests.bundledFontLoads` checks each face loads by PostScript name.
- Re-captured all 11 App Store screenshots on the iPhone 17 Pro Max
  (1320x2868) from the mock-backend UI tests.

**Verified (real output)**
- `FontTests`: all 8 faces load; MetalARMTests pass.
- UI tests pass on the iPhone 17 Pro Max (source of the screenshots).
- Full suite with the live tour on the merged branch: see the PR.

**Blocked**
- Nothing.

**Other agent needs to know**
- Use `Theme.display(size, weight)` / `Theme.body(size, weight)` for new
  text, never `.system(size:)`. Space Grotesk's SemiBold instance has a
  hand-set name table (its STAT table has no 600 value); regenerate it the
  same way if the font files are ever updated.

---

## 2026-09-14 (15) - Opus - sign out one device, not all of them

**Changed**
- New `auth_sessions` table (`AuthSession`, migration `ce1968933857`): one row
  per signed-in device. Login and `/auth/token` start a session; both tokens
  carry its id as the `sid` claim, and `/auth/refresh` keeps it. A refresh
  token without `sid` (minted before sessions existed) is rejected: sign in again.
- `get_current_user` and `/auth/refresh` reject tokens whose session is
  revoked. `POST /auth/logout` now revokes only the caller's session;
  new `POST /auth/logout-all` bumps `token_version` and revokes every session
  (the old "sign out everywhere"). Deleting the account cascades its sessions.
- `/auth/logout` takes `{"refresh_token": ...}` in the body (no bearer needed),
  so a client whose access token has expired still revokes its session; a
  bearer access token alone also works. Signing out a token without `sid`
  bumps `token_version` (the only way to end it) instead of a silent 204.
- iOS: `signOut()` forgets the tokens first, then sends the refresh token to
  `/auth/logout` (best effort); `AppModel` resets the UI before that call, so
  a slow or offline server never holds sign-out. `signOutEverywhere()` uses
  `logout-all`.
- Web: `AuthState.do_logout` sends the refresh token to `/auth/logout`
  before clearing tokens.
- `scripts/e2e`: waits for the discard confirmation row before clicking its
  DISCARD button (the click could land on the old button and stall).
- iOS UI tests: `dismissSavePasswordPrompt` retries "Not Now" until the
  Save Password sheet is gone (a tap during its slide-in was swallowed and
  the sheet covered Home, failing the live tour).

**Verified (real output)**
- Backend suite passes (4 new tests: this-device logout, refresh keeps the
  session, logout-all, account deletion removes sessions); `alembic check` clean.
- `scripts/e2e`: **ALL PASSED (72)**. Web sign-out check: the signed-out
  browser's refresh token -> 401, another device's session -> 200.
- iOS `xcodebuild test`: MetalARMTests 33 passed (3 new sign-out tests),
  UI tests passed including the live-backend tour.

**Blocked**
- Nothing.

**Other agent needs to know**
- The auth signup limit is 5/hour per IP; running e2e, the sign-out check and
  the iOS live tour back to back exhausts it locally (the tour then fails on
  a 429). Wait out the window or delete `ratelimit:signup-ip:*` in dev Redis.

---

## 2026-09-14 (14) - Opus - web sessions survive the 60-minute access token

**Changed**
- The Reflex frontend now keeps the `refresh_token` (LocalStorage `lf_refresh`)
  next to the access token and renews the pair before it expires:
  `AuthState.refresh_me` (first handler on every signed-in page) refreshes a
  token with under 10 minutes left and retries once on a 401 before signing
  out; a hidden 5-minute `rx.moment` tick in `components/layout.py:shell()`
  calls `AuthState.keep_fresh`, so a page left open (a long workout) never
  hits an expired token mid-set. A rejected refresh ends the session; a
  network failure keeps it.
- New `api.refresh()`. Expiry is read from the JWT payload without verifying
  it (the server verifies every request).

**Verified (real output)**
- `docker compose build frontend` (runs `reflex export`) succeeded.
- `scripts/e2e`: **ALL PASSED (72)** against the rebuilt frontend.
- Short-expiry check with `ACCESS_TOKEN_EXPIRE_MINUTES=1`: signed in through
  the login page, both tokens stored, waited 75 s, reopened the dashboard ->
  still signed in, account loaded, access token replaced; the backend served
  2 `POST /auth/refresh` -> 200. Backend restored to 60 minutes afterwards.

**Blocked**
- Nothing.

**Other agent needs to know**
- Other states still read `AuthState.token` directly; freshness is handled
  centrally, so they need no change.

## 2026-09-13 (13) - Opus - deployment readiness: mobile auth, production stack, CI, iOS app

Made the project deployable end to end and moved the native iPhone app into
this repo (`ios/`, previously a separate copy talking to an older SQLite demo
API).

**Changed**
- **Auth for mobile and production.** Login returns a 30-day `refresh_token`;
  `POST /auth/refresh` swaps it for a new pair. Tokens carry `typ`, and
  `deps.get_current_user` now rejects anything that is not an access token
  (before this, a refresh token would have worked as a 30-day API key).
  New `users.token_version` (migration `7b3e9d41c2a8`, default 0 so existing
  tokens stay valid): `POST /auth/logout` bumps it and revokes every token.
- **Account deletion** (App Store requirement): `DELETE /auth/me` with password
  confirmation. Party ownership handover was pulled out of `leave_party` into
  `release_membership()` and reused, because `parties.owner_id` cascades: a
  deleted owner would otherwise have taken the whole party with them.
- **Rate limits** (`app/core/rate_limit.py`): Redis fixed windows on login
  (per IP and per account), signup and refresh; 429 + `Retry-After`; fails
  open if Redis is down. Off by default in the test suite (autouse fixture).
- **`ENVIRONMENT=production`** hides `/docs`, `/redoc`, `/openapi.json`.
- **`deploy/`**: single-server Compose stack behind Caddy (automatic HTTPS,
  security headers, only 80/443 public), uvicorn `--proxy-headers`, nightly
  `pg_dump` with retention, `backup.sh` restore, `/privacy` and `/support`
  pages, `.env.production.example`. Guide: `docs/deployment.md`.
- **CI** (`.github/workflows/ci.yml`): backend pytest + `alembic check` on
  Postgres/Redis service containers, both image builds, prod Compose
  validation, iOS tests on a macOS runner.
- **iOS app on `/api/v1`**: Keychain tokens with refresh-once-then-sign-out,
  sign up / sign in, workouts with library picker and ghost values,
  `client_set_id` per tap, server-driven PR/level-up/finish screens, progress
  from history + records, party boards, kg/lb from the account, delete
  account. Release setup: iOS 18+, iPhone portrait, opaque icon, privacy
  manifest, per-configuration API/web URLs.
- README rewritten to cover all three parts.

**Verified (real output)**
- `pytest`: **332 passed**. `alembic check`: no drift at `7b3e9d41c2a8`
  (applied to the dev DB after a `pg_dump` backup; `/health` ok).
- Production stack run locally with `DOMAIN=localhost`: all services healthy;
  `https://api.localhost/health` ok; `/docs`, `/openapi.json`, `/redoc` 404;
  HSTS and security headers present; `/privacy` served; 11th bad login 429
  with `Retry-After`; backend logged the real client address, not Caddy's;
  backup service wrote a dump. Torn down with `down -v` afterwards.
- iOS: **30 unit + 7 UI tests passed** on the iPhone 17 simulator (iOS 26.5),
  including the live tour against the dev stack (signup -> workout -> finish
  -> every tab -> delete account, every request 2xx). Unsigned Release build
  for a generic iPhone succeeded. App Store screenshots captured on iPhone 17
  Pro Max (1320x2868).

**Blocked**
- Needs the owner's accounts: a domain and server, an Apple Developer
  membership (signing team, TestFlight), and App Store Connect.

**Other agent needs to know**
- Refresh tokens are stateless: revocation is per user (`token_version`), not
  per device. Per-device sign-out is the client dropping its tokens.
- The Reflex frontend ignores `refresh_token`; it still re-logs in when its
  60-minute access token expires.
- iOS UI tests must dismiss the system "Use Strong Password?" and "Save
  Password?" sheets (helpers in `MetalARMUITests.swift`).

## 2026-09-10 (12) - Opus - close every open workout item; UI polish pass

Built everything left open in entry (11), then verified and cleaned the whole
UI, not only the new pages.

**Built**
- **Weight unit on the account.** New `users.weight_unit` column (migration
  `2caadc5c9d12`, CHECK kg/lb) and `PATCH /auth/me`. The kg/lb toggle now
  saves to the account and follows the user to a fresh browser. It was
  previously per-browser LocalStorage.
- **Edit a logged set in the UI.** Tap a set row to open an inline editor
  (weight/reps or minutes/km, RPE, warm-up). It saves through the existing
  `PATCH`, and the result is shown exactly like a new log, so an edit that
  earns a PR raises the PR moment.
- **Unlogged exercises survive a refresh.** They are persisted per session in
  LocalStorage and restored on load. They are dropped once logged, removed,
  or the session ends.
- **Workout stats and badges on the profile.** Workouts completed, PR sets,
  lifetime volume and best week streak are shown in the user's unit, plus six
  badges (Iron Initiate, Regular, Gym Rat, Record Breaker, Always Climbing,
  Four-Week Block). Like the existing badges they are derived, never stored,
  and key off values that never go down (`longest_weekly_streak`).
- **Party workout board.** `GET /parties/{id}/workout-leaderboard?period=week|all`:
  members ranked by ledger points, with workouts finished. Members only.
  `week` is the viewer's ISO week.
- **Browser E2E committed** as `scripts/e2e/` (playwright-core against the
  installed Chrome). It is documented in the README.

**UI fixes found by reviewing every page at phone and desktop width**
- Removed the sticky "Built with Reflex" badge
  (`show_built_with_reflex=False`). It covered the workout summary's point
  lines on phones.
- The mobile nav wrapped into two ragged rows. It is now one line that scrolls
  sideways, with an edge fade so the hidden links read as reachable.
- The PR-moment and level-up rings scaled x2.4 forever and swept through the
  headline text. Both are now bounded, pulse three times, and are clipped by
  their card.
- The records list wrapped at random points on phones. It now uses two fixed
  lines per record.
- "First time - this sets your baseline" stayed on a card after sets were
  logged. It now shows only before the first set.
- The party page's "WORKOUT LEADERBOARD" heading wrapped beside its toggle. It
  is now "WORKOUT BOARD" with WEEK / ALL TIME.
- Blank workouts are named by time of day ("Evening workout") instead of a
  column of identical "Workout" rows.

**Verified (real output)**
- `alembic check`: no drift at `2caadc5c9d12`.
- `pytest`: **318 passed**, exit 0. That includes 16 new tests covering the
  account unit, profile stats and badges, the workout board's
  ranking/week window/404, and `longest_weekly_streak`.
- `scripts/smoke_test.py`: **All 128 checks passed**.
- `scripts/e2e`: **ALL PASSED (72)**. That covers the full journey including
  set editing, pending-exercise restore, the unit following the account into
  a fresh browser, the profile stats and badges and the party board. It also
  covers all 7 signed-in pages at phone and desktop width, with no uncaught
  errors, no horizontal overflow, and no Reflex badge.
- `docs/api-contract.md` regenerated: 45 paths, 80 schemas.

**Still open (decisions, not build work)**
- Point values remain placeholders in `workout_rules.py`.

---

## 2026-09-10 (11) - Opus - gym workout module (frontend)

Built the brief's Section 6 in Reflex against `docs/workouts-api.md`, inventing
no endpoint and computing no points client-side.

**Changed**
- Pages: `/workout` (start, live logging, finish summary), `/routines`,
  `/progress`. WORKOUT and PROGRESS are in both navs; the mobile nav now wraps.
- State: `state/workout.py` (live session), `state/picker.py` (exercise
  library), `state/routines.py`, `state/progress.py`. The live session is never
  held only in client memory: every load of `/workout` rehydrates it from
  `GET /workouts/sessions/active`. The only client-persisted value is the
  kg/lb display preference.
- Components:
  - `components/workout.py`: the HUD and the exercise cards. The HUD keeps
    level, rank, XP bar, weekly streak and this workout's points on screen the
    whole time.
  - `components/pr_overlay.py`: the PR moment, a full-screen beat in A-rank
    orange that reuses the level-up keyframes.
  - `components/exercise_picker.py`: search, muscle chips, and custom exercise
    creation.
  - `components/rest_timer.py`: the rest bar and elapsed clock, both
    client-side.
- `workout_models.py` / `workout_api.py`: typed payloads (kg converted to the
  display unit once, labels stored rather than computed) and the API client.

**UX decisions**
- **One-handed logging.** Each card is pre-filled from the last set this
  session, else last time's first set, else the routine target. The previous
  session's matching set is shown as a ghost line. Weight and reps have 52px
  steppers, so repeating a set is one tap.
- **No double logging.** Each card carries a `client_set_id` that rotates only
  after a confirmed log, so a double tap or a retry cannot log a set twice.
- **Celebrations are sized by the API's own classification.**
  - A paid PR (`bonus_awarded`) gets the full-screen moment.
  - A record that earned no bonus gets a pill on its card.
  - A first-ever log is noted quietly.
  - A level-up earned by the same set waits until the PR moment is dismissed,
    then plays through the app's existing level-up overlay. It is not a
    second copy of that overlay.

**Two bugs found by driving the UI in real Chrome, both fixed**
- **Hydration mismatch (React #418).** With a rest still running at page
  load, the timer script wrote countdown text into a server-rendered node
  before React hydrated it. The script now only sets attributes React never
  manages (`data-ma-state`, `data-ma-time`, `data-ma-clock`), and CSS renders
  them with `content: attr(...)`.
- **Baseline badged as a PR.** A first-ever set showed "BASELINE SET" and a PR
  badge at the same time, because the backend set `set.is_pr` for baseline
  record rows too. `is_pr` now means "beat an existing record" in both the log
  path and replay. A test asserts it, and the rule is documented in
  `workouts-api.md`.

**Verified (real output)**
- `docker compose build frontend`: the full `reflex export` compile succeeds.
- `pytest`: **302 passed**, exit 0.
- `scripts/smoke_test.py`: **All 128 checks passed**. It now also checks that
  `/workout`, `/routines` and `/progress` are served.
- End-to-end in headless Chrome at 400px (playwright-core against the running
  stack): **32/32 passed**. The run covered:
  - sign-in through the form
  - picker, set logging, baseline, rest timer, stepper
  - the PR moment, then the chained level-up
  - deleting a set
  - refresh mid-workout rehydrating the session, the rest countdown and the
    clock
  - the finish summary, with its points matching the API
  - routine create, then start, then discard
  - charts, records and a body measurement
  - no uncaught page errors
- Screenshots were reviewed at phone and desktop widths.

**Not built / known limits**
- Editing a logged set in the UI. The API supports `PATCH`; the UI fixes a
  mistake by deleting the set and logging it again.
- An exercise added from the picker but never logged is not persisted across a
  refresh, because it has no sets on the server. Anything with a logged set
  is persisted.
- The kg/lb preference is per browser (LocalStorage), not per account.
- The E2E script lives outside the repo (it needs `playwright-core`, and the
  repo avoids hand-written JS tooling). Say if it should be committed.

---

## 2026-09-10 (10) - Opus - rename to MetalArm; gym workout module (backend)

**Changed**
- **Renamed LevelForge -> MetalArm** (commit `53ceac6`): branding, API title,
  frontend package `levelforge/` -> `metalarm/`, containers, Redis key prefix.
  Data-bearing names deliberately kept: Docker volumes are pinned to the
  existing `levelforge_*` names (a bare project rename would have mounted empty
  volumes), and `POSTGRES_USER` / `POSTGRES_DB` stay `levelforge`.
- **Gym workout module** per the MetalArm master build prompt, Section 5:
  - Models + migration `085f917f46f8`: exercises, routines, routine_exercises,
    workout_sessions, set_entries, personal_records, points_ledger,
    body_measurements. Contract additions are documented in `data-model.md`.
  - Pure, unit-tested rules: `core/workout_rules.py` (the ONLY place point
    values live), `core/points_engine.py`, `core/personal_records.py`,
    `core/workout_streaks.py`. DB layer in `core/workout_store.py`.
  - 28 endpoints under `/exercises`, `/routines`, `/workouts`,
    `/body-measurements`.
  - 91-exercise starter library + `scripts/import_exercises.py` (JSON/CSV,
    idempotent, run by the `migrate` service).
  - New `progression.apply_xp()` for XP-only awards and reversals.
  - Wallet and profile "points earned" now include workout credits.

**Decisions (confirmed with the user)**
- 1 workout point = 1 XP **and** 1 shop point. XP moves live on every set;
  shop points are credited once, at finish - sets are editable until then, and
  a reversal must never debit points already spent in the shop.
- Streak = consecutive ISO weeks with >= 3 qualifying workouts (tunable).
  A qualifying workout also advances the global daily streak (A/S rank gate).
- Anti-farming: set points capped per session; warm-ups earn 0; PR bonus only
  for max_weight / est_1rm (and bodyweight rep PRs), never for a first-ever
  log, a <1% gain, lighter-weight rep PRs or volume; one bonus per exercise per
  session, three per session; trivial sessions (<10 min or <3 working sets)
  earn no bonus and do not count toward the streak; abandoning reverses
  everything; one live session per user (DB-enforced).

**Verified (real output)**
- `pytest`: **302 passed** (168 existing + 134 new), exit 0.
- `alembic check`: "No new upgrade operations detected."; `upgrade` ->
  `downgrade -1` -> `upgrade` clean.
- Importer: "91 inserted", then "0 inserted, 0 updated, 91 unchanged"; the
  `migrate` service logs the same no-op on every start.
- Stack rebuilt: all services healthy, `/health` ready at `085f917f46f8`.
- `scripts/smoke_test.py`: **All 125 checks passed** (new workout journey:
  routine -> live session -> retry dedupe -> paid PR -> lb conversion ->
  delete reversal -> finish -> wallet credit -> ledger reconciliation ->
  ownership 404s).
- `docs/api-contract.md` regenerated: 44 paths, 77 schemas.

**Blocked**
- Nothing. Point values remain placeholders (brief Section 7) - retune in
  `workout_rules.py` only.

**Other agent needs to know**
- **Frontend Agent (Sonnet):** build against `docs/workouts-api.md` (behaviour +
  payload examples) and `docs/api-contract.md` (shapes). Key rules: never
  compute points/PRs/streaks; rehydrate with `GET /workouts/sessions/active`;
  send a fresh `client_set_id` per submit; celebrate from
  `pr_events[].bonus_awarded` and `progression.leveled_up`; weights come back
  in kg. The frontend package is now `frontend/metalarm/`.
- Not built (out of scope this pass): workout badges / profile workout stats,
  friend leaderboard over `points_ledger`, a user weight-unit preference.

---

## 2026-09-10 (9) - Opus - close the last Section 2 gaps; PROJECT COMPLETE

Audited every checkpoint in the brief rather than only the sprint plan, which
surfaced **three MVP items in Section 2 that no sprint had covered**:

- **Badges.** Section 2: the Stat Panel shows "level, rank, XP bar, streaks,
  and **badges**". There were none. Added `core/badges.py` - 13 badges, all
  **derived** from data already stored, so there is no award-time write path to
  get wrong, no way for a badge to drift from the facts behind it, and no
  migration. Tiers key off values that never decrease (`longest_streak`, not
  the current streak; level, not the streak-gated rank), so taking a week off
  cannot revoke something genuinely earned. Unearned badges are returned with
  progress, because a panel that lists only what you have gives you nothing to
  aim at.
- **Profile page.** Section 2 calls the Stat Panel a "profile page"; it only
  existed embedded in the dashboard. Added `GET /api/v1/profile` (kept separate
  from `/auth/me`, which runs on every page load and must stay cheap) and a
  `/profile` route with the Stat Panel pinned, lifetime stats, and the badge
  grid.
- **Quest-complete animation.** Listed in the MVP features. Deliberately kept
  small: Section 7 reserves the heavy motion for level-up and rank-up, "not
  every quest checkbox", so a completed card gets one 320ms settle and a check
  pill, transform/opacity only.

**Verified (real output)**
- **168 tests** (was 158), **94 smoke checks** (was 82), 25 endpoints,
  `alembic check` clean, **ruff clean on both halves**, 5/5 services healthy,
  zero error lines in any container log.
- All 7 frontend routes 200: `/ /login /signup /dashboard /parties /rewards
  /profile`.
- Section 8's checklist re-verified end to end, including `/health` reporting a
  real PG 17.10 connection.
- Section 11: all four open questions resolved and recorded.

**Status: every checkpoint in the brief is complete.** Sprints 1-6 done, the
full Section 2 MVP feature list delivered, and the Section 8 setup checklist
verified against the running stack.

---

## 2026-09-10 (8) - Opus (both agents) - bug sweep + Sprint 6 (FINAL SPRINT)

### Part 1 - three bugs cleared

- **Timezone bug in the party leaderboard.** `_derive_rank` accepted `tz_name`
  and never used it, judging every member's streak against the **server's**
  date. At 02:00 UTC a Los Angeles member is still on the previous day, so a
  streak completed "yesterday" their time read as two days idle - a live
  40-day streak reported as rank **B** when they actually held **S**.
  Demonstrated numerically before fixing.
- **Two endpoints disagreed about a party's total XP.** `GET /parties/{id}`
  summed every contribution; the leaderboard summed only the rows it listed,
  which skips departed members and truncates at `limit`. A party where someone
  earned 300 XP then left reported **300 in one place and 0 in the other**.
- **Reflex reactivity bug.** `_load_detail` mutated `selected.total_party_xp`
  in place. Reflex marks a var dirty on assignment to the var itself, so a
  nested write can render stale - and `selected` aliases an entry in
  `self.parties`, so it quietly edited the list too. Now `dataclasses.replace`.

Ruff over the whole codebase found only two genuinely unused imports (both
removed). The one other hit was B008 on FastAPI's `Query()` default - the
documented idiom, a known false positive. **Frontend lints clean.**

### Part 2 - Sprint 6: scroll & level-up animations

- **`components/scroll_reveal.py`** - two implementations of one effect:
  1. **CSS scroll-driven animation** (`animation-timeline: view()`) where
     supported. Genuinely scroll-LINKED, compositor-driven, **zero JS**.
  2. **IntersectionObserver** elsewhere, as a trigger.
- **Pinned hero:** the Stat Panel holds position while the quest board scrolls
  past (sticky, never fixed). The wallet does the same on the rewards page.
- **Level-up beat** now shows the value reached - the new level number or the
  new rank letter - and rank-up reads gold rather than accent blue, since it is
  the rarer, larger moment.

**Two real problems solved in the design, not papered over**
- **The XP bar was animating `width`**, which Section 7 explicitly forbids:
  width is a layout property, so it forced a reflow every frame. Now
  `transform: scaleX()` with `transform-origin: left`, via an explicit
  `xp_scale` rx.var rather than dividing a Var in the template.
- **Hydration flash.** `rx.script` is bundled and runs AFTER first paint, so
  hiding content via a document-level class would have flashed it out and back
  in - worse than no animation. The hidden state is now scoped to `lf-armed`,
  which the script adds **only to elements below the fold**. Anything already
  on screen is left untouched. Content is visible by default, so a blocked or
  failed script costs the animation, never the content.

**Verified (real output)**
- **158 tests, 82 smoke checks** (was 72), 5/5 services healthy, **zero** error
  lines in backend/frontend/migrate logs.
- The smoke test now pins the animation contract against the SERVED page:
  base `.lf-reveal` rule is empty (visible without JS), hidden state scoped to
  the JS-added class, scroll-timeline feature-detected, reduced-motion handled,
  pinning only at >=1024px where a second column exists, **no layout property
  transitioned anywhere**, and every one of the 5 `lf-*` keyframe blocks
  animates **only `transform`/`opacity`**.

**Blocked**
- Nothing.

### Sprint plan status: COMPLETE

Sprints 1-6 are all done and verified. 24 endpoints, 158 backend tests, 82
end-to-end smoke checks, 5 services, 2 migrations, no schema drift.

Remaining Section 11 items are product decisions, not gaps: real-time party
updates were deliberately deferred in favour of periodic refresh, and no
external visual assets were used - `theme.py` is an original palette.

---

## 2026-09-10 (7) - Opus (both agents) - Sprint 5: parties + leaderboard

**Sprint 5 complete, backend and frontend.** Settled with the user first:
periodic refresh (no WebSockets), **max 10 members**, freely dissolved,
leaving owner hands off, and **party XP counts only what was earned while a
member**.

**Backend** - 10 endpoints under `/api/v1/parties`: create/list/get/rename,
join by code, leave, dissolve, rotate-invite, members, leaderboard, plus the
shared quest board (list/create/patch/delete/complete).

**Frontend** - `/parties` page: party selector, invite panel with rotate,
shared board showing "2 of 4 done", and the leaderboard. Nav updated.

**Verified (real output)**
- **156 backend tests** (was 124), **72 smoke checks** (was 51), all 5
  services healthy, `alembic check` clean, 24 endpoints.
- **Member-cap race closed:** 12 users raced for ONE free seat ->
  `{409: 11, 200: 1}`, exactly 2 memberships. The party row is locked FOR
  UPDATE before the headcount is read; without it two joins into a 9-of-10
  party would both see room.
- **Redis outage survived:** with Redis *stopped*, the leaderboard still
  served correct totals at **HTTP 200** from Postgres while `/health`
  correctly reported 503. The three WARNING lines in the backend log are that
  test - the fallback logging as designed, not faults.
- Party UI data layer exercised against the live backend from inside the
  frontend container: 15/15, including the rotate-then-old-code-rejected path.

**Design decisions worth knowing**
- **Party XP needs no extra bookkeeping.** It is `SUM(party_quest_completions)`,
  and a party quest cannot be completed by a non-member - so a recruit
  contributes zero however much personal XP they arrive with. Pinned by a test
  that grinds 10,000 personal XP *before* joining and asserts the party total
  stays 0.
- **Dissolving a party and removing a shared quest are SOFT.** A hard delete
  would cascade away the completion rows backing every member's contributed
  XP, silently rewriting the leaderboard and the record of work people did.
- **Redis is a cache, never truth.** Reads fall back to Postgres and rebuild
  on a miss; every Redis call is wrapped so an outage degrades to *slower*,
  not broken; and the cache is credited only AFTER the commit, since crediting
  a transaction that then rolls back would invent XP.
- Leaderboard rows **derive** rank rather than reading the cached column, so a
  member whose streak lapsed cannot appear holding a rank they no longer hold.
- Any member may add to the shared board - a board only one person can write
  to is a to-do list handed down, not a party. Editing is limited to the
  author or the owner.

**Two infrastructure bugs found**
- **`compare_server_default` was off in alembic/env.py.** Changing a column
  default autogenerated an EMPTY migration and `alembic check` reported no
  drift - false confidence, not a pass. Now on, which is what made the
  `max_members` 8 -> 10 change produce a real migration (`fa8ce42996db`).
- **backend and migrate were separate images** from the same Dockerfile, so
  `docker compose build backend` left migrate stale and the next `up` died
  with `Can't locate revision`. They now share one image tag, so drift is
  impossible.

**Blocked**
- Nothing.

**Next**
- **Sprint 6** is the last one: scroll & level-up animations (Section 7). The
  level-up overlay already exists (`components/level_up.py`) with
  transform/opacity-only motion and `prefers-reduced-motion` support; Sprint 6
  is the scroll-reveal pass over the quest board and Stat Panel, plus the
  pinned rank-up beat.
- Still unanswered from Section 11: visual assets/fonts (a palette was chosen
  from scratch in `theme.py` - original work, no Solo Leveling material).

---

## 2026-09-10 (6) - Opus (now BOTH agents) - audit + frontend catch-up

The user asked for a full audit of Sprints 1-4 before continuing, and took
over the Frontend Agent role in this session since no Sonnet session had run.

### Part 1 - audit findings

**One serious bug.** Nothing ran `alembic upgrade head`. On a fresh volume the
README's quick start produced a stack where `/health` returned **200 "ok"**
while every real request failed with `relation "users" does not exist` - the
check only ran `SELECT 1`, which an empty database answers happily.
Reproduced against a scratch DB before fixing. Two fixes, since either alone
leaves a hole:
- A `migrate` compose service runs `alembic upgrade head` to completion and
  exits before the backend starts (`service_completed_successfully`).
- `/health` now reports READINESS: it compares the applied migration revision
  to the head this code expects and returns 503 naming the fix.

**Also fixed:** Postgres/Redis/pgAdmin were published on `0.0.0.0` (Redis runs
unauthenticated and logs a warning saying so) - now bound to `127.0.0.1`.
`alembic.ini` gained `path_separator = os`, and a test forging a 23-byte key
now uses a full-length one; warnings 4 -> 2, both remaining third-party.

**Clean:** all 28 modules import, no stale doc references, backend/frontend
logs error-free, migration round-trip (up/down/up) clean, contract generator
idempotent. The Postgres ERROR lines in the logs are all deliberate negative
tests - constraints doing their job.

New `scripts/smoke_test.py`: **51 end-to-end checks** over real HTTP against a
running stack, covering every sprint plus ownership isolation.

### Part 2 - frontend catch-up (Sprints 2-4 UI)

The frontend was still the Sprint 1 placeholder: 88 lines, one file, empty
`components/` and `pages/`, not connected to the API. Now built:
- `api.py` - typed client for all 19 endpoints, driven by `docs/api-contract.md`.
- `models.py` - Progress / Quest / Reward / Redemption.
- `state/` - auth (token in LocalStorage), quests, rewards.
- `components/` - layout, stat_panel, quest_card, reward_card, **level_up**.
- `pages/` - login, signup, dashboard (Stat Panel + quest board), rewards shop.
- `theme.py` - original dark palette, per-rank colours. No Solo Leveling asset,
  logo, colour or copy is reproduced.

**Four Reflex-specific bugs caught during the build**
- **`rx.Base` was REMOVED in Reflex 0.9** ("No reflex attribute Base"). Reflex
  0.9 recognises plain **dataclasses** as state-var models instead - see
  `reflex/istate/proxy.py` dispatching on `dataclasses.is_dataclass`.
- **`return <value>` in an async generator is a SyntaxError.** A handler that
  `yield`s (to flash a loading state) must navigate with
  `yield rx.redirect(...)`. This breaks the BUILD, not runtime.
- **A Python `@property` on a model is invisible to the compiled component** -
  Reflex renders to JS and cannot evaluate it. Derived values are now stored
  fields (`Quest.recurrence_label`) or `rx.var` on the state (`xp_percent`,
  `rank_is_gated`, `streak_label`).
- Spreading `**PANEL_STYLE` beside an explicit `width=` is a compile-time
  `got multiple values for keyword argument`. Replaced with `theme.panel(**overrides)`,
  which merges and makes the collision impossible.

**One bug that would have made the whole UI dead**
- `LEVELFORGE_API_BASE_URL` was `http://localhost:8000` inside the frontend
  container -> **ECONNREFUSED on every call**, while the UI still rendered
  perfectly. Reflex event handlers run **server-side**, so `localhost` there is
  the Reflex server, not the backend. Compose now pins `http://backend:8000`
  and deliberately does NOT read the `.env` value - that variable means the
  browser-reachable URL for a local `reflex run`, and letting it through
  silently pointed the container at itself. (`REFLEX_API_URL` is the opposite:
  genuinely browser-facing, and baked in at build time.)

**One UX bug caught in the SSR output**
- A brand-new user was shown **"Maximum rank reached"** and a full XP bar:
  `next_rank` is `""` both at the top of the ladder and in the unloaded
  default, and `xp_for_next_level` of 0 rendered as 100%. Both are now gated
  on `AuthState.loaded`, and the streak reads "NONE YET" rather than "BROKEN"
  for someone who never had one.

**Verified (real output)**
- 124 backend tests, 51 smoke checks, 5/5 services healthy, all 5 frontend
  routes 200, **zero** error lines in backend/frontend/migrate logs.
- Frontend data layer exercised against the LIVE backend from inside the
  container: every model parses, the 409 "already completed" message is
  readable, and FastAPI's list-shaped 422 body flattens to `point_cost: ...`
  rather than an unreadable blob.

**Blocked**
- Nothing.

**Next**
- Sprint 5: Party/Guild + Redis leaderboard. Settled with the user:
  **periodic refresh (REST, no WebSockets)**; **max 10 members**, owner can
  dissolve, members can leave, owner leaving transfers to the longest-serving
  member; **party XP counts only what was earned while a member**, so
  recruiting a high-level user cannot inflate a party's total.

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
