"""MetalArm frontend entrypoint.

Routes and page registration only. Layout lives in components/, data in
state/, and the Section 7 motion work in components/level_up.py - kept apart
so animation can be iterated on without touching how data flows.
"""

import reflex as rx

from metalarm import theme
from metalarm.pages.credits import credits_page
from metalarm.pages.dashboard import dashboard_page
from metalarm.pages.explore import explore_page
from metalarm.pages.gallery import gallery_page
from metalarm.pages.login import login_page, signup_page
from metalarm.pages.duels import duels_page
from metalarm.pages.parties import parties_page
from metalarm.pages.profile import profile_page
from metalarm.pages.progress import progress_page
from metalarm.pages.rewards import rewards_page
from metalarm.pages.routines import routines_page
from metalarm.pages.workout import workout_page
from metalarm.state.auth import AuthState
from metalarm.state.credits import CreditsState
from metalarm.state.explore import ExploreState
from metalarm.state.parties import PartyState
from metalarm.state.profile import ProfileState
from metalarm.state.progress import ProgressState
from metalarm.state.duels import DuelState
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
        return rx.redirect("/home" if auth.token else "/login")

    def to_home(self):
        """/dashboard was the home screen before the five-tab shell."""
        return rx.redirect("/home")

    async def enter_explore(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, ExploreState.load]

    async def enter_credits(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return CreditsState.load

    async def enter_dashboard(self):
        """Guard + load. Redirects out when there is no session, so a page is
        never rendered against a token the API has already rejected."""
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [
            AuthState.refresh_me,
            QuestState.load,
            DuelState.load_summary,
            QuestState.preview_celebration,
        ]

    async def enter_rewards(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, RewardState.load]

    async def enter_duels(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        return [AuthState.refresh_me, DuelState.load]

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
            return rx.redirect("/home")


# Global CSS the components share: skeleton shimmer, the "+N points" fade,
# and their reduced-motion variants. Values come from theme tokens.
GLOBAL_CSS = f"""
html, body {{ background: {theme.COLOR_BG}; }}
body {{ font-family: {theme.FONT_UI}; font-variant-numeric: tabular-nums;
       -webkit-font-smoothing: antialiased; }}
.ma-skeleton {{ background: linear-gradient(90deg, {theme.SURFACE_1} 0%, {theme.SURFACE_2} 50%,
  {theme.SURFACE_1} 100%); background-size: 200% 100%; animation: ma-shimmer 1.4s ease-in-out infinite; }}
@keyframes ma-shimmer {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}
.ma-points-fade {{ animation: ma-points 1.2s {theme.EASE} forwards; pointer-events: none; }}
@keyframes ma-points {{ 0% {{ opacity: 0; transform: translateY(4px); }} 20% {{ opacity: 1; transform: none; }}
  80% {{ opacity: 1; }} 100% {{ opacity: 0; transform: translateY(-6px); }} }}
@media (prefers-reduced-motion: reduce) {{
  .ma-skeleton {{ animation: none; }}
  .ma-points-fade {{ animation: ma-points-still 1.2s linear forwards; }}
  @keyframes ma-points-still {{ 0%, 80% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
}}
"""

app = rx.App(
    # The app icon (scripts/icon/render_icon.mjs writes both files).
    head_components=[
        rx.el.link(rel="icon", type="image/png", href="/favicon.png"),
        rx.el.link(rel="apple-touch-icon", href="/apple-touch-icon.png"),
        rx.el.meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover"),
        rx.el.style(GLOBAL_CSS),
    ],
    # Inter for the interface, Space Grotesk for the game's numerals.
    stylesheets=[theme.FONT_STYLESHEET],
    # Applied to <body>; without it the page shows the browser default behind
    # the layout on overscroll.
    style={
        "background": theme.COLOR_BG,
        "color": theme.TEXT_PRIMARY,
        "font_family": theme.FONT_UI,
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
    route="/home",
    title="Home - MetalArm",
    on_load=RouteState.enter_dashboard,
)
app.add_page(landing, route="/dashboard", title="MetalArm", on_load=RouteState.to_home)
app.add_page(explore_page, route="/explore", title="Explore - MetalArm",
             on_load=RouteState.enter_explore)
app.add_page(routines_page, route="/library", title="Library - MetalArm",
             on_load=RouteState.enter_routines)
app.add_page(profile_page, route="/you", title="You - MetalArm",
             on_load=RouteState.enter_profile)
app.add_page(credits_page, route="/about/credits", title="Credits - MetalArm",
             on_load=RouteState.enter_credits)
# Hidden: the design-system catalogue, for review and the screenshot sweep.
app.add_page(gallery_page, route="/gallery", title="Gallery - MetalArm")
app.add_page(
    rewards_page,
    route="/rewards",
    title="Rewards - MetalArm",
    on_load=RouteState.enter_rewards,
)
app.add_page(
    duels_page,
    route="/duels",
    title="Duels - MetalArm",
    on_load=RouteState.enter_duels,
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
