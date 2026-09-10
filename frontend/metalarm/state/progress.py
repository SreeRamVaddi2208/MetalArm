"""Progress: per-exercise charts, personal records, workout history, points,
and body measurements."""

from __future__ import annotations

import datetime as dt
from typing import Any

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.workout_models import (
    LB_PER_KG,
    BodyRow,
    ExerciseOption,
    HistoryRow,
    RecordRow,
    StreakView,
    short_date,
    to_unit,
)

HISTORY_PAGE = 10
_UNITS_FOR_METRIC = {"weight": ["kg", "lb"], "body_fat": ["percent"], "custom": ["cm", "in", "kg", "lb", "percent"]}


def _r1(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


class ProgressState(rx.State):
    loading: bool = False
    error: str = ""

    total_points: int = 0
    week_points: int = 0
    sessions_completed: int = 0
    streak: StreakView = StreakView()

    exercise_options: list[ExerciseOption] = []
    selected_id: str = ""
    chart_data: list[dict[str, Any]] = []

    records: list[RecordRow] = []

    history: list[HistoryRow] = []
    history_cursor: str = ""
    has_more: bool = False

    measurements: list[BodyRow] = []
    weight_chart: list[dict[str, Any]] = []
    m_metric: str = "weight"
    m_value: str = ""
    m_unit: str = "kg"
    m_label: str = ""

    @rx.var
    def has_chart(self) -> bool:
        return len(self.chart_data) > 0

    @rx.var
    def has_records(self) -> bool:
        return len(self.records) > 0

    @rx.var
    def has_history(self) -> bool:
        return len(self.history) > 0

    @rx.var
    def has_measurements(self) -> bool:
        return len(self.measurements) > 0

    @rx.var
    def has_weight_chart(self) -> bool:
        return len(self.weight_chart) > 1

    @rx.var
    def m_unit_options(self) -> list[str]:
        return _UNITS_FOR_METRIC.get(self.m_metric, ["kg"])

    @rx.var
    def is_custom_metric(self) -> bool:
        return self.m_metric == "custom"

    async def _ctx(self) -> tuple[str, str, str]:
        auth = await self.get_state(AuthState)
        return auth.token, auth.weight_unit or "kg", auth.timezone

    async def load(self):
        token, unit, tz = await self._ctx()
        if not token:
            return
        self.loading = True
        self.error = ""
        yield
        try:
            summary = await wapi.points(token)
            self.total_points = summary.get("total_points") or 0
            self.week_points = summary.get("this_week_points") or 0
            self.sessions_completed = summary.get("sessions_completed") or 0
            self.streak = StreakView.from_api(summary.get("streak") or {})

            raw_records = await wapi.records(token)
            self.records = [RecordRow.from_api(r, unit, tz) for r in raw_records]
            seen: dict[str, str] = {}
            for r in raw_records:
                seen.setdefault(r.get("exercise_id") or "", r.get("exercise_name") or "")
            self.exercise_options = [
                ExerciseOption(id=i, name=n)
                for i, n in sorted(seen.items(), key=lambda kv: kv[1].casefold())
            ]

            page = await wapi.list_sessions(token, limit=HISTORY_PAGE)
            self.history = [HistoryRow.from_api(h, unit, tz) for h in page]
            self._set_cursor(page)

            await self._load_measurements(token, unit, tz)
        except ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

        if self.exercise_options and self.selected_id not in {o.id for o in self.exercise_options}:
            self.selected_id = self.exercise_options[0].id
        if self.selected_id:
            yield ProgressState.select_exercise(self.selected_id)

    def _set_cursor(self, page: list[dict]) -> None:
        self.has_more = len(page) == HISTORY_PAGE
        self.history_cursor = page[-1].get("started_at") or "" if page else ""

    async def select_exercise(self, exercise_id: str):
        token, unit, tz = await self._ctx()
        self.selected_id = exercise_id
        try:
            points = await wapi.exercise_history(token, exercise_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.chart_data = [
            {
                "date": short_date(p.get("performed_at"), tz),
                "top": _r1(to_unit(p.get("top_weight_kg"), unit)) if p.get("top_weight_kg") else None,
                "e1rm": _r1(to_unit(p.get("best_est_1rm"), unit)) if p.get("best_est_1rm") else None,
                "volume": round(to_unit(p.get("volume_kg"), unit)),
            }
            for p in points
        ]

    async def more_history(self):
        token, unit, tz = await self._ctx()
        if not self.history_cursor:
            return
        try:
            page = await wapi.list_sessions(token, limit=HISTORY_PAGE, before=self.history_cursor)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.history = [*self.history, *(HistoryRow.from_api(h, unit, tz) for h in page)]
        self._set_cursor(page)

    # --- body measurements -------------------------------------------------

    async def _load_measurements(self, token: str, unit: str, tz: str) -> None:
        rows = await wapi.list_measurements(token)
        self.measurements = [BodyRow.from_api(m, tz) for m in rows]
        weights = [m for m in rows if m.get("metric") == "weight"]
        weights.sort(key=lambda m: m.get("recorded_at") or "")
        self.weight_chart = [
            {
                "date": short_date(m.get("recorded_at"), tz),
                "value": _r1(
                    float(m.get("value") or 0)
                    if m.get("unit") == unit
                    else (float(m.get("value") or 0) * LB_PER_KG if unit == "lb" else float(m.get("value") or 0) / LB_PER_KG)
                ),
            }
            for m in weights
        ]

    def set_m_metric(self, value: str) -> None:
        self.m_metric = value
        self.m_unit = _UNITS_FOR_METRIC.get(value, ["kg"])[0]

    def set_m_value(self, value: str) -> None:
        self.m_value = value

    def set_m_unit(self, value: str) -> None:
        self.m_unit = value

    def set_m_label(self, value: str) -> None:
        self.m_label = value

    async def add_measurement(self):
        token, unit, tz = await self._ctx()
        try:
            value = float(self.m_value)
        except ValueError:
            self.error = "Enter a number."
            return
        payload: dict[str, Any] = {
            "metric": self.m_metric,
            "value": value,
            "unit": self.m_unit,
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        if self.m_metric == "custom":
            if not self.m_label.strip():
                self.error = "Name the measurement, e.g. Waist."
                return
            payload["label"] = self.m_label.strip()
        try:
            await wapi.create_measurement(token, payload)
            await self._load_measurements(token, unit, tz)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.error = ""
        self.m_value = ""

    async def delete_measurement(self, measurement_id: str):
        token, unit, tz = await self._ctx()
        try:
            await wapi.delete_measurement(token, measurement_id)
            await self._load_measurements(token, unit, tz)
        except ApiError as exc:
            self.error = exc.detail
