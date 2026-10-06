"""Request/response shapes for the gym workout module.

Two rules shape everything here:

1. No request schema has a points field. Points are computed server-side from
   the raw workout data; unknown fields are ignored (pydantic's default), so a
   client that sends `"points": 9999` simply gets nothing for it.
2. Weights are stored as NUMERIC and handled as Decimal, but go out as JSON
   numbers (float fields), not strings - pydantic serialises Decimal as a
   string, which every client would then have to parse back.
"""

import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core import workout_rules as rules
from app.models.workout_enums import (
    Equipment,
    ExerciseCategory,
    MeasurementMetric,
    MeasurementUnit,
    MuscleGroup,
    WeightUnit,
    SetType,
)
from app.schemas.quest import ProgressionDeltaOut
from app.schemas.quest_board import QuestProgressOut

_CENTS = Decimal("0.01")
# The largest submittable number is MAX_WEIGHT_KG expressed in pounds; the
# converted kilogram value is what is actually bounded, in the validator.
_MAX_WEIGHT_INPUT = rules.MAX_WEIGHT_KG / rules.LB_TO_KG


def to_kg(weight: float, unit: WeightUnit) -> Decimal:
    value = Decimal(str(weight))
    if unit is WeightUnit.LB:
        value *= Decimal(str(rules.LB_TO_KG))
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


class ExerciseCreate(BaseModel):
    """A user's own exercise. Library exercises come only from the importer."""

    name: str = Field(min_length=1, max_length=120)
    category: ExerciseCategory
    primary_muscle_groups: list[MuscleGroup] = Field(min_length=1, max_length=6)
    equipment: Equipment
    instructions: str | None = Field(default=None, max_length=5000)
    media_url: str | None = Field(default=None, max_length=500)


class ExerciseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: ExerciseCategory | None = None
    primary_muscle_groups: list[MuscleGroup] | None = Field(
        default=None, min_length=1, max_length=6
    )
    equipment: Equipment | None = None
    instructions: str | None = Field(default=None, max_length=5000)
    media_url: str | None = Field(default=None, max_length=500)


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str | None
    category: str
    primary_muscle_groups: list[str]
    equipment: str
    tags: list[str] = []
    secondary_muscle_groups: list[str] = []
    # 'compound' | 'isolation' | null
    mechanic: str | None = None
    instructions: str | None
    # Numbered steps and tips for the detail screen.
    steps: list[str] = []
    tips: list[str] = []
    media_url: str | None
    thumbnail_url: str | None = None
    illustration_url: str | None = None
    animation_url: str | None = None
    # Attribution for the artwork above; shown wherever it is.
    media_license: str | None = None
    media_author: str | None = None
    media_source_url: str | None = None
    is_custom: bool
    is_archived: bool


class ExerciseMetaOut(BaseModel):
    """The closed vocabularies, so the UI never hardcodes filter chips."""

    categories: list[str]
    equipment: list[str]
    muscle_groups: list[str]
    weight_units: list[str]
    measurement_metrics: list[str]
    measurement_units: list[str]


class ExerciseHistoryPoint(BaseModel):
    """One completed session's performance on one exercise - a chart point."""

    session_id: uuid.UUID
    performed_at: dt.datetime
    top_weight_kg: float | None
    top_weight_reps: int | None
    best_est_1rm: float | None
    volume_kg: float
    working_sets: int
    total_reps: int


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------


class SetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    exercise_id: uuid.UUID
    set_number: int
    weight_kg: float
    reps: int | None
    rpe: float | None
    is_warmup: bool
    # normal / warmup / drop / failure.
    set_type: str = "normal"
    session_exercise_id: uuid.UUID | None = None
    is_pr: bool
    # Kept out of duels and leaderboards (app/core/plausibility.py). Shown as
    # a neutral note; the reason is for support, not for the UI.
    is_flagged: bool = False
    duration_seconds: int | None
    distance_m: float | None
    completed_at: dt.datetime


class HintOut(BaseModel):
    """What to try next on an exercise (app/core/progression_hints.py).
    `kind` is progress, plateau or deload; `text` is ready to show."""

    kind: str
    text: str
    # In kilograms, whatever unit `text` is written in.
    target_weight_kg: float | None
    target_reps: int | None

    @classmethod
    def from_hint(cls, hint) -> "HintOut | None":
        """From a progression_hints.Hint, passing None straight through."""
        if hint is None:
            return None
        return cls(
            kind=hint.kind,
            text=hint.text,
            target_weight_kg=float(hint.target_weight_kg)
            if hint.target_weight_kg is not None
            else None,
            target_reps=hint.target_reps,
        )


class LastPerformanceOut(BaseModel):
    """The previous session's sets on an exercise - the ghost values in the
    logging UI. Empty when the exercise has never been done."""

    exercise_id: uuid.UUID
    session_id: uuid.UUID | None
    performed_at: dt.datetime | None
    sets: list[SetOut]
    hint: HintOut | None = None


class _SetMeasures(BaseModel):
    weight: float = Field(
        default=0,
        ge=0,
        le=_MAX_WEIGHT_INPUT,
        description="In `unit`. 0 for unweighted sets. Stored as kilograms.",
    )
    unit: WeightUnit = WeightUnit.KG
    reps: int | None = Field(default=None, ge=1, le=rules.MAX_REPS)
    rpe: float | None = Field(default=None, ge=1, le=10)
    is_warmup: bool = False
    # normal / warmup / drop / failure. Wins over is_warmup when both are
    # sent; older clients send only is_warmup.
    set_type: SetType | None = None
    duration_seconds: int | None = Field(
        default=None, ge=1, le=rules.MAX_DURATION_SECONDS
    )
    distance_m: float | None = Field(default=None, gt=0, le=rules.MAX_DISTANCE_M)

    @property
    def resolved_type(self) -> SetType:
        if self.set_type is not None:
            return self.set_type
        return SetType.WARMUP if self.is_warmup else SetType.NORMAL

    @property
    def weight_kg(self) -> Decimal:
        return to_kg(self.weight, self.unit)

    @model_validator(mode="after")
    def _within_bounds(self):
        if self.weight_kg > rules.MAX_WEIGHT_KG:
            raise ValueError(f"weight must be at most {rules.MAX_WEIGHT_KG} kg")
        return self


class SetCreate(_SetMeasures):
    exercise_id: uuid.UUID
    # The card it belongs to. Optional: without it the set goes on the
    # session's first card for exercise_id, which is made if there is none.
    session_exercise_id: uuid.UUID | None = None
    # Generated by the client per submit. A retry with the same id returns the
    # original set instead of logging a second one.
    client_set_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _has_a_measure(self):
        if self.reps is None and self.duration_seconds is None and self.distance_m is None:
            raise ValueError("a set needs reps, a duration, or a distance")
        return self


class SetUpdate(BaseModel):
    """PATCH: fields left out are unchanged. `weight` is read in `unit`."""

    weight: float | None = Field(default=None, ge=0, le=_MAX_WEIGHT_INPUT)
    unit: WeightUnit = WeightUnit.KG
    reps: int | None = Field(default=None, ge=1, le=rules.MAX_REPS)
    rpe: float | None = Field(default=None, ge=1, le=10)
    is_warmup: bool | None = None
    set_type: SetType | None = None
    duration_seconds: int | None = Field(
        default=None, ge=1, le=rules.MAX_DURATION_SECONDS
    )
    distance_m: float | None = Field(default=None, gt=0, le=rules.MAX_DISTANCE_M)


# ---------------------------------------------------------------------------
# Awards and records
# ---------------------------------------------------------------------------


class AwardOut(BaseModel):
    source_type: str
    points: int
    reason: str


class PrEventOut(BaseModel):
    """One record broken. `bonus_awarded` marks the one that paid the PR bonus,
    which is what the celebration should lead with."""

    exercise_id: uuid.UUID
    exercise_name: str
    record_type: str
    value: float
    weight_kg: float | None
    previous_value: float | None
    is_baseline: bool
    bonus_awarded: bool
    set_id: uuid.UUID | None


class RecordOut(BaseModel):
    exercise_id: uuid.UUID
    exercise_name: str
    record_type: str
    value: float
    weight_kg: float | None
    achieved_at: dt.datetime
    session_id: uuid.UUID
    set_id: uuid.UUID | None


class SetLogResponse(BaseModel):
    set: SetOut
    pr_events: list[PrEventOut]
    awards: list[AwardOut]
    # Net points this request changed (negative only after an edit that loses
    # an award).
    points_awarded: int
    # Net points the session holds so far.
    session_points: int
    set_cap_reached: bool
    # Level/rank movement from this set - drives the level-up animation.
    progression: ProgressionDeltaOut
    # True when client_set_id matched an existing set: nothing new was logged.
    is_duplicate: bool = False
    # Every current generated quest after this set (GET /quests/current), and
    # the ones it completed - so the UI can celebrate in the same round trip.
    quest_progress: list[QuestProgressOut] = []
    quests_completed: list[QuestProgressOut] = []


class SetDeleteResponse(BaseModel):
    points_awarded: int
    session_points: int
    progression: ProgressionDeltaOut
    quest_progress: list[QuestProgressOut] = []


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class SessionStart(BaseModel):
    routine_id: uuid.UUID | None = None
    # A ready-made workout (GET /workouts/presets). Mutually exclusive with
    # routine_id: two plans for one session has no meaning.
    preset_slug: str | None = Field(default=None, min_length=1, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def _one_plan_only(self) -> "SessionStart":
        if self.routine_id is not None and self.preset_slug is not None:
            raise ValueError("send routine_id or preset_slug, not both")
        return self


class PresetExerciseOut(BaseModel):
    """One slot of a ready-made workout, with the exercise it names - the
    client needs the name, the muscles and media_url to show a demo."""

    exercise: ExerciseOut
    target_sets: int
    target_reps: int
    rest_seconds: int


class PresetOut(BaseModel):
    slug: str
    category: str
    # "Athletic", not "Athlete": the stored value is the path, the label is
    # what the training path profile calls it.
    category_label: str
    name: str
    summary: str
    exercises: list[PresetExerciseOut]
    # True for the workout matching the user's training path
    # (users.character_class). The clients lead with it.
    matches_your_path: bool = False


class SessionTargetOut(BaseModel):
    """What the routine asked for, if the session was started from one."""

    target_sets: int | None
    target_reps: int | None
    target_weight_kg: float | None
    rest_seconds: int | None


class SessionExerciseIn(BaseModel):
    """Add a card to a live workout."""

    exercise_id: uuid.UUID
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    notes: str | None = Field(default=None, max_length=1000)


class SessionExercisePatch(BaseModel):
    """Every field optional. superset_group: a number shared with another card
    makes them a superset; null takes this one out."""

    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    notes: str | None = Field(default=None, max_length=1000)
    superset_group: int | None = Field(default=None, ge=1, le=99)
    # Swap the exercise - only while the card has no sets.
    exercise_id: uuid.UUID | None = None


class ReorderIn(BaseModel):
    """Every card id of the session, in the new order."""

    order: list[uuid.UUID] = Field(min_length=1, max_length=60)


class PreviousSetOut(BaseModel):
    set_number: int
    weight_kg: float
    reps: int | None
    set_type: str
    rpe: float | None


class PreviousOut(BaseModel):
    """The last finished session's sets on one exercise, by set number - the
    PREVIOUS column. Empty when it has never been done."""

    exercise_id: uuid.UUID
    session_id: uuid.UUID | None
    performed_at: dt.datetime | None
    sets: list[PreviousSetOut]


class SessionExerciseOut(BaseModel):
    # The card: its id (for log/edit/reorder calls), place, superset, notes
    # and rest. An exercise added but not logged yet is a card with no sets.
    session_exercise_id: uuid.UUID | None = None
    position: int = 0
    superset_group: int | None = None
    notes: str | None = None
    rest_seconds: int | None = None
    exercise: ExerciseOut
    hint: HintOut | None = None
    target: SessionTargetOut | None
    sets: list[SetOut]
    # Last completed session's sets on this exercise: the ghost values.
    previous_sets: list[SetOut]


class SessionOut(BaseModel):
    id: uuid.UUID
    name: str | None
    status: str
    routine_id: uuid.UUID | None
    started_at: dt.datetime
    ended_at: dt.datetime | None
    # Live for a session in progress.
    duration_seconds: int
    working_sets: int
    total_volume_kg: float
    points_total: int
    points_credited: int
    qualified: bool | None
    exercises: list[SessionExerciseOut]


class ActiveSessionOut(BaseModel):
    """`session` is null when nothing is in progress - a 200 either way, so the
    UI can rehydrate after a refresh without treating 'no workout' as an error."""

    session: SessionOut | None


class SessionSummaryOut(BaseModel):
    id: uuid.UUID
    name: str | None
    status: str
    started_at: dt.datetime
    ended_at: dt.datetime | None
    duration_seconds: int
    working_sets: int
    exercise_count: int
    total_volume_kg: float
    points_total: int
    pr_count: int


class StreakOut(BaseModel):
    weeks: int
    this_week_sessions: int
    target: int
    this_week_done: bool
    sessions_to_go: int
    # Streak freezes held (GET /streak has the detail).
    freezes_held: int = 0


class PointsBreakdownOut(BaseModel):
    set_points: int
    pr_bonus: int
    session_bonus: int
    streak_bonus: int
    reversals: int
    # Generated quests completed during the workout, and the all-weekly bonus.
    quest_points: int = 0
    total: int


class RaidHitOut(BaseModel):
    """A party boss this workout hit (app/core/raids.py)."""

    party_id: uuid.UUID
    party_name: str
    boss_name: str
    damage: int
    hp_remaining: int
    defeated: bool
    defeated_now: bool


class FinishResponse(BaseModel):
    session: SessionSummaryOut
    qualified: bool
    awards: list[AwardOut]
    breakdown: PointsBreakdownOut
    # Shop points credited to the wallet by this finish.
    points_credited: int
    # Every record set during the session, volume records included.
    pr_events: list[PrEventOut]
    streak: StreakOut
    progression: ProgressionDeltaOut
    # Party bosses hit by this workout (qualified workouts only).
    raids: list[RaidHitOut] = []
    # 0-1 per muscle group code, relative to the most-worked - the summary's
    # body map. Map codes to SVG paths with GET /taxonomy.
    muscles_worked: dict[str, float] = {}
    # Set when this workout moved the rank: {"from": "C", "to": "B"}. Promotion
    # only - the rank-up animation plays after the summary.
    rank_change: dict[str, str] | None = None
    quest_progress: list[QuestProgressOut] = []
    quests_completed: list[QuestProgressOut] = []


class AbandonResponse(BaseModel):
    session: SessionSummaryOut
    points_reversed: int
    progression: ProgressionDeltaOut


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------


class PointsSummaryOut(BaseModel):
    total_points: int
    this_week_points: int
    sessions_completed: int
    streak: StreakOut


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    points: int
    reason: str
    session_id: uuid.UUID | None
    created_at: dt.datetime


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------


class RoutineExerciseIn(BaseModel):
    exercise_id: uuid.UUID
    target_sets: int | None = Field(default=None, ge=1, le=50)
    # A single target, as before - or a range with the two below. A range
    # wins; target_reps is then stored as its top.
    target_reps: int | None = Field(default=None, ge=1, le=rules.MAX_REPS)
    target_reps_low: int | None = Field(default=None, ge=1, le=rules.MAX_REPS)
    target_reps_high: int | None = Field(default=None, ge=1, le=rules.MAX_REPS)
    target_weight_kg: float | None = Field(default=None, ge=0, le=rules.MAX_WEIGHT_KG)
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    # Slots sharing a number are a superset.
    superset_group: int | None = Field(default=None, ge=1, le=99)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _range(self) -> "RoutineExerciseIn":
        low, high = self.target_reps_low, self.target_reps_high
        if low is not None and high is not None and low > high:
            raise ValueError("target_reps_low cannot be above target_reps_high")
        return self


class RoutineIn(BaseModel):
    """Create, or full replace via PUT - the ordered exercise list is replaced
    as a whole, which is simpler and less error-prone than per-slot patches."""

    name: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    exercises: list[RoutineExerciseIn] = Field(default_factory=list, max_length=40)
    # In one of the caller's programs, at this place.
    program_id: uuid.UUID | None = None
    order_in_program: int | None = Field(default=None, ge=0, le=100)
    # "#RRGGBB"; null means the tile colour is derived from the name.
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class RoutineExerciseOut(BaseModel):
    position: int
    exercise: ExerciseOut
    target_sets: int | None
    target_reps: int | None
    target_reps_low: int | None = None
    target_reps_high: int | None = None
    target_weight_kg: float | None
    rest_seconds: int | None
    superset_group: int | None = None
    notes: str | None = None


class RoutineOut(BaseModel):
    id: uuid.UUID
    name: str
    notes: str | None
    exercises: list[RoutineExerciseOut]
    created_at: dt.datetime
    updated_at: dt.datetime
    program_id: uuid.UUID | None = None
    order_in_program: int | None = None
    color: str | None = None
    # When a workout from it was last finished.
    last_performed_at: dt.datetime | None = None


# ---------------------------------------------------------------------------
# Body measurements
# ---------------------------------------------------------------------------

_UNITS_FOR_METRIC: dict[MeasurementMetric, set[MeasurementUnit]] = {
    MeasurementMetric.WEIGHT: {MeasurementUnit.KG, MeasurementUnit.LB},
    MeasurementMetric.BODY_FAT: {MeasurementUnit.PERCENT},
}


class BodyMeasurementCreate(BaseModel):
    metric: MeasurementMetric
    label: str | None = Field(default=None, min_length=1, max_length=40)
    value: float = Field(gt=0, lt=100_000)
    unit: MeasurementUnit
    # Defaults to now. Backdating is allowed - measurements earn no points.
    recorded_at: dt.datetime | None = None

    @model_validator(mode="after")
    def _consistent(self):
        allowed = _UNITS_FOR_METRIC.get(self.metric)
        if allowed is not None and self.unit not in allowed:
            names = ", ".join(sorted(u.value for u in allowed))
            raise ValueError(f"unit for {self.metric.value} must be one of: {names}")
        if (self.metric is MeasurementMetric.CUSTOM) != (self.label is not None):
            raise ValueError("label is required for custom metrics and only for them")
        if self.metric is MeasurementMetric.BODY_FAT and self.value > 100:
            raise ValueError("body fat is a percentage")
        if self.recorded_at is not None and self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
        return self


class BodyMeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric: str
    label: str | None
    value: float
    unit: str
    recorded_at: dt.datetime


# ---------------------------------------------------------------------------
# Imports from Strong and Hevy
# ---------------------------------------------------------------------------


class WorkoutImportIn(BaseModel):
    """A Strong or Hevy CSV export, as text (app/core/importer.py)."""

    csv: str = Field(min_length=1, max_length=5_000_000)
    # What Strong's weights are in - its export doesn't say. Defaults to the
    # account's unit. Hevy's columns name their unit, so it's ignored there.
    unit: WeightUnit | None = None


class WorkoutImportOut(BaseModel):
    source: str
    workouts_imported: int
    sets_imported: int
    # Already in the history (same start time), so not imported again.
    workouts_skipped: int
    # Rows with nothing loggable: no reps, time or distance, or bad numbers.
    rows_skipped: int
    exercises_created: list[str]
    xp_awarded: int
    # True when this exact file was imported before; nothing changed.
    duplicate: bool
    progression: ProgressionDeltaOut | None
