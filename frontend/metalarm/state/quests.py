"""Quest board state."""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm.models import Quest
from metalarm.state.auth import AuthState
from metalarm import ranks


class QuestState(rx.State):
    quests: list[Quest] = []
    loading: bool = False
    error: str = ""

    # Create form
    show_form: bool = False
    new_title: str = ""
    new_description: str = ""
    new_xp: str = "50"
    new_points: str = "5"
    new_recurrence: str = "daily"

    # Set after a completion that crossed a level or rank boundary. The
    # backend reports both explicitly, so the celebration never has to be
    # inferred by diffing two responses.
    level_up_message: str = ""
    show_level_up: bool = False
    # A rank-up is the bigger of the two beats and gets a different treatment,
    # so the component needs to tell them apart.
    level_up_is_rank: bool = False
    level_up_badge: str = ""
    # "Intermediate → Advanced" on a rank-up; empty on a level-up.
    level_up_ladder: str = ""

    @rx.var
    def has_quests(self) -> bool:
        return len(self.quests) > 0

    def set_new_title(self, v: str) -> None:
        self.new_title = v

    def set_new_description(self, v: str) -> None:
        self.new_description = v

    def set_new_xp(self, v: str) -> None:
        self.new_xp = v

    def set_new_points(self, v: str) -> None:
        self.new_points = v

    def set_new_recurrence(self, v: str) -> None:
        self.new_recurrence = v

    def toggle_form(self) -> None:
        self.show_form = not self.show_form
        self.error = ""

    def dismiss_level_up(self) -> None:
        self.show_level_up = False

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        self.loading = True
        self.error = ""
        yield
        try:
            data = await api.list_quests(auth.token)
            self.quests = [Quest.from_api(q) for q in data]
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

    async def create(self):
        auth = await self.get_state(AuthState)
        if not self.new_title.strip():
            self.error = "A quest needs a title."
            return
        try:
            xp = int(self.new_xp or 0)
            points = int(self.new_points or 0)
        except ValueError:
            self.error = "XP and points must be whole numbers."
            return

        self.error = ""
        try:
            await api.create_quest(
                auth.token,
                {
                    "title": self.new_title.strip(),
                    "description": self.new_description.strip() or None,
                    "xp_reward": xp,
                    "points_reward": points,
                    "recurrence": self.new_recurrence,
                },
            )
        except api.ApiError as exc:
            self.error = exc.detail
            return

        self.new_title = ""
        self.new_description = ""
        self.show_form = False
        return QuestState.load

    async def complete(self, quest_id: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        try:
            result = await api.complete_quest(auth.token, quest_id)
        except api.ApiError as exc:
            # 409 is the expected answer for "already done this period" - it is
            # a normal state, not a failure, so it is shown plainly.
            self.error = exc.detail
            return
        progression = result.get("progression", {})
        # Driven off the backend's explicit flags. `ranked_up` is true only on
        # a promotion, so a demotion from a lapsed streak never fires this.
        if progression.get("ranked_up"):
            self.level_up_is_rank = True
            after = str(progression.get("rank_after") or "")
            self.level_up_badge = ranks.rank_title(after).upper()
            self.level_up_ladder = ranks.promotion(
                str(progression.get("rank_before") or ""), after
            )
            self.level_up_message = "RANK UP"
            self.show_level_up = True
        elif progression.get("leveled_up"):
            self.level_up_is_rank = False
            self.level_up_badge = str(progression.get("level_after") or "")
            self.level_up_ladder = ""
            self.level_up_message = "LEVEL UP"
            self.show_level_up = True

        yield QuestState.load
        yield AuthState.refresh_me

    async def remove(self, quest_id: str):
        auth = await self.get_state(AuthState)
        try:
            await api.delete_quest(auth.token, quest_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        return QuestState.load

    async def archive(self, quest_id: str):
        auth = await self.get_state(AuthState)
        try:
            await api.update_quest(auth.token, quest_id, {"status": "archived"})
        except api.ApiError as exc:
            self.error = exc.detail
            return
        return QuestState.load
