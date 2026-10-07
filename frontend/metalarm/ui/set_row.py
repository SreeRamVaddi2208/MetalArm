"""The workout's set rows.

A logged set is one calm line: its number (or W / D / F), what was lifted,
a PR pill if it was one, and an accent check. The set being entered is the
entry panel: weight and reps as large steppers, last time's values as ghosts
in text-3, and the screen's one accent action - Log set - under them.
"""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t
from metalarm.ui.primitives import button, pill, stepper, text, when

TYPE_LETTER = {"warmup": "W", "drop": "D", "failure": "F"}


def _badge(number: Any, set_type: Any) -> Any:
    return rx.match(set_type, ("warmup", "W"), ("drop", "D"), ("failure", "F"), number)


def done_row(number: Any, set_type: Any, line: Any, *, pr: Any = False, on_click: Any = None,
             flash: Any = False) -> rx.Component:
    """A logged set. Tap it for its options (edit, type, RPE, delete)."""
    return rx.hstack(
        text(_badge(number, set_type), t.LABEL, t.TEXT_2, width="24px", text_align="center"),
        text(line, t.BODY, t.TEXT_2, flex="1", min_width="0"),
        rx.cond(pr, pill("PR")),
        rx.icon("check", size=20, stroke_width=2, color=t.ACCENT),
        width="100%", align="center", spacing="3", min_height=t.TOUCH, padding_x=t.space(8),
        border_radius=t.RADIUS, cursor="pointer", on_click=on_click,
        background=when(flash, t.ACCENT_SOFT, "transparent"),
        transition=f"background {t.BASE} {t.EASE}",
        class_name="ma-done-row ma-press",
        custom_attrs={"role": "button", "aria-label": "Edit set"},
    )


def entry_panel(number: Any, set_type: Any, *, weight: Any, reps: Any, unit: Any, ghost_weight: Any,
                ghost_reps: Any, on_weight: Any, on_reps: Any, on_weight_minus: Any, on_weight_plus: Any,
                on_reps_minus: Any, on_reps_plus: Any, on_log: Any, on_type: Any, busy: Any = False,
                **attrs) -> rx.Component:
    """The next set: two steppers and Log set."""
    return rx.vstack(
        rx.hstack(
            rx.hstack(text(rx.cond(set_type == "normal", "Set", ""), t.LABEL, t.TEXT_2),
                      text(_badge(number, set_type), t.LABEL, when(set_type == "normal", t.TEXT_2, t.ACCENT)),
                      spacing="1", align="center", cursor="pointer", on_click=on_type, min_height=t.TOUCH, min_width=t.TOUCH,
                      custom_attrs={"role": "button", "aria-label": "Set type"}),
            rx.spacer(),
            width="100%", align="center",
        ),
        stepper(weight, on_weight, on_weight_minus, on_weight_plus, unit=unit, placeholder=ghost_weight,
                label="Weight"),
        stepper(reps, on_reps, on_reps_minus, on_reps_plus, unit="reps", placeholder=ghost_reps,
                label="Reps", mode="numeric"),
        button("Log set", on_log, icon="check", full=True, disabled=busy,
               custom_attrs={"aria-label": "Log set"}),
        spacing="3", width="100%", class_name="ma-entry", **attrs,
    )
