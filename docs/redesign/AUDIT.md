# Minimal redesign: audit

The state of the web app before the redesign (`origin/main` at `d19ed70`, 7 Oct 2026), and what changed. The before and after screenshots are in [`before-after/`](before-after/): one JPEG per screen, the old capture on the left and the new one on the right, at 390 px.

## Before

**Navigation.** Five tabs: Home, Explore, Workout, Library and You. A floating "Start New Workout" pill sat over every page.

The app had 23 routes:
- Home, Explore, Workout, Library, You;
- `/progress` (the v1 progress page);
- `/quests` (the old dashboard);
- duels, parties, rewards, profile, notifications, credits;
- `/gallery`;
- `/exercise/[id]`, `/session/[id]`, `/u/[id]`, `/summary/[ym]`;
- login and signup;
- two redirects.

**Colour.** One blue accent plus four "meaning" colours: recovery green, PR gold, streak orange and danger red. Across the pages they were used 107 times. Feed cards, summary heroes and the monthly card used gradients. Badges, panels and the PR overlay glowed.

**Type.** Inter for text, Space Grotesk for numerals, and ten type styles (DISPLAY_HERO, DISPLAY_NUMBER, LARGE_TITLE, TITLE_1, TITLE_2, HEADLINE, SUBHEAD, BODY, FOOTNOTE, CAPTION) plus a numeral style. Many screens used five or six sizes at once, and labels were often in letter-spaced capitals ("CHALLENGE YOUR RIVAL", "START THIS WORKOUT").

**Hard-coded styles.** There were 534 inline hex colours, rgba values, literal font sizes, literal radii and rem sizes in `ui/`, `components/` and `pages/`. The token lint exempted 21 files. The worst were:

| File | Inline values |
|---|---|
| components/workout.py | 109 |
| components/duel_card.py | 65 |
| pages/parties.py | 60 |
| pages/profile.py | 40 |
| pages/duels.py | 34 |
| components/quest_card.py | 34 |
| components/level_up.py | 32 |
| components/party_card.py | 29 |
| components/voice_log.py | 21 |
| components/presets.py | 20 |
| 10 more files | 90 |

**Active workout.**
- Every card showed its own row of fields and its own accent check, so a five-exercise workout had five accent buttons.
- At 360 px the stepper rows did not fit.
- A PR took over the whole screen with an overlay in the middle of a set.

## After

**Navigation.** Four tabs: Home, Train, Progress and Profile. Every shipped screen is folded under one of them (the full map is in [`DESIGN_SYSTEM.md`](../../frontend/DESIGN_SYSTEM.md#information-architecture)). The old URLs redirect. The floating pill is gone. A screen that has a primary action pins it above the tab bar (Start workout on Home, Start empty workout on Train); Progress and Profile have none.

**Colour.** Near-black neutrals plus one accent, Forge orange `#FF6B2C`. Danger red is kept for destructive actions only. Rank-tier colours appear only in the rank badge and the rank-up overlay, and the lint enforces that. There are no gradients, shadows or glow, except in the rank-up and duel-win moments.

**Type.** Manrope for text and Space Grotesk for titles and numbers. There are six styles: display, title-lg, title, body, label and caption. Labels are in sentence case.

**Hard-coded styles.** None. The exemption list is gone, and `frontend/tests/test_tokens.py` checks every module under `ui/`, `components/` and `pages/` for:
- hex colours, rgba values, literal font sizes, radii and font families, and rem sizes;
- tier colours outside the badge and the overlay;
- any second accent in `theme.py`.

**Active workout.**
- Only the card in focus shows the steppers and **Log set**, the screen's one accent action.
- When an exercise's planned sets are done, focus moves to the next exercise, alternating within a superset. The logging test measures at most 2 taps per set, including a warm-up.
- Set type, RPE, notes, rest, order, superset and remove are in an options sheet.
- A PR shows as a 2.5-second banner from the bottom.

## Verification (7 Oct 2026, against the running stack on the demo database)

| Check | Result |
|---|---|
| `frontend/tests` (token lint, WCAG contrast, rank tiers, assets) | 38 passed |
| `screens.mjs` at 360, 390 and 430 px: 26 routes plus the signed-out pages | No horizontal overflow |
| `logging_e2e` at 360, 390 and 430 px: taps per set, 48 px targets, refresh, summary points against the API | 66 passed |
| `workout_e2e` | 117 passed |
| `analytics_e2e` (every number against a hand-checked calculation) | 82 passed |
| `explore_e2e` | 56 passed |
| `social_e2e` | 29 passed |
| `duels_e2e` | 12 passed |
| `rank_up_e2e` (sequencing unchanged) | 51 passed |
| `pwa_e2e` (offline queue, installable, monthly story) | 26 passed |
| `motion_e2e`: the system setting and the in-app setting, with a control | 22 passed |
| `git diff origin/main -- backend ios` | Empty |

## Independent review

A fresh sub-agent reviewed the before/after sheets and the 360 px captures against the spec's rules, with no other context. Rule 1 (one primary per screen) held everywhere.

**Fixed:**
- Focus after a reload now stays on the exercise you were on when nothing is owed.
- History dividers run full width, and the month arrows sit on the month's title row.
- Inline Remove, Archive, Delete and Details buttons sit on the 20 px gutter.
- Parties keeps one self-highlight (the tinted row), with no orange names.
- The selected measurement is marked without accent.
- The stepper unit sits right after its number.
- Numbers use one format ("3,608 / 20,000", "1,050").
- The streak-freeze notice shows on Home only.
- Progress's metric control is a segmented control instead of a clipped chip row.
- The routine editor has one way out.
- "4/10 MEMBERS" now reads "4 of 10 members".
- The body-weight chart fits its range instead of starting at zero.
- The orange "ring" and the clipped toast were the toast covering the pinned Done button; toasts and banners now float above it (`theme.FLOAT_BOTTOM`).

**Kept, with reasons:**
- Type scale: see [FLAGS.md](FLAGS.md) #8.
- Per-row Remove and Delete stay as quiet danger-text buttons rather than outlined pills, which would add a bordered pill to every row.
- The default-rest − and + are 44 px icon buttons, the IconButton size.
