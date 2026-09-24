"""Typed views of the gym-workout API payloads.

Same conventions as models.py: plain dataclasses (rx.Base is gone in Reflex
0.9), nulls coerced to safe defaults, and every derived label STORED as a field
rather than exposed as a @property - Reflex compiles templates to JS and cannot
evaluate a Python property on a model.

Weights arrive in kilograms. They are converted to the user's display unit
here, once, so no template ever does arithmetic on a Var. Nothing in this file
computes a point value, a PR or a streak: those come from the API verbatim.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from metalarm import motivation, ranks

LB_PER_KG = 1 / 0.45359237

_RECORD_LABELS = {
    "max_weight": "HEAVIEST",
    "max_reps_at_weight": "REP PR",
    "est_1rm": "EST. 1RM",
    "max_volume": "VOLUME",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def to_unit(kg: float | None, unit: str) -> float:
    if not kg:
        return 0.0
    return float(kg) * LB_PER_KG if unit == "lb" else float(kg)


def fmt(value: float) -> str:
    """12.0 -> '12', 12.25 -> '12.3'. Trailing zeros read as noise on a set."""
    rounded = round(float(value), 1)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.1f}"


def weight_label(kg: float | None, unit: str) -> str:
    return f"{fmt(to_unit(kg, unit))} {unit}"


def thousands(value: float) -> str:
    return f"{round(value):,}"


def muscles_label(groups: list[str] | None) -> str:
    return " · ".join(g.replace("_", " ").upper() for g in groups or [])


def clock(seconds: int | float | None) -> str:
    total = int(seconds or 0)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def local_dt(iso: str | None, tz: str) -> dt.datetime | None:
    """The user's local time for an API timestamp. The API speaks UTC; a
    session logged at 01:00 in IST must not be dated the previous day."""
    if not iso:
        return None
    try:
        moment = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    try:
        return moment.astimezone(ZoneInfo(tz or "UTC"))
    except ZoneInfoNotFoundError:
        return moment


def day_label(iso: str | None, tz: str) -> str:
    moment = local_dt(iso, tz)
    return moment.strftime("%a %d %b") if moment else ""


def short_date(iso: str | None, tz: str) -> str:
    moment = local_dt(iso, tz)
    return moment.strftime("%d %b") if moment else ""


def session_title(name: str | None, started_at: str | None, tz: str) -> str:
    """A blank workout gets a name from when it started - "Evening workout"
    reads better in history than a column of identical "Workout" rows."""
    if name:
        return name
    moment = local_dt(started_at, tz)
    if moment is None:
        return "Workout"
    hour = moment.hour
    if 5 <= hour < 12:
        part = "Morning"
    elif 12 <= hour < 17:
        part = "Afternoon"
    elif 17 <= hour < 22:
        part = "Evening"
    else:
        part = "Late-night"
    return f"{part} workout"


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Sets and exercise cards
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SetRow:
    id: str = ""
    set_number: int = 0
    summary: str = ""
    detail: str = ""
    is_warmup: bool = False
    is_pr: bool = False
    # Raw values in the display unit, used to pre-fill the next set and the
    # edit form.
    rpe: str = ""
    weight: str = ""
    reps: str = ""
    duration_min: str = ""
    distance_km: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], unit: str) -> "SetRow":
        kg = _num(data.get("weight_kg"))
        reps = data.get("reps")
        duration = data.get("duration_seconds")
        distance = data.get("distance_m")

        if reps:
            summary = f"{weight_label(kg, unit)} × {reps}" if kg else f"{reps} reps"
        else:
            parts = []
            if duration:
                parts.append(clock(duration))
            if distance:
                parts.append(f"{fmt(_num(distance) / 1000)} km")
            summary = " · ".join(parts) or "-"

        details = []
        if data.get("rpe"):
            details.append(f"RPE {fmt(_num(data['rpe']))}")
        if reps and (duration or distance):
            details.append(clock(duration) if duration else f"{fmt(_num(distance) / 1000)} km")

        return cls(
            id=data.get("id") or "",
            set_number=data.get("set_number") or 0,
            summary=summary,
            detail=" · ".join(details),
            is_warmup=bool(data.get("is_warmup")),
            is_pr=bool(data.get("is_pr")),
            rpe=fmt(_num(data["rpe"])) if data.get("rpe") else "",
            weight=fmt(to_unit(kg, unit)) if kg else "",
            reps=str(reps) if reps else "",
            duration_min=fmt(duration / 60) if duration else "",
            distance_km=fmt(_num(distance) / 1000) if distance else "",
        )


@dataclasses.dataclass
class ExerciseCard:
    """One exercise in the live workout, with its entry fields.

    The entry fields live on the card (not in per-exercise dicts) so the
    template binds to plain attributes of the foreach item.
    """

    exercise_id: str = ""
    name: str = ""
    muscles_label: str = ""
    # "" when the library has no demo clip for this movement yet.
    media_url: str = ""
    is_cardio: bool = False
    target_label: str = ""
    rest_seconds: int = 90
    sets: list[SetRow] = dataclasses.field(default_factory=list)
    previous: list[SetRow] = dataclasses.field(default_factory=list)
    previous_label: str = ""
    ghost_label: str = ""
    # What to try next (backend app/core/progression_hints.py).
    hint_label: str = ""
    hint_kind: str = ""
    weight_input: str = ""
    reps_input: str = ""
    rpe_input: str = ""
    duration_input: str = ""
    distance_input: str = ""
    warmup: bool = False
    # Idempotency key for the NEXT submit of this card. Rotated only after a
    # successful log, so a double-tap or a retry reuses it and the API returns
    # the original set instead of logging a second one.
    client_set_id: str = ""
    # The last set's outcome: "pr" (paid PR), "record", "first", or "".
    flash_kind: str = ""
    flash_label: str = ""


@dataclasses.dataclass
class PrView:
    exercise_name: str = ""
    record_label: str = ""
    headline: str = ""
    delta: str = ""
    bonus_awarded: bool = False
    is_baseline: bool = False
    # The line that follows the record, from the set that set it.
    motivation: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], unit: str) -> "PrView":
        kind = data.get("record_type") or ""
        value = _num(data.get("value"))
        previous = data.get("previous_value")
        weight = data.get("weight_kg")

        if kind == "max_reps_at_weight":
            headline = f"{int(value)} reps" + (f" @ {weight_label(weight, unit)}" if weight else "")
            delta = f"+{int(value - _num(previous))} reps" if previous else ""
        elif kind == "max_volume":
            headline = f"{thousands(to_unit(value, unit))} {unit}"
            delta = f"+{thousands(to_unit(value - _num(previous), unit))} {unit}" if previous else ""
        else:
            headline = weight_label(value, unit)
            delta = f"+{fmt(to_unit(value - _num(previous), unit))} {unit}" if previous else ""

        baseline = bool(data.get("is_baseline"))
        return cls(
            exercise_name=data.get("exercise_name") or "",
            record_label=_RECORD_LABELS.get(kind, kind.upper()),
            headline=headline,
            delta="FIRST LOG" if baseline else delta,
            bonus_awarded=bool(data.get("bonus_awarded")),
            is_baseline=baseline,
            motivation=motivation.line_for(
                str(data.get("set_id") or data.get("exercise_id") or "")
            ),
        )


# ---------------------------------------------------------------------------
# Library, routines, history
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ExercisePick:
    id: str = ""
    name: str = ""
    muscles_label: str = ""
    meta_label: str = ""
    is_custom: bool = False
    # "" when the library has no clip for this movement yet.
    media_url: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "ExercisePick":
        equipment = (data.get("equipment") or "").replace("_", " ")
        return cls(
            id=data.get("id") or "",
            name=data.get("name") or "",
            muscles_label=muscles_label(data.get("primary_muscle_groups")),
            meta_label=("CUSTOM · " if data.get("is_custom") else "") + equipment.upper(),
            is_custom=bool(data.get("is_custom")),
            media_url=data.get("media_url") or "",
        )


@dataclasses.dataclass
class PresetSlot:
    """One movement of a ready-made workout, with what it asks for."""

    exercise_id: str = ""
    name: str = ""
    muscles_label: str = ""
    media_url: str = ""
    plan: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PresetSlot":
        exercise = data.get("exercise") or {}
        rest = int(data.get("rest_seconds") or 0)
        rest_label = f"{rest // 60}:{rest % 60:02d}" if rest >= 60 else f"{rest}s"
        return cls(
            exercise_id=exercise.get("id") or "",
            name=exercise.get("name") or "",
            muscles_label=muscles_label(exercise.get("primary_muscle_groups")),
            media_url=exercise.get("media_url") or "",
            plan=f"{data.get('target_sets')} × {data.get('target_reps')} · rest {rest_label}",
        )


@dataclasses.dataclass
class WorkoutPreset:
    """A ready-made workout for one training style (GET /workouts/presets)."""

    slug: str = ""
    category: str = ""
    category_label: str = ""
    name: str = ""
    summary: str = ""
    length_label: str = ""
    exercises: list[PresetSlot] = dataclasses.field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "WorkoutPreset":
        slots = [PresetSlot.from_api(slot) for slot in data.get("exercises") or []]
        return cls(
            slug=data.get("slug") or "",
            category=data.get("category") or "",
            category_label=(data.get("category") or "").upper(),
            name=data.get("name") or "",
            summary=data.get("summary") or "",
            length_label=f"{len(slots)} exercise" + ("" if len(slots) == 1 else "s"),
            exercises=slots,
        )


@dataclasses.dataclass
class Chip:
    value: str = ""
    label: str = ""

    @classmethod
    def of(cls, value: str) -> "Chip":
        return cls(value=value, label=value.replace("_", " ").upper())


@dataclasses.dataclass
class RoutineSlot:
    exercise_id: str = ""
    name: str = ""
    muscles_label: str = ""
    # Strings: these are bound to inputs in the editor.
    target_sets: str = ""
    target_reps: str = ""
    target_weight: str = ""
    rest_seconds: str = ""
    target_label: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], unit: str) -> "RoutineSlot":
        exercise = data.get("exercise") or {}
        sets, reps, kg = data.get("target_sets"), data.get("target_reps"), data.get("target_weight_kg")
        bits = []
        if sets:
            bits.append(f"{sets}")
        if reps:
            bits.append(f"× {reps}")
        if kg:
            bits.append(f"@ {weight_label(kg, unit)}")
        return cls(
            exercise_id=exercise.get("id") or "",
            name=exercise.get("name") or "",
            muscles_label=muscles_label(exercise.get("primary_muscle_groups")),
            target_sets=str(sets) if sets else "",
            target_reps=str(reps) if reps else "",
            target_weight=fmt(to_unit(kg, unit)) if kg else "",
            rest_seconds=str(data.get("rest_seconds")) if data.get("rest_seconds") else "",
            target_label=" ".join(bits),
        )


@dataclasses.dataclass
class RoutineItem:
    id: str = ""
    name: str = ""
    notes: str = ""
    summary_label: str = ""
    exercise_count: int = 0
    slots: list[RoutineSlot] = dataclasses.field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], unit: str) -> "RoutineItem":
        slots = [RoutineSlot.from_api(s, unit) for s in data.get("exercises") or []]
        names = [s.name for s in slots]
        summary = " · ".join(names[:3]) + (f"  +{len(names) - 3}" if len(names) > 3 else "")
        return cls(
            id=data.get("id") or "",
            name=data.get("name") or "",
            notes=data.get("notes") or "",
            summary_label=summary or "No exercises yet",
            exercise_count=len(slots),
            slots=slots,
        )


@dataclasses.dataclass
class HistoryRow:
    id: str = ""
    title: str = ""
    date_label: str = ""
    duration_label: str = ""
    sets_label: str = ""
    volume_label: str = ""
    points: int = 0
    pr_count: int = 0
    status: str = ""
    status_label: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], unit: str, tz: str) -> "HistoryRow":
        status = data.get("status") or ""
        return cls(
            id=data.get("id") or "",
            title=session_title(data.get("name"), data.get("started_at"), tz),
            date_label=day_label(data.get("started_at"), tz),
            duration_label=f"{int((data.get('duration_seconds') or 0) // 60)} min",
            sets_label=f"{data.get('working_sets') or 0} sets",
            volume_label=f"{thousands(to_unit(data.get('total_volume_kg'), unit))} {unit}",
            points=data.get("points_total") or 0,
            pr_count=data.get("pr_count") or 0,
            status=status,
            status_label={"completed": "DONE", "abandoned": "DISCARDED"}.get(status, "LIVE"),
        )


@dataclasses.dataclass
class StreakView:
    weeks: int = 0
    this_week: int = 0
    target: int = 3
    done: bool = False
    label: str = "NO STREAK YET"
    sub: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "StreakView":
        weeks = data.get("weeks") or 0
        this_week = data.get("this_week_sessions") or 0
        target = data.get("target") or 3
        to_go = data.get("sessions_to_go") or 0
        done = bool(data.get("this_week_done"))
        if done:
            sub = "This week is locked in"
        elif weeks:
            sub = f"{to_go} more workout{'s' if to_go != 1 else ''} this week keeps it alive"
        else:
            sub = f"{this_week}/{target} workouts this week - hit {target} to start a streak"
        return cls(
            weeks=weeks,
            this_week=this_week,
            target=target,
            done=done,
            label=f"{weeks}-WEEK STREAK" if weeks else "NO STREAK YET",
            sub=sub,
        )


@dataclasses.dataclass
class AwardLine:
    label: str = ""
    points_label: str = ""
    negative: bool = False


@dataclasses.dataclass
class FinishSummary:
    title: str = ""
    duration_label: str = ""
    volume_label: str = ""
    sets_label: str = ""
    pr_count: int = 0
    points_credited: int = 0
    qualified: bool = True
    qualified_note: str = ""
    lines: list[AwardLine] = dataclasses.field(default_factory=list)
    prs: list[PrView] = dataclasses.field(default_factory=list)
    streak: StreakView = dataclasses.field(default_factory=StreakView)
    # The story card (metalarm/share_card.py): the workout's biggest moment.
    share_kind: str = ""
    share_eyebrow: str = ""
    share_headline: str = ""
    share_caption: str = ""

    @staticmethod
    def share_moment(data: dict[str, Any], prs: list[PrView]) -> tuple[str, str, str, str]:
        """(kind, eyebrow, headline, caption): rank-up, then level-up, then a
        record, then the points - the same order as the iOS card."""
        progression = data.get("progression") or {}
        if progression.get("ranked_up"):
            title = ranks.rank_title(str(progression.get("rank_after") or ""))
            return "rank", "RANK UP", title.upper(), f"{title} at level {progression.get('level_after')}"
        if progression.get("leveled_up"):
            level = str(progression.get("level_after") or "")
            return "level", "LEVEL UP", level, f"Level {level} reached"
        if prs:
            lead = next((p for p in prs if p.bonus_awarded), prs[0])
            return "record", "NEW PERSONAL RECORD", lead.headline, lead.motivation or lead.exercise_name
        return "workout", "WORKOUT COMPLETE", f"+{data.get('points_credited') or 0}", "points earned"

    @classmethod
    def from_api(cls, data: dict[str, Any], title: str, unit: str) -> "FinishSummary":
        session = data.get("session") or {}
        breakdown = data.get("breakdown") or {}
        lines = []
        for key, label in (
            ("set_points", "Sets logged"),
            ("pr_bonus", "PR bonus"),
            ("session_bonus", "Workout bonus"),
            ("streak_bonus", "Streak bonus"),
            ("reversals", "Corrections"),
        ):
            points = breakdown.get(key) or 0
            if points:
                lines.append(
                    AwardLine(
                        label=label,
                        points_label=f"{'+' if points > 0 else ''}{points}",
                        negative=points < 0,
                    )
                )
        prs = [
            PrView.from_api(e, unit)
            for e in data.get("pr_events") or []
            if not e.get("is_baseline")
        ]
        qualified = bool(data.get("qualified"))
        share_kind, share_eyebrow, share_headline, share_caption = cls.share_moment(data, prs)
        return cls(
            share_kind=share_kind,
            share_eyebrow=share_eyebrow,
            share_headline=share_headline,
            share_caption=share_caption,
            title=title or "Workout",
            duration_label=clock(session.get("duration_seconds")),
            volume_label=f"{thousands(to_unit(session.get('total_volume_kg'), unit))} {unit}",
            sets_label=str(session.get("working_sets") or 0),
            pr_count=len(prs),
            points_credited=data.get("points_credited") or 0,
            qualified=qualified,
            qualified_note=""
            if qualified
            else (
                "Short session: under 10 minutes or 3 working sets earns no workout "
                "bonus and doesn't count toward your streak. Your set points still count."
            ),
            lines=lines,
            prs=prs,
            streak=StreakView.from_api(data.get("streak") or {}),
        )


# ---------------------------------------------------------------------------
# Progress page
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ExerciseOption:
    id: str = ""
    name: str = ""


@dataclasses.dataclass
class RecordRow:
    exercise_name: str = ""
    record_label: str = ""
    value_label: str = ""
    date_label: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], unit: str, tz: str) -> "RecordRow":
        view = PrView.from_api({**data, "is_baseline": False, "previous_value": None}, unit)
        return cls(
            exercise_name=data.get("exercise_name") or "",
            record_label=view.record_label,
            value_label=view.headline,
            date_label=short_date(data.get("achieved_at"), tz),
        )


_METRIC_LABELS = {"weight": "BODY WEIGHT", "body_fat": "BODY FAT"}
_UNIT_LABELS = {"percent": "%"}


@dataclasses.dataclass
class BodyRow:
    id: str = ""
    metric_label: str = ""
    value_label: str = ""
    date_label: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], tz: str) -> "BodyRow":
        metric = data.get("metric") or ""
        unit = data.get("unit") or ""
        unit_label = _UNIT_LABELS.get(unit, f" {unit}")
        return cls(
            id=data.get("id") or "",
            metric_label=(data.get("label") or "").upper() or _METRIC_LABELS.get(metric, metric.upper()),
            value_label=f"{fmt(_num(data.get('value')))}{unit_label}",
            date_label=day_label(data.get("recorded_at"), tz),
        )
