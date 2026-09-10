"""The PR moment - the emotional payoff of the whole workout feature.

Deliberately NOT a toast: the brief asks for "a distinct, satisfying UI
moment". It is a sibling of the level-up reveal (components/level_up.py) and
reuses its keyframes (lf-veil / lf-card / lf-line / lf-ring), so it follows
the same rules: transform and opacity only, pinned to the viewport rather than
hijacking scroll, and reduced-motion collapses it to a fade. Include
level_up.keyframes() on any page that renders it.

Its colour is the A-rank orange - distinct from the blue level-up and the gold
rank-up, so each of the three beats is recognisable at a glance.

It only ever shows what the API said: the record the PR bonus was paid for
(`bonus_awarded`), what it beat, and the points the API awarded.
"""

import reflex as rx

from metalarm import theme
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import PrView

PR_COLOR = theme.RANK_COLORS["A"]


def _other_record(view: PrView) -> rx.Component:
    return rx.hstack(
        rx.text(view.record_label, **{**theme.LABEL_STYLE, "font_size": "0.62rem"}),
        rx.text(view.headline, color=theme.TEXT, font_size="0.8rem", font_weight="700"),
        spacing="2",
        align="center",
    )


def pr_overlay() -> rx.Component:
    pr = WorkoutState.pr
    return rx.cond(
        WorkoutState.show_pr,
        rx.box(
            rx.center(
                rx.vstack(
                    rx.text(
                        "PERSONAL RECORD",
                        **{**theme.LABEL_STYLE, "color": PR_COLOR, "letter_spacing": "0.3em"},
                        class_name="lf-line",
                    ),
                    rx.box(
                        rx.box(
                            class_name="lf-ring",
                            position="absolute",
                            width="150px",
                            height="150px",
                            border_radius="50%",
                            pointer_events="none",
                            border_color=PR_COLOR,
                        ),
                        rx.vstack(
                            rx.heading(
                                pr.headline,
                                size="8",
                                color=PR_COLOR,
                                font_weight="900",
                                line_height="1",
                                text_align="center",
                            ),
                            rx.text(pr.record_label, **theme.LABEL_STYLE),
                            spacing="2",
                            align="center",
                        ),
                        position="relative",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        min_width="150px",
                        min_height="150px",
                    ),
                    rx.heading(
                        pr.exercise_name,
                        size="5",
                        color=theme.TEXT,
                        text_align="center",
                        class_name="lf-line",
                    ),
                    rx.cond(
                        pr.delta != "",
                        rx.box(
                            rx.text(
                                pr.delta,
                                color=PR_COLOR,
                                font_weight="800",
                                font_size="0.85rem",
                                letter_spacing="0.1em",
                            ),
                            padding="0.3rem 0.8rem",
                            border=f"1px solid {PR_COLOR}66",
                            border_radius="999px",
                            background=f"{PR_COLOR}14",
                            class_name="lf-line",
                        ),
                    ),
                    rx.cond(
                        WorkoutState.has_pr_others,
                        rx.vstack(
                            rx.text("ALSO BROKEN", **{**theme.LABEL_STYLE, "font_size": "0.6rem"}),
                            rx.foreach(WorkoutState.pr_others, _other_record),
                            spacing="1",
                            align="center",
                            class_name="lf-line",
                        ),
                    ),
                    rx.cond(
                        WorkoutState.pr_points > 0,
                        rx.text(
                            f"+{WorkoutState.pr_points} PR BONUS",
                            color=theme.WARNING,
                            font_weight="900",
                            letter_spacing="0.16em",
                            font_size="0.85rem",
                            class_name="lf-line",
                        ),
                    ),
                    rx.button(
                        "KEEP LIFTING",
                        on_click=WorkoutState.dismiss_pr,
                        background=PR_COLOR,
                        color="#1c0d04",
                        border="none",
                        border_radius="12px",
                        font_weight="900",
                        letter_spacing="0.14em",
                        font_size="0.8rem",
                        padding="0.8rem 1.6rem",
                        height="48px",
                        cursor="pointer",
                        class_name="lf-line",
                    ),
                    spacing="4",
                    align="center",
                    class_name="lf-card",
                    padding="2.25rem 1.75rem",
                    background=theme.PANEL,
                    border=f"1px solid {PR_COLOR}66",
                    border_radius="20px",
                    box_shadow=theme.glow(PR_COLOR, "110px"),
                    max_width="92vw",
                ),
                width="100%",
                height="100%",
            ),
            class_name="lf-veil",
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            background="rgba(12, 6, 2, 0.84)",
            backdrop_filter="blur(3px)",
            z_index="110",
            # Tap anywhere to dismiss: it must never trap a lifter mid-set.
            on_click=WorkoutState.dismiss_pr,
        ),
    )
