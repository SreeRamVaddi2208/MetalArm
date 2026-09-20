"""Profile page state."""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm.models import (
    Badge,
    LifetimeStats,
    StatRow,
    TrainingPathRow,
    TrialRow,
    import_summary,
)
from metalarm.state.auth import AuthState


class ProfileState(rx.State):
    badges: list[Badge] = []
    stats: LifetimeStats = LifetimeStats()
    badges_earned: int = 0
    badges_total: int = 0
    trials: list[TrialRow] = []
    stats_sheet: list[StatRow] = []
    character_class: str = ""
    class_label: str = ""
    # The training paths, from GET /training-categories: name, tagline and how
    # each one trains. Not hardcoded here, so the copy lives in one place.
    paths: list[TrainingPathRow] = []
    importing: bool = False
    import_message: str = ""
    loading: bool = False
    error: str = ""

    @rx.var
    def badge_summary(self) -> str:
        return f"{self.badges_earned} of {self.badges_total} earned"

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        self.loading = True
        self.error = ""
        yield
        try:
            data = await api.profile(auth.token)
            self.badges = [Badge.from_api(b) for b in data.get("badges", [])]
            # Lifetime volume is shown in the account's chosen weight unit.
            self.stats = LifetimeStats.from_api(data.get("stats") or {}, auth.weight_unit)
            self.badges_earned = data.get("badges_earned") or 0
            self.badges_total = data.get("badges_total") or 0
            trials = await api.rank_trials(auth.token)
            self.trials = [TrialRow.from_api(t, auth.weight_unit) for t in trials]
            sheet = await api.character(auth.token)
            self.stats_sheet = [StatRow.from_api(s) for s in sheet.get("stats") or []]
            self.character_class = sheet.get("character_class") or ""
            self.class_label = sheet.get("class_label") or ""
            if not self.paths:
                # A failure here leaves the cards out rather than the page.
                try:
                    self.paths = [
                        TrainingPathRow.from_api(row)
                        for row in await api.training_categories(auth.token)
                    ]
                except api.ApiError:
                    self.paths = []
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

    async def import_history(self, files: list[rx.UploadFile]):
        """A Strong or Hevy CSV dropped on the IMPORT HISTORY panel."""
        auth = await self.get_state(AuthState)
        if not auth.token or not files:
            return
        self.importing = True
        self.import_message = ""
        self.error = ""
        yield
        try:
            text = (await files[0].read()).decode("utf-8-sig", errors="replace")
            result = await api.import_workouts(auth.token, text, auth.weight_unit)
            self.import_message = import_summary(result)
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.importing = False
        # Imported history moves XP, records and trials.
        yield AuthState.refresh_me
        yield ProfileState.load

    async def choose_class(self, value: str):
        """Pick (or clear) the training path. It decides which stats are
        highlighted and which ready-made workout the app leads with - never a
        score, which is why it can be changed whenever goals change."""
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        try:
            await api.set_character_class(auth.token, "" if value == self.character_class else value)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        yield AuthState.refresh_me
        yield ProfileState.load
