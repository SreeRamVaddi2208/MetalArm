"""The Monthly Summary (overhaul 7.9): a month as story slides - tap to
advance - ending in a card to share. Every figure is the server's
(GET /analytics/monthly-summary)."""

from __future__ import annotations

import datetime as dt

import reflex as rx

from metalarm import analytics_api as aapi
from metalarm.api import ApiError
from metalarm.ranks import rank_title
from metalarm.share_card import share_card_script
from metalarm.state.auth import AuthState
from metalarm.state.workout_home import duration_label
from metalarm.ui.body_map import paths_for
from metalarm.workout_models import fmt, thousands, to_unit

SLIDES = 7
RECORD_NAMES = {"max_weight": "Heaviest", "est_1rm": "Best e1RM", "max_volume": "Most volume",
                "max_reps_at_weight": "Most reps"}


class MonthlyState(rx.State):
    month_key: str = ""
    title: str = ""
    slide: int = 0
    loaded: bool = False
    error: str = ""

    workouts: int = 0
    time_label: str = ""
    active_days: int = 0
    best_week: int = 0
    volume_label: str = ""
    comparison: str = ""
    sets: int = 0
    top_muscle: str = ""
    muscle_paths: dict[str, float] = {}
    muscle_list: str = ""
    record_count: int = 0
    records: list[dict[str, str]] = []
    points: int = 0
    rank_line: str = ""
    rank_ups: list[str] = []
    quests: int = 0
    duels_played: int = 0
    duels_won: int = 0

    # Home / You: last month's card.
    hero_month: str = ""
    hero_title: str = ""
    hero_show: bool = False
    hero_workouts: int = 0

    @rx.var
    def bars(self) -> list[str]:
        """Each story bar: 'done', 'now' or ''."""
        return ["done" if i < self.slide else ("now" if i == self.slide else "") for i in range(SLIDES)]

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.month_key = parts[-1] if len(parts) >= 2 else ""
        unit = auth.weight_unit or "kg"
        self.slide, self.loaded, self.error = 0, False, ""
        try:
            s = await aapi.monthly_summary(auth.token, self.month_key)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.month_key = s["month"]
        self.title = dt.date.fromisoformat(f"{s['month']}-01").strftime("%B %Y")
        self.workouts, self.active_days, self.best_week = s["workouts"], s["active_days"], s["best_week_workouts"]
        self.time_label = duration_label(s["duration_seconds"])
        self.volume_label = f"{thousands(to_unit(s['volume_kg'], unit))} {unit}"
        self.comparison, self.sets = s["volume_comparison"], s["working_sets"]
        muscles = s.get("muscles") or []
        self.top_muscle = muscles[0]["display_name"] if muscles else ""
        self.muscle_paths = paths_for({m["code"]: m["intensity"] for m in muscles},
                                      {m["code"]: m["svg_path_ids"] for m in muscles})
        self.muscle_list = " · ".join(m["display_name"] for m in muscles[1:5])
        self.record_count = s["record_count"]
        self.records = [
            {"name": r["exercise_name"], "kind": RECORD_NAMES.get(r["record_type"], r["record_type"]),
             "value": (str(int(r["value"])) + " reps" if r["record_type"] == "max_reps_at_weight"
                       else f"{fmt(to_unit(r['value'], unit))} {unit}")}
            for r in reversed(s.get("records") or [])
        ]
        self.points = s["points"]
        self.rank_line = f"{rank_title(s['rank'])} · Level {s['level']}"
        self.rank_ups = list(s.get("rank_ups") or [])
        self.quests, self.duels_played, self.duels_won = s["quests_completed"], s["duels_played"], s["duels_won"]
        self.loaded = True

    async def load_hero(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        try:
            h = await aapi.monthly_hero(auth.token)
        except ApiError:
            return
        self.hero_month, self.hero_show, self.hero_workouts = h["month"], h["show"], h["workouts"]
        self.hero_title = dt.date.fromisoformat(f"{h['month']}-01").strftime("%B")

    def next_slide(self) -> None:
        self.slide = min(SLIDES - 1, self.slide + 1)

    def prev_slide(self) -> None:
        self.slide = max(0, self.slide - 1)

    def share(self):
        card = {
            "kind": "workout",
            "eyebrow": "MY MONTH",
            "headline": self.title.upper(),
            "caption": self.comparison or f"{self.workouts} workouts",
            "stats": [
                {"value": str(self.workouts), "label": "Workouts"},
                {"value": self.volume_label, "label": "Volume"},
                {"value": str(self.record_count), "label": "Records"},
            ],
            "footer": "Level up every workout",
        }
        return rx.call_script(share_card_script(card))
