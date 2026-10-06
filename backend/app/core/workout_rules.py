"""Scoring numbers for the gym workout module.

Deliberately the ONLY place these numbers appear, the same way leveling.py is
the only home of the XP curve. The points engine, PR detection and streak logic
read from here and never hardcode a value, so tuning a reward is a one-file
change.

Exact values are an open decision (brief, Section 7); these are placeholders
sized against the quest economy. A typical workout - ~20 working sets, an hour,
one PR - earns about 40 + 35 + 50 = 125 points, against the ~268 XP/day an
active user earns from quests (see leveling.py), so the gym does not dwarf
every other habit.

Every workout point is worth one XP AND one shop point: XP is applied as each
award is made, shop points are credited once when the session is finished.
See app/api/routes/workouts.py for why the two are timed differently.

Changing these does NOT rewrite history: each award is snapshotted into the
points ledger when it is made.
"""

# --- Logging a set ---------------------------------------------------------
SET_POINTS = 2
# Per session. Stops padding a workout with dozens of trivial sets.
SET_POINTS_CAP_PER_SESSION = 50
# Warm-ups earn nothing: otherwise they are an uncapped way to reach the cap.
WARMUP_SET_POINTS = 0

# --- Finishing a session ---------------------------------------------------
SESSION_BONUS = 25
# Below either threshold the session still completes, but earns no bonus - a
# start/finish tap with nothing in between is not a workout.
SESSION_MIN_WORKING_SETS = 3
SESSION_MIN_MINUTES = 10
# The bonus multiplier grows with duration and with working-set count, each
# contributing up to +25%, for a ceiling of x1.5. Working SETS rather than
# kilograms moved: tonnage would pay a strong lifter several times more than a
# beginner doing the same work, and pays bodyweight training nothing.
SESSION_DURATION_WEIGHT = 0.25
SESSION_DURATION_FULL_MINUTES = 60
SESSION_SETS_WEIGHT = 0.25
SESSION_SETS_FULL = 20

# --- Personal records ------------------------------------------------------
PR_BONUS = 50
# At most one PR bonus per exercise per session, however many record types a
# single lift beats, and at most this many per session overall.
PR_BONUSES_PER_SESSION = 3

# --- Weekly streak -----------------------------------------------------------
# A week "counts" once it holds this many completed sessions. Weeks, not days:
# rest days are part of training, and a daily streak would punish them.
STREAK_SESSIONS_PER_WEEK = 3
# Paid once per qualifying week, escalating with the streak length.
STREAK_BONUS_PER_WEEK = 10
STREAK_BONUS_CAP = 100

# --- Generated quests (app/core/quest_board.py) --------------------------------
# How many are handed out per period. Each template carries its own reward;
# these are what the shipped templates are sized against.
DAILY_QUESTS = 2
WEEKLY_QUESTS = 3
DAILY_QUEST_POINTS = 15
WEEKLY_QUEST_POINTS = 40
# Paid once a week, when the last of that week's quests is done.
ALL_WEEKLY_QUESTS_BONUS = 25
# Swaps of one daily quest for another, per local day.
QUEST_REROLLS_PER_DAY = 1

# --- Streak freezes (app/core/streak_freezes.py) -------------------------------
# A freeze covers one week that fell short, so the weekly streak survives a
# deliberate rest week. Earned every FREEZE_EARN_EVERY_WEEKS counting weeks of
# streak and for finishing a week's quests; never more than FREEZE_CAP held.
# Weeks rather than the spec's "every 7 days", because the streak is weekly.
FREEZE_CAP = 2
FREEZE_EARN_EVERY_WEEKS = 4

# --- Suggested workouts (GET /workouts/suggested) -------------------------------
# Routines are ranked by how long since they were last done; one that fits the
# user's training path counts as this many days staler, and one never done
# counts as this many days since. Tune by moving these, not the code.
SUGGEST_CATEGORY_BONUS_DAYS = 3
SUGGEST_NEVER_DONE_DAYS = 14
SUGGEST_LIMIT = 10

# --- Analytics (app/core/analytics.py, app/core/recovery.py) -------------------
# The You tab's range control, in whole weeks; "All" starts at the first workout.
ANALYTICS_RANGE_WEEKS = {"3M": 13, "6M": 26, "Year": 52}
# Recovery is an ESTIMATE from training volume, not physiology. A working set
# loads its primary muscles 1.0 and its secondary 0.5 (analytics.PRIMARY_WEIGHT
# / SECONDARY_WEIGHT); that load decays, halving every half-life, and only the
# last RECOVERY_WINDOW_HOURS count. A muscle carrying THRESHOLD units of load
# reads 0% recovered. Large muscles shrug off load more slowly but take more.
RECOVERY_WINDOW_HOURS = 96
RECOVERY_HALF_LIFE_HOURS = {"small": 24.0, "large": 36.0}
RECOVERY_THRESHOLD = {"small": 6.0, "large": 10.0}
# Overall recovery: the average over muscles trained in this many days,
# weighted by how much each was trained.
RECOVERY_OVERALL_DAYS = 7

# --- Plausibility (app/core/plausibility.py) ---------------------------------
# A set that trips one of these is still logged and still scores for its owner,
# but stays out of duels and leaderboards. Generous on purpose: the cost of a
# false flag is someone's honest PR not counting against a friend.
FLAG_E1RM_JUMP = 0.15          # e1RM this far above the last 7 days' best
FLAG_E1RM_LOOKBACK_DAYS = 7
FLAG_MAX_WEIGHTED_REPS = 50    # reps on a set with any weight on it
# Heaviest believable load by equipment, in kg (per hand for dumbbells and
# kettlebells, as logged). Anything above is past world records.
FLAG_CEILING_KG = {
    "barbell": 500,
    "trap_bar": 500,
    "smith_machine": 500,
    "ez_bar": 200,
    "dumbbell": 120,
    "kettlebell": 100,
    "cable": 300,
    "machine": 700,
    "plate": 100,
    "band": 150,
}

# --- Session hygiene -------------------------------------------------------
# A session left open this long refuses new sets, and duration counts only up
# to this for the bonus - a forgotten session cannot bank a 20-hour multiplier.
MAX_SESSION_HOURS = 6

# --- Estimated 1RM -----------------------------------------------------------
# Epley becomes unreliable at high reps; above this a set earns no e1RM record.
EST_1RM_MAX_REPS = 12

# --- Progression hints -------------------------------------------------------
# Double progression: work a rep range, and add weight once its top is reached.
HINT_REP_RANGE = (5, 8)
# The smallest loadable jump: a pair of 1.25 kg plates on a bar, and a smaller
# step where the load comes in single increments (dumbbells, cables, machines).
WEIGHT_STEP_KG = 2.5
SMALL_WEIGHT_STEP_KG = 1.0
# Sessions with no new best estimated 1RM before it counts as a plateau.
PLATEAU_SESSIONS = 3
# Weeks of unbroken climbing before a lighter week is suggested.
DELOAD_AFTER_WEEKS = 6

# --- Input bounds ------------------------------------------------------------
# Enforced in the request schemas AND by CHECK constraints. They exist to stop
# absurd values minting records, not to judge anyone's strength.
MAX_WEIGHT_KG = 1000
MAX_REPS = 1000
MAX_DURATION_SECONDS = 24 * 60 * 60
MAX_DISTANCE_M = 1_000_000

LB_TO_KG = 0.45359237
