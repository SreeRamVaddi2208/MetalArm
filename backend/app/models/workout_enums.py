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
