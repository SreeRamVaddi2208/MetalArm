"""App chrome: the top bar, the floating tab bar, the Start pill, the avatar
with its rank frame, and the shell every tab renders inside."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t
from metalarm.ui.assets import TAB_ICONS
from metalarm.ui.primitives import text, when

TABS = [("home", "Home", "/home"), ("explore", "Explore", "/explore"),
        ("workout", "Workout", "/workout"), ("library", "Library", "/library"),
        ("you", "You", "/you")]

# A hexagon, drawn as a clip path: the avatar frame's shape.
HEXAGON = "polygon(25% 3%, 75% 3%, 100% 50%, 75% 97%, 25% 97%, 0% 50%)"


def avatar(initials: Any, rank: Any = "E", *, size: int = 36, image: Any = "") -> rx.Component:
    """The user's face (or initials) inside a hexagonal frame coloured by rank
    tier - so a feed post, a board row or a duel card shows rank at a glance."""
    frame = t.tier_color(rank) if isinstance(rank, str) else rx.match(
        rank, *[(r, c) for r, c in t.TIER_COLORS.items()], t.TEXT_SECONDARY)
    inner = rx.center(
        text(initials, t.FOOTNOTE, t.TEXT_PRIMARY, font_weight="700"),
        width=f"{size - 4}px", height=f"{size - 4}px",
        background=t.SURFACE_2, clip_path=HEXAGON,
    )
    return rx.center(inner, width=f"{size}px", height=f"{size}px",
                     background=frame, clip_path=HEXAGON, flex_shrink="0")


def icon_button(name: str, label: str, on_click: Any = None, *, badge: Any = None,
                color: str = t.TEXT_PRIMARY, href: str = "") -> rx.Component:
    button = rx.box(
        rx.icon(name, size=22, color=color, stroke_width=1.85),
        rx.cond(badge > 0, rx.box(position="absolute", top="8px", right="8px", width="8px",
                                  height="8px", border_radius=t.RADIUS_PILL,
                                  background=t.DANGER_RED)) if badge is not None else rx.fragment(),
        position="relative",
        display="flex", align_items="center", justify_content="center",
        width=t.TOUCH_MIN, height=t.TOUCH_MIN,
        cursor="pointer", on_click=on_click,
        custom_attrs={"role": "button", "aria-label": label},
    )
    return rx.link(button, href=href, underline="none") if href else button


def top_bar(title: Any, *right: rx.Component, leading: rx.Component | None = None,
            large: bool = True) -> rx.Component:
    """Avatar on the left, a large bold title, up to three icons on the right."""
    return rx.hstack(
        leading if leading is not None else rx.fragment(),
        text(title, t.LARGE_TITLE if large else t.HEADLINE, overflow="hidden",
             text_overflow="ellipsis", white_space="nowrap", min_width="0", flex="1"),
        *right,
        spacing="2",
        align="center",
        width="100%",
        padding_top=t.space(3),
        padding_bottom=t.space(2),
    )


def _tab(key: str, label: str, href: str, active: Any) -> rx.Component:
    selected = active == key
    return rx.link(
        rx.vstack(
            rx.icon(TAB_ICONS[key], size=22, stroke_width=when(selected, 2.4, 1.75)),
            text(label, t.CAPTION, when(selected, t.TEXT_PRIMARY, t.TEXT_SECONDARY),
                 text_transform="none"),
            spacing="1",
            align="center",
            justify="center",
            color=when(selected, t.TEXT_PRIMARY, t.TEXT_SECONDARY),
            background=when(selected, t.SURFACE_3, "transparent"),
            border_radius=t.RADIUS_BAR,
            padding=f"{t.space(1)} {t.space(2)}",
            min_width="58px",
            min_height="52px",
            transition=f"background {t.DURATION_FAST} {t.EASE}",
        ),
        href=href,
        underline="none",
        custom_attrs={"aria-label": label, "aria-current": when(selected, "page", "false")},
    )


def bottom_tab_bar(active: Any) -> rx.Component:
    """The floating translucent pill. Safe-area aware; the shell keeps content
    clear of it."""
    return rx.hstack(
        *[_tab(key, label, href, active) for key, label, href in TABS],
        justify="between",
        align="center",
        position="fixed",
        left="50%",
        transform="translateX(-50%)",
        bottom=f"calc({t.space(3)} + env(safe-area-inset-bottom))",
        width=f"calc(100% - {t.space(6)})",
        max_width="480px",
        height=t.TAB_BAR_HEIGHT,
        padding=f"0 {t.space(2)}",
        background=t.TRANSLUCENT_BAR,
        backdrop_filter=t.BLUR,
        style={"WebkitBackdropFilter": t.BLUR},
        border_radius=t.RADIUS_BAR,
        z_index="40",
    )


def start_pill(*, active_since: Any = "", href: str = "/workout", floating: bool = True) -> rx.Component:
    """White, floating, one tap from anywhere it shows. During a live session
    it becomes "Resume · mm:ss" (the clock is the shared [data-ma-start]
    script, which writes an attribute, not React text)."""
    live = active_since != "" if not isinstance(active_since, str) else bool(active_since)
    label = rx.cond(
        live,
        rx.hstack(rx.el.span("Resume ·"),
                  rx.el.span(custom_attrs={"data-ma-start": active_since}), spacing="1"),
        rx.el.span("Start New Workout"),
    ) if not isinstance(active_since, str) else (
        rx.hstack(rx.el.span("Resume ·"),
                  rx.el.span(custom_attrs={"data-ma-start": active_since}), spacing="1")
        if live else rx.el.span("Start New Workout"))
    return rx.link(
        rx.hstack(rx.icon("play", size=18, fill=t.ON_LIGHT), label, spacing="2", align="center"),
        href=href,
        underline="none",
        **({"position": "fixed", "left": "50%", "transform": "translateX(-50%)",
            "bottom": f"calc({t.TAB_BAR_HEIGHT} + {t.space(6)} + env(safe-area-inset-bottom))"}
           if floating else {"display": "inline-flex"}),
        background=t.TEXT_PRIMARY,
        color=t.ON_LIGHT,
        border_radius=t.RADIUS_PILL,
        padding=f"{t.space(3)} {t.space(5)}",
        z_index="41",
        white_space="nowrap",
        **{**t.HEADLINE, **t.TABULAR},
    )


def shell(*children: rx.Component, tab: Any, show_start: Any = False,
          active_since: Any = "") -> rx.Component:
    """One tab's page: black field, phone-width column, gutters, the tab bar,
    and (on Home and Workout) the Start pill. Content never sits under the
    floating chrome."""
    return rx.box(
        rx.vstack(
            *children,
            spacing="6",
            width="100%",
            max_width="560px",
            margin="0 auto",
            padding_left=t.GUTTER,
            padding_right=t.GUTTER,
            padding_bottom=t.TAB_BAR_CLEARANCE,
        ),
        rx.cond(show_start, start_pill(active_since=active_since)) if not isinstance(show_start, bool)
        else (start_pill(active_since=active_since) if show_start else rx.fragment()),
        bottom_tab_bar(tab),
        background=t.COLOR_BG,
        color=t.TEXT_PRIMARY,
        min_height="100vh",
        width="100%",
        font_family=t.FONT_UI,
        overflow_x="hidden",
    )
