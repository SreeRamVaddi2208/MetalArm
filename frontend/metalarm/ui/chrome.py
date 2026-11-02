"""The app shell: avatar, top bar, the floating five-tab bar, and the page column.

Every signed-in page sits in shell(): a 430 px column centred on wide
screens, 20 px gutters, safe-area insets, the tab bar at the bottom, and -
optionally - ONE pinned action above it (the screen's primary button).
"""

from __future__ import annotations

from typing import Any

import reflex as rx
from reflex.vars import Var

from metalarm import theme as t
from metalarm.ui.primitives import icon_button, text, when

TABS = [("home", "Home", "/home", "house"), ("explore", "Explore", "/explore", "search"),
        ("workout", "Workout", "/train", "circle-plus"), ("library", "Library", "/library", "library"),
        ("you", "You", "/progress", "user")]


def avatar(initials: Any, *, size: int = 40, image: Any = "") -> rx.Component:
    """Neutral: a surface-2 circle with initials. Rank is shown by a
    RankBadge beside it, never by tinting the avatar."""
    style = {48: t.TITLE, 96: t.TITLE_LG}.get(size, t.LABEL)
    return rx.center(text(initials, style, t.TEXT_2), width=f"{size}px", height=f"{size}px",
                     border_radius=t.RADIUS_PILL, background=t.SURFACE_2, flex_shrink="0")


def top_bar(title: Any = "", *, back: Any = "", trailing: rx.Component | None = None,
            large: bool = False) -> rx.Component:
    """Back icon, centred title, at most one trailing action. Tab roots use
    the large variant: the title on the left, in title-lg."""
    if large:
        return rx.hstack(text(title, t.TITLE_LG, flex="1", min_width="0"),
                         trailing if trailing is not None else rx.fragment(),
                         width="100%", align="center", min_height="56px")
    # back: "" for none, "history" to go back a page, or a path.
    if isinstance(back, str) and back == "history":
        left = icon_button("chevron-left", "Back", on_click=rx.call_script(
            "history.length > 1 ? history.back() : location.assign('/home')"))
    elif isinstance(back, Var) or back:
        left = icon_button("chevron-left", "Back", href=back)
    else:
        left = rx.box(width=t.ICON_HIT)
    return rx.grid(
        left,
        text(title, t.LABEL, text_align="center", overflow="hidden", text_overflow="ellipsis",
             white_space="nowrap"),
        rx.flex(trailing if trailing is not None else rx.fragment(), justify="end"),
        grid_template_columns=f"{t.ICON_HIT} minmax(0,1fr) {t.ICON_HIT}", align_items="center",
        width="100%", min_height="56px",
    )


def _tab(key: str, label: str, href: str, icon: str, active: Any) -> rx.Component:
    on = active == key
    return rx.link(
        rx.vstack(rx.icon(icon, size=22, stroke_width=1.75), text(label, t.CAPTION, t.TEXT),
                  spacing="1", align="center", color=t.TEXT),
        href=href, underline="none", flex="1", min_width="0", display="flex", justify_content="center",
        align_items="center", height="100%", border_radius=t.RADIUS_PILL, background=when(on, t.BG, "transparent"),
        custom_attrs={"aria-current": rx.cond(on, "page", "false") if isinstance(on, Var) else ("page" if on else "false"),
                      "data-tab": key},
    )


def tab_bar(active: Any) -> rx.Component:
    """Floats over the content, which shows through it."""
    return rx.hstack(
        *[_tab(key, label, href, icon, active) for key, label, href, icon in TABS],
        position="fixed", left=t.GUTTER, right=t.GUTTER, margin="0 auto", max_width=f"calc({t.MAX_WIDTH} - 2 * {t.GUTTER})",
        bottom=f"calc({t.TAB_BAR_GAP} + env(safe-area-inset-bottom))", height=t.TAB_BAR_HEIGHT, padding=t.space(4),
        background=t.TAB_BAR_BG, border=t.HAIRLINE, border_radius=t.RADIUS_PILL, spacing="0", z_index="40",
        backdrop_filter="blur(16px)", role="navigation", class_name="ma-tab-bar",
    )


def you_switch(selected: str) -> rx.Component:
    """The You tab's two halves."""
    def part(label: str, href: str) -> rx.Component:
        on = selected == label
        return rx.link(text(label, t.LABEL, t.TEXT if on else t.TEXT_2), href=href, underline="none", flex="1",
                       display="flex", justify_content="center", align_items="center", min_height=t.TOUCH,
                       border_radius=t.RADIUS, background=t.SURFACE_2 if on else "transparent",
                       custom_attrs={"aria-current": "page" if on else "false"})

    return rx.hstack(part("Progress", "/progress"), part("Profile", "/profile"), spacing="1", width="100%",
                     background=t.SURFACE, border_radius=t.RADIUS, padding=t.space(4), class_name="ma-you-switch")


def shell(*children: rx.Component, tab: Any, pinned: rx.Component | None = None) -> rx.Component:
    """One page: the column, the tab bar, and an optional pinned action."""
    return rx.box(
        rx.vstack(
            *children,
            spacing="6", width="100%", max_width=t.MAX_WIDTH, margin="0 auto",
            padding=f"calc({t.space(8)} + env(safe-area-inset-top)) {t.GUTTER} {t.BOTTOM_CLEARANCE}",
            align="start",
        ),
        rx.box(pinned, position="fixed", left="0", right="0", margin="0 auto", max_width=t.MAX_WIDTH,
               padding=f"0 {t.GUTTER}", bottom=f"calc({t.TAB_BAR_HEIGHT} + {t.TAB_BAR_GAP} + {t.space(12)} + env(safe-area-inset-bottom))",
               z_index="39", class_name="ma-pinned") if pinned is not None else rx.fragment(),
        tab_bar(tab),
        background=t.BG, color=t.TEXT, min_height="100vh", width="100%", overflow_x="hidden",
        font_family=t.FONT_BODY,
    )
