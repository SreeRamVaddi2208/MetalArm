"""Import workout history from Strong and Hevy CSV exports.

Both apps export one row per set:

    Strong  Date, Workout Name, Duration, Exercise Name, Set Order, Weight,
            Reps, Distance, Seconds, Notes, Workout Notes, RPE
            (comma or semicolon separated; older exports add Weight Unit and
            Distance Unit, and Set Order is "W" for a warm-up)
    Hevy    title, start_time, end_time, description, exercise_title,
            superset_id, exercise_notes, set_index, set_type, weight_kg (or
            weight_lbs), reps, distance_km (or distance_miles),
            duration_seconds, rpe

`parse` is pure, so both formats are unit-tested without a database;
`run_import` persists the result. Exercise names are matched to the library
by slug: "Bench Press (Barbell)" tries barbell-bench-press, then the aliases
below, then the bare name when its equipment agrees - so "Squat (Smith
Machine)" never lands on the barbell Back Squat and its rank trial. Anything
unmatched becomes the user's own exercise.

Imported history is real history - personal records, rank trials, charts and
progression hints all see it - but it can't be verified, so it pays a little
XP and never shop points, streaks, party raids or leaderboard places.
Imported sessions are stored as completed but not qualified, which is what
keeps them out of streaks and raids. The same file imports once (by hash),
and a workout already in the history - same start time - is skipped, so a
newer, cumulative export only adds what is new.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import hashlib
import io
import re
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import rank_trials
from app.core import workout_rules as rules
from app.core import workout_store as store
from app.core import workout_streaks as streaks
from app.core.exercise_names import clean_name, name_key, slugify
from app.core.progression import ProgressionDelta, apply_xp
from app.models.user import LevelProgress, User
from app.models.workout import Exercise, SetEntry, WorkoutImport, WorkoutSession
from app.models.workout_enums import SessionStatus

STRONG = "strong"
HEVY = "hevy"

MAX_CSV_CHARS = 5_000_000
MAX_WORKOUTS = 5_000
MAX_SETS = 50_000
XP_PER_WORKOUT = 10
XP_CAP_PER_IMPORT = 500

LB_TO_KG = Decimal(str(rules.LB_TO_KG))
MILE_TO_M = Decimal("1609.344")
_CENTS = Decimal("0.01")


class ImportFormatError(ValueError):
    """The file can't be imported; the message is shown to the user."""


@dataclasses.dataclass(frozen=True)
class ImportedSet:
    exercise_name: str
    weight_kg: Decimal
    reps: int | None
    duration_seconds: int | None
    distance_m: Decimal | None
    rpe: Decimal | None
    is_warmup: bool


@dataclasses.dataclass
class ImportedWorkout:
    name: str
    started_at: dt.datetime
    ended_at: dt.datetime
    sets: list[ImportedSet]


@dataclasses.dataclass
class ParsedImport:
    source: str
    workouts: list[ImportedWorkout]
    # Rows that looked like sets but couldn't be logged (no reps, time or
    # distance; out-of-range numbers; a date in the future).
    skipped_rows: int


def file_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_DURATION_PART = re.compile(r"(\d+)\s*([hms])")
_TIME_FORMATS = (
    "%d %b %Y, %H:%M",
    "%d %b %Y %H:%M",
    "%b %d, %Y, %I:%M %p",
    "%b %d, %Y %I:%M %p",
    "%Y-%m-%d %H:%M",
)
# A row that belongs to a workout but isn't a set (Strong's rest timers and
# notes rows). Not counted as skipped.
_NOT_A_SET = object()


def _decimal(value: str | None) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    # Semicolon exports from comma-decimal locales write 82,5.
    if "," in value and "." not in value:
        value = value.replace(",", ".")
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _int(value: str | None) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None else None


def _duration_seconds(value: str | None) -> int | None:
    value = (value or "").strip().lower()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    units = {"h": 3600, "m": 60, "s": 1}
    parts = _DURATION_PART.findall(value)
    return sum(int(n) * units[u] for n, u in parts) if parts else None


def _parse_time(value: str | None, tz: ZoneInfo) -> dt.datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    moment = None
    try:
        moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for fmt in _TIME_FORMATS:
            try:
                moment = dt.datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if moment is None:
        return None
    # Both apps write local wall-clock times.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    return moment.astimezone(dt.timezone.utc)


def _make_set(
    exercise: str,
    weight: Decimal | None,
    reps: int | None,
    seconds: int | None,
    distance_m: Decimal | None,
    rpe: Decimal | None,
    is_warmup: bool,
) -> ImportedSet | None:
    weight = weight if weight is not None else Decimal(0)
    if weight < 0 or weight > rules.MAX_WEIGHT_KG:
        return None
    reps = reps if reps is not None and 1 <= reps <= rules.MAX_REPS else None
    seconds = seconds if seconds is not None and 1 <= seconds <= rules.MAX_DURATION_SECONDS else None
    distance_m = distance_m if distance_m is not None and 0 < distance_m <= rules.MAX_DISTANCE_M else None
    if reps is None and seconds is None and distance_m is None:
        return None
    rpe = rpe if rpe is not None and 1 <= rpe <= 10 else None
    return ImportedSet(
        exercise_name=clean_name(exercise)[:120],
        weight_kg=weight.quantize(_CENTS),
        reps=reps,
        duration_seconds=seconds,
        distance_m=distance_m.quantize(_CENTS) if distance_m is not None else None,
        rpe=rpe.quantize(Decimal("0.1")) if rpe is not None else None,
        is_warmup=is_warmup,
    )


def _strong_row(row: dict[str, str], unit: str, tz: ZoneInfo):
    started = _parse_time(row.get("Date"), tz)
    exercise = row.get("Exercise Name", "")
    if started is None or not exercise:
        return None
    name = row.get("Workout Name") or "Strong workout"
    ended = started + dt.timedelta(seconds=_duration_seconds(row.get("Duration")) or 0)
    key = (row.get("Date"), name)
    order = row.get("Set Order", "").upper()
    if not (order.isdigit() or order in {"W", "D", "F"}):
        return key, name, started, ended, _NOT_A_SET

    weight = _decimal(row.get("Weight"))
    if weight is not None and (row.get("Weight Unit") or unit).lower().startswith("lb"):
        weight *= LB_TO_KG
    distance = _decimal(row.get("Distance"))
    if distance is not None:
        distance_unit = (row.get("Distance Unit") or ("km" if unit == "kg" else "mi")).lower()
        distance *= MILE_TO_M if distance_unit.startswith("mi") else Decimal(1000)
    entry = _make_set(
        exercise,
        weight,
        _int(row.get("Reps")),
        _int(row.get("Seconds")),
        distance,
        _decimal(row.get("RPE")),
        is_warmup=order == "W",
    )
    return key, name, started, ended, entry


def _hevy_row(row: dict[str, str], tz: ZoneInfo):
    started = _parse_time(row.get("start_time"), tz)
    exercise = row.get("exercise_title", "")
    if started is None or not exercise:
        return None
    name = row.get("title") or "Hevy workout"
    ended = _parse_time(row.get("end_time"), tz) or started
    key = (row.get("start_time"), name)

    if row.get("weight_lbs"):
        pounds = _decimal(row["weight_lbs"])
        weight = pounds * LB_TO_KG if pounds is not None else None
    else:
        weight = _decimal(row.get("weight_kg"))
    if row.get("distance_miles"):
        miles = _decimal(row["distance_miles"])
        distance = miles * MILE_TO_M if miles is not None else None
    else:
        km = _decimal(row.get("distance_km"))
        distance = km * 1000 if km is not None else None
    entry = _make_set(
        exercise,
        weight,
        _int(row.get("reps")),
        _int(row.get("duration_seconds")),
        distance,
        _decimal(row.get("rpe")),
        is_warmup=row.get("set_type", "").lower() == "warmup",
    )
    return key, name, started, ended, entry


def parse(text: str, *, unit: str, tz_name: str, now: dt.datetime) -> ParsedImport:
    """Read a Strong or Hevy export. `unit` is what Strong's weights are in
    when the file doesn't say (Strong writes the app's unit, not a column)."""
    if len(text) > MAX_CSV_CHARS:
        raise ImportFormatError("That file is too large - the limit is 5 MB")
    text = text.lstrip("﻿")
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fields = {(f or "").strip() for f in reader.fieldnames or []}
    if {"Date", "Exercise Name", "Set Order"} <= fields:
        source = STRONG
    elif {"start_time", "exercise_title", "set_index"} <= fields:
        source = HEVY
    else:
        raise ImportFormatError("That isn't a Strong or Hevy CSV export")

    tz = ZoneInfo(tz_name)
    workouts: dict[tuple, ImportedWorkout] = {}
    skipped = 0
    total_sets = 0
    for raw in reader:
        row = {(k or "").strip(): v.strip() for k, v in raw.items() if isinstance(v, str)}
        parsed = _strong_row(row, unit, tz) if source == STRONG else _hevy_row(row, tz)
        if parsed is None:
            skipped += 1
            continue
        key, name, started, ended, entry = parsed
        if entry is _NOT_A_SET:
            continue
        if entry is None or started > now:
            skipped += 1
            continue
        workout = workouts.get(key)
        if workout is None:
            if len(workouts) >= MAX_WORKOUTS:
                raise ImportFormatError(f"That file has more than {MAX_WORKOUTS:,} workouts")
            workout = workouts[key] = ImportedWorkout(name, started, ended, [])
        workout.sets.append(entry)
        total_sets += 1
        if total_sets > MAX_SETS:
            raise ImportFormatError(f"That file has more than {MAX_SETS:,} sets")

    return ParsedImport(
        source=source,
        workouts=sorted(workouts.values(), key=lambda w: w.started_at),
        skipped_rows=skipped,
    )


# ---------------------------------------------------------------------------
# Exercise matching
# ---------------------------------------------------------------------------

_PAREN = re.compile(r"^(?P<base>.*?)\s*\((?P<detail>[^)]*)\)\s*$")
# The equipment a name's "(...)" suffix names, as Equipment values.
_EQUIPMENT = {
    "barbell": "barbell",
    "dumbbell": "dumbbell",
    "machine": "machine",
    "cable": "cable",
    "kettlebell": "kettlebell",
    "bodyweight": "bodyweight",
    "band": "band",
    "smith machine": "smith_machine",
    "ez bar": "ez_bar",
    "trap bar": "trap_bar",
    "hex bar": "trap_bar",
    "plate": "plate",
}
# Slugs the generic rules miss -> library slug. Keys are the slugs built from
# the source name ("equipment base", "base equipment" or the bare base).
ALIASES = {
    "squat": "back-squat",
    "barbell-squat": "back-squat",
    "barbell-deadlift": "deadlift",
    "military-press": "overhead-press",
    "barbell-strict-military-press": "overhead-press",
    "barbell-bent-over-row": "barbell-row",
    "bent-over-row": "barbell-row",
    "seated-row": "seated-cable-row",
    "cable-seated-row": "seated-cable-row",
    "hip-thrust": "barbell-hip-thrust",
    "barbell-incline-bench-press": "incline-barbell-bench-press",
    "barbell-decline-bench-press": "decline-barbell-bench-press",
    "dumbbell-incline-bench-press": "incline-dumbbell-press",
    "barbell-close-grip-bench-press": "close-grip-bench-press",
    "dumbbell-chest-fly": "dumbbell-fly",
    "dumbbell-shoulder-press": "seated-dumbbell-shoulder-press",
    "calf-raise": "standing-calf-raise",
    "running": "outdoor-run",
    "treadmill-running": "treadmill-run",
    "cycling": "stationary-bike",
    "indoor-cycling": "stationary-bike",
    "rowing": "rowing-machine",
}
# Spelling variants between the apps and the library.
_SPELLINGS = (
    ("biceps-", ""),
    ("bicep-", ""),
    ("triceps", "tricep"),
    ("pullup", "pull-up"),
    ("chinup", "chin-up"),
    ("pushup", "push-up"),
    ("skullcrusher", "skull-crusher"),
)


@dataclasses.dataclass(frozen=True)
class LibraryEntry:
    id: uuid.UUID
    equipment: str


def _spellings(slug: str) -> list[str]:
    out = [slug]
    for old, new in _SPELLINGS:
        if old in slug:
            out.append(slug.replace(old, new).strip("-"))
    return out


def _lookup(candidate: str, library: dict[str, LibraryEntry]) -> LibraryEntry | None:
    for spelling in _spellings(candidate):
        for slug in (spelling, ALIASES.get(spelling)):
            if slug and slug in library:
                return library[slug]
    return None


def match_library(name: str, library: dict[str, LibraryEntry]) -> LibraryEntry | None:
    """The library exercise a Strong or Hevy name means, if any."""
    found = _PAREN.match(name)
    base, detail = (found["base"], found["detail"].strip()) if found else (name, "")
    exact = [slugify(name)]
    if detail:
        exact += [slugify(f"{detail} {base}"), slugify(f"{base} {detail}")]
    for candidate in exact:
        if (entry := _lookup(candidate, library)) is not None:
            return entry
    # The bare name only when the equipment agrees - or the suffix isn't
    # equipment at all ("Assisted", "Wide Grip").
    entry = _lookup(slugify(base), library)
    equipment = _EQUIPMENT.get(detail.lower())
    if entry is not None and (equipment is None or entry.equipment == equipment):
        return entry
    return None


def custom_shape(name: str, first: ImportedSet) -> tuple[str, str, list[str]]:
    """(category, equipment, muscles) for a new exercise from its first set."""
    found = _PAREN.match(name)
    equipment = _EQUIPMENT.get(found["detail"].strip().lower(), "other") if found else "other"
    if first.reps is None and first.weight_kg == 0:
        return "cardio", equipment, ["cardio"]
    if equipment == "bodyweight" or first.weight_kg == 0:
        return "bodyweight", "bodyweight", ["full_body"]
    return "strength", equipment, ["full_body"]


class _ExerciseResolver:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user
        self.library: dict[str, LibraryEntry] = {}
        self.custom: dict[str, uuid.UUID] = {}
        for exercise in db.scalars(select(Exercise).where(store.visible_to(user.id))):
            if exercise.is_custom:
                self.custom[exercise.name_key] = exercise.id
            elif exercise.slug:
                self.library[exercise.slug] = LibraryEntry(exercise.id, exercise.equipment)
        self.resolved: dict[str, uuid.UUID] = {}
        self.created: list[str] = []

    def resolve(self, entry: ImportedSet) -> uuid.UUID:
        key = name_key(entry.exercise_name)
        if key not in self.resolved:
            # The user's own exercise of that name first - including one an
            # earlier import created - then the library, then a new one.
            exercise_id = self.custom.get(key)
            if exercise_id is None:
                match = match_library(entry.exercise_name, self.library)
                exercise_id = match.id if match else self._create(entry)
            self.resolved[key] = exercise_id
        return self.resolved[key]

    def _create(self, entry: ImportedSet) -> uuid.UUID:
        category, equipment, muscles = custom_shape(entry.exercise_name, entry)
        exercise = Exercise(
            name=entry.exercise_name,
            name_key=name_key(entry.exercise_name),
            category=category,
            primary_muscle_groups=muscles,
            equipment=equipment,
            is_custom=True,
            created_by_user_id=self.user.id,
        )
        self.db.add(exercise)
        self.db.flush()
        self.custom[exercise.name_key] = exercise.id
        self.created.append(exercise.name)
        return exercise.id


# ---------------------------------------------------------------------------
# Persisting
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ImportOutcome:
    record: WorkoutImport
    duplicate: bool
    workouts_skipped: int
    rows_skipped: int
    exercises_created: list[str]
    delta: ProgressionDelta | None


def run_import(
    db: Session,
    *,
    user: User,
    progress: LevelProgress,
    text: str,
    unit: str,
    now: dt.datetime,
) -> ImportOutcome:
    """Import a file into the user's history. The caller holds the progress
    lock and commits. The same file a second time changes nothing."""
    digest = file_hash(text)
    existing = db.execute(
        select(WorkoutImport).where(
            WorkoutImport.user_id == user.id, WorkoutImport.file_hash == digest
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ImportOutcome(existing, True, 0, 0, [], None)

    parsed = parse(text, unit=unit, tz_name=user.timezone, now=now)
    if not parsed.workouts:
        raise ImportFormatError("No workouts with loggable sets were found in that file")

    known_starts = set(
        db.scalars(
            select(WorkoutSession.started_at).where(
                WorkoutSession.user_id == user.id,
                WorkoutSession.started_at.between(
                    parsed.workouts[0].started_at, parsed.workouts[-1].started_at
                ),
            )
        )
    )
    fresh = [w for w in parsed.workouts if w.started_at not in known_starts]

    record = WorkoutImport(
        user_id=user.id,
        source=parsed.source,
        file_hash=digest,
        workouts=len(fresh),
        sets=sum(len(w.sets) for w in fresh),
        exercises_created=0,
        xp_awarded=min(XP_CAP_PER_IMPORT, XP_PER_WORKOUT * len(fresh)),
    )
    db.add(record)
    db.flush()

    resolver = _ExerciseResolver(db, user)
    touched: set[uuid.UUID] = set()
    for workout in fresh:
        session = WorkoutSession(
            user_id=user.id,
            name=clean_name(workout.name)[:80] or None,
            started_at=workout.started_at,
            ended_at=max(workout.ended_at, workout.started_at),
            status=SessionStatus.COMPLETED.value,
            qualified=False,
            week_key=streaks.week_key(workout.started_at, user.timezone),
            import_id=record.id,
        )
        db.add(session)
        db.flush()
        numbers: dict[uuid.UUID, int] = defaultdict(int)
        for index, entry in enumerate(workout.sets):
            exercise_id = resolver.resolve(entry)
            numbers[exercise_id] += 1
            touched.add(exercise_id)
            db.add(
                SetEntry(
                    session_id=session.id,
                    user_id=user.id,
                    exercise_id=exercise_id,
                    set_number=numbers[exercise_id],
                    weight_kg=entry.weight_kg,
                    reps=entry.reps,
                    rpe=entry.rpe,
                    duration_seconds=entry.duration_seconds,
                    distance_m=entry.distance_m,
                    is_warmup=entry.is_warmup,
                    # File order, one second apart: the replay orders by it.
                    completed_at=workout.started_at + dt.timedelta(seconds=index),
                )
            )
    db.flush()

    # Records are rebuilt in date order, so an old lift lands where it
    # belongs in the history rather than as today's PR.
    for exercise_id in touched:
        store.replay_exercise(db, user.id, exercise_id)
    record.exercises_created = len(resolver.created)

    delta = apply_xp(progress, xp=record.xp_awarded, at=now, tz_name=user.timezone)
    delta = rank_trials.refresh(db, progress, user, delta, now)
    return ImportOutcome(
        record=record,
        duplicate=False,
        workouts_skipped=len(parsed.workouts) - len(fresh),
        rows_skipped=parsed.skipped_rows,
        exercises_created=resolver.created,
        delta=delta,
    )
