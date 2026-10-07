"""The Workout tab before a session starts (overhaul 7.4): this week at a
glance, what to do next, and how you stand - recovery, streak, quests, rank.

Every figure is the server's. Dates are the user's local dates; the API's
instants are converted only to decide which day a workout belongs to.
"""

from __future__ import annotations

import datetime as dt

import reflex as rx

from metalarm import analytics_api as aapi
from metalarm import api
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.ui.body_map import paths_for
from metalarm.workout_models import local_dt, session_title, thousands, to_unit

LETTERS = "MTWTFSS"


def duration_label(seconds: int | float | None) -> str:
    """3720 -> '1h 2m', 2700 -> '45m'."""
    minutes = int(seconds or 0) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def last_done_label(days: int | None) -> str:
    if days is None:
        return "Not done yet"
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


def history_rows(page: dict, tz: str, unit: str) -> list[dict[str, str]]:
    """The /history page as display rows, each with its local date."""
    rows = []
    for month in page.get("months") or []:
        for s in month.get("sessions") or []:
            moment = local_dt(s.get("started_at"), tz)
            rows.append({
                "id": str(s["id"]),
                "title": session_title(s.get("name"), s.get("started_at"), tz),
                "date": moment.date().isoformat() if moment else "",
                "date_label": moment.strftime("%a %d %b") if moment else "",
                "month": month.get("month") or "",
                "duration": duration_label(s.get("duration_seconds")),
                "volume": f"{thousands(to_unit(s.get('volume_kg'), unit))} {unit}",
                "sets": str(s.get("working_sets") or 0),
                "prs": str(s.get("pr_count") or 0),
                "points": f"+{s.get('points') or 0}",
            })
    return rows


class WorkoutHomeState(rx.State):
    title: str = ""
    week_days: list[dict[str, str]] = []
    selected_day: str = ""
    today: str = ""
    recent: list[dict[str, str]] = []
    suggested: list[dict[str, str]] = []

    recovery_overall: int = 100
    recovery_loaded: bool = False
    # Body map fill for the recovery sheet: how FATIGUED each region is, 0-1.
    recovery_paths: dict[str, float] = {}
    recovery_rows: list[dict[str, str]] = []
    recovery_note: str = ""
    show_recovery: bool = False

    quests_done: int = 0
    quests_total: int = 0
    error: str = ""

    @rx.var
    def day_sessions(self) -> list[dict[str, str]]:
        return [r for r in self.recent if r["date"] == self.selected_day]

    @rx.var
    def selected_is_today(self) -> bool:
        return self.selected_day == self.today

    @rx.var
    def selected_label(self) -> str:
        if not self.selected_day or self.selected_day == self.today:
            return "Today"
        return dt.date.fromisoformat(self.selected_day).strftime("%A %d %B")

    @rx.var
    def quests_label(self) -> str:
        return f"{self.quests_done} of {self.quests_total}" if self.quests_total else "None yet"

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        tz, unit = auth.timezone or "UTC", auth.weight_unit or "kg"
        now = dt.datetime.now(dt.timezone.utc)
        today = local_dt(now.isoformat(), tz).date()
        monday = today - dt.timedelta(days=today.weekday())
        self.today = today.isoformat()
        self.selected_day = self.today
        self.title = today.strftime("%A, %d %b")
        self.error = ""
        try:
            months = {monday.strftime("%Y-%m"), (monday + dt.timedelta(days=6)).strftime("%Y-%m")}
            trained: set[str] = set()
            for month in months:
                cal = await aapi.calendar(auth.token, month)
                trained |= {d["date"] for d in cal.get("days") or []}
            self.week_days = [
                {"letter": LETTERS[i], "number": str((monday + dt.timedelta(days=i)).day),
                 "iso": (monday + dt.timedelta(days=i)).isoformat(),
                 "today": "1" if monday + dt.timedelta(days=i) == today else "",
                 "trained": "1" if (monday + dt.timedelta(days=i)).isoformat() in trained else ""}
                for i in range(7)
            ]
            self.recent = history_rows(await aapi.history(auth.token, limit=30), tz, unit)
            self.suggested = [
                {"id": str(s["routine_id"]), "name": s["name"], "last": last_done_label(s.get("days_since"))}
                for s in await wapi.suggested(auth.token)
            ]
            rec = await aapi.recovery(auth.token)
            self.recovery_overall = rec.get("overall", 100)
            self.recovery_note = rec.get("note") or ""
            muscles = rec.get("muscles") or []
            self.recovery_paths = paths_for(
                {m["code"]: round(1 - m["percent"] / 100, 3) for m in muscles},
                {m["code"]: m["svg_path_ids"] for m in muscles})
            self.recovery_rows = [{"name": m["display_name"], "percent": f"{m['percent']}%"}
                                  for m in muscles if m["percent"] < 100]
            self.recovery_loaded = True
            board = await api.quest_board(auth.token)
            quests = (board.get("daily") or []) + (board.get("weekly") or [])
            self.quests_total = len(quests)
            self.quests_done = sum(1 for q in quests if q.get("status") == "completed")
        except ApiError as exc:
            self.error = exc.detail

    def select_day(self, iso: str) -> None:
        self.selected_day = iso

    def open_recovery(self) -> None:
        self.show_recovery = True

    def close_recovery(self) -> None:
        self.show_recovery = False
