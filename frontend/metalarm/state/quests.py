"""Quest board state."""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm.models import Quest
from metalarm.state.auth import AuthState
from metalarm import rank_tiers, ranks


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

    # The tier's look, resolved here rather than in the component: a dict
    # cannot be indexed by a Var in compiled JSX, and resolving it once keeps
    # rank_tiers.py the single place a tier is described. Defaults are the
    # quietest tier, so a celebration raised by older code still renders.
    level_up_line: str = ""
    level_up_base: str = rank_tiers.LEVEL_UP.base
    level_up_glow: str = rank_tiers.LEVEL_UP.glow
    level_up_jewel: str = rank_tiers.LEVEL_UP.jewel
    level_up_ornament: str = rank_tiers.LEVEL_UP.ornament
    level_up_particles: list[dict[str, str]] = []
    level_up_rings: int = rank_tiers.LEVEL_UP.rings
    level_up_shock: bool = rank_tiers.LEVEL_UP.shock
    level_up_duration: int = rank_tiers.LEVEL_UP.duration_ms
    level_up_shake: str = "0px"
    level_up_zoom: str = "1"
    level_up_pop: str = "1"
    level_up_sound: str = ""
    level_up_haptic: str = ""
    # The counter ticks between these two.
    level_up_level_from: int = 0
    level_up_level_to: int = 0

    # The only sound MetalArm makes, so it carries its own preference rather
    # than waiting for a global one. Kept in the browser: it is a per-device
    # comfort setting, not account data.
    sound_pref: str = rx.LocalStorage("", name="ma_celebration_mute")

    @rx.var
    def has_quests(self) -> bool:
        return len(self.quests) > 0

    @rx.var
    def sound_muted(self) -> bool:
        return self.sound_pref == "1"

    @rx.var
    def level_up_duration_css(self) -> str:
        """The one clock the whole sequence is timed against."""
        return f"{self.level_up_duration}ms"

    def toggle_sound(self) -> None:
        self.sound_pref = "" if self.sound_pref == "1" else "1"

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

    def celebrate(
        self,
        kind: str,
        badge: str,
        ladder: str = "",
        rank: str = "",
        level_from: int = 0,
        level_to: int = 0,
    ) -> None:
        """Raise the overlay, dressed for the tier just entered.

        Every celebration in the app comes through here - quests and workouts
        both - so there is one place that decides what a promotion looks like.
        A level-up borrows the quietest tier, which is what keeps the two
        beats from being confused with each other.
        """
        tier = rank_tiers.tier_for(rank) if kind == "rank" else rank_tiers.LEVEL_UP
        self.level_up_is_rank = kind == "rank"
        self.level_up_badge = badge
        self.level_up_ladder = ladder
        self.level_up_message = "RANK UP" if kind == "rank" else "LEVEL UP"
        self.level_up_line = tier.line
        self.level_up_base = tier.base
        self.level_up_glow = tier.glow
        self.level_up_jewel = tier.jewel
        self.level_up_ornament = tier.ornament
        self.level_up_particles = rank_tiers.particles(tier)
        self.level_up_rings = tier.rings
        self.level_up_shock = tier.shock
        self.level_up_duration = tier.duration_ms
        self.level_up_shake = f"{tier.shake_px}px"
        self.level_up_zoom = str(tier.zoom)
        self.level_up_pop = str(tier.pop)
        self.level_up_sound = ",".join(tier.sound)
        self.level_up_haptic = ",".join(str(ms) for ms in tier.haptic)
        self.level_up_level_from = level_from
        self.level_up_level_to = level_to
        self.show_level_up = True

    def preview_celebration(self) -> None:
        """?celebrate=S on the dashboard plays that promotion, for looking at
        it without grinding to World Class first.

        It changes no data - it is the same overlay the real event raises, with
        the tier resolved the same way - so it is safe to leave in: the worst a
        curious user can do is watch an animation. The rank letters are the
        server's (E-D-C-B-A-S); anything else is ignored.
        """
        wanted = self.router.url.query_parameters.get("celebrate", "")
        if wanted not in rank_tiers.TIERS:
            return
        self.celebrate(
            "rank",
            ranks.rank_title(wanted).upper(),
            ranks.promotion(rank_tiers.previous(wanted), wanted),
            rank=wanted,
            level_from=14,
            level_to=15,
        )

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
        levels = (
            int(progression.get("level_before") or 0),
            int(progression.get("level_after") or 0),
        )
        if progression.get("ranked_up"):
            after = str(progression.get("rank_after") or "")
            self.celebrate(
                "rank",
                ranks.rank_title(after).upper(),
                ranks.promotion(str(progression.get("rank_before") or ""), after),
                rank=after,
                level_from=levels[0],
                level_to=levels[1],
            )
        elif progression.get("leveled_up"):
            self.celebrate(
                "level",
                str(progression.get("level_after") or ""),
                level_from=levels[0],
                level_to=levels[1],
            )

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
