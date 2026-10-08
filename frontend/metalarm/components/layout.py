"""Page frame: the five-tab shell (metalarm/ui/chrome.py) around every
signed-in page, the session keeper, and the inline message lines."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.rest_timer import timer_assets
from metalarm.state.auth import AuthState
from metalarm.ui import chrome
from metalarm.ui.primitives import text
from metalarm.ui.toast import toast


def brand() -> rx.Component:
    """The wordmark, for the signed-out pages."""
    return rx.hstack(rx.box(width="10px", height="10px", background=t.ACCENT, border_radius=t.RADIUS_PILL),
                     text("MetalArm", t.TITLE), spacing="2", align="center")


def session_keeper() -> rx.Component:
    """Invisible 5-minute tick that renews the access token while a page stays
    open (a workout can outlast a 60-minute token). Rendered only when signed
    in; the seconds in the format make every tick a change, so on_change fires."""
    return rx.cond(
        AuthState.is_authenticated,
        rx.moment(interval=5 * 60 * 1000, format="HH:mm:ss", on_change=AuthState.keep_fresh, display="none"),
    )


# Which tab each route belongs to.
ROUTE_TABS = (
    ("/home", "home"), ("/leaderboard", "home"), ("/notifications", "home"), ("/u/[id]", "home"),
    ("/train", "train"), ("/train/routine/[id]", "train"), ("/train/program/[id]", "train"),
    ("/library", "library"), ("/library/path/[lib_path]", "library"), ("/library/program/[lib_program]", "library"),
    ("/library/workout/[lib_workout]", "library"), ("/library/exercises", "library"), ("/exercise/[id]", "library"),
    ("/progress", "progress"), ("/progress/history", "progress"), ("/progress/measurements", "progress"),
    ("/progress/recovery", "progress"), ("/session/[id]", "progress"), ("/summary/[ym]", "progress"),
    ("/profile", "profile"), ("/profile/people", "profile"), ("/quests", "profile"), ("/duels", "profile"),
    ("/parties", "profile"), ("/rewards", "profile"), ("/about/credits", "profile"),
)


def active_tab() -> rx.Var:
    return rx.match(rx.State.router.page.path, *[(route, key) for route, key in ROUTE_TABS], "home")


def shell(*children: rx.Component, pinned: rx.Component | None = None) -> rx.Component:
    """Standard signed-in page frame."""
    return chrome.shell(session_keeper(), timer_assets(), toast(), *children, tab=active_tab(), pinned=pinned)


def error_banner(message: rx.Var) -> rx.Component:
    """What went wrong, in a sentence. Calm: danger red is for destructive
    actions only."""
    return rx.cond(
        message != "",
        rx.hstack(rx.icon("circle-alert", size=20, stroke_width=1.75, color=t.TEXT_2, flex_shrink="0"),
                  text(message, t.BODY, t.TEXT_2), spacing="2", align="start", width="100%",
                  custom_attrs={"role": "alert"}),
    )


def notice_banner(message: rx.Var) -> rx.Component:
    return rx.cond(
        message != "",
        rx.hstack(rx.icon("check", size=20, stroke_width=1.75, color=t.TEXT_2, flex_shrink="0"),
                  text(message, t.BODY, t.TEXT_2), spacing="2", align="start", width="100%",
                  custom_attrs={"role": "status"}),
    )
