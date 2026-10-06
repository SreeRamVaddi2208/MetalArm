"""Vocabularies for the gym workout module.

Every set here is stored as VARCHAR + CHECK rather than a native Postgres enum,
for the reason given in enums.py: all of them are expected to grow (another
piece of equipment, another muscle group, another ledger source when steps or
cardio tracking land), and `ALTER TYPE ... ADD VALUE` fights Alembic's
transactional migrations. Adding a value is a one-line change to the tuple plus
a migration that swaps the CHECK.

The Python enums give the application layer type safety and give the API's
OpenAPI spec a closed list, so the frontend can render filter chips without
hardcoding them (see GET /exercises/meta).
"""

import enum


class ExerciseCategory(str, enum.Enum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    BODYWEIGHT = "bodyweight"
    MOBILITY = "mobility"


class Equipment(str, enum.Enum):
    BARBELL = "barbell"
    DUMBBELL = "dumbbell"
    MACHINE = "machine"
    CABLE = "cable"
    KETTLEBELL = "kettlebell"
    BODYWEIGHT = "bodyweight"
    BAND = "band"
    SMITH_MACHINE = "smith_machine"
    EZ_BAR = "ez_bar"
    TRAP_BAR = "trap_bar"
    PLATE = "plate"
    CARDIO_MACHINE = "cardio_machine"
    OTHER = "other"


class MuscleGroup(str, enum.Enum):
    CHEST = "chest"
    BACK = "back"
    LATS = "lats"
    TRAPS = "traps"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    FOREARMS = "forearms"
    ABS = "abs"
    OBLIQUES = "obliques"
    LOWER_BACK = "lower_back"
    GLUTES = "glutes"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    CALVES = "calves"
    ADDUCTORS = "adductors"
    ABDUCTORS = "abductors"
    NECK = "neck"
    FULL_BODY = "full_body"
    CARDIO = "cardio"


class ExerciseTag(str, enum.Enum):
    """What KIND of work an exercise is, in the vocabulary the training paths
    already speak (training_categories.json `emphasis_tags`). Generated quests
    filter on these ("6 isolation sets"); nothing scores on them."""

    BIG3 = "big3"
    COMPOUND_HEAVY = "compound_heavy"
    COMPOUND = "compound"
    COMPOUND_LIGHT = "compound_light"
    ISOLATION = "isolation"
    MOBILITY = "mobility"
    PLYOMETRIC = "plyometric"


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    # Explicitly discarded. Its awards are reversed and its sets stop counting
    # toward records - see routes/workouts.py.
    ABANDONED = "abandoned"


class RecordType(str, enum.Enum):
    MAX_WEIGHT = "max_weight"
    # Best reps at a given weight or heavier - see personal_records.py.
    MAX_REPS_AT_WEIGHT = "max_reps_at_weight"
    EST_1RM = "est_1rm"
    # Best single-session volume for the exercise, judged at finish.
    MAX_VOLUME = "max_volume"


class LedgerSource(str, enum.Enum):
    SET_LOGGED = "set_logged"
    SESSION_COMPLETED = "session_completed"
    PR_ACHIEVED = "pr_achieved"
    STREAK_BONUS = "streak_bonus"
    # Won a head-to-head over its window (app/core/duels.py). Awarded once,
    # when the duel is judged; the ledger's UNIQUE on (source_type, source_id)
    # is what makes "once" true rather than a flag that can be checked stale.
    DUEL_WON = "duel_won"
    # A generated quest reached its target (app/core/quest_board.py). source_id
    # is the QuestAssignment. Not in uq_points_ledger_once: like a set award,
    # it is reversed if the set that completed it is deleted, and re-awarded if
    # the quest is completed again - the level_progress lock serialises that.
    QUEST_COMPLETED = "quest_completed"
    # All of a week's generated quests done. source_id is the assignment whose
    # completion finished the set.
    QUEST_BONUS = "quest_bonus"
    # A fair duel that ended level: each side is paid. source_id is
    # duel_engine.reward_key(duel, user), one per side, so the once-only
    # index still holds.
    DUEL_DRAW = "duel_draw"
    # The loser of a duel who still trained: paid for showing up.
    DUEL_PARTICIPATION = "duel_participation"
    # Negates an earlier entry (a deleted or edited set, an abandoned session).
    # The ledger is append-only, so undoing an award is a new row, never an
    # UPDATE or DELETE of the original.
    REVERSAL = "reversal"


class MeasurementMetric(str, enum.Enum):
    WEIGHT = "weight"
    BODY_FAT = "body_fat"
    CUSTOM = "custom"


class MeasurementUnit(str, enum.Enum):
    KG = "kg"
    LB = "lb"
    PERCENT = "percent"
    CM = "cm"
    IN = "in"


class WeightUnit(str, enum.Enum):
    """Units a set's weight may be SUBMITTED in. Storage is always kilograms."""

    KG = "kg"
    LB = "lb"


def values(py_enum: type[enum.Enum]) -> tuple[str, ...]:
    return tuple(m.value for m in py_enum)


def check_in(column: str, py_enum: type[enum.Enum]) -> str:
    """SQL for a CHECK constraint restricting `column` to the enum's values."""
    listed = ", ".join(f"'{v}'" for v in values(py_enum))
    return f"{column} IN ({listed})"
