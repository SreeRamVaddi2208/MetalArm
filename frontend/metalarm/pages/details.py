"""Exercise Detail (overhaul 7.3) and Session Detail (7.10)."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.exercise_detail import CHARTS, TABS, ExerciseDetailState
from metalarm.state.session_detail import SessionDetailState
from metalarm.ui.body_map import body_map
from metalarm.ui.chart import area_chart
from metalarm.ui.chrome import avatar
from metalarm.ui.primitives import (
    segmented_control,
    card,
    empty_state,
    metric_chips,
    primary_button,
    skeleton,
    sub_tabs,
    text,
)


def _back(href: str = "") -> rx.Component:
    """Back to wherever the user came from."""
    return rx.box(
        rx.hstack(rx.icon("chevron-left", size=22, color=t.ACCENT_BLUE), text("Back", t.BODY, t.ACCENT_BLUE),
                  spacing="0", align="center"),
        on_click=rx.call_script("window.history.length > 1 ? window.history.back() : window.location.assign('/you')"),
        cursor="pointer", min_height=t.TOUCH_MIN, display="flex", align_items="center",
        custom_attrs={"role": "button"},
    )


def _set_row(row) -> rx.Component:
    """A header row (session or exercise) or a set row, from one flat list."""
    return rx.cond(
        row["kind"] == "head",
        rx.vstack(text(row["title"], t.HEADLINE), rx.cond(row["sub"] != "", text(row["sub"], t.FOOTNOTE,
                                                                                  t.TEXT_SECONDARY)),
                  spacing="0", align="start", width="100%", padding_top=t.space(3)),
        rx.hstack(
            rx.center(text(row["badge"], t.SUBHEAD,
                           rx.match(row["badge"], ("W", t.STREAK_ORANGE), ("D", t.ACCENT_BLUE),
                                    ("F", t.DANGER_RED), t.TEXT_SECONDARY), **t.TABULAR),
                      width="28px", height="28px", background=t.SURFACE_2, border_radius=t.RADIUS_PILL),
            text(row["title"], t.BODY, **t.TABULAR),
            rx.spacer(),
            rx.cond(row["pr"] != "", rx.icon("medal", size=16, color=t.PR_GOLD)),
            width="100%", align="center", spacing="3", min_height="36px",
        ),
    )


# ---------------------------------------------------------------------------
# Exercise Detail
# ---------------------------------------------------------------------------


def _about() -> rx.Component:
    s = ExerciseDetailState
    return rx.vstack(
        card(body_map(s.muscle_paths, size="190px"),
             text(s.muscles_label, t.FOOTNOTE, t.TEXT_SECONDARY, text_align="center", width="100%")),
        rx.cond(s.steps.length() > 0,
                card(text("How to", t.HEADLINE),
                     rx.el.ol(rx.foreach(s.steps, lambda step: rx.el.li(text(step, t.BODY), padding_bottom=t.space(2))),
                              padding_left=t.space(5), margin="0", color=t.TEXT_PRIMARY))),
        rx.cond(s.tips.length() > 0,
                card(text("Tips", t.HEADLINE),
                     rx.foreach(s.tips, lambda tip: rx.hstack(rx.icon("lightbulb", size=16, color=t.STREAK_ORANGE),
                                                              text(tip, t.SUBHEAD), spacing="2", align="start")))),
        spacing="3", width="100%",
    )


def _charts() -> rx.Component:
    s = ExerciseDetailState
    return rx.cond(
        s.series.length() > 0,
        rx.vstack(metric_chips(CHARTS, s.chart_metric, s.set_chart_metric),
                  rx.box(area_chart(s.chart, height=220), width="100%"), spacing="3", width="100%"),
        empty_state("No data yet", "Log this exercise to see your progress."),
    )


def _record(r) -> rx.Component:
    return rx.hstack(
        rx.icon("medal", size=20, color=t.PR_GOLD),
        rx.vstack(text(r["name"], t.SUBHEAD), text(r["date"], t.FOOTNOTE, t.TEXT_SECONDARY), spacing="0",
                  align="start"),
        rx.spacer(), text(r["value"], t.HEADLINE, **t.TABULAR),
        width="100%", align="center", spacing="3", min_height=t.TOUCH_MIN, border_bottom=t.HAIRLINE,
    )


def exercise_page() -> rx.Component:
    s = ExerciseDetailState
    return shell(
        _back(),
        error_banner(s.error),
        rx.cond(
            s.loaded,
            rx.vstack(
                rx.cond(s.image != "",
                        rx.image(src=s.image, width="100%", max_height="320px", object_fit="contain",
                                 background=t.SURFACE_1, border_radius=t.RADIUS_CARD, alt=s.name),
                        rx.center(rx.icon("dumbbell", size=40, color=t.TEXT_TERTIARY), width="100%",
                                  height="180px", background=t.SURFACE_1, border_radius=t.RADIUS_CARD)),
                rx.cond(s.credit != "", text(s.credit, t.CAPTION, t.TEXT_TERTIARY, text_transform="none")),
                rx.hstack(
                    rx.vstack(text(s.name, t.TITLE_1),
                              rx.box(text(s.equipment, t.FOOTNOTE, text_transform="capitalize"),
                                     background=t.SURFACE_2, border_radius=t.RADIUS_PILL,
                                     padding=f"{t.space(0.5)} {t.space(2.5)}"),
                              spacing="2", align="start", min_width="0", flex="1"),
                    rx.box(rx.icon("star", size=24, color=rx.cond(s.favorite, t.STREAK_ORANGE, t.TEXT_SECONDARY),
                                   fill=rx.cond(s.favorite, t.STREAK_ORANGE, "none")),
                           width=t.TOUCH_MIN, height=t.TOUCH_MIN, display="flex", align_items="center",
                           justify_content="center", cursor="pointer", on_click=s.toggle_favorite,
                           custom_attrs={"role": "button", "aria-label": "Favourite"}),
                    width="100%", align="start",
                ),
                primary_button("Add to workout", s.add_to_workout, icon="plus", width="100%"),
                sub_tabs([(name, "") for name in TABS], s.tab, s.set_tab),
                rx.match(
                    s.tab,
                    ("History", rx.cond(s.history_rows.length() > 0,
                                        rx.vstack(rx.foreach(s.history_rows, _set_row), spacing="1", width="100%"),
                                        empty_state("No history yet", "Sets you log appear here, by workout."))),
                    ("Charts", _charts()),
                    ("Records", rx.cond(s.records.length() > 0, card(rx.foreach(s.records, _record)),
                                        empty_state("No records yet", "Your bests on this lift show up here."))),
                    _about(),
                ),
                spacing="4", width="100%",
            ),
            rx.vstack(skeleton("240px"), skeleton("44px"), skeleton("160px"), spacing="3", width="100%"),
        ),
    )


# ---------------------------------------------------------------------------
# Session Detail
# ---------------------------------------------------------------------------


def _stat(stat) -> rx.Component:
    return rx.vstack(text(stat["label"], t.FOOTNOTE, t.TEXT_SECONDARY), text(stat["value"], t.HEADLINE, **t.TABULAR),
                     spacing="0", align="start", min_width="0")


def session_page() -> rx.Component:
    s = SessionDetailState
    return shell(
        _back(),
        error_banner(s.error),
        rx.cond(
            s.loaded,
            rx.vstack(
                rx.cond(~s.mine,
                        rx.link(rx.hstack(avatar(s.owner_initials, s.owner_rank, size=36),
                                          text(s.owner_name, t.HEADLINE), spacing="2", align="center"),
                                href=f"/u/{s.owner_id}", underline="none")),
                text(s.title, t.TITLE_1),
                text(s.when, t.SUBHEAD, t.TEXT_SECONDARY),
                rx.cond(
                    s.mine,
                    rx.vstack(text("Who can see this", t.FOOTNOTE, t.TEXT_SECONDARY),
                              segmented_control(["Public", "Followers", "Only me"],
                                                rx.match(s.visibility, ("public", "Public"), ("private", "Only me"),
                                                         "Followers"),
                                                s.set_visibility),
                              spacing="1", width="100%"),
                    rx.hstack(rx.spacer(),
                              rx.hstack(rx.icon("hand-metal", size=20,
                                                color=rx.cond(s.spotted_by_me, t.STREAK_ORANGE, t.TEXT_SECONDARY)),
                                        text(rx.cond(s.spotted > 0, s.spotted.to_string(), "Spot"), t.SUBHEAD,
                                             rx.cond(s.spotted_by_me, t.STREAK_ORANGE, t.TEXT_SECONDARY)),
                                        spacing="1", align="center", cursor="pointer", min_height=t.TOUCH_MIN,
                                        on_click=s.toggle_spot,
                                        custom_attrs={"role": "button", "aria-label": "Spotted"}),
                              width="100%"),
                ),
                rx.grid(rx.foreach(s.stats, _stat), columns="3", gap=t.space(3), width="100%",
                        background=t.SURFACE_1, border_radius=t.RADIUS_CARD, padding=t.CARD_PADDING),
                rx.vstack(rx.foreach(s.rows, _set_row), spacing="1", width="100%"),
                spacing="3", width="100%",
            ),
            rx.vstack(skeleton("80px"), skeleton("240px"), spacing="3", width="100%"),
        ),
    )
