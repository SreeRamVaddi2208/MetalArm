"""Ready-made workouts: three cards, and the plan behind each one.

Athletic, powerlifting and bodybuilding, offered where a workout begins. Picking
one opens its plan with a demo beside it, so the movements are seen before
anything is committed to; Start loads the whole plan in one call
(POST /workouts/sessions {preset_slug}).
"""

import reflex as rx

from metalarm import theme
from metalarm.components.exercise_demo import exercise_demo
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import PresetSlot, WorkoutPreset


def _card(preset: WorkoutPreset) -> rx.Component:
    return rx.hstack(
        exercise_demo(preset.exercises[0].media_url, preset.exercises[0].name, size="56px", radius="10px"),
        rx.vstack(
            rx.text(
                preset.category_label,
                color=theme.ACCENT,
                font_size="0.62rem",
                font_weight="800",
                letter_spacing="0.12em",
            ),
            rx.text(preset.name, color=theme.TEXT, font_weight="800", font_size="0.95rem"),
            rx.text(preset.length_label, color=theme.FAINT, font_size="0.74rem"),
            spacing="1",
            align="start",
            min_width="0",
        ),
        rx.spacer(),
        rx.icon("chevron-right", size=16, color=theme.FAINT),
        on_click=WorkoutState.choose_preset(preset.slug),
        cursor="pointer",
        width="100%",
        align="center",
        spacing="3",
        padding="0.75rem 1rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER}",
        border_radius="12px",
        class_name="ma-preset-card",
        custom_attrs={"data-preset": preset.slug},
    )


def preset_cards() -> rx.Component:
    """The three styles, shown under the start button."""
    return rx.cond(
        WorkoutState.has_presets,
        rx.vstack(
            rx.text("OR START A READY-MADE WORKOUT", **theme.LABEL_STYLE),
            rx.foreach(WorkoutState.presets, _card),
            spacing="2",
            width="100%",
        ),
    )


def _slot_row(slot: PresetSlot) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(
                slot.name,
                color=rx.cond(WorkoutState.demo_exercise.exercise_id == slot.exercise_id, theme.ACCENT, theme.TEXT),
                font_weight="700",
                font_size="0.86rem",
            ),
            rx.text(slot.plan, color=theme.MUTED, font_size="0.72rem"),
            spacing="1",
            align="start",
            min_width="0",
        ),
        rx.spacer(),
        rx.cond(slot.media_url != "", rx.icon("circle-play", size=15, color=theme.MUTED)),
        on_click=WorkoutState.show_demo(slot.exercise_id),
        cursor="pointer",
        width="100%",
        align="center",
        spacing="3",
        padding="0.7rem 0.9rem",
        border_bottom=f"1px solid {theme.BORDER}",
        class_name="ma-preset-slot",
        custom_attrs={"data-slot": slot.name},
    )


def preset_dialog() -> rx.Component:
    """The chosen workout: what it is, and what each movement looks like."""
    preset = WorkoutState.chosen_preset
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title(
                    f"{preset.category_label} · {preset.name}",
                    color=theme.TEXT,
                    font_size="1rem",
                    margin="0",
                ),
                rx.text(preset.summary, color=theme.MUTED, font_size="0.8rem"),
                rx.hstack(
                    exercise_demo(
                        WorkoutState.demo_exercise.media_url,
                        WorkoutState.demo_exercise.name,
                        size="120px",
                        radius="12px",
                    ),
                    rx.vstack(
                        rx.text(WorkoutState.demo_exercise.name, color=theme.TEXT, font_weight="800"),
                        rx.text(
                            WorkoutState.demo_exercise.muscles_label,
                            color=theme.MUTED,
                            font_size="0.72rem",
                        ),
                        rx.text(
                            WorkoutState.demo_exercise.plan,
                            color=theme.ACCENT,
                            font_size="0.76rem",
                            font_weight="700",
                        ),
                        rx.text(
                            "Pick a movement below to see it.",
                            color=theme.FAINT,
                            font_size="0.68rem",
                        ),
                        spacing="1",
                        align="start",
                        min_width="0",
                    ),
                    spacing="3",
                    align="start",
                    width="100%",
                    padding="0.75rem",
                    background=theme.FIELD,
                    border=f"1px solid {theme.BORDER}",
                    border_radius="12px",
                    class_name="ma-preset-demo",
                ),
                rx.box(
                    rx.foreach(preset.exercises, _slot_row),
                    width="100%",
                    background=theme.FIELD,
                    border=f"1px solid {theme.BORDER}",
                    border_radius="12px",
                    overflow="hidden",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "CANCEL",
                            on_click=WorkoutState.close_preset,
                            background="transparent",
                            color=theme.MUTED,
                            border=f"1px solid {theme.BORDER}",
                            border_radius="10px",
                            height="44px",
                            cursor="pointer",
                        )
                    ),
                    rx.button(
                        "START THIS WORKOUT",
                        on_click=WorkoutState.start_preset(preset.slug),
                        background=theme.ACCENT,
                        color=theme.ON_ACCENT,
                        border="none",
                        border_radius="10px",
                        height="44px",
                        font_weight="800",
                        letter_spacing="0.1em",
                        font_size="0.78rem",
                        flex="1",
                        cursor="pointer",
                        class_name="ma-preset-start",
                    ),
                    spacing="3",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            background=theme.PANEL,
            border=f"1px solid {theme.BORDER_HI}",
            border_radius="16px",
            max_width="460px",
        ),
        open=WorkoutState.open_preset != "",
        on_open_change=WorkoutState.close_preset,
    )
