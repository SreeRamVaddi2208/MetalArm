"""Home: your rank and level, this week in three numbers, the last workout,
the friends leaderboard's top three and you, then friends' workouts. Every
number is the server's."""

from __future__ import annotations

import dataclasses

import reflex as rx

from metalarm import analytics_api as aapi
from metalarm import social_api as sapi
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.ranks import rank_title
from metalarm.state.auth import AuthState
from metalarm.state.workout_home import duration_label, history_rows
from metalarm.workout_models import FeedCard, initials_of, thousands, to_unit

VIEWS = ["Following", "Leaderboard", "Duels"]
PREVIEW = 3


def _delta(value: float, fmt) -> tuple[str, str]:
    """('+2', 'up') for the DeltaPill; ('0', 'flat') when unchanged."""
    if value == 0:
        return "0", "flat"
    return ("+" if value > 0 else "−") + fmt(abs(value)), "up" if value > 0 else "down"


class HomeState(rx.State):
    view: str = "Following"
    show_views: bool = False
    error: str = ""

    # Game strip
    rank: str = "E"
    rank_name: str = ""
    level: int = 1
    xp_label: str = ""
    xp_scale: str = "0"
    points_week: str = ""
    points_week_value: str = "0"
    workouts_week: str = "0"
    live: bool = False
    last: dict[str, str] = {}
    loaded: bool = False
    quests_label: str = ""
    streak_weeks: int = 0
    unread: int = 0

    # Weekly snapshot
    tiles: list[dict[str, str]] = []

    # Feed
    feed: list[FeedCard] = []
    feed_cursor: str = ""
    feed_loaded: bool = False

    # Leaderboard
    period: str = "week"
    board: list[dict[str, str]] = []
    me_row: dict[str, str] = {}
    me_in_view: bool = True
    board_loaded: bool = False

    @rx.var
    def preview(self) -> list[dict[str, str]]:
        return self.board[:PREVIEW]

    @rx.var
    def me_in_preview(self) -> bool:
        return any(r["me"] for r in self.board[:PREVIEW])

    async def _ctx(self) -> tuple[str, str]:
        auth = await self.get_state(AuthState)
        return auth.token, auth.weight_unit or "kg"

    async def load(self):
        token, unit = await self._ctx()
        if not token:
            return
        self.error = ""
        try:
            await self._load_game(token)
            await self._load_snapshot(token, unit)
            await self._load_feed(token, unit, "")
            await self._load_board(token)
            auth = await self.get_state(AuthState)
            recent = history_rows(await aapi.history(token, limit=1), auth.timezone or "UTC", unit)
            self.last = recent[0] if recent else {}
            self.live = bool((await wapi.active_session(token)).get("session"))
        except ApiError as exc:
            self.error = exc.detail
        self.loaded = True

    async def _load_game(self, token: str) -> None:
        g = await sapi.game(token)
        self.rank, self.level = g["rank"], g["level"]
        self.rank_name = rank_title(g["rank"])
        if g.get("next_rank") and g.get("xp_next_rank"):
            self.xp_label = f"{g['xp']:,} / {g['xp_next_rank']:,} XP to {rank_title(g['next_rank'])}"
            self.xp_scale = f"{min(1.0, g['xp'] / g['xp_next_rank']):.3f}"
        else:
            self.xp_label, self.xp_scale = f"{g['xp']:,} XP · top rank", "1"
        self.points_week = f"{g['points_this_week']} pts this week"
        self.points_week_value = f"{g['points_this_week']:,}"
        self.quests_label = f"{g['quests_done']} of {g['quests_total']} quests"
        self.streak_weeks = g["streak_weeks"]
        self.unread = g["unread_notifications"]

    async def _load_snapshot(self, token: str, unit: str) -> None:
        s = await aapi.snapshot(token)
        self.workouts_week = str(s["workouts"])
        w, wd = _delta(s["workouts_delta"], lambda v: str(int(v)))
        d, dd = _delta(s["duration_delta"], duration_label)
        v, vd = _delta(s["volume_delta"], lambda x: thousands(to_unit(x, unit)))
        self.tiles = [
            {"label": "Workouts", "value": str(s["workouts"]), "unit": "", "delta": w, "dir": wd},
            {"label": "Duration", "value": duration_label(s["duration_seconds"]), "unit": "", "delta": d, "dir": dd},
            {"label": "Volume", "value": thousands(to_unit(s["volume_kg"], unit)), "unit": unit, "delta": v, "dir": vd},
        ]

    async def _load_feed(self, token: str, unit: str, cursor: str) -> None:
        page = await sapi.feed(token, cursor)
        cards = [FeedCard.from_api(i, unit) for i in page.get("items") or []]
        self.feed = (self.feed + cards) if cursor else cards
        self.feed_cursor = page.get("next_cursor") or ""
        self.feed_loaded = True

    async def more_feed(self):
        token, unit = await self._ctx()
        try:
            await self._load_feed(token, unit, self.feed_cursor)
        except ApiError as exc:
            self.error = exc.detail

    async def toggle_spot(self, session_id: str):
        token, _ = await self._ctx()
        card = next((c for c in self.feed if c.session_id == session_id), None)
        if card is None:
            return
        try:
            r = await sapi.spot(token, session_id, not card.spotted_by_me)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.feed = [dataclasses.replace(c, spotted=r["spotted"], spotted_by_me=r["spotted_by_me"])
                     if c.session_id == session_id else c for c in self.feed]

    # --- views ------------------------------------------------------------

    def toggle_views(self) -> None:
        self.show_views = not self.show_views

    async def set_view(self, view: str):
        self.view = view
        self.show_views = False
        if view == "Leaderboard":
            token, _ = await self._ctx()
            try:
                await self._load_board(token)
            except ApiError as exc:
                self.error = exc.detail

    async def _load_board(self, token: str) -> None:
        data = await sapi.leaderboard(token, self.period)

        def row(r: dict) -> dict[str, str]:
            u = r["user"]
            return {"position": str(r["position"]), "id": str(u["id"]), "name": u["display_name"],
                    "initials": initials_of(u["display_name"]), "rank": u["rank"],
                    "points": f"{r['points']:,}", "me": "1" if r["is_me"] else ""}

        self.board = [row(r) for r in data.get("rows") or []]
        self.me_row = row(data["me"])
        self.me_in_view = any(r["me"] for r in self.board)
        self.board_loaded = True

    async def load_board(self):
        """/leaderboard: the board alone."""
        token, _ = await self._ctx()
        if not token:
            return
        try:
            await self._load_board(token)
        except ApiError as exc:
            self.error = exc.detail

    async def set_period(self, label: str):
        self.period = "week" if label == "This week" else "all"
        token, _ = await self._ctx()
        try:
            await self._load_board(token)
        except ApiError as exc:
            self.error = exc.detail
