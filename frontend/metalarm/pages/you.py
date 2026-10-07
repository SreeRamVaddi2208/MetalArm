"""You (overhaul 7.8): profile header, then Overview / Exercises /
Measurements / History. The old profile (character sheet, trials, badges,
import, training path) stays at /profile, one tap from the gear."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.components.workout_home import session_row
from metalarm.ranks import rank_title_var
from metalarm.state.auth import AuthState
from metalarm.state.monthly import MonthlyState
from metalarm.state.you import METRICS, RANGES, TABS, YouState
from metalarm.ui.cards import hero_card
from metalarm.ui.body_map import body_map
from metalarm.ui.calendar import month_calendar
from metalarm.ui.chart import area_chart
from metalarm.ui.chrome import avatar, icon_button, top_bar
from metalarm.ui.primitives import (
    card,
    empty_state,
    filter_chip,
    list_row,
    metric_chips,
    primary_button,
    secondary_button,
    section_header,
    segmented_control,
    sub_tabs,
    text,
)


def _header() -> rx.Component:
    p = AuthState.progress
    return rx.hstack(
        avatar(AuthState.initials, p.rank, size=64),
        rx.vstack(
            text(AuthState.display_name, t.TITLE_2, overflow="hidden", text_overflow="ellipsis",
                 white_space="nowrap", max_width="100%"),
            rx.hstack(
                text(rank_title_var(p.rank), t.SUBHEAD, t.TEXT_SECONDARY),
                text(f"· Level {p.current_level}", t.SUBHEAD, t.TEXT_SECONDARY),
                spacing="1",
            ),
            text(f"{YouState.followers} followers · {YouState.following} following", t.FOOTNOTE,
                 t.TEXT_SECONDARY),
            rx.hstack(
                text(f"{p.points_balance} pts", t.FOOTNOTE, t.STREAK_ORANGE, **t.NUMERAL_GAME),
                rx.cond(AuthState.character_class != "",
                        rx.box(text(AuthState.character_class, t.FOOTNOTE, text_transform="capitalize"),
                               background=t.SURFACE_2, border_radius=t.RADIUS_PILL,
                               padding=f"{t.space(0.5)} {t.space(2.5)}")),
                spacing="2", align="center",
            ),
            spacing="1", align="start", min_width="0", flex="1",
        ),
        width="100%", align="center", spacing="4",
    )


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


def _overview() -> rx.Component:
    return rx.vstack(
        rx.cond(MonthlyState.hero_workouts > 0,
                hero_card(f"Your {MonthlyState.hero_title}", "Your month, in a story",
                          on_play=rx.redirect(f"/summary/{MonthlyState.hero_month}"))),
        segmented_control(RANGES, YouState.range_, YouState.set_range),
        rx.vstack(
            text(YouState.headline_label, t.SUBHEAD, t.TEXT_SECONDARY),
            rx.hstack(text(YouState.headline, t.DISPLAY_NUMBER),
                      text(YouState.headline_unit, t.HEADLINE, t.TEXT_SECONDARY),
                      spacing="1", align="baseline"),
            spacing="0", align="start", width="100%",
        ),
        rx.box(area_chart(YouState.chart, height=220), width="100%", class_name="ma-you-chart"),
        metric_chips(METRICS, YouState.metric, YouState.set_metric),
        card(
            section_header("This week", "See which muscles you worked"),
            rx.cond(YouState.muscle_names != "",
                    rx.vstack(body_map(YouState.muscle_paths, size="190px"),
                              text(YouState.muscle_names, t.FOOTNOTE, t.TEXT_SECONDARY, text_align="center",
                                   width="100%"), spacing="2", width="100%"),
                    text("No workouts yet this week.", t.SUBHEAD, t.TEXT_SECONDARY)),
        ),
        rx.vstack(
            rx.hstack(
                rx.box(rx.icon("chevron-left", size=20, color=t.ACCENT_BLUE), cursor="pointer",
                       on_click=YouState.shift_month(-1), padding=t.space(2),
                       custom_attrs={"role": "button", "aria-label": "Previous month"}),
                rx.spacer(),
                text(YouState.month_count, t.SUBHEAD, t.TEXT_SECONDARY),
                rx.spacer(),
                rx.box(rx.icon("chevron-right", size=20, color=t.ACCENT_BLUE), cursor="pointer",
                       on_click=YouState.shift_month(1), padding=t.space(2),
                       custom_attrs={"role": "button", "aria-label": "Next month"}),
                width="100%", align="center",
            ),
            month_calendar(YouState.month_title, YouState.month_weeks),
            spacing="1", width="100%",
        ),
        spacing="4", width="100%",
    )


# ---------------------------------------------------------------------------
# Exercises, History, Measurements
# ---------------------------------------------------------------------------


def _exercise(row) -> rx.Component:
    return rx.link(list_row(row["name"], f"{row['best']}  {row['e1rm']}", image=row["image"], icon="dumbbell"),
                   href=f"/exercise/{row['id']}", underline="none", width="100%")


def _exercises() -> rx.Component:
    return rx.cond(
        YouState.exercises.length() > 0,
        rx.vstack(
            rx.foreach(YouState.exercises, _exercise),
            rx.cond(YouState.exercises_cursor != "",
                    secondary_button("Show more", YouState.more_exercises, width="100%")),
            spacing="3", width="100%",
        ),
        empty_state("No exercises yet", "Every exercise you log shows up here, with your best set."),
    )


def _history_row(row) -> rx.Component:
    return rx.vstack(
        rx.cond(row["first_of_month"] != "", text(row["month_label"], t.HEADLINE, padding_top=t.space(2))),
        session_row(row),
        spacing="2", width="100%",
    )


def _history() -> rx.Component:
    return rx.cond(
        YouState.history.length() > 0,
        rx.vstack(
            rx.foreach(YouState.history, _history_row),
            rx.cond(YouState.history_cursor != "",
                    secondary_button("Show more", YouState.more_history, width="100%")),
            spacing="2", width="100%",
        ),
        empty_state("No workouts yet", "Finished workouts are kept here, month by month."),
    )


def _measure_chip(group) -> rx.Component:
    return filter_chip(group["title"], selected=YouState.measure_selected == group["key"],
                       on_click=YouState.pick_measure(group["key"]))


def _measure_row(group) -> rx.Component:
    return rx.hstack(
        rx.vstack(text(group["title"], t.HEADLINE), text(group["when"], t.FOOTNOTE, t.TEXT_SECONDARY),
                  spacing="0", align="start"),
        rx.spacer(), text(group["latest"], t.HEADLINE, **t.TABULAR),
        width="100%", align="center", min_height=t.TOUCH_MIN, border_bottom=t.HAIRLINE,
        cursor="pointer", on_click=YouState.pick_measure(group["key"]),
    )


def _measure_input(value, on_change, placeholder: str, mode: str = "decimal") -> rx.Component:
    return rx.el.input(value=value, on_change=on_change, placeholder=placeholder, input_mode=mode,
                       background=t.SURFACE_2, color=t.TEXT_PRIMARY, border="none",
                       border_radius=t.RADIUS_THUMB, padding=f"0 {t.space(3)}", min_height=t.TOUCH_MIN,
                       width="100%", min_width="0", **t.BODY)


def _measurements() -> rx.Component:
    return rx.vstack(
        rx.cond(
            YouState.measure_groups.length() > 0,
            rx.vstack(
                rx.hstack(rx.foreach(YouState.measure_groups, _measure_chip), spacing="2",
                          overflow_x="auto", width="100%", style={"scrollbar_width": "none"}),
                rx.box(area_chart(YouState.measure_chart, height=200), width="100%"),
                card(rx.foreach(YouState.measure_groups, _measure_row)),
                spacing="3", width="100%",
            ),
            empty_state("No measurements yet", "Log your body weight to see it over time."),
        ),
        card(
            text("Add measurement", t.HEADLINE),
            rx.hstack(
                *[filter_chip(label, selected=YouState.measure_kind == kind,
                              on_click=YouState.set_measure_kind(kind))
                  for label, kind in (("Body weight", "weight"), ("Body fat", "body_fat"), ("Custom", "custom"))],
                spacing="2", flex_wrap="wrap",
            ),
            rx.cond(YouState.measure_kind == "custom",
                    _measure_input(YouState.measure_label, YouState.set_measure_label, "Name, e.g. Waist (cm)",
                                   "text")),
            rx.hstack(
                _measure_input(YouState.measure_value, YouState.set_measure_value,
                               rx.match(YouState.measure_kind, ("weight", f"Value ({AuthState.weight_unit})"),
                                        ("body_fat", "Value (%)"), "Value (cm)")),
                primary_button("Add", YouState.add_measure),
                width="100%", spacing="2",
            ),
        ),
        spacing="4", width="100%",
    )


def you_page() -> rx.Component:
    return shell(
        top_bar("You", icon_button("calendar", "Calendar", on_click=YouState.set_tab("Overview")),
                icon_button("settings", "Settings and profile", href="/profile")),
        error_banner(YouState.error),
        _header(),
        sub_tabs([(name, "") for name in TABS], YouState.tab, YouState.set_tab),
        rx.match(
            YouState.tab,
            ("Exercises", _exercises()),
            ("Measurements", _measurements()),
            ("History", _history()),
            _overview(),
        ),
    )
