# App Store listing: MetalArm

Paste-ready text for App Store Connect. Character limits are Apple's; every
field below is within them. Replace `DOMAIN` with your real domain.

## App information

| Field | Value |
|---|---|
| Name (30) | MetalArm |
| Subtitle (30) | Level up every workout |
| Primary category | Health & Fitness |
| Secondary category | Lifestyle |
| Privacy Policy URL | `https://DOMAIN/privacy` |
| Support URL | `https://DOMAIN/support` |
| Marketing URL (optional) | `https://DOMAIN` |

## Promotional text (170)

Log a set and watch your XP bar climb. Break a record and MetalArm celebrates it. Train with friends and climb your party's weekly leaderboard.

## Description (4000)

MetalArm turns your gym workouts into RPG-style progression.

Every set you log earns points. Points become XP, XP becomes levels, and levels
unlock tiers from Untrained all the way to World Class. Keep a weekly streak
going, earn badges, and watch your character grow as you do.

TRAIN
• Start a workout in one tap and pick from a library of 91 exercises, or add your own.
• See last session's numbers next to every set, so you always know what to beat.
• A rest timer between sets, and editing or deleting sets when you slip up.
• Save routines for the days you repeat.

BREAK RECORDS
• Heaviest set, estimated one-rep max, session volume and most reps at a weight are detected as you log.
• A new personal record gets its own celebration, and so does every level-up.

• What to try next on every exercise card, from your own last sessions.

PROGRESS
• Charts of your top sets over time, and every personal record per exercise.
• Log body measurements and see the trend.
• Weekly workout streaks keep you consistent.
• Ranks B, A and S also take a strength trial: bench at 1x, squat at 1.5x and deadlift at 2x your bodyweight.
• A character sheet scores Strength, Endurance and Discipline from real training. Pick Powerlifter, Bodybuilder or Athlete to highlight what you care about.

TRAIN TOGETHER
• Create a party and share the invite code with friends.
• Climb the weekly workout leaderboard together.
• Take on a weekly raid boss that your whole party's workouts bring down.
• Weekly leagues of twenty lifters: the top five move up a division, the bottom five move down.
• Share a story card of a workout's best moment - a rank-up, level-up or record.

APPLE HEALTH
• Finished workouts are saved to Apple Health, so they appear in Fitness with everything else.
• Write only. MetalArm never reads your health data, and nothing is written until you turn it on in Profile.

REMINDERS
• A local alert when your rest timer ends, and "your streak ends tonight" on a day you haven't trained.
• Asked for after your first finished workout, never at launch, and both have switches in Profile.

BRINGING YOUR HISTORY
• Already training? Import your history from Strong or Hevy, and your records and charts count it from day one.

YOUR DATA
• No ads, no tracking, no third-party analytics.
• Sign out of one device or all of them, and delete your account and everything in it from inside the app.

Every number in MetalArm (points, XP, records, streaks) is calculated on the
server from what you actually logged, so the leaderboard is fair.

## Keywords (100)

workout,gym,fitness,tracker,lifting,strength,rpg,level,xp,streak,personal record,log,routine

## Age rating

Answer "None" to every content question (no violence, mature themes, gambling,
unrestricted web access or user-generated content beyond display names shown
to party members). Expected rating: **4+**.

## App Privacy ("nutrition label")

Matches `ios/MetalARM/PrivacyInfo.xcprivacy`. Tracking: **No**. No data is
used for advertising or shared with third parties.

| Data type | Collected | Linked to the user | Used for tracking | Purpose |
|---|---|---|---|---|
| Contact Info → Email Address | Yes | Yes | No | App Functionality |
| Contact Info → Name (display name) | Yes | Yes | No | App Functionality |
| Health & Fitness → Fitness (workouts, sets, records) | Yes | Yes | No | App Functionality |
| Identifiers → User ID | Yes | Yes | No | App Functionality |

Body measurements are logged by the user as part of their training history and
are covered under Fitness above. If you'd rather be conservative, also declare
Health & Fitness → Health (add it to `PrivacyInfo.xcprivacy` as well, so the
two stay in step).

## App Review information

- **Sign-in required:** yes. Apple expects a working sign-in for apps that
  require an account, so create a demo account on the production server
  (sign up in the app or at `https://DOMAIN/signup`), log a workout or two so
  the screens have data, and enter its email and password under
  **App Review Information → Sign-in required**.
- **Notes for the reviewer:**
  > MetalArm is a workout tracker with RPG-style progression. Sign in with the
  > demo account (or create a new one on the first screen), tap Start Workout,
  > add an exercise and log a few sets, then Finish to see points, records and
  > level progress. Account deletion is in Profile → Delete Account.
  >
  > HealthKit: MetalArm asks to WRITE workouts to Apple Health only - it never
  > requests read access. The permission sheet appears the first time you turn
  > on "Save to Apple Health" in Profile, never at launch, and the app works
  > fully without it. Notifications (rest-timer done, and a streak reminder)
  > are local only, asked for after your first finished workout, and both have
  > switches in Profile.
- Keep the production server running while the app is in review.

## Screenshots

`ios/AppStore/screenshots/` holds the 6.9-inch set (iPhone 17 Pro Max,
1320 × 2868): upload `01` to `12` in order. App Store Connect scales them for
smaller iPhones.
