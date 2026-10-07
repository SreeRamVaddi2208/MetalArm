"""Exercise detail (/exercise/<id>) and session detail (/session/<id>)."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.exercise_detail import CHARTS, TABS, ExerciseDetailState
from metalarm.state.session_detail import SessionDetailState
from metalarm.ui.body_map import body_map
from metalarm.ui.chart import line_chart
from metalarm.ui.chrome import avatar, top_bar
from metalarm.ui.primitives import (
    button,
    chip,
    chips,
    empty_state,
    icon_button,
    list_row,
    pill,
    rows,
    section,
    segmented,
    skeleton,
    stat_tile,
    text,
)
from metalarm.ui.rank_badge import rank_badge


def _set_row(row) -> rx.Component:
    """A header row (session or exercise) or a set row, from one flat list."""
    return rx.cond(
        row["kind"] == "head",
        rx.vstack(text(row["title"], t.LABEL), rx.cond(row["sub"] != "", text(row["sub"], t.CAPTION, t.TEXT_2)),
                  spacing="0", align="start", width="100%", padding_top=t.space(16)),
        rx.hstack(
            rx.center(text(row["badge"], t.CAPTION, t.TEXT_2, **t.TABULAR), width="28px", height="28px",
                      background=t.SURFACE_2, border_radius=t.RADIUS_PILL, flex_shrink="0"),
            text(row["title"], t.BODY, **t.TABULAR),
            rx.spacer(),
            rx.cond(row["pr"] != "", pill("PR")),
            width="100%", align="center", spacing="3", min_height=t.TOUCH,
        ),
    )


# ---------------------------------------------------------------------------
# Exercise detail
# ---------------------------------------------------------------------------


def _about() -> rx.Component:
    s = ExerciseDetailState
    return rx.vstack(
        rx.center(body_map(s.muscle_paths, size="180px"), width="100%"),
        text(s.muscles_label, t.CAPTION, t.TEXT_2, text_align="center", width="100%"),
        rx.cond(s.steps.length() > 0,
                section("How to",
                        rx.el.ol(rx.foreach(s.steps, lambda step: rx.el.li(text(step, t.BODY),
                                                                         padding_bottom=t.space(8))),
                                 padding_left=t.space(24), margin="0", color=t.TEXT))),
        rx.cond(s.tips.length() > 0,
                section("Tips", rx.foreach(s.tips, lambda tip: text(f"· {tip}", t.BODY, t.TEXT_2)))),
        spacing="5", width="100%",
    )


def _charts() -> rx.Component:
    s = ExerciseDetailState
    return rx.cond(
        s.series.length() > 0,
        rx.vstack(chips(*[chip(m, selected=s.chart_metric == m, on_click=s.set_chart_metric(m)) for m in CHARTS]),
                  rx.box(line_chart(s.chart), width="100%"), spacing="4", width="100%"),
        empty_state("chart-line", "Log this exercise to see your progress."),
    )


def exercise_page() -> rx.Component:
    s = ExerciseDetailState
    return shell(
        top_bar("", back="history",
                trailing=icon_button("star", rx.cond(s.favorite, "Unfavourite", "Favourite"),
                                     on_click=s.toggle_favorite, color=rx.cond(s.favorite, t.ACCENT, t.TEXT_2))),
        error_banner(s.error),
        rx.cond(
            s.loaded,
            rx.vstack(
                rx.cond(s.image != "",
                        rx.image(src=s.image, width="100%", max_height="280px", object_fit="contain",
                                 background=t.SURFACE, border_radius=t.RADIUS, alt=s.name),
                        rx.center(rx.icon("dumbbell", size=40, color=t.TEXT_3), width="100%", height="160px",
                                  background=t.SURFACE, border_radius=t.RADIUS)),
                rx.cond(s.credit != "", text(s.credit, t.CAPTION, t.TEXT_3)),
                rx.vstack(text(s.name, t.TITLE_LG), text(s.equipment, t.CAPTION, t.TEXT_2,
                                                         text_transform="capitalize"),
                          spacing="1", align="start", width="100%"),
                segmented(TABS, s.tab, s.set_tab),
                rx.match(
                    s.tab,
                    ("History", rx.cond(s.history_rows.length() > 0,
                                        rx.vstack(rx.foreach(s.history_rows, _set_row), spacing="0", width="100%"),
                                        empty_state("history", "Sets you log appear here, by workout."))),
                    ("Charts", _charts()),
                    ("Records", rx.cond(s.records.length() > 0,
                                        rows(rx.foreach(s.records, lambda r: list_row(r["name"], r["date"],
                                                                                      trailing=r["value"]))),
                                        empty_state("trophy", "Your bests on this lift show up here."))),
                    _about(),
                ),
                spacing="5", width="100%",
            ),
            rx.vstack(skeleton("240px"), skeleton("48px"), skeleton("160px"), spacing="3", width="100%"),
        ),
        pinned=rx.cond(s.loaded, button("Add to workout", s.add_to_workout, icon="plus", full=True)),
    )


# ---------------------------------------------------------------------------
# Session detail
# ---------------------------------------------------------------------------


def session_page() -> rx.Component:
    s = SessionDetailState
    return shell(
        top_bar("", back="history",
                trailing=rx.cond(~s.mine, icon_button("hand-metal", "Spotted", on_click=s.toggle_spot,
                                                      color=rx.cond(s.spotted_by_me, t.ACCENT, t.TEXT_2)))),
        error_banner(s.error),
        rx.cond(
            s.loaded,
            rx.vstack(
                rx.cond(~s.mine,
                        rx.link(rx.hstack(avatar(s.owner_initials, size=40), text(s.owner_name, t.LABEL),
                                          rank_badge(s.owner_rank, 24), spacing="2", align="center"),
                                href=f"/u/{s.owner_id}", underline="none")),
                rx.vstack(text(s.title, t.TITLE_LG), text(s.when, t.BODY, t.TEXT_2), spacing="1", align="start",
                          width="100%"),
                rx.grid(rx.foreach(s.stats, lambda x: stat_tile(x["value"], x["label"])), columns="3",
                        gap=t.space(16), width="100%"),
                rx.cond(~s.mine & (s.spotted > 0), text(f"Spotted by {s.spotted}", t.CAPTION, t.TEXT_2)),
                rx.vstack(rx.foreach(s.rows, _set_row), spacing="0", width="100%"),
                rx.cond(s.mine,
                        section("Who can see this",
                                segmented(["Public", "Followers", "Only me"],
                                          rx.match(s.visibility, ("public", "Public"), ("private", "Only me"),
                                                   "Followers"),
                                          s.set_visibility))),
                spacing="5", width="100%",
            ),
            rx.vstack(skeleton("80px"), skeleton("240px"), spacing="3", width="100%"),
        ),
    )
