"""The set row of the active workout: SET (number or a W / D / F badge),
PREVIOUS (tap to copy), KG, REPS, optional RPE, and the check."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t
from metalarm.ui.primitives import text, when

TYPE_BADGE = {"warmup": "W", "drop": "D", "failure": "F"}


def _field(value: Any, on_change: Any, *, placeholder: str = "", width: str = "56px",
           mode: str = "decimal") -> rx.Component:
    return rx.el.input(
        value=value,
        on_change=on_change,
        placeholder=placeholder,
        input_mode=mode,
        width=width,
        height=t.TOUCH_MIN,
        background=t.SURFACE_2,
        color=t.TEXT_PRIMARY,
        border="none",
        border_radius=t.RADIUS_THUMB,
        text_align="center",
        **{**t.HEADLINE, **t.TABULAR},
    )


def set_header(rpe: bool = False) -> rx.Component:
    cols = ["SET", "PREVIOUS", "KG", "REPS"] + (["RPE"] if rpe else []) + [""]
    return rx.grid(*[text(c, t.CAPTION, t.TEXT_SECONDARY, text_align="center") for c in cols],
                   grid_template_columns=_columns(rpe), gap=t.space(1.5), width="100%",
                   align_items="center")


def _columns(rpe: bool) -> str:
    """SET, PREVIOUS (takes the rest), KG, REPS, [RPE], check. Fixed widths
    keep every input at least touch-sized while PREVIOUS stays readable at
    375px."""
    return " ".join(["32px", "minmax(0,1fr)", "56px", "56px"] + (["44px"] if rpe else []) + [t.TOUCH_MIN])


def set_row(number: Any, *, set_type: Any = "normal", previous: Any = "-", weight: Any = "",
            reps: Any = "", rpe: Any = None, done: Any = False, on_type: Any = None,
            on_copy: Any = None, on_weight: Any = None, on_reps: Any = None, on_rpe: Any = None,
            on_check: Any = None, pr: Any = False, points: Any = "") -> rx.Component:
    badge = rx.match(set_type, ("warmup", "W"), ("drop", "D"), ("failure", "F"), number) \
        if not isinstance(set_type, str) else TYPE_BADGE.get(set_type, number)
    badge_color = rx.match(set_type, ("warmup", t.STREAK_ORANGE), ("drop", t.ACCENT_BLUE),
                           ("failure", t.DANGER_RED), t.TEXT_PRIMARY) \
        if not isinstance(set_type, str) else {"warmup": t.STREAK_ORANGE, "drop": t.ACCENT_BLUE,
                                                "failure": t.DANGER_RED}.get(set_type, t.TEXT_PRIMARY)
    with_rpe = rpe is not None
    cells = [
        rx.center(text(badge, t.HEADLINE, badge_color, **t.TABULAR), height=t.TOUCH_MIN,
                  cursor="pointer", on_click=on_type,
                  custom_attrs={"role": "button", "aria-label": "Set type"}),
        rx.hstack(text(previous, t.SUBHEAD, t.TEXT_SECONDARY, overflow="hidden",
                       text_overflow="ellipsis", white_space="nowrap", **t.TABULAR),
                  rx.cond(pr, rx.icon("medal", size=15, color=t.PR_GOLD)) if not isinstance(pr, bool)
                  else (rx.icon("medal", size=15, color=t.PR_GOLD) if pr else rx.fragment()),
                  justify="center", align="center", spacing="1", min_width="0",
                  cursor="pointer", on_click=on_copy),
        _field(weight, on_weight),
        _field(reps, on_reps, mode="numeric"),
    ]
    if with_rpe:
        cells.append(_field(rpe, on_rpe, width="44px", placeholder="-"))
    cells.append(rx.center(
        rx.icon("check", size=20, color=when(done, t.TEXT_PRIMARY, t.TEXT_SECONDARY), stroke_width=2.5),
        width=t.TOUCH_MIN, height=t.TOUCH_MIN, border_radius=t.RADIUS_THUMB,
        background=when(done, t.RECOVERY_GREEN, t.SURFACE_2), cursor="pointer", on_click=on_check,
        custom_attrs={"role": "button", "aria-label": "Log set"},
    ))
    return rx.box(
        rx.grid(*cells, grid_template_columns=_columns(with_rpe), gap=t.space(1.5), width="100%",
                align_items="center"),
        rx.cond(points != "", rx.el.span(points, class_name="ma-points-fade", color=t.RECOVERY_GREEN,
                                         position="absolute", right=t.space(14), top=t.space(1),
                                         **t.FOOTNOTE)) if not isinstance(points, str)
        else (rx.el.span(points, class_name="ma-points-fade", color=t.RECOVERY_GREEN,
                         position="absolute", right=t.space(14), top=t.space(1), **t.FOOTNOTE)
              if points else rx.fragment()),
        position="relative",
        width="100%",
        background=when(done, t.alpha(t.RECOVERY_GREEN, 0.08), "transparent"),
        border_radius=t.RADIUS_THUMB,
    )
