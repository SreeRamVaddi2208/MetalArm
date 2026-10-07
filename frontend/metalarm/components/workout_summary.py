"""The workout summary (overhaul 7.6): what the workout was, what it earned,
what it broke, and what it worked - then Save as routine, Share, Done.

Every number comes from the finish response; the body map's intensities are
the server's `muscles_worked`. A rank-up plays after this screen, as the
level-up overlay already does.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.state.workout import WorkoutState
from metalarm.ui.body_map import body_map
from metalarm.ui.primitives import card, primary_button, secondary_button, section_header, segmented_control, text
from metalarm.workout_models import AwardLine, PrView, QuestLine


def _stat(label: str, value, color: str = t.TEXT_PRIMARY) -> rx.Component:
    return rx.vstack(
        text(label, t.CAPTION, t.TEXT_SECONDARY),
        text(value, t.TITLE_2, color, **t.TABULAR),
        spacing="1",
        align="start",
        min_width="0",
    )


def _row(left: rx.Component, right: rx.Component) -> rx.Component:
    return rx.hstack(left, rx.spacer(), right, width="100%", align="center", spacing="2",
                     min_height=t.TOUCH_MIN, border_bottom=t.HAIRLINE)


def _award(line: AwardLine) -> rx.Component:
    return _row(text(line.label, t.SUBHEAD, t.TEXT_SECONDARY),
                text(line.points_label, t.HEADLINE, rx.cond(line.negative, t.DANGER_RED, t.TEXT_PRIMARY),
                     **t.NUMERAL_GAME))


def _record(view: PrView) -> rx.Component:
    return _row(
        rx.hstack(
            rx.icon("medal", size=18, color=t.PR_GOLD),
            rx.vstack(text(view.exercise_name, t.SUBHEAD), text(view.record_label, t.FOOTNOTE, t.TEXT_SECONDARY),
                      spacing="0", align="start", min_width="0"),
            spacing="2", align="center", min_width="0",
        ),
        rx.vstack(text(view.headline, t.HEADLINE, **t.TABULAR),
                  rx.cond(view.delta != "", text(view.delta, t.FOOTNOTE, t.PR_GOLD)),
                  spacing="0", align="end"),
    )


def _quest(line: QuestLine) -> rx.Component:
    return _row(
        text(line.title, t.SUBHEAD, rx.cond(line.done, t.TEXT_PRIMARY, t.TEXT_SECONDARY)),
        rx.cond(line.done, text(line.reward_label, t.HEADLINE, t.STREAK_ORANGE, **t.NUMERAL_GAME),
                text(line.progress_label, t.FOOTNOTE, t.TEXT_SECONDARY, **t.TABULAR)),
    )


def summary_view() -> rx.Component:
    s = WorkoutState.summary
    return rx.vstack(
        rx.vstack(
            text("Workout complete", t.CAPTION, t.TEXT_SECONDARY),
            text(s.title, t.TITLE_1),
            rx.hstack(
                text(f"+{s.points_credited}", t.DISPLAY_NUMBER, **t.NUMERAL_GAME),
                text("points", t.SUBHEAD, t.TEXT_SECONDARY),
                align="baseline", spacing="2",
            ),
            rx.grid(
                _stat("Duration", s.duration_label),
                _stat("Volume", s.volume_label),
                _stat("Sets", s.sets_label),
                _stat("Records", s.pr_count.to_string(), rx.cond(s.pr_count > 0, t.PR_GOLD, t.TEXT_PRIMARY)),
                columns="2",
                gap=t.space(4),
                width="100%",
                padding_top=t.space(2),
            ),
            spacing="2",
            width="100%",
            align="start",
            background=t.SUMMARY_GRADIENT,
            border_radius=t.RADIUS_CARD,
            padding=t.space(5),
        ),
        rx.cond(s.qualified_note != "", text(s.qualified_note, t.FOOTNOTE, t.STREAK_ORANGE)),
        rx.cond(
            WorkoutState.summary_muscle_names.length() > 0,
            card(
                section_header("Muscles worked"),
                body_map(WorkoutState.summary_muscles, size="200px"),
                text(WorkoutState.summary_muscle_names.join(" · "), t.FOOTNOTE, t.TEXT_SECONDARY,
                     text_align="center", width="100%"),
            ),
        ),
        rx.cond(s.prs.length() > 0, card(section_header("Records"), rx.foreach(s.prs, _record))),
        card(section_header("Points"), rx.foreach(s.lines, _award)),
        rx.cond(s.quests.length() > 0, card(section_header("Quests"), rx.foreach(s.quests, _quest))),
        card(
            rx.hstack(
                rx.icon("flame", size=22, color=rx.cond(s.streak.weeks > 0, t.STREAK_ORANGE, t.TEXT_TERTIARY)),
                rx.vstack(text(s.streak.label, t.HEADLINE), text(s.streak.sub, t.FOOTNOTE, t.TEXT_SECONDARY),
                          spacing="0", align="start"),
                spacing="3", align="center",
            ),
        ),
        rx.vstack(
            text("Who can see this", t.FOOTNOTE, t.TEXT_SECONDARY),
            segmented_control(["Public", "Followers", "Only me"],
                              rx.match(WorkoutState.summary_visibility, ("public", "Public"),
                                       ("private", "Only me"), "Followers"),
                              WorkoutState.set_summary_visibility),
            spacing="1", width="100%",
        ),
        rx.vstack(
            secondary_button(
                rx.cond(WorkoutState.summary_saved != "", "Saved to your Library", "Save as routine"),
                WorkoutState.save_as_routine,
                icon="bookmark-plus",
                disabled=WorkoutState.summary_saved != "",
                width="100%",
            ),
            rx.hstack(
                secondary_button("Share", WorkoutState.share_card, icon="share", flex="1"),
                primary_button("Done", WorkoutState.close_summary, flex="1"),
                width="100%", spacing="2",
            ),
            width="100%",
            spacing="2",
        ),
        spacing="3",
        width="100%",
    )
