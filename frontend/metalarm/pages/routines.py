"""Routines: reusable workout templates."""

import reflex as rx

from metalarm import theme
from metalarm.components.exercise_picker import picker_dialog
from metalarm.components.layout import error_banner, notice_banner, section_heading, shell
from metalarm.components.workout import FIELD_BG, button, empty
from metalarm.state.auth import AuthState
from metalarm.state.picker import PickerState
from metalarm.state.routines import RoutineState
from metalarm.workout_models import RoutineItem, RoutineSlot


def _text_input(placeholder: str, value, on_change, **overrides) -> rx.Component:
    style = {
        "width": "100%",
        "size": "3",
        "background": FIELD_BG,
        "color": theme.TEXT,
    }
    style.update(overrides)
    return rx.input(placeholder=placeholder, value=value, on_change=on_change, **style)


def _small_field(label, value, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, **{**theme.LABEL_STYLE, "font_size": "0.6rem"}),
        rx.input(
            value=value,
            on_change=on_change,
            type="number",
            size="2",
            width="100%",
            background=FIELD_BG,
            color=theme.TEXT,
        ),
        spacing="1",
        flex="1",
        min_width="64px",
    )


def _icon_button(label: str, on_click, hover: str = theme.TEXT) -> rx.Component:
    return rx.button(
        label,
        on_click=on_click,
        background="transparent",
        color=theme.FAINT,
        border=f"1px solid {theme.BORDER}",
        border_radius="8px",
        width="34px",
        height="34px",
        padding="0",
        cursor="pointer",
        _hover={"color": hover, "border_color": hover},
    )


def _slot_row(slot: RoutineSlot, index) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(slot.name, color=theme.TEXT, font_weight="700", font_size="0.9rem"),
                rx.text(slot.muscles_label, color=theme.FAINT, font_size="0.6rem", letter_spacing="0.1em"),
                spacing="1",
                align="start",
                min_width="0",
            ),
            rx.spacer(),
            _icon_button("↑", RoutineState.move_slot(index, -1)),
            _icon_button("↓", RoutineState.move_slot(index, 1)),
            _icon_button("✕", RoutineState.remove_slot(index), theme.DANGER),
            width="100%",
            align="center",
            spacing="2",
        ),
        rx.hstack(
            _small_field("SETS", slot.target_sets, lambda v: RoutineState.set_slot_sets(index, v)),
            _small_field("REPS", slot.target_reps, lambda v: RoutineState.set_slot_reps(index, v)),
            _small_field(f"WEIGHT ({AuthState.weight_unit})", slot.target_weight,
                         lambda v: RoutineState.set_slot_weight(index, v)),
            _small_field("REST (S)", slot.rest_seconds, lambda v: RoutineState.set_slot_rest(index, v)),
            spacing="2",
            width="100%",
            flex_wrap="wrap",
        ),
        spacing="2",
        width="100%",
        padding="0.85rem",
        background=FIELD_BG,
        border=f"1px solid {theme.BORDER}",
        border_radius="12px",
    )


def editor() -> rx.Component:
    return rx.vstack(
        rx.text(RoutineState.form_title, **{**theme.LABEL_STYLE, "color": theme.ACCENT}),
        _text_input("Routine name, e.g. Push day", RoutineState.form_name, RoutineState.set_form_name),
        _text_input("Notes (optional)", RoutineState.form_notes, RoutineState.set_form_notes),
        rx.cond(
            RoutineState.has_slots,
            rx.vstack(rx.foreach(RoutineState.slots, _slot_row), spacing="2", width="100%"),
            empty("Add the exercises this routine runs through, in order."),
        ),
        rx.button(
            "+ ADD EXERCISE",
            on_click=PickerState.open_for("routine"),
            width="100%",
            height="48px",
            background="transparent",
            color=theme.ACCENT,
            border=f"1px dashed {theme.ACCENT}88",
            border_radius="12px",
            font_weight="800",
            letter_spacing="0.14em",
            font_size="0.74rem",
            cursor="pointer",
        ),
        rx.hstack(
            button("SAVE ROUTINE", RoutineState.save, flex="1", height="48px"),
            button("CANCEL", RoutineState.cancel, color=theme.MUTED, solid=False, height="48px"),
            width="100%",
            spacing="2",
        ),
        spacing="3",
        **theme.panel(box_shadow=theme.glow(theme.ACCENT, "50px")),
    )


def _routine_card(routine: RoutineItem) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(routine.name, color=theme.TEXT, font_weight="800", font_size="1rem"),
                rx.text(routine.summary_label, color=theme.FAINT, font_size="0.76rem"),
                rx.cond(routine.notes != "", rx.text(routine.notes, color=theme.MUTED, font_size="0.76rem")),
                spacing="1",
                align="start",
                min_width="0",
            ),
            rx.spacer(),
            button("START", RoutineState.start(routine.id), height="44px", flex_shrink="0"),
            width="100%",
            align="center",
            spacing="3",
        ),
        rx.hstack(
            button("EDIT", RoutineState.edit(routine.id), color=theme.MUTED, solid=False,
                   font_size="0.64rem", padding="0.4rem 0.75rem"),
            button("DELETE", RoutineState.delete(routine.id), color=theme.DANGER, solid=False,
                   font_size="0.64rem", padding="0.4rem 0.75rem"),
            spacing="2",
        ),
        spacing="3",
        **theme.panel(padding="1.1rem"),
    )


def routines_page() -> rx.Component:
    return shell(
        picker_dialog(),
        rx.vstack(
            section_heading(
                "ROUTINES",
                button("+ NEW ROUTINE", RoutineState.new_routine, color=theme.ACCENT, solid=False,
                       font_size="0.68rem", padding="0.45rem 0.8rem"),
            ),
            error_banner(RoutineState.error),
            notice_banner(RoutineState.notice),
            rx.cond(RoutineState.editing, editor()),
            rx.cond(
                RoutineState.has_routines,
                rx.vstack(rx.foreach(RoutineState.routines, _routine_card), spacing="3", width="100%"),
                rx.cond(
                    RoutineState.loading,
                    rx.center(rx.spinner(), width="100%"),
                    empty("No routines yet. A routine is a saved list of exercises with targets - start any workout from it in one tap."),
                ),
            ),
            spacing="4",
            width="100%",
            max_width="760px",
            margin="0 auto",
        ),
    )
