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
