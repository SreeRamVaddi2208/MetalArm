"""Duels and the activity feed.

Read models, both of them: the server decides who is ahead and what happened,
and this state only fetches and formats. Nothing here recomputes a score from
raw data the frontend cannot see all of - that is how two screens start
disagreeing about who is winning.

One thing to know about `load()`: fetching duels is what JUDGES the ones whose
window has closed, so the response can carry a win that has just been decided.
That is why a completed duel the user won raises the celebration here rather
than the client diffing two fetches.
"""

from __future__ import annotations

import datetime as dt

import reflex as rx

from metalarm import api
from metalarm.models import ActivityEntry, Duel, DuelMode, LeaderboardRow, parse_dt
from metalarm.state.auth import AuthState

# A settled duel older than this is history, not news: its result screen is
# not shown to someone opening the app for the first time in weeks.
RESULT_FRESH_FOR = dt.timedelta(days=3)


class DuelState(rx.State):
    active: list[Duel] = []
    pending: list[Duel] = []
    completed: list[Duel] = []
    feed: list[ActivityEntry] = []
    # Who can be challenged: everyone in your parties, since a challenge to a
    # stranger is refused by the server anyway.
    opponents: list[LeaderboardRow] = []

    loading: bool = False
    error: str = ""

    # The challenge form.
    show_challenge: bool = False
    challenge_metric: str = "volume"
    challenge_days: str = "7"
    challenge_opponent: str = ""

    # The mode picker for a challenge to one party member: every mode with
    # the server's verdict on whether it is open to the two of you.
    show_modes: bool = False
    modes: list[DuelMode] = []
    picking_id: str = ""
    picking_name: str = ""

    # The duel whose breakdown is open.
    open_duel: str = ""

    # A settled duel's result, shown once per device: win, draw or loss. The
    # overlay reads these; they are cleared when it is dismissed.
    show_win: bool = False
    result_kind: str = ""
    won_against: str = ""
    won_points: int = 0
    result_duel_id: str = ""
    result_metric: str = ""
    result_their_id: str = ""
    # Settled duels whose result has been seen here, comma-separated. Per
    # device on purpose: a result is a moment, and each screen gets it once.
    seen_results: str = rx.LocalStorage("", name="ma_duel_results_seen")

    @rx.var
    def has_duels(self) -> bool:
        return bool(self.active or self.pending or self.completed)

    @rx.var
    def can_challenge(self) -> bool:
        """A challenge needs either a name to send it to, or the rival."""
        return self.challenge_opponent != "" or not self.show_challenge

    def set_challenge_metric(self, value: str) -> None:
        self.challenge_metric = value

    def set_challenge_days(self, value: str) -> None:
        self.challenge_days = value

    def bump_days(self, delta: int) -> None:
        try:
            days = int(self.challenge_days)
        except ValueError:
            days = 7
        self.challenge_days = str(max(1, min(28, days + delta)))

    def set_challenge_opponent(self, value: str) -> None:
        self.challenge_opponent = value

    def toggle_challenge(self) -> None:
        self.show_challenge = not self.show_challenge
        self.error = ""

    def dismiss_win(self) -> None:
        if self.result_duel_id:
            seen = [i for i in self.seen_results.split(",") if i][-50:]
            self.seen_results = ",".join([*seen, self.result_duel_id])
        self.show_win = False
        self.won_against = ""
        self.won_points = 0

    def toggle_detail(self, duel_id: str) -> None:
        self.open_duel = "" if self.open_duel == duel_id else duel_id

    def close_modes(self) -> None:
        self.show_modes = False
        self.modes = []

    async def open_modes(self, user_id: str, name: str):
        """Challenge flow: pick a person, then a mode. Modes the two of you
        cannot use yet come back disabled, with the server's reason."""
        auth = await self.get_state(AuthState)
        self.error = ""
        self.picking_id, self.picking_name = user_id, name
        try:
            data = await api.duel_modes(auth.token, user_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.modes = [DuelMode.from_api(m) for m in data.get("modes") or []]
        self.show_modes = True

    async def choose_mode(self, metric: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        try:
            await api.create_duel(
                auth.token, metric=metric, days=self._days(), opponent_id=self.picking_id
            )
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.show_modes = False
        self.show_challenge = False
        yield DuelState.load

    async def rematch(self):
        """Same mode, same person, straight from the result screen."""
        auth = await self.get_state(AuthState)
        metric, their_id = self.result_metric, self.result_their_id
        self.dismiss_win()
        if not their_id:
            return
        try:
            await api.create_duel(auth.token, metric=metric, days=7, opponent_id=their_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        yield DuelState.load

    async def cancel(self, duel_id: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        try:
            await api.cancel_duel(auth.token, duel_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        yield DuelState.load

    async def load_summary(self):
        """Just the running duels, for the dashboard's head-to-head bars."""
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        try:
            data = await api.list_duels(auth.token)
        except api.ApiError:
            return
        self.active = [Duel.from_api(d, auth.user_id) for d in data.get("active", [])]

    def _days(self) -> int:
        try:
            return max(1, min(28, int(self.challenge_days)))
        except ValueError:
            return 7

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        self.loading = True
        self.error = ""
        yield
        try:
            data = await api.list_duels(auth.token)
            me = auth.user_id
            self.active = [Duel.from_api(d, me) for d in data.get("active", [])]
            self.pending = [Duel.from_api(d, me) for d in data.get("pending", [])]
            self.completed = [Duel.from_api(d, me) for d in data.get("completed", [])]
            feed = await api.activity_feed(auth.token)
            self.feed = [ActivityEntry.from_api(e) for e in feed.get("entries", [])]
            await self._load_opponents(auth.token, me)
        except api.ApiError as exc:
            self.error = exc.detail
            self.loading = False
            return
        self.loading = False

        # The first recently settled duel this device has not shown yet - won,
        # drawn or lost. Both sides get their moment, not just whoever's read
        # happened to judge it.
        seen = set(self.seen_results.split(","))
        now = dt.datetime.now(dt.timezone.utc)
        fresh = next(
            (
                d for d in self.completed
                if d.id not in seen
                and (when := parse_dt(d.resolved_at)) is not None
                and now - when < RESULT_FRESH_FOR
                and not d.opponent.is_rival
            ),
            None,
        )
        won = next((d for d in self.completed if d.i_won and d.points_awarded), None)
        pick = fresh or (won if won is not None and won.id not in seen else None)
        if pick is not None:
            self.result_kind = "win" if pick.i_won else ("draw" if pick.is_draw else "loss")
            self.won_against = pick.their_name
            self.won_points = pick.reward_points or pick.points_awarded
            self.result_duel_id = pick.id
            self.result_metric = pick.metric
            self.result_their_id = pick.their_id
            self.show_win = True
        yield AuthState.refresh_me

    async def _load_opponents(self, token: str, me: str) -> None:
        """Friends (mutual follows) and party members - the server decides."""
        from metalarm import social_api

        self.opponents = [
            LeaderboardRow(user_id=str(u["id"]), display_name=u["display_name"], level=u["level"], rank=u["rank"])
            for u in await social_api.duel_opponents(token)
        ]

    async def challenge_rival(self):
        auth = await self.get_state(AuthState)
        self.error = ""
        try:
            await api.create_duel(
                auth.token, metric=self.challenge_metric, days=self._days(), against_rival=True
            )
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.show_challenge = False
        yield DuelState.load

    async def challenge_member(self, user_id: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        if not user_id:
            self.error = "Pick someone to challenge."
            return
        try:
            await api.create_duel(
                auth.token, metric=self.challenge_metric, days=self._days(), opponent_id=user_id
            )
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.show_challenge = False
        self.challenge_opponent = ""
        yield DuelState.load

    async def accept(self, duel_id: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        try:
            await api.accept_duel(auth.token, duel_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        yield DuelState.load

    async def decline(self, duel_id: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        try:
            await api.decline_duel(auth.token, duel_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        yield DuelState.load
