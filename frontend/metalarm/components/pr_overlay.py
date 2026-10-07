"""The PR moment - the third of four celebration tiers (set logged < quest
complete < PR < rank-up). Not a toast: a card over the workout, in record
gold, with what was beaten and the bonus paid.

Shares the level-up reveal's keyframes (components/level_up.py: lf-veil,
lf-card, lf-line), so the same rules hold: transform and opacity only,
reduced motion collapses it to a fade. Include level_up.keyframes() on any
page that renders it. Tap anywhere to dismiss - it never traps a lifter
mid-set.

It shows only what the API said: the record the bonus was paid for, what it
beat, and the points awarded.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import PrView

_CSS = f"""
@keyframes ma-pr-ring {{
  0%   {{ opacity: 0.7; transform: scale(0.75); }}
  100% {{ opacity: 0;   transform: scale(1.35); }}
}}
.ma-pr-ring {{
  border: 2px solid {t.PR_GOLD};
  animation: ma-pr-ring 1300ms ease-out 120ms 3 both;
}}
@media (prefers-reduced-motion: reduce) {{
  .ma-pr-ring {{ display: none; }}
}}
"""


def _other_record(view: PrView) -> rx.Component:
    return rx.hstack(
        rx.text(view.record_label, color=t.TEXT_SECONDARY, **t.FOOTNOTE),
        rx.text(view.headline, color=t.TEXT_PRIMARY, **{**t.FOOTNOTE, **t.TABULAR}),
        spacing="2", align="center",
    )


def pr_overlay() -> rx.Component:
    pr = WorkoutState.pr
    return rx.cond(
        WorkoutState.show_pr,
        rx.box(
            rx.el.style(_CSS),
            rx.center(
                rx.vstack(
                    rx.hstack(rx.icon("medal", size=18, color=t.PR_GOLD),
                              rx.text("PERSONAL RECORD", color=t.PR_GOLD, **t.CAPTION),
                              spacing="2", align="center", class_name="lf-line"),
                    rx.box(
                        rx.box(class_name="ma-pr-ring", position="absolute", width="150px", height="150px",
                               border_radius=t.RADIUS_PILL, pointer_events="none"),
                        rx.vstack(
                            rx.text(pr.headline, color=t.PR_GOLD, text_align="center",
                                    **{**t.DISPLAY_NUMBER, **t.NUMERAL_GAME}),
                            rx.text(pr.record_label, color=t.TEXT_SECONDARY, **t.FOOTNOTE),
                            spacing="1", align="center",
                        ),
                        position="relative", display="flex", align_items="center", justify_content="center",
                        min_width="150px", min_height="150px",
                    ),
                    rx.text(pr.exercise_name, color=t.TEXT_PRIMARY, text_align="center", class_name="lf-line",
                            **t.TITLE_2),
                    # The line that follows the record - the same words the
                    # iPhone app shows for this set.
                    rx.text(pr.motivation, color=t.TEXT_SECONDARY, text_align="center", class_name="lf-line",
                            **t.SUBHEAD),
                    rx.cond(
                        pr.delta != "",
                        rx.box(rx.text(pr.delta, color=t.PR_GOLD, **{**t.HEADLINE, **t.TABULAR}),
                               padding=f"{t.space(1)} {t.space(3)}", border_radius=t.RADIUS_PILL,
                               background=t.alpha(t.PR_GOLD, 0.14), class_name="lf-line"),
                    ),
                    rx.cond(
                        WorkoutState.has_pr_others,
                        rx.vstack(rx.text("Also broken", color=t.TEXT_SECONDARY, **t.CAPTION),
                                  rx.foreach(WorkoutState.pr_others, _other_record),
                                  spacing="1", align="center", class_name="lf-line"),
                    ),
                    rx.cond(
                        WorkoutState.pr_points > 0,
                        rx.text(f"+{WorkoutState.pr_points} PR BONUS", color=t.STREAK_ORANGE, class_name="lf-line",
                                **{**t.HEADLINE, **t.NUMERAL_GAME}),
                    ),
                    rx.el.button(
                        "KEEP LIFTING",
                        on_click=WorkoutState.dismiss_pr,
                        background=t.PR_GOLD, color=t.ON_LIGHT, border="none", border_radius=t.RADIUS_PILL,
                        min_height=t.TOUCH_MIN, padding=f"0 {t.space(6)}", cursor="pointer", class_name="lf-line",
                        **t.HEADLINE,
                    ),
                    spacing="4", align="center", class_name="lf-card",
                    padding=f"{t.space(8)} {t.space(6)}", background=t.SURFACE_1,
                    border_radius=t.RADIUS_CARD, max_width="92vw", overflow="hidden",
                ),
                width="100%", height="100%",
            ),
            class_name="lf-veil",
            position="fixed", top="0", left="0", width="100vw", height="100vh",
            background=t.SCRIM, backdrop_filter=t.BLUR, z_index="110",
            on_click=WorkoutState.dismiss_pr,
        ),
    )
