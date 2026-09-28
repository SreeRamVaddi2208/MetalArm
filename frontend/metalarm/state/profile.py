"""Profile page state."""

from __future__ import annotations

import json

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

    # Notifications. `push_key` is empty when this deployment has no VAPID
    # pair, and the button is hidden rather than offered and broken.
    push_key: str = ""
    push_enabled: bool = False
    push_notice: str = ""
    import_message: str = ""
    loading: bool = False
    error: str = ""

    @rx.var
    def badge_summary(self) -> str:
        return f"{self.badges_earned} of {self.badges_total} earned"

    async def load_push(self):
        """Whether this deployment can notify at all. Cheap, unauthenticated,
        and the answer decides whether the button exists."""
        try:
            config = await api.web_push_config()
            self.push_key = config.get("public_key") or ""
        except api.ApiError:
            self.push_key = ""

    def enable_notifications(self):
        """Ask the browser, then hand whatever it gives us to the server.

        Two steps because only the browser can subscribe and only the server
        has the token: the script returns the subscription, and the callback
        below posts it.
        """
        self.push_notice = ""
        return rx.call_script(
            f"window.maSubscribe && window.maSubscribe({self.push_key!r})",
            callback=ProfileState.push_subscribed,
        )

    async def push_subscribed(self, subscription: str):
        """The browser's answer. An empty string means it could not, or the
        person said no - which is not an error and is not nagged about."""
        if not subscription:
            self.push_notice = "Notifications are off. You can turn them on any time."
            return
        auth = await self.get_state(AuthState)
        try:
            await api.subscribe_web_push(auth.token, json.loads(subscription))
        except (api.ApiError, ValueError) as exc:
            self.push_notice = getattr(exc, "detail", "Could not turn notifications on.")
            return
        self.push_enabled = True
        self.push_notice = "Notifications are on for this device."

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
