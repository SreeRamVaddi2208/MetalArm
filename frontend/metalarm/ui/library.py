"""The Library's own primitives: program card, workout card, path chip and the
schedule grid. Built from the system's tokens and primitives; no cover art in
v1, so a card is its words."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t
from metalarm.ui.primitives import list_row, pill, text, when

PROGRAM_CARD_WIDTH = "280px"


def program_card(p: Any, *, width: str = "100%", show_pill: bool = True) -> rx.Component:
    """Surface card: name, one line of description, weeks · days · level. A
    program for the user's path carries a quiet "For your path" pill."""
    return rx.link(
        rx.vstack(
            rx.hstack(rx.cond(p["recommended"] != "", pill("For your path")) if show_pill else rx.fragment(),
                      rx.cond(p["following"] != "", pill("Following", accent=False)),
                      spacing="2", min_height=t.space(24), align="center"),
            # Two lines, then an ellipsis: a program's name is its whole pitch.
            text(p["name"], t.TITLE, max_width="100%", class_name="ma-clamp-2"),
            text(p["description"], t.BODY, t.TEXT_2, overflow="hidden", text_overflow="ellipsis",
                 white_space="nowrap", max_width="100%"),
            text(p["meta"], t.CAPTION, t.TEXT_2),
            spacing="2", align="start", width="100%", background=t.SURFACE, border_radius=t.RADIUS,
            padding=t.CARD_PADDING, class_name="ma-press ma-program-card",
            custom_attrs={"data-program": p["slug"]},
        ),
        href=f"/library/program/{p['slug']}", underline="none", width=width, min_width=width, flex_shrink="0",
    )


def program_shelf(items: Any) -> rx.Component:
    """Recommended programs, scrolling sideways inside their own row."""
    return rx.hstack(
        rx.foreach(items, lambda p: program_card(p, width=PROGRAM_CARD_WIDTH)),
        spacing="3", width="100%", overflow_x="auto", flex_wrap="nowrap", padding_bottom=t.space(4),
        class_name="ma-scroll-x ma-shelf ma-bleed",
    )


def workout_card(w: Any) -> rx.Component:
    """A list row: name, then duration · exercises · equipment."""
    return list_row(w["name"], f"{w['meta']} · {w['gear']}", chevron=True, href=f"/library/workout/{w['slug']}",
                    class_name="ma-workout-card", custom_attrs={"data-workout": w["slug"]})


def path_chip(label: str, *, selected: Any, own: Any, href: str) -> rx.Component:
    """A training path. The user's own is marked with a dot."""
    return rx.link(
        rx.hstack(
            rx.cond(own, rx.box(width="6px", height="6px", border_radius=t.RADIUS_PILL,
                                background=when(selected, t.ACCENT, t.TEXT_2),
                                custom_attrs={"aria-label": "Your path"})),
            rx.text(label, margin="0", **t.LABEL),
            spacing="2", align="center", padding=f"0 {t.space(16)}", min_height=t.TOUCH,
            border_radius=t.RADIUS_PILL, background=when(selected, t.ACCENT_SOFT, t.SURFACE_2),
            color=when(selected, t.ACCENT, t.TEXT), white_space="nowrap", class_name="ma-press",
        ),
        href=href, underline="none", flex_shrink="0",
        custom_attrs={"aria-current": rx.cond(selected, "page", "false")},
    )


def schedule_grid(weeks: Any) -> rx.Component:
    """Weeks as rows, days 1-7 as cells. A workout day shows its short name
    and opens it; a rest day is muted. Scrolls sideways in its own box."""
    def cell(d: Any) -> rx.Component:
        body = rx.center(
            text(d["label"], t.CAPTION, rx.cond(d["slug"] != "", t.TEXT, t.TEXT_3), text_align="center",
                 overflow="hidden", text_overflow="ellipsis", max_width="100%"),
            width="76px", min_width="76px", height=t.TOUCH, border_radius=t.RADIUS, padding=f"0 {t.space(4)}",
            background=rx.cond(d["slug"] != "", t.SURFACE_2, "transparent"),
            border=rx.cond(d["slug"] != "", "none", t.HAIRLINE),
        )
        return rx.cond(d["slug"] != "",
                       rx.link(body, href=f"/library/workout/{d['slug']}", underline="none", class_name="ma-press"),
                       body)

    header = rx.hstack(
        rx.box(width="40px", min_width="40px"),
        *[rx.center(text(f"Day {n}", t.CAPTION, t.TEXT_2), width="76px", min_width="76px") for n in range(1, 8)],
        spacing="1",
    )
    body = rx.foreach(
        weeks,
        lambda week, i: rx.hstack(
            rx.center(text(f"W{i + 1}", t.CAPTION, t.TEXT_2), width="40px", min_width="40px"),
            rx.foreach(week, cell), spacing="1", align="center",
        ),
    )
    return rx.box(
        rx.vstack(header, body, spacing="1", width="max-content"),
        width="100%", overflow_x="auto", class_name="ma-scroll-x ma-schedule ma-bleed",
        custom_attrs={"role": "region", "aria-label": "Program schedule"},
    )
