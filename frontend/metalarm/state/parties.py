"""Party state.

Periodic refresh, not WebSockets (settled with the user): the board is
re-fetched on load and after any action, and a member can refresh manually.
For a habit app where updates are minutes apart, that is the right trade -
no connection lifecycle, no reconnect handling, no auth-over-socket.
"""

from __future__ import annotations

import dataclasses

import reflex as rx

from metalarm import api
from metalarm import workout_api as wapi
from metalarm.models import LeaderboardRow, Party, PartyQuest, RaidView, WorkoutBoardRow
from metalarm.state.auth import AuthState


class PartyState(rx.State):
    parties: list[Party] = []
    selected: Party = Party()
    quests: list[PartyQuest] = []
    board: list[LeaderboardRow] = []
    # The gym module's friend competition: members by workout points.
    workout_board: list[WorkoutBoardRow] = []
    workout_period: str = "week"
    # This week's party boss (core/raids.py on the backend).
    raid: RaidView = RaidView()

    loading: bool = False
    error: str = ""
    notice: str = ""

    show_create: bool = False
    show_join: bool = False
    new_name: str = ""
    join_code: str = ""

    show_quest_form: bool = False
    quest_title: str = ""
    quest_xp: str = "25"
    quest_recurrence: str = "daily"

    @rx.var
    def has_parties(self) -> bool:
        return len(self.parties) > 0

    @rx.var
    def has_selection(self) -> bool:
        return bool(self.selected.id)

    @rx.var
    def has_quests(self) -> bool:
        return len(self.quests) > 0

    def set_new_name(self, v: str) -> None:
        self.new_name = v

    def set_join_code(self, v: str) -> None:
        self.join_code = v

    def set_quest_title(self, v: str) -> None:
        self.quest_title = v

    def set_quest_xp(self, v: str) -> None:
        self.quest_xp = v

    def set_quest_recurrence(self, v: str) -> None:
        self.quest_recurrence = v

    def toggle_create(self) -> None:
        self.show_create = not self.show_create
        self.show_join = False
        self.error = ""

    def toggle_join(self) -> None:
        self.show_join = not self.show_join
        self.show_create = False
        self.error = ""

    def toggle_quest_form(self) -> None:
        self.show_quest_form = not self.show_quest_form
        self.error = ""

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        self.loading = True
        self.error = ""
        yield
        try:
            data = await api.list_parties(auth.token)
            self.parties = [Party.from_api(p) for p in data]
            # Keep the current selection if it still exists, else pick the
            # first - so a refresh does not silently bounce the user elsewhere.
            keep = self.selected.id
            match = next((p for p in self.parties if p.id == keep), None)
            self.selected = match or (self.parties[0] if self.parties else Party())
        except api.ApiError as exc:
            self.error = exc.detail
            self.loading = False
            return
        self.loading = False
        if self.selected.id:
            await self._load_detail(auth.token)

    async def _load_detail(self, token: str) -> None:
        try:
            raw_quests = await api.list_party_quests(token, self.selected.id)
            self.quests = [
                PartyQuest.from_api(q, self.selected.member_count) for q in raw_quests
            ]
            board = await api.party_leaderboard(token, self.selected.id)
            self.board = [LeaderboardRow.from_api(e) for e in board.get("entries", [])]
            await self._load_workout_board(token)
            await self._load_raid(token)
            # REPLACE rather than mutate a field in place. Reflex marks a state
            # var dirty on assignment to the var itself, so an in-place nested
            # write can leave the rendered value stale - and `selected` is
            # usually the same object as an entry in `self.parties`, so
            # mutating it would quietly edit the list too.
            self.selected = dataclasses.replace(
                self.selected, total_party_xp=board.get("total_party_xp") or 0
            )
        except api.ApiError as exc:
            self.error = exc.detail

    async def _load_raid(self, token: str) -> None:
        """A raid that fails to load hides the panel; the boards still show."""
        try:
            self.raid = RaidView.from_api(await api.party_raid(token, self.selected.id))
        except api.ApiError:
            self.raid = RaidView()

    async def _load_workout_board(self, token: str) -> None:
        data = await wapi.party_workout_leaderboard(token, self.selected.id, self.workout_period)
        self.workout_board = [WorkoutBoardRow.from_api(e) for e in data.get("entries", [])]

    async def set_workout_period(self, period: str):
        if period == self.workout_period or not self.selected.id:
            return
        self.workout_period = period
        auth = await self.get_state(AuthState)
        try:
            await self._load_workout_board(auth.token)
        except api.ApiError as exc:
            self.error = exc.detail

    async def select(self, party_id: str):
        auth = await self.get_state(AuthState)
        match = next((p for p in self.parties if p.id == party_id), None)
        if match is None:
            return
        self.selected = match
        self.error = ""
        self.notice = ""
        await self._load_detail(auth.token)

    async def create(self):
        auth = await self.get_state(AuthState)
        if not self.new_name.strip():
            self.error = "A party needs a name."
            return
        try:
            created = await api.create_party(auth.token, self.new_name.strip())
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.new_name = ""
        self.show_create = False
        self.selected = Party.from_api(created)
        return PartyState.load

    async def join(self):
        auth = await self.get_state(AuthState)
        if not self.join_code.strip():
            self.error = "Enter an invite code."
            return
        try:
            joined = await api.join_party(auth.token, self.join_code.strip())
        except api.ApiError as exc:
            # 404 (bad/expired code) and 409 (party full) are both normal
            # answers here; the API writes them for display.
            self.error = exc.detail
            return
        self.join_code = ""
        self.show_join = False
        self.selected = Party.from_api(joined)
        self.notice = f"Joined {self.selected.name}."
        return PartyState.load

    async def add_quest(self):
        auth = await self.get_state(AuthState)
        if not self.quest_title.strip():
            self.error = "A quest needs a title."
            return
        try:
            xp = int(self.quest_xp or 0)
        except ValueError:
            self.error = "XP must be a whole number."
            return
        try:
            await api.create_party_quest(
                auth.token,
                self.selected.id,
                {
                    "title": self.quest_title.strip(),
                    "xp_reward": xp,
                    "recurrence": self.quest_recurrence,
                },
            )
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.quest_title = ""
        self.show_quest_form = False
        return PartyState.load

    async def complete(self, quest_id: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        self.notice = ""
        try:
            result = await api.complete_party_quest(
                auth.token, self.selected.id, quest_id
            )
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.notice = f"+{result['xp_awarded']} XP to the party."
        yield PartyState.load
        yield AuthState.refresh_me

    async def remove_quest(self, quest_id: str):
        auth = await self.get_state(AuthState)
        try:
            await api.delete_party_quest(auth.token, self.selected.id, quest_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        return PartyState.load

    async def rotate_invite(self):
        """Owner-only. The only way to revoke a leaked invite link."""
        auth = await self.get_state(AuthState)
        try:
            updated = await api.rotate_invite(auth.token, self.selected.id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.selected = Party.from_api(updated)
        self.notice = "New invite code issued. The old one no longer works."
        return PartyState.load

    async def leave(self):
        auth = await self.get_state(AuthState)
        try:
            await api.leave_party(auth.token, self.selected.id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.selected = Party()
        self.quests = []
        self.board = []
        return PartyState.load

    async def dissolve(self):
        auth = await self.get_state(AuthState)
        try:
            await api.dissolve_party(auth.token, self.selected.id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        self.selected = Party()
        self.quests = []
        self.board = []
        return PartyState.load
