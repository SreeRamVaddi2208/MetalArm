"""LevelForge frontend entrypoint.

Routes and page registration only. Layout lives in components/, data in
state/, and the Section 7 motion work in components/level_up.py - kept apart
so animation can be iterated on without touching how data flows.
"""

import reflex as rx

from levelforge import theme
from levelforge.pages.dashboard import dashboard_page
from levelforge.pages.login import login_page, signup_page
from levelforge.pages.parties import parties_page
from levelforge.pages.profile import profile_page
from levelforge.pages.rewards import rewards_page
from levelforge.state.auth import AuthState
from levelforge.state.parties import PartyState
from levelforge.state.profile import ProfileState
from levelforge.state.quests import QuestState
from levelforge.state.rewards import RewardState


def landing() -> rx.Component:
    """`/` decides where to send you, rather than rendering a third variant of
    the signed-in and signed-out views."""
    return rx.center(
        rx.spinner(),
        min_height="100vh",
        width="100%",
        background=theme.BG,
    )


class RouteState(rx.State):
    async def route_home(self):
        auth = await self.get_state(AuthState)
        return rx.redirect("/dashboard" if auth.token else "/login")

    async def enter_dashboard(self):
        """Guard + load. Redirects out when there is no session, so a page is
        never rendered against a token the API has already rejected."""
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, QuestState.load]

    async def enter_rewards(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, RewardState.load]

    async def enter_parties(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, PartyState.load]

    async def enter_profile(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, ProfileState.load]

    async def bounce_if_signed_in(self):
        """Keep a signed-in user off the auth pages."""
        auth = await self.get_state(AuthState)
        if auth.token:
            return rx.redirect("/dashboard")


app = rx.App(
    # Applied to <body>; without it the page shows the browser default behind
    # the layout on overscroll.
    style={
        "background": theme.BG,
        "color": theme.TEXT,
        "font_family": (
            "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, "
            "'Helvetica Neue', Arial, sans-serif"
        ),
    },
)

app.add_page(landing, route="/", title="LevelForge", on_load=RouteState.route_home)
app.add_page(
    login_page,
    route="/login",
    title="Sign in - LevelForge",
    on_load=RouteState.bounce_if_signed_in,
)
app.add_page(
    signup_page,
    route="/signup",
    title="Create account - LevelForge",
    on_load=RouteState.bounce_if_signed_in,
)
app.add_page(
    dashboard_page,
    route="/dashboard",
    title="Quest board - LevelForge",
    on_load=RouteState.enter_dashboard,
)
app.add_page(
    rewards_page,
    route="/rewards",
    title="Rewards - LevelForge",
    on_load=RouteState.enter_rewards,
)
app.add_page(
    parties_page,
    route="/parties",
    title="Parties - LevelForge",
    on_load=RouteState.enter_parties,
)
app.add_page(
    profile_page,
    route="/profile",
    title="Profile - LevelForge",
    on_load=RouteState.enter_profile,
)
