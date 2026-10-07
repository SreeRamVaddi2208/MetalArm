"""The workout summary: what the workout was, what it earned, what it broke.

Every number comes from the finish response; the body map's intensities are
the server's `muscles_worked`. A rank-up plays after this screen, as the
level-up overlay already does. One primary: Done.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.state.workout import WorkoutState
from metalarm.ui.body_map import body_map
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import (
    button,
    icon_button,
    list_row,
    number,
    pill,
    rows,
    section,
    segmented,
    stat_group,
    stat_tile,
    text,
)
from metalarm.workout_models import AwardLine, PrView, QuestLine


def _award(line: AwardLine) -> rx.Component:
    return list_row(line.label, trailing=text(line.points_label, t.BODY, rx.cond(line.negative, t.DANGER, t.TEXT),
                                              **t.TABULAR))


def _record(view: PrView) -> rx.Component:
    return rx.box(
        list_row(
            view.exercise_name, view.record_label,
            leading=pill("PR"),
            trailing=rx.vstack(text(view.headline, t.BODY, **t.TABULAR),
                               rx.cond(view.delta != "", text(view.delta, t.CAPTION, t.TEXT_2)),
                               spacing="0", align="end"),
        ),
        background=t.ACCENT_SOFT, border_radius=t.RADIUS, padding_x=t.space(12), width="100%",
        class_name="ma-pr-row",
    )


def _quest(line: QuestLine) -> rx.Component:
    return list_row(line.title, title_color=rx.cond(line.done, t.TEXT, t.TEXT_2),
                    trailing=rx.cond(line.done, text(line.reward_label, t.BODY, **t.TABULAR),
                                     text(line.progress_label, t.CAPTION, t.TEXT_2, **t.TABULAR)))


def summary_view() -> rx.Component:
    s = WorkoutState.summary
    return rx.vstack(
        top_bar("Workout complete", large=True,
                trailing=icon_button("share", "Share", on_click=WorkoutState.share_card)),
        text(s.title, t.BODY, t.TEXT_2, margin_top=f"-{t.space(16)}"),
        stat_group(stat_tile(s.duration_label, "Duration"), stat_tile(s.volume_label, "Volume"),
                   stat_tile(s.sets_label, "Sets")),
        rx.cond(s.prs.length() > 0, section("Records", rx.vstack(rx.foreach(s.prs, _record), spacing="2",
                                                                 width="100%"))),
        section(
            "Points",
            rows(rx.foreach(s.lines, _award)),
            rx.hstack(text("Total", t.BODY, t.TEXT_2), rx.spacer(),
                      number(f"+{s.points_credited}", style=t.DISPLAY, color=t.ACCENT),
                      width="100%", align="baseline", class_name="ma-points-total"),
            rx.cond(s.qualified_note != "", text(s.qualified_note, t.CAPTION, t.TEXT_2)),
        ),
        rows(list_row(s.streak.label, s.streak.sub,
                      leading=rx.icon("flame", size=20, stroke_width=1.75,
                                      color=rx.cond(s.streak.weeks > 0, t.TEXT, t.TEXT_3)))),
        rx.cond(s.quests.length() > 0, section("Quests", rows(rx.foreach(s.quests, _quest)))),
        rx.cond(
            WorkoutState.summary_muscle_names.length() > 0,
            section("Muscles worked",
                    rx.center(body_map(WorkoutState.summary_muscles, size="180px"), width="100%"),
                    text(WorkoutState.summary_muscle_names.join(" · "), t.CAPTION, t.TEXT_2,
                         text_align="center", width="100%")),
        ),
        section(
            "Who can see this",
            segmented(["Public", "Followers", "Only me"],
                      rx.match(WorkoutState.summary_visibility, ("public", "Public"), ("private", "Only me"),
                               "Followers"),
                      WorkoutState.set_summary_visibility),
        ),
        button(rx.cond(WorkoutState.summary_saved != "", "Saved to your routines", "Save as routine"),
               WorkoutState.save_as_routine, variant="secondary", icon="bookmark-plus",
               disabled=WorkoutState.summary_saved != "", full=True),
        spacing="6", width="100%", class_name="ma-summary",
    )


def summary_done() -> rx.Component:
    """The summary's one primary, pinned above the tab bar."""
    return button("Done", WorkoutState.close_summary, full=True)
