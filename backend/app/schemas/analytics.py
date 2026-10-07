"""Clarity and analytics read models (overhaul phase 2). Every number is
computed server-side in the user's timezone; weights are kg."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class SnapshotOut(BaseModel):
    week_start: dt.date
    workouts: int
    duration_seconds: int
    volume_kg: float
    # This week minus last week.
    workouts_delta: int
    duration_delta: int
    volume_delta: float


class SeriesPoint(BaseModel):
    week_start: dt.date
    value: float


class SeriesOut(BaseModel):
    metric: str
    range: str
    # Seconds for duration, kg for volume, counts for workouts and points.
    unit: str
    points: list[SeriesPoint]


class MuscleVolumeOut(BaseModel):
    code: str
    display_name: str
    # Working sets, primary 1.0 + secondary 0.5.
    sets: float
    intensity: float
    svg_path_ids: list[str]


class MusclesOut(BaseModel):
    from_date: dt.date
    to_date: dt.date
    muscles: list[MuscleVolumeOut]


class CalendarDayOut(BaseModel):
    date: dt.date
    workouts: int


class CalendarRunOut(BaseModel):
    start: dt.date
    end: dt.date
    days: int


class CalendarOut(BaseModel):
    month: str
    days: list[CalendarDayOut]
    runs: list[CalendarRunOut]


class MuscleRecoveryOut(BaseModel):
    code: str
    display_name: str
    percent: int
    svg_path_ids: list[str]


class RecoveryOut(BaseModel):
    overall: int
    muscles: list[MuscleRecoveryOut]
    # Shown wherever the number is: this is a model, not a measurement.
    note: str


class HistoryRowOut(BaseModel):
    id: uuid.UUID
    name: str | None
    started_at: dt.datetime
    duration_seconds: int
    volume_kg: float
    working_sets: int
    exercise_count: int
    pr_count: int
    points: int


class HistoryMonthOut(BaseModel):
    month: str                   # "2026-10"
    sessions: list[HistoryRowOut]


class HistoryPage(BaseModel):
    months: list[HistoryMonthOut]
    next_cursor: str | None = None


class MyExerciseOut(BaseModel):
    exercise_id: uuid.UUID
    name: str
    thumbnail_url: str | None
    primary_muscle_groups: list[str]
    equipment: str
    last_performed_at: dt.datetime
    sessions: int
    best_weight_kg: float | None
    best_weight_reps: int | None
    best_est_1rm: float | None


class MyExercisesPage(BaseModel):
    items: list[MyExerciseOut]
    next_cursor: str | None = None


class StatsPoint(BaseModel):
    session_id: uuid.UUID
    date: dt.date
    best_set_weight_kg: float | None
    best_set_reps: int | None
    est_1rm: float | None
    volume_kg: float
    max_reps: int | None


class StatsSet(BaseModel):
    set_number: int
    set_type: str
    weight_kg: float
    reps: int | None
    is_pr: bool


class StatsSession(BaseModel):
    session_id: uuid.UUID
    name: str | None
    started_at: dt.datetime
    sets: list[StatsSet]


class StatsRecord(BaseModel):
    record_type: str
    value: float
    weight_kg: float | None
    achieved_at: dt.datetime


class ExerciseStatsOut(BaseModel):
    exercise_id: uuid.UUID
    range: str
    series: list[StatsPoint]
    # Newest first; at most the last 20 sessions in the range.
    sessions: list[StatsSession]
    records: list[StatsRecord]


class MonthlyRecordOut(BaseModel):
    exercise_name: str
    record_type: str
    value: float
    achieved_at: dt.datetime


class MonthlySummaryOut(BaseModel):
    """Every slide of the Monthly Summary."""

    month: str                      # "2026-09"
    workouts: int
    duration_seconds: int
    active_days: int
    best_week_workouts: int
    volume_kg: float
    working_sets: int
    volume_comparison: str
    # Most-trained first; the body map's input.
    muscles: list[MuscleVolumeOut]
    records: list[MonthlyRecordOut]
    record_count: int
    points: int
    rank: str
    level: int
    # Promotions in the month, as they read ("Reached Novice").
    rank_ups: list[str]
    quests_completed: int
    duels_played: int
    duels_won: int


class MonthlyHeroOut(BaseModel):
    month: str
    show: bool
    workouts: int
