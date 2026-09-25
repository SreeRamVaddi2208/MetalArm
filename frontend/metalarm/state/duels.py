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

import reflex as rx

from metalarm import api
from metalarm.models import ActivityEntry, Duel, LeaderboardRow
from metalarm.state.auth import AuthState


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

    # A win that has just been judged: the overlay reads these, and they are
    # cleared when it is dismissed.
    show_win: bool = False
    won_against: str = ""
    won_points: int = 0

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

    def set_challenge_opponent(self, value: str) -> None:
        self.challenge_opponent = value

    def toggle_challenge(self) -> None:
        self.show_challenge = not self.show_challenge
        self.error = ""

    def dismiss_win(self) -> None:
        self.show_win = False
        self.won_against = ""
        self.won_points = 0

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

        # A duel the server judged during THIS fetch carries its points; that
        # is the moment to celebrate, and it happens at most once because the
        # award is written once.
        won = next((d for d in self.completed if d.i_won and d.points_awarded), None)
        if won is not None:
            self.won_against = won.their_name
            self.won_points = won.points_awarded
            self.show_win = True
        yield AuthState.refresh_me

    async def _load_opponents(self, token: str, me: str) -> None:
        """Party members, deduplicated across parties and minus yourself."""
        seen: dict[str, LeaderboardRow] = {}
        for party in await api.list_parties(token):
            board = await api.party_leaderboard(token, party["id"])
            for entry in board.get("entries", []):
                row = LeaderboardRow.from_api(entry)
                if row.user_id and row.user_id != me:
                    seen[row.user_id] = row
        self.opponents = list(seen.values())

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
