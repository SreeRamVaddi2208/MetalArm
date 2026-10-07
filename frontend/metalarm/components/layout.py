"""Page shell: the five-tab chrome (metalarm/ui/chrome.py) around every
signed-in page, plus the shared banners."""

import reflex as rx

from metalarm import theme
from metalarm.state.auth import AuthState
from metalarm.ui import chrome


def brand() -> rx.Component:
    """The wordmark, for the signed-out pages."""
    return rx.hstack(
        rx.box(width="10px", height="10px", background=theme.ACCENT_BLUE,
               border_radius=theme.RADIUS_PILL),
        rx.text("MetalArm", color=theme.TEXT_PRIMARY, font_family=theme.FONT_UI,
                **theme.HEADLINE),
        spacing="2",
        align="center",
    )


def session_keeper() -> rx.Component:
    """Invisible 5-minute tick that renews the access token while a page stays
    open (a workout can outlast a 60-minute token). Rendered only when signed
    in; the seconds in the format make every tick a change, so on_change fires."""
    return rx.cond(
        AuthState.is_authenticated,
        rx.moment(
            interval=5 * 60 * 1000,
            format="HH:mm:ss",
            on_change=AuthState.keep_fresh,
            display="none",
        ),
    )


# Which tab a route belongs to. The pre-overhaul pages live under the tab
# they will be rebuilt into: the competition pages under Home (its switcher),
# progress and profile under You, routines under Library.
ROUTE_TABS = (
    ("/home", "home"), ("/dashboard", "home"), ("/parties", "home"),
    ("/duels", "home"), ("/rewards", "home"), ("/quests", "home"), ("/notifications", "home"),
    ("/u/[id]", "home"),
    ("/explore", "explore"), ("/exercise/[id]", "explore"),
    ("/workout", "workout"),
    ("/library", "library"), ("/routines", "library"),
    ("/you", "you"), ("/profile", "you"), ("/progress", "you"), ("/session/[id]", "you"),
)


def active_tab() -> rx.Var:
    path = rx.State.router.page.path
    return rx.match(path, *[(route, key) for route, key in ROUTE_TABS], "home")


def shell(*children: rx.Component) -> rx.Component:
    """Standard signed-in page frame: the overhaul's five-tab shell (black
    field, phone-width column, floating tab bar; the Start pill on Home)."""
    tab = active_tab()
    return chrome.shell(
        session_keeper(),
        *children,
        tab=tab,
        show_start=tab == "home",
    )


def error_banner(message: rx.Var) -> rx.Component:
    """Inline message area. Also carries expected 409s such as 'already
    completed for this period', which are normal states rather than faults."""
    return rx.cond(
        message != "",
        rx.box(
            rx.text(message, color=theme.DANGER, font_size="0.85rem"),
            width="100%",
            padding="0.75rem 1rem",
            background=theme.DANGER_BG,
            border=f"1px solid {theme.DANGER}55",
            border_radius="10px",
        ),
    )


def notice_banner(message: rx.Var) -> rx.Component:
    return rx.cond(
        message != "",
        rx.box(
            rx.text(message, color=theme.SUCCESS, font_size="0.85rem"),
            width="100%",
            padding="0.75rem 1rem",
            background=theme.SUCCESS_BG,
            border=f"1px solid {theme.SUCCESS}55",
            border_radius="10px",
        ),
    )


def section_heading(label: str, *trailing: rx.Component) -> rx.Component:
    return rx.hstack(
        rx.text(label, **theme.LABEL_STYLE),
        rx.spacer(),
        *trailing,
        width="100%",
        align="center",
    )
