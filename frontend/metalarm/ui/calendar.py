"""The week strip and the month calendar."""

from __future__ import annotations

from typing import Any

import reflex as rx
from reflex.vars import Var

from metalarm import theme as t
from metalarm.ui.primitives import text, when


def _day(letter: Any, number_: Any, *, today: Any, trained: Any, selected: Any = False,
         on_click: Any = None) -> rx.Component:
    """A day: its letter, its number (circled when selected), a dot when trained."""
    return rx.vstack(
        text(letter, t.CAPTION, when(today, t.TEXT, t.TEXT_2)),
        rx.center(text(number_, t.LABEL, t.TEXT), width="40px", height="40px", border_radius=t.RADIUS_PILL,
                  background=when(selected, t.SURFACE_2, "transparent"),
                  border=when(today, f"1px solid {t.TEXT_2}", "1px solid transparent")),
        rx.box(width="4px", height="4px", border_radius=t.RADIUS_PILL,
               background=when(trained, t.ACCENT, "transparent")),
        spacing="1", align="center", cursor="pointer", on_click=on_click, flex="1", min_height=t.TOUCH,
        class_name="ma-press",
    )


def week_strip(days: Any, selected: Any = "", on_select=None) -> rx.Component:
    """M-S, today outlined, the chosen day filled, a dot on each day trained.
    `days`: [{letter, number, today, trained, iso}]."""
    return rx.hstack(
        rx.foreach(days, lambda d: _day(d["letter"], d["number"], today=d["today"] != "",
                                        trained=d["trained"] != "", selected=d["iso"] == selected,
                                        on_click=on_select(d["iso"]) if on_select else None)),
        width="100%", justify="between")


def month_calendar(title: Any, weeks: Any) -> rx.Component:
    """A month grid: days trained marked in accent-soft. `weeks`: rows of
    {number, trained, today, in_month}."""
    def cell(d: dict) -> rx.Component:
        trained = d["trained"] != ""
        return rx.center(
            text(d["number"], t.LABEL, when(d["in_month"] != "", when(trained, t.ACCENT, t.TEXT_2), t.TEXT_3)),
            height="36px", border_radius=t.RADIUS_PILL,
            background=when(trained, t.ACCENT_SOFT, "transparent"),
            border=when(d["today"] != "", f"1px solid {t.TEXT_2}", "1px solid transparent"),
        )
    header = rx.grid(*[text(c, t.CAPTION, t.TEXT_2, text_align="center") for c in "MTWTFSS"],
                     columns="7", width="100%")
    body = rx.grid(rx.foreach(weeks, lambda week: rx.foreach(week, cell)), columns="7",
                   row_gap=t.space(4), width="100%")
    head = (text(title, t.LABEL) if (isinstance(title, Var) or title) else rx.fragment())
    return rx.vstack(head, header, body, spacing="2", width="100%")
