"""Ready-made workouts: the plan behind each one, in a sheet.

Picking one on the Train tab opens its plan with a demo beside it, so the
movements are seen before anything is committed to; Start loads the whole
plan in one call (POST /workouts/sessions {preset_slug}).
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.exercise_demo import exercise_demo
from metalarm.state.workout import WorkoutState
from metalarm.ui.primitives import button, list_row, rows, sheet, text
from metalarm.workout_models import PresetSlot


def _slot_row(slot: PresetSlot) -> rx.Component:
    return list_row(
        slot.name, slot.plan,
        title_color=rx.cond(WorkoutState.demo_exercise.exercise_id == slot.exercise_id, t.ACCENT, t.TEXT),
        trailing=rx.cond(slot.media_url != "", rx.icon("circle-play", size=20, color=t.TEXT_2, stroke_width=1.75)),
        on_click=WorkoutState.show_demo(slot.exercise_id),
        class_name="ma-preset-slot", custom_attrs={"data-slot": slot.name},
    )


def preset_sheet() -> rx.Component:
    """The chosen workout: what it is, and what each movement looks like."""
    preset = WorkoutState.chosen_preset
    demo = WorkoutState.demo_exercise
    return sheet(
        WorkoutState.open_preset != "",
        WorkoutState.close_preset,
        text(preset.summary, t.BODY, t.TEXT_2),
        rx.hstack(
            exercise_demo(demo.media_url, demo.name, size="96px"),
            rx.vstack(text(demo.name, t.LABEL), text(demo.muscles_label, t.CAPTION, t.TEXT_2),
                      text(demo.plan, t.CAPTION, t.TEXT_2), spacing="1", align="start", min_width="0"),
            spacing="3", align="center", width="100%", class_name="ma-preset-demo",
        ),
        rows(rx.foreach(preset.exercises, _slot_row)),
        title=preset.name,
        action=button("Start this workout", WorkoutState.start_preset(preset.slug), icon="play", full=True,
                      class_name="ma-preset-start"),
    )
