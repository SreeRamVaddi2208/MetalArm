"""The exercise picker dialog: search, muscle-group filter, and custom
exercise creation. Serves both the live workout and the routine editor."""

import reflex as rx

from metalarm import theme
from metalarm.components.layout import error_banner
from metalarm.state.picker import PickerState
from metalarm.workout_models import Chip, ExercisePick


def _chip(chip: Chip) -> rx.Component:
    active = PickerState.muscle == chip.value
    return rx.button(
        chip.label,
        on_click=PickerState.pick_muscle(chip.value),
        background=rx.cond(active, f"{theme.ACCENT}22", "transparent"),
        color=rx.cond(active, theme.ACCENT, theme.MUTED),
        border=rx.cond(active, f"1px solid {theme.ACCENT}", f"1px solid {theme.BORDER}"),
        border_radius="999px",
        font_size="0.62rem",
        font_weight="800",
        letter_spacing="0.1em",
        padding="0.3rem 0.65rem",
        height="auto",
        cursor="pointer",
    )


def _row(item: ExercisePick) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(item.name, color=theme.TEXT, font_weight="700", font_size="0.92rem"),
                rx.text(item.muscles_label, color=theme.FAINT, font_size="0.66rem", letter_spacing="0.08em"),
                spacing="1",
                align="start",
                min_width="0",
            ),
            rx.spacer(),
            rx.text(item.meta_label, color=theme.FAINT, font_size="0.6rem", letter_spacing="0.1em"),
            rx.text("+", color=theme.ACCENT, font_size="1.3rem", font_weight="800"),
            align="center",
            spacing="3",
            width="100%",
        ),
        on_click=PickerState.pick(item.id),
        width="100%",
        padding="0.7rem 0.8rem",
        border_radius="10px",
        border=f"1px solid {theme.BORDER}",
        background=theme.FIELD,
        cursor="pointer",
        _hover={"border_color": theme.ACCENT},
    )


def _select(items, value, on_change) -> rx.Component:
    return rx.select(items, value=value, on_change=on_change, width="100%", size="2")


def _create_form() -> rx.Component:
    return rx.vstack(
        rx.text(PickerState.create_label, color=theme.TEXT, font_weight="700", font_size="0.85rem"),
        rx.hstack(
            rx.vstack(rx.text("MUSCLE", **theme.LABEL_STYLE),
                      _select(PickerState.muscle_values, PickerState.new_muscle, PickerState.set_new_muscle),
                      spacing="1", width="100%"),
            rx.vstack(rx.text("EQUIPMENT", **theme.LABEL_STYLE),
                      _select(PickerState.equipment, PickerState.new_equipment, PickerState.set_new_equipment),
                      spacing="1", width="100%"),
            rx.vstack(rx.text("TYPE", **theme.LABEL_STYLE),
                      _select(PickerState.categories, PickerState.new_category, PickerState.set_new_category),
                      spacing="1", width="100%"),
            spacing="2",
            width="100%",
            flex_wrap="wrap",
        ),
        rx.button(
            "CREATE AND ADD",
            on_click=PickerState.create_custom,
            background=theme.ACCENT,
            color=theme.ON_ACCENT,
            border="none",
            border_radius="9px",
            font_weight="800",
            letter_spacing="0.12em",
            font_size="0.72rem",
            width="100%",
            height="42px",
            cursor="pointer",
        ),
        spacing="3",
        width="100%",
        padding="0.9rem",
        border=f"1px dashed {theme.BORDER_HI}",
        border_radius="12px",
    )


def picker_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.dialog.title(
                        "ADD EXERCISE",
                        **{**theme.LABEL_STYLE, "color": theme.ACCENT, "margin": "0"},
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button(
                            "CLOSE",
                            background="transparent",
                            color=theme.FAINT,
                            border=f"1px solid {theme.BORDER}",
                            border_radius="8px",
                            font_size="0.65rem",
                            letter_spacing="0.12em",
                            cursor="pointer",
                        )
                    ),
                    width="100%",
                    align="center",
                ),
                rx.input(
                    placeholder="Search exercises…",
                    value=PickerState.query,
                    on_change=PickerState.set_query,
                    debounce_timeout=250,
                    width="100%",
                    size="3",
                    background=theme.FIELD,
                    color=theme.TEXT,
                ),
                rx.flex(
                    rx.foreach(PickerState.muscles, _chip),
                    wrap="wrap",
                    gap="0.35rem",
                    width="100%",
                ),
                error_banner(PickerState.error),
                rx.box(
                    rx.cond(
                        PickerState.has_results,
                        rx.vstack(rx.foreach(PickerState.results, _row), spacing="2", width="100%"),
                        rx.cond(
                            PickerState.loading,
                            rx.center(rx.spinner(), width="100%", padding="1rem"),
                            rx.text("No matches.", color=theme.FAINT, font_size="0.85rem"),
                        ),
                    ),
                    max_height="42vh",
                    overflow_y="auto",
                    width="100%",
                    padding_right="0.25rem",
                ),
                rx.cond(
                    PickerState.show_create,
                    _create_form(),
                    rx.button(
                        "Can't find it? Create a custom exercise",
                        on_click=PickerState.toggle_create,
                        background="transparent",
                        color=theme.MUTED,
                        border="none",
                        font_size="0.78rem",
                        cursor="pointer",
                        text_decoration="underline",
                    ),
                ),
                spacing="3",
                width="100%",
            ),
            background=theme.PANEL,
            border=f"1px solid {theme.BORDER_HI}",
            border_radius="16px",
            max_width="560px",
            width="94vw",
        ),
        open=PickerState.is_open,
        on_open_change=PickerState.set_open,
    )
