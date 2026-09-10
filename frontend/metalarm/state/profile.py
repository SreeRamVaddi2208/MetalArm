"""Profile page state."""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm.models import Badge, LifetimeStats
from metalarm.state.auth import AuthState


class ProfileState(rx.State):
    badges: list[Badge] = []
    stats: LifetimeStats = LifetimeStats()
    badges_earned: int = 0
    badges_total: int = 0
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
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False
