"""Rewards shop state."""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm.models import Redemption, Reward
from metalarm.state.auth import AuthState


class RewardState(rx.State):
    rewards: list[Reward] = []
    history: list[Redemption] = []
    balance: int = 0
    earned: int = 0
    spent: int = 0

    loading: bool = False
    error: str = ""
    notice: str = ""

    show_form: bool = False
    new_title: str = ""
    new_cost: str = "50"

    @rx.var
    def has_rewards(self) -> bool:
        return len(self.rewards) > 0

    @rx.var
    def has_history(self) -> bool:
        return len(self.history) > 0

    def set_new_title(self, v: str) -> None:
        self.new_title = v

    def set_new_cost(self, v: str) -> None:
        self.new_cost = v

    def toggle_form(self) -> None:
        self.show_form = not self.show_form
        self.error = ""

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        self.loading = True
        self.error = ""
        yield
        try:
            self.rewards = [Reward.from_api(r) for r in await api.list_rewards(auth.token)]
            wallet = await api.wallet(auth.token)
            # points_balance is authoritative. Deliberately NOT earned - spent:
            # deleting a quest cascades its completions away, so `earned` can
            # drop while the balance correctly does not.
            self.balance = wallet.get("points_balance") or 0
            self.earned = wallet.get("total_points_earned") or 0
            self.spent = wallet.get("total_points_spent") or 0
            self.history = [
                Redemption.from_api(h) for h in await api.redemptions(auth.token)
            ]
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

    async def create(self):
        auth = await self.get_state(AuthState)
        if not self.new_title.strip():
            self.error = "A reward needs a title."
            return
        try:
            cost = int(self.new_cost or 0)
        except ValueError:
            self.error = "Cost must be a whole number."
            return

        self.error = ""
        try:
            await api.create_reward(
                auth.token, {"title": self.new_title.strip(), "point_cost": cost}
            )
        except api.ApiError as exc:
            self.error = exc.detail
            return

        self.new_title = ""
        self.show_form = False
        return RewardState.load

    async def redeem(self, reward_id: str):
        auth = await self.get_state(AuthState)
        self.error = ""
        self.notice = ""
        try:
            result = await api.redeem_reward(auth.token, reward_id)
        except api.ApiError as exc:
            # 409 here means insufficient points or a deactivated reward. The
            # API writes those messages for display, so they are shown as-is.
            self.error = exc.detail
            return
        self.notice = (
            f"Redeemed {result['redemption']['reward_title']} "
            f"for {result['redemption']['points_spent']} points."
        )
        yield RewardState.load
        yield AuthState.refresh_me

    async def deactivate(self, reward_id: str):
        auth = await self.get_state(AuthState)
        try:
            await api.update_reward(auth.token, reward_id, {"is_active": False})
        except api.ApiError as exc:
            self.error = exc.detail
            return
        return RewardState.load

    async def remove(self, reward_id: str):
        """Delete, falling back to deactivation.

        A redeemed reward cannot be deleted - the API returns 409 rather than
        erasing spend history - so that answer is surfaced as guidance instead
        of an error the user cannot act on.
        """
        auth = await self.get_state(AuthState)
        self.error = ""
        try:
            await api.delete_reward(auth.token, reward_id)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        return RewardState.load
