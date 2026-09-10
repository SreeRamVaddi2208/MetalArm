"""The workout page: start, log, celebrate, finish.

One narrow column on every screen size - this page is used standing in a gym
with a phone in one hand, so width is spent on tap targets, not layout.
"""

import reflex as rx

from metalarm.components.exercise_picker import picker_dialog
from metalarm.components.layout import error_banner, shell
from metalarm.components.level_up import keyframes, level_up_overlay
from metalarm.components.pr_overlay import pr_overlay
from metalarm.components.rest_timer import rest_bar, timer_assets
from metalarm.components.workout import hud, live_view, start_view, summary_view
from metalarm.state.workout import WorkoutState


def workout_page() -> rx.Component:
    return shell(
        keyframes(),
        timer_assets(),
        level_up_overlay(),
        pr_overlay(),
        picker_dialog(),
        rest_bar(),
        rx.vstack(
            hud(),
            error_banner(WorkoutState.error),
            rx.cond(
                WorkoutState.loaded,
                rx.cond(
                    WorkoutState.show_summary,
                    summary_view(),
                    rx.cond(WorkoutState.has_session, live_view(), start_view()),
                ),
                rx.center(rx.spinner(), width="100%", padding="2rem"),
            ),
            spacing="4",
            width="100%",
            max_width="680px",
            margin="0 auto",
        ),
    )
