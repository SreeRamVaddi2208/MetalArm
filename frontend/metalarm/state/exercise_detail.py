"""Exercise Detail (overhaul 7.3): what the movement is, and what you have
done with it - About, History, Charts, Records. All stats are the server's
(GET /exercises/{id}/stats)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import reflex as rx

from metalarm import analytics_api as aapi
from metalarm import api
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.ui.body_map import paths_for
from metalarm.workout_models import fmt, local_dt, session_title, to_unit

TABS = ["About", "History", "Charts", "Records"]
CHARTS = ["Best set", "Estimated 1RM", "Volume", "Max reps"]
RECORD_NAMES = {"max_weight": "Heaviest weight", "est_1rm": "Best estimated 1RM",
                "max_volume": "Most volume in a workout"}
TYPE_BADGE = {"warmup": "W", "drop": "D", "failure": "F"}
SECONDARY_FILL = 0.4


class ExerciseDetailState(rx.State):
    exercise_id: str = ""
    name: str = ""
    image: str = ""
    equipment: str = ""
    muscles_label: str = ""
    credit: str = ""
    muscle_paths: dict[str, float] = {}
    steps: list[str] = []
    tips: list[str] = []
    favorite: bool = False

    tab: str = "About"
    chart_metric: str = "Estimated 1RM"
    series: list[dict[str, Any]] = []
    history_rows: list[dict[str, str]] = []
    records: list[dict[str, str]] = []
    loaded: bool = False
    error: str = ""

    @rx.var
    def chart(self) -> list[dict[str, Any]]:
        key = {"Best set": "best", "Estimated 1RM": "e1rm", "Volume": "volume", "Max reps": "reps"}[self.chart_metric]
        rows = [{"label": p["label"], "value": p[key], "mark": None} for p in self.series if p[key] is not None]
        if rows:
            rows[-1]["mark"] = rows[-1]["value"]
        return rows

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.exercise_id = parts[-1] if len(parts) >= 2 else ""
        self.loaded = False
        self.error = ""
        self.tab = "About"
        unit, tz = auth.weight_unit or "kg", auth.timezone or "UTC"
        try:
            e = await wapi.get_exercise(auth.token, self.exercise_id)
            taxonomy = await api.taxonomy(auth.token)
            stats = await aapi.exercise_stats(auth.token, self.exercise_id)
            favs = await wapi.library(auth.token, filter="favorites", limit=100)
        except ApiError as exc:
            self.error = exc.detail
            return
        names = {m["code"]: m["display_name"] for m in taxonomy.get("muscle_groups", [])}
        svg = {m["code"]: m["svg_path_ids"] for m in taxonomy.get("muscle_groups", [])}
        equipment = {q["code"]: q["display_name"] for q in taxonomy.get("equipment", [])}
        primary, secondary = e.get("primary_muscle_groups") or [], e.get("secondary_muscle_groups") or []
        self.name = e.get("name") or ""
        self.image = e.get("illustration_url") or e.get("thumbnail_url") or ""
        self.equipment = equipment.get(e.get("equipment") or "", (e.get("equipment") or "").replace("_", " "))
        self.muscles_label = " · ".join(names.get(c, c) for c in primary) + (
            f"  (also {', '.join(names.get(c, c) for c in secondary)})" if secondary else "")
        self.credit = (f"Image: {e['media_author']}, {e['media_license']}"
                       if e.get("media_author") and e.get("media_license") else "")
        # Primary muscles at full strength, secondary at 40% (spec 7.3).
        self.muscle_paths = paths_for({**{c: SECONDARY_FILL for c in secondary}, **{c: 1.0 for c in primary}}, svg)
        self.steps = list(e.get("steps") or []) or ([e["instructions"]] if e.get("instructions") else [])
        self.tips = list(e.get("tips") or [])
        self.favorite = any(i.get("id") == self.exercise_id for i in favs.get("items") or [])

        self.series = [
            {"label": dt.date.fromisoformat(p["date"]).strftime("%d %b"),
             "best": round(to_unit(p["best_set_weight_kg"], unit), 1) if p.get("best_set_weight_kg") else None,
             "e1rm": round(to_unit(p["est_1rm"], unit), 1) if p.get("est_1rm") else None,
             "volume": round(to_unit(p["volume_kg"], unit)),
             "reps": p.get("max_reps")}
            for p in stats.get("series") or []
        ]
        rows: list[dict[str, str]] = []
        for s in stats.get("sessions") or []:
            moment = local_dt(s.get("started_at"), tz)
            rows.append({"kind": "head", "title": session_title(s.get("name"), s.get("started_at"), tz),
                         "sub": moment.strftime("%a %d %b %Y") if moment else "", "badge": "", "pr": ""})
            for x in s.get("sets") or []:
                weight = f"{fmt(to_unit(x['weight_kg'], unit))} {unit}" if x.get("weight_kg") else "Bodyweight"
                rows.append({"kind": "set", "badge": TYPE_BADGE.get(x["set_type"], str(x["set_number"])),
                             "title": f"{weight} × {x.get('reps') or 0}", "sub": "",
                             "pr": "1" if x.get("is_pr") else ""})
        self.history_rows = rows
        self.records = [
            {"name": RECORD_NAMES.get(r["record_type"], r["record_type"]),
             "value": (f"{fmt(to_unit(r['value'], unit))} {unit}"),
             "date": (local_dt(r["achieved_at"], tz) or dt.datetime.now()).strftime("%d %b %Y")}
            for r in stats.get("records") or []
        ]
        self.loaded = True

    def set_tab(self, tab: str) -> None:
        self.tab = tab

    def set_chart_metric(self, metric: str) -> None:
        self.chart_metric = metric

    async def toggle_favorite(self):
        auth = await self.get_state(AuthState)
        try:
            await wapi.favorite(auth.token, "exercise", self.exercise_id, not self.favorite)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.favorite = not self.favorite

    async def add_to_workout(self):
        """Into the live workout, or a new blank one; then to it."""
        auth = await self.get_state(AuthState)
        try:
            session = (await wapi.active_session(auth.token)).get("session")
            if not session:
                session = await wapi.start_session(auth.token)
            await wapi.add_session_exercise(auth.token, str(session["id"]), self.exercise_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        return rx.redirect("/train")
