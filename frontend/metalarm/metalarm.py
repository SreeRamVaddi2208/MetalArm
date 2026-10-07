"""MetalArm frontend entrypoint.

Routes, the global stylesheet and the document head. Layout lives in
components/ and ui/, data in state/, tokens in theme.py.

Four tabs - Home, Train, Progress, Profile - and everything else folded under
one of them (components/layout.py ROUTE_TABS). The URLs of the five-tab app
still work: each redirects to where its screen lives now.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.offline import PUBLIC_API
from metalarm.pages.credits import credits_page
from metalarm.pages.design_system import design_system_page
from metalarm.pages.details import exercise_page, session_page
from metalarm.pages.duels import duels_page
from metalarm.pages.home import home_page
from metalarm.pages.leaderboard import leaderboard_page
from metalarm.pages.login import login_page, signup_page, welcome_page
from metalarm.pages.monthly import monthly_page
from metalarm.pages.parties import parties_page
from metalarm.pages.people import notifications_page, people_page, user_page
from metalarm.pages.profile import profile_page
from metalarm.pages.progress import history_page, measurements_page, progress_page, recovery_page
from metalarm.pages.quests import quests_page
from metalarm.pages.rewards import rewards_page
from metalarm.pages.train import exercises_page, program_page, routine_page, train_page
from metalarm.state.auth import AuthState
from metalarm.state.credits import CreditsState
from metalarm.state.duels import DuelState
from metalarm.state.exercise_detail import ExerciseDetailState
from metalarm.state.explore import ExploreState
from metalarm.state.home import HomeState
from metalarm.state.monthly import MonthlyState
from metalarm.state.parties import PartyState
from metalarm.state.people import NotificationsState, PeopleState, ProfileViewState
from metalarm.state.profile import ProfileState
from metalarm.state.quests import QuestState
from metalarm.state.rewards import RewardState
from metalarm.state.routines import RoutineState
from metalarm.state.session_detail import SessionDetailState
from metalarm.state.settings import SettingsState, WelcomeState
from metalarm.state.train import ProgramState, TrainState
from metalarm.state.workout import WorkoutState
from metalarm.state.workout_home import WorkoutHomeState
from metalarm.state.you import YouState


def landing() -> rx.Component:
    """`/` and the old URLs: decide where to go, render nothing meanwhile."""
    return rx.box(min_height="100vh", width="100%", background=t.BG)


# The five-tab app's URLs, and where each screen lives now.
REDIRECTS = {
    "/workout": "/train",
    "/library": "/train",
    "/routines": "/train",
    "/dashboard": "/home",
    "/gallery": "/design-system",
}


class RouteState(rx.State):
    async def _signed_in(self) -> bool:
        return bool((await self.get_state(AuthState)).token)

    async def route_home(self):
        return rx.redirect("/home" if await self._signed_in() else "/login")

    def moved(self):
        """An old URL: send it on, keeping nothing of the old layout."""
        path = str(self.router.url.path).rstrip("/") or "/"
        query = self.router.url.query_parameters
        tab = str(query.get("tab", "")).lower()
        if path == "/explore":
            return rx.redirect("/profile/people" if tab == "people" else "/train/exercises")
        if path == "/you":
            return rx.redirect({"history": "/progress/history",
                                "measurements": "/progress/measurements"}.get(tab, "/progress"))
        return rx.redirect(REDIRECTS.get(path, "/home"))

    async def bounce_if_signed_in(self):
        """Keep a signed-in user off the auth pages."""
        if await self._signed_in():
            return rx.redirect("/home")

    # --- Home ---------------------------------------------------------------

    async def enter_home(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, HomeState.load, QuestState.load]

    async def enter_leaderboard(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return HomeState.load_board

    async def enter_notifications(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return NotificationsState.load

    async def enter_user(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return ProfileViewState.load

    # --- Train --------------------------------------------------------------

    async def enter_train(self):
        """Also the rehydration point: WorkoutState.load asks the API for the
        live session, so a refresh mid-workout comes back exactly as it was."""
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, WorkoutState.load, TrainState.load]

    async def enter_exercises(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return ExploreState.load

    async def enter_routine(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, RoutineState.load_detail]

    async def enter_program(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return ProgramState.load

    async def enter_exercise(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, ExerciseDetailState.load]

    # --- Progress -----------------------------------------------------------

    async def enter_progress(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, YouState.load, MonthlyState.load_hero]

    async def enter_history(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return YouState.load_for("History")

    async def enter_measurements(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return YouState.load_for("Measurements")

    async def enter_recovery(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [YouState.load, WorkoutHomeState.load]

    async def enter_session(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return SessionDetailState.load

    async def enter_monthly(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return MonthlyState.load

    # --- Profile ------------------------------------------------------------

    async def enter_profile(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, ProfileState.load, SettingsState.load]

    async def enter_people(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return PeopleState.load

    async def enter_quests(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, QuestState.load, QuestState.preview_celebration]

    async def enter_duels(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, DuelState.load]

    async def enter_parties(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, PartyState.load]

    async def enter_rewards(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return [AuthState.refresh_me, RewardState.load]

    async def enter_credits(self):
        if not await self._signed_in():
            return rx.redirect("/login")
        return CreditsState.load


# The stylesheet every primitive leans on. Every value is a token; the
# custom properties let scripts and CSS read the same tokens.
_REDUCE = ":root[data-ma-reduce]"
GLOBAL_CSS = f"""
{t.css_variables()}
html, body {{ background: {t.BG}; color: {t.TEXT}; }}
body {{ font-family: {t.FONT_BODY}; font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased;
       -webkit-tap-highlight-color: transparent; }}
.radix-themes {{ --default-font-family: {t.FONT_BODY}; --heading-font-family: {t.FONT_HEAD};
  --color-background: {t.BG}; --accent-9: {t.ACCENT}; --accent-10: {t.ACCENT}; --accent-contrast: {t.ON_ACCENT};
  --accent-a3: {t.ACCENT_SOFT}; --accent-11: {t.ACCENT}; --focus-8: {t.ACCENT}; }}
/* Dialogs open over sheets and the tab bar. */
.rt-BaseDialogOverlay {{ z-index: 90; }}
input::placeholder, textarea::placeholder {{ color: {t.TEXT_3}; }}
:focus-visible {{ outline: 2px solid {t.ACCENT}; outline-offset: 2px; }}

/* Rows: hairlines between, none around. */
.ma-rows > * + * {{ border-top: {t.HAIRLINE}; }}
/* A row in a group is pressed edge to edge, so the hairline stays straight. */
.ma-rows > .ma-press, .ma-rows > a > .ma-press {{ border-radius: 0; }}
.ma-press {{ transition: background {t.FAST} {t.EASE}; border-radius: {t.RADIUS}; }}
.ma-press:active {{ background: {t.SURFACE_2}; }}
.ma-button-primary:active {{ opacity: 0.85; }}
.ma-button-secondary:active, .ma-button-ghost:active, .ma-button-danger:active {{ background: {t.SURFACE_2}; }}
.ma-scroll-x {{ overflow-x: auto; flex-wrap: nowrap; scrollbar-width: none; }}
.ma-scroll-x::-webkit-scrollbar {{ display: none; }}

/* Skeleton, sheet, toast. */
.ma-skeleton {{ background: linear-gradient(90deg, {t.SURFACE} 0%, {t.SURFACE_2} 50%, {t.SURFACE} 100%);
  background-size: 200% 100%; animation: ma-shimmer 1.4s ease-in-out infinite; }}
@keyframes ma-shimmer {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}
.ma-sheet {{ animation: ma-sheet-in {t.BASE} {t.EASE}; }}
@keyframes ma-sheet-in {{ from {{ transform: translateY(24px); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
.ma-scrim {{ animation: ma-fade-in {t.BASE} {t.EASE}; }}
@keyframes ma-fade-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.ma-toast {{ animation: ma-toast 3s {t.EASE} forwards; pointer-events: none; }}
@keyframes ma-toast {{ 0% {{ opacity: 0; transform: translateY(8px); }} 8%, 88% {{ opacity: 1; transform: none; }}
  100% {{ opacity: 0; visibility: hidden; }} }}
@keyframes ma-toast-still {{ 0%, 99% {{ opacity: 1; }} 100% {{ opacity: 0; visibility: hidden; }} }}

/* Reduced motion - the system setting, or the app's own (Profile > App). The
   toast still has to go away, so it steps out instead of fading. */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important; scroll-behavior: auto !important; }}
  .ma-toast {{ animation: ma-toast-still 3s step-end forwards !important; }}
}}
{_REDUCE} *, {_REDUCE} *::before, {_REDUCE} *::after {{ animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }}
{_REDUCE} .ma-toast {{ animation: ma-toast-still 3s step-end forwards !important; }}
"""

# Before first paint: the app's reduced-motion setting, from the browser.
_REDUCE_ON_LOAD = ("try { if (localStorage.getItem('ma_reduce_motion') === '1') "
                   "document.documentElement.setAttribute('data-ma-reduce', '1'); } catch (e) {}")

app = rx.App(
    head_components=[
        # The app icon (scripts/icon/render_icon.mjs writes both files).
        rx.el.link(rel="icon", type="image/png", href="/favicon.png"),
        rx.el.link(rel="apple-touch-icon", href="/apple-touch-icon.png"),
        rx.el.meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover"),
        # Installable: the manifest, the bar colour, the service worker.
        rx.el.link(rel="manifest", href="/manifest.json"),
        rx.el.meta(name="theme-color", content=t.BG),
        rx.el.meta(name="apple-mobile-web-app-capable", content="yes"),
        rx.el.meta(name="apple-mobile-web-app-status-bar-style", content="black"),
        rx.el.meta(name="ma-api", content=PUBLIC_API),
        rx.script(_REDUCE_ON_LOAD),
        rx.script("if ('serviceWorker' in navigator) { window.addEventListener('load', function () {"
                  " navigator.serviceWorker.register('/sw.js').catch(function () {}); }); }"),
        rx.el.style(GLOBAL_CSS),
    ],
    # Manrope for the interface, Space Grotesk for titles and big numbers.
    stylesheets=[t.FONT_STYLESHEET],
    # Applied to <body>; without it overscroll shows the browser default.
    style={"background": t.BG, "color": t.TEXT, "font_family": t.FONT_BODY},
)


def page(component, route: str, title: str, on_load=None) -> None:
    app.add_page(component, route=route, title=f"{title} - MetalArm" if title else "MetalArm", on_load=on_load)


r = RouteState

# Signed out
page(landing, "/", "", r.route_home)
page(login_page, "/login", "Sign in", r.bounce_if_signed_in)
page(signup_page, "/signup", "Create account", r.bounce_if_signed_in)
page(welcome_page, "/welcome", "Welcome", WelcomeState.load)

# Home
page(home_page, "/home", "Home", r.enter_home)
page(leaderboard_page, "/leaderboard", "Leaderboard", r.enter_leaderboard)
page(notifications_page, "/notifications", "Notifications", r.enter_notifications)
page(user_page, "/u/[id]", "Profile", r.enter_user)

# Train
page(train_page, "/train", "Train", r.enter_train)
page(exercises_page, "/train/exercises", "Exercises", r.enter_exercises)
page(routine_page, "/train/routine/[id]", "Routine", r.enter_routine)
page(program_page, "/train/program/[id]", "Program", r.enter_program)
page(exercise_page, "/exercise/[id]", "Exercise", r.enter_exercise)

# Progress
page(progress_page, "/progress", "Progress", r.enter_progress)
page(history_page, "/progress/history", "History", r.enter_history)
page(measurements_page, "/progress/measurements", "Body measurements", r.enter_measurements)
page(recovery_page, "/progress/recovery", "Muscles & recovery", r.enter_recovery)
page(session_page, "/session/[id]", "Workout", r.enter_session)
page(monthly_page, "/summary/[ym]", "Your month", r.enter_monthly)

# Profile
page(profile_page, "/profile", "Profile", r.enter_profile)
page(people_page, "/profile/people", "People", r.enter_people)
page(quests_page, "/quests", "Quests", r.enter_quests)
page(duels_page, "/duels", "Duels", r.enter_duels)
page(parties_page, "/parties", "Parties", r.enter_parties)
page(rewards_page, "/rewards", "Rewards", r.enter_rewards)
page(credits_page, "/about/credits", "Credits", r.enter_credits)

# Not in any navigation: the reference the screens are built from.
page(design_system_page, "/design-system", "Design system")

# The five-tab app's URLs.
for old in (*REDIRECTS, "/explore", "/you"):
    page(landing, old, "", r.moved)
