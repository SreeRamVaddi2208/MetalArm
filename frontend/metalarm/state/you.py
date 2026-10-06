"""The You tab (overhaul 7.8): who you are in the game, and how your training
is going - Overview (chart, muscles, calendar), Exercises, Measurements,
History.

The server computes every figure (app/core/analytics.py); this state only
fetches, converts kg to the user's unit, and shapes rows for display.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import reflex as rx

from metalarm import analytics_api as aapi
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.workout_home import duration_label, history_rows
from metalarm.ui.body_map import paths_for
from metalarm.workout_models import fmt, local_dt, to_unit

TABS = ["Overview", "Exercises", "Measurements", "History"]
RANGES = ["3M", "6M", "Year", "All"]
METRICS = ["Duration", "Volume", "Workouts", "Points"]


def _metric_display(metric: str, value: float, unit: str) -> float:
    """The chart's y value: hours for duration, the user's unit for volume."""
    if metric == "duration":
        return round(value / 3600, 1)
    if metric == "volume":
        return round(to_unit(value, unit))
    return round(value)


def month_grid(first: dt.date, trained: set[dt.date], today: dt.date) -> list[list[dict[str, str]]]:
    """Rows of Monday-Sunday cells covering the month, for ui.calendar."""
    start = first - dt.timedelta(days=first.weekday())
    nxt = (first + dt.timedelta(days=32)).replace(day=1)
    end = nxt - dt.timedelta(days=1)
    end += dt.timedelta(days=6 - end.weekday())
    rows: list[list[dict[str, str]]] = []
    day = start
    while day <= end:
        week = []
        for _ in range(7):
            on = day in trained
            week.append({
                "number": str(day.day), "trained": "1" if on else "",
                "run_left": "1" if on and day - dt.timedelta(days=1) in trained and day.weekday() > 0 else "",
                "run_right": "1" if on and day + dt.timedelta(days=1) in trained and day.weekday() < 6 else "",
                "today": "1" if day == today else "", "in_month": "1" if day.month == first.month else "",
            })
            day += dt.timedelta(days=1)
        rows.append(week)
    return rows


class YouState(rx.State):
    tab: str = "Overview"
    error: str = ""

    # --- Overview ---
    range_: str = "3M"
    metric: str = "Volume"
    chart: list[dict[str, Any]] = []
    headline: str = "0"
    headline_unit: str = ""
    headline_label: str = ""
    muscle_paths: dict[str, float] = {}
    muscle_names: str = ""
    month: str = ""             # "2026-10"
    month_title: str = ""
    month_weeks: list[list[dict[str, str]]] = []
    month_count: str = ""

    # --- Exercises ---
    exercises: list[dict[str, str]] = []
    exercises_cursor: str = ""

    # --- History ---
    history: list[dict[str, str]] = []
    history_cursor: str = ""

    # --- Measurements ---
    measures: list[dict[str, Any]] = []
    measure_key: str = ""
    measure_kind: str = "weight"
    measure_value: str = ""
    measure_label: str = ""

    @rx.var
    def measure_groups(self) -> list[dict[str, str]]:
        groups: dict[str, dict[str, str]] = {}
        for m in self.measures:   # newest first
            if m["key"] not in groups:
                groups[m["key"]] = {"key": m["key"], "title": m["title"],
                                    "latest": f"{m['value']} {m['unit']}", "when": m["date"]}
        return list(groups.values())

    @rx.var
    def measure_chart(self) -> list[dict[str, Any]]:
        key = self.measure_key or (self.measures[0]["key"] if self.measures else "")
        return [{"label": m["date"], "value": float(m["value"])}
                for m in reversed(self.measures) if m["key"] == key]

    @rx.var
    def measure_selected(self) -> str:
        return self.measure_key or (self.measures[0]["key"] if self.measures else "")

    async def _ctx(self) -> tuple[str, str, str]:
        auth = await self.get_state(AuthState)
        return auth.token, auth.timezone or "UTC", auth.weight_unit or "kg"

    async def load(self):
        token, tz, unit = await self._ctx()
        if not token:
            return
        requested = self.router.url.query_parameters.get("tab", "")
        if requested:
            self.tab = {t.lower(): t for t in TABS}.get(str(requested).lower(), self.tab)
        today = local_dt(dt.datetime.now(dt.timezone.utc).isoformat(), tz).date()
        self.month = today.strftime("%Y-%m")
        self.error = ""
        try:
            await self._load_series(token, unit)
            await self._load_muscles(token)
            await self._load_month(token, tz)
            await self._load_tab(token, tz, unit)
        except ApiError as exc:
            self.error = exc.detail

    async def _load_tab(self, token: str, tz: str, unit: str) -> None:
        if self.tab == "Exercises" and not self.exercises:
            await self._load_exercises(token, unit, "")
        elif self.tab == "History" and not self.history:
            await self._load_history(token, tz, unit, "")
        elif self.tab == "Measurements":
            await self._load_measures(token)

    async def set_tab(self, tab: str):
        self.tab = tab
        token, tz, unit = await self._ctx()
        try:
            await self._load_tab(token, tz, unit)
        except ApiError as exc:
            self.error = exc.detail

    # --- Overview -------------------------------------------------------

    async def _load_series(self, token: str, unit: str) -> None:
        metric = self.metric.lower()
        data = await aapi.series(token, metric, self.range_)
        points = data.get("points") or []
        self.chart = [{"label": dt.date.fromisoformat(p["week_start"]).strftime("%d %b"),
                       "value": _metric_display(metric, p["value"], unit)} for p in points]
        last = points[-1]["value"] if points else 0
        self.headline_unit = {"duration": "", "volume": unit, "workouts": "", "points": "pts"}[metric]
        self.headline = (duration_label(last) if metric == "duration"
                         else f"{_metric_display(metric, last, unit):,.0f}")
        self.headline_label = "This week"

    async def set_range(self, value: str):
        self.range_ = value
        token, _, unit = await self._ctx()
        try:
            await self._load_series(token, unit)
        except ApiError as exc:
            self.error = exc.detail

    async def set_metric(self, value: str):
        self.metric = value
        token, _, unit = await self._ctx()
        try:
            await self._load_series(token, unit)
        except ApiError as exc:
            self.error = exc.detail

    async def _load_muscles(self, token: str) -> None:
        data = await aapi.muscles(token)
        muscles = data.get("muscles") or []
        self.muscle_paths = paths_for({m["code"]: m["intensity"] for m in muscles},
                                      {m["code"]: m["svg_path_ids"] for m in muscles})
        self.muscle_names = " · ".join(m["display_name"] for m in muscles[:6])

    async def _load_month(self, token: str, tz: str) -> None:
        data = await aapi.calendar(token, self.month)
        first = dt.date.fromisoformat(f"{self.month}-01")
        today = local_dt(dt.datetime.now(dt.timezone.utc).isoformat(), tz).date()
        trained = {dt.date.fromisoformat(d["date"]) for d in data.get("days") or []}
        self.month_title = first.strftime("%B %Y")
        self.month_weeks = month_grid(first, trained, today)
        n = sum(d["workouts"] for d in data.get("days") or [])
        self.month_count = f"{n} workout{'s' if n != 1 else ''}"

    async def shift_month(self, delta: int):
        first = dt.date.fromisoformat(f"{self.month}-01")
        target = (first + dt.timedelta(days=32)).replace(day=1) if delta > 0 else (
            (first - dt.timedelta(days=1)).replace(day=1))
        self.month = target.strftime("%Y-%m")
        token, tz, _ = await self._ctx()
        try:
            await self._load_month(token, tz)
        except ApiError as exc:
            self.error = exc.detail

    # --- Exercises ------------------------------------------------------

    async def _load_exercises(self, token: str, unit: str, cursor: str) -> None:
        page = await aapi.my_exercises(token, cursor)
        rows = []
        for e in page.get("items") or []:
            best = ""
            if e.get("best_weight_kg"):
                best = f"{fmt(to_unit(e['best_weight_kg'], unit))} {unit}"
                if e.get("best_weight_reps"):
                    best += f" × {e['best_weight_reps']}"
            rows.append({
                "id": str(e["exercise_id"]), "name": e["name"], "image": e.get("thumbnail_url") or "",
                "best": f"Best set {best}" if best else f"{e['sessions']} workouts",
                "e1rm": f"e1RM {fmt(to_unit(e['best_est_1rm'], unit))} {unit}" if e.get("best_est_1rm") else "",
            })
        self.exercises = (self.exercises + rows) if cursor else rows
        self.exercises_cursor = page.get("next_cursor") or ""

    async def more_exercises(self):
        token, _, unit = await self._ctx()
        await self._load_exercises(token, unit, self.exercises_cursor)

    # --- History --------------------------------------------------------

    async def _load_history(self, token: str, tz: str, unit: str, cursor: str) -> None:
        page = await aapi.history(token, cursor)
        rows = history_rows(page, tz, unit)
        for row in rows:
            row["month_label"] = dt.date.fromisoformat(f"{row['month']}-01").strftime("%B %Y")
        merged = (self.history + rows) if cursor else rows
        # The month header shows on a month's first row only.
        last = ""
        for row in merged:
            row["first_of_month"] = "1" if row["month"] != last else ""
            last = row["month"]
        self.history = merged
        self.history_cursor = page.get("next_cursor") or ""

    async def more_history(self):
        token, tz, unit = await self._ctx()
        await self._load_history(token, tz, unit, self.history_cursor)

    # --- Measurements ---------------------------------------------------

    async def _load_measures(self, token: str) -> None:
        tz = (await self.get_state(AuthState)).timezone or "UTC"
        rows = await wapi.list_measurements(token, limit=500)
        titles = {"weight": "Body weight", "body_fat": "Body fat"}
        self.measures = [
            {"id": str(m["id"]),
             "key": m["metric"] if m["metric"] != "custom" else f"custom:{m.get('label') or ''}",
             "title": titles.get(m["metric"], (m.get("label") or "").capitalize()),
             "value": fmt(m["value"]), "unit": "%" if m["unit"] == "percent" else m["unit"],
             "date": (local_dt(m.get("recorded_at"), tz) or dt.datetime.now()).strftime("%d %b")}
            for m in rows
        ]

    def pick_measure(self, key: str) -> None:
        self.measure_key = key

    def set_measure_kind(self, kind: str) -> None:
        self.measure_kind = kind

    def set_measure_value(self, value: str) -> None:
        self.measure_value = value

    def set_measure_label(self, value: str) -> None:
        self.measure_label = value

    async def add_measure(self):
        token, _, unit = await self._ctx()
        try:
            value = float(self.measure_value)
        except ValueError:
            self.error = "Enter a number."
            return
        payload: dict[str, Any] = {"metric": self.measure_kind, "value": value,
                                   "unit": {"weight": unit, "body_fat": "percent"}.get(self.measure_kind, "cm")}
        if self.measure_kind == "custom":
            if not self.measure_label.strip():
                self.error = "Name the measurement, e.g. Waist."
                return
            payload["label"] = self.measure_label.strip().lower()
        try:
            await wapi.create_measurement(token, payload)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.measure_value = ""
        self.error = ""
        self.measure_key = payload["metric"] if self.measure_kind != "custom" else f"custom:{payload['label']}"
        await self._load_measures(token)
