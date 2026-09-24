"""MetalArm frontend entrypoint.

Routes and page registration only. Layout lives in components/, data in
state/, and the Section 7 motion work in components/level_up.py - kept apart
so animation can be iterated on without touching how data flows.
"""

import reflex as rx

from metalarm import theme
from metalarm.pages.dashboard import dashboard_page
from metalarm.pages.login import login_page, signup_page
from metalarm.pages.parties import parties_page
from metalarm.pages.profile import profile_page
from metalarm.pages.progress import progress_page
from metalarm.pages.rewards import rewards_page
from metalarm.pages.routines import routines_page
from metalarm.pages.workout import workout_page
from metalarm.state.auth import AuthState
from metalarm.state.parties import PartyState
from metalarm.state.profile import ProfileState
from metalarm.state.progress import ProgressState
from metalarm.state.quests import QuestState
from metalarm.state.rewards import RewardState
from metalarm.state.routines import RoutineState
from metalarm.state.workout import WorkoutState


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
        return [AuthState.refresh_me, QuestState.load, QuestState.preview_celebration]

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

    async def enter_workout(self):
        """Also the rehydration point: WorkoutState.load asks the API for the
        live session, so a refresh mid-workout comes back exactly as it was."""
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, WorkoutState.load]

    async def enter_routines(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, RoutineState.load]

    async def enter_progress(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, ProgressState.load]

    async def bounce_if_signed_in(self):
        """Keep a signed-in user off the auth pages."""
        auth = await self.get_state(AuthState)
        if auth.token:
            return rx.redirect("/dashboard")


app = rx.App(
    # The app icon (scripts/icon/render_icon.mjs writes both files).
    head_components=[
        rx.el.link(rel="icon", type="image/png", href="/favicon.png"),
        rx.el.link(rel="apple-touch-icon", href="/apple-touch-icon.png"),
    ],
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

app.add_page(landing, route="/", title="MetalArm", on_load=RouteState.route_home)
app.add_page(
    login_page,
    route="/login",
    title="Sign in - MetalArm",
    on_load=RouteState.bounce_if_signed_in,
)
app.add_page(
    signup_page,
    route="/signup",
    title="Create account - MetalArm",
    on_load=RouteState.bounce_if_signed_in,
)
app.add_page(
    dashboard_page,
    route="/dashboard",
    title="Quest board - MetalArm",
    on_load=RouteState.enter_dashboard,
)
app.add_page(
    rewards_page,
    route="/rewards",
    title="Rewards - MetalArm",
    on_load=RouteState.enter_rewards,
)
app.add_page(
    parties_page,
    route="/parties",
    title="Parties - MetalArm",
    on_load=RouteState.enter_parties,
)
app.add_page(
    profile_page,
    route="/profile",
    title="Profile - MetalArm",
    on_load=RouteState.enter_profile,
)
app.add_page(
    workout_page,
    route="/workout",
    title="Workout - MetalArm",
    on_load=RouteState.enter_workout,
)
app.add_page(
    routines_page,
    route="/routines",
    title="Routines - MetalArm",
    on_load=RouteState.enter_routines,
)
app.add_page(
    progress_page,
    route="/progress",
    title="Progress - MetalArm",
    on_load=RouteState.enter_progress,
)
