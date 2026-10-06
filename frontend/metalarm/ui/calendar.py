"""The week strip and the month calendar."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t
from metalarm.ui.primitives import text, when


def _day(letter: Any, number_: Any, *, today: Any, trained: Any, on_click: Any = None) -> rx.Component:
    return rx.vstack(
        text(when(today, "TODAY", letter), t.CAPTION, when(today, t.TEXT_PRIMARY, t.TEXT_SECONDARY)),
        rx.center(text(number_, t.HEADLINE, when(today, t.ON_LIGHT, t.TEXT_PRIMARY), **t.TABULAR),
                  width="38px", height="38px", border_radius=t.RADIUS_PILL,
                  background=when(today, t.TEXT_PRIMARY, "transparent")),
        rx.box(width="5px", height="5px", border_radius=t.RADIUS_PILL,
               background=when(trained, t.ACCENT_BLUE, "transparent")),
        spacing="1",
        align="center",
        cursor="pointer",
        on_click=on_click,
        flex="1",
    )


def week_strip(days: list[dict] | Any, on_select=None) -> rx.Component:
    """M-S, today circled and labelled, a dot on each day trained.
    `days`: [{letter, number, today, trained, iso}]."""
    if isinstance(days, list):
        cells = [_day(d["letter"], d["number"], today=d["today"], trained=d["trained"],
                      on_click=on_select(d["iso"]) if on_select else None) for d in days]
        return rx.hstack(*cells, width="100%", justify="between")
    return rx.hstack(
        rx.foreach(days, lambda d: _day(d["letter"], d["number"], today=d["today"],
                                        trained=d["trained"],
                                        on_click=on_select(d["iso"]) if on_select else None)),
        width="100%", justify="between")


def month_calendar(title: Any, weeks: list[list[dict]] | Any) -> rx.Component:
    """A month grid: trained days filled, consecutive trained days joined into
    a run. `weeks`: rows of {number, trained, run_left, run_right, today, in_month}."""
    def cell(d: dict) -> rx.Component:
        trained = d["trained"]
        return rx.center(
            text(d["number"], t.SUBHEAD,
                 when(d["in_month"], when(trained, t.TEXT_PRIMARY, t.TEXT_SECONDARY), t.TEXT_TERTIARY),
                 **t.TABULAR),
            height="36px",
            background=when(trained, t.alpha(t.ACCENT_BLUE, 0.28), "transparent"),
            border_radius=when(trained, t.RADIUS_PILL, "0"),
            border=when(d["today"], f"1.5px solid {t.TEXT_PRIMARY}", "1.5px solid transparent"),
        )
    header = rx.grid(*[text(c, t.CAPTION, t.TEXT_SECONDARY, text_align="center")
                       for c in "MTWTFSS"], columns="7", width="100%")
    if isinstance(weeks, list):
        body = rx.grid(*[cell(d) for week in weeks for d in week], columns="7",
                       row_gap=t.space(1), width="100%")
    else:
        body = rx.grid(rx.foreach(weeks, lambda week: rx.foreach(week, cell)), columns="7",
                       row_gap=t.space(1), width="100%")
    return rx.vstack(text(title, t.HEADLINE), header, body, spacing="2", width="100%",
                     background=t.SURFACE_1, border_radius=t.RADIUS_CARD, padding=t.CARD_PADDING)
