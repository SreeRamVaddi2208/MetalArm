"""The Workout tab when no session is running (overhaul 7.4): the date, this
week's strip, today (or the day tapped), suggested routines, and the insights
grid - recovery, streak, quests, next rank. Ready-made workouts and the unit
switch follow.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.presets import preset_cards
from metalarm.components.workout import unit_toggle
from metalarm.ranks import rank_title_var
from metalarm.state.auth import AuthState
from metalarm.state.workout import WorkoutState
from metalarm.state.workout_home import WorkoutHomeState
from metalarm.ui.body_map import body_map
from metalarm.ui.calendar import week_strip
from metalarm.ui.cards import ring_metric, routine_tile
from metalarm.ui.chrome import icon_button, top_bar
from metalarm.ui.primitives import (
    card,
    primary_button,
    section_header,
    sheet,
    text,
)


def session_row(row) -> rx.Component:
    """A finished workout: name, date, and its four numbers."""
    return rx.link(
        rx.vstack(
            rx.hstack(text(row["title"], t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
                           white_space="nowrap", min_width="0", flex="1"),
                      rx.icon("chevron-right", size=18, color=t.TEXT_TERTIARY),
                      width="100%", align="center"),
            text(row["date_label"], t.FOOTNOTE, t.TEXT_SECONDARY),
            rx.hstack(
                *[rx.vstack(text(label, t.FOOTNOTE, t.TEXT_SECONDARY), text(row[key], t.SUBHEAD, **t.TABULAR),
                            spacing="0", align="start", flex="1", min_width="0")
                  for label, key in (("Duration", "duration"), ("Volume", "volume"), ("Records", "prs"),
                                     ("Points", "points"))],
                width="100%", spacing="2",
            ),
            spacing="1", width="100%", align="start",
            background=t.SURFACE_1, border_radius=t.RADIUS_CARD, padding=t.CARD_PADDING,
        ),
        href=f"/session/{row['id']}", underline="none", width="100%",
    )


def _today() -> rx.Component:
    return rx.vstack(
        section_header(WorkoutHomeState.selected_label),
        rx.cond(
            WorkoutHomeState.day_sessions.length() > 0,
            rx.vstack(
                rx.foreach(WorkoutHomeState.day_sessions, session_row),
                # Another one today is always one tap away.
                rx.cond(WorkoutHomeState.selected_is_today,
                        primary_button("Start New Workout", WorkoutState.start_session(""), icon="play",
                                       width="100%")),
                spacing="2", width="100%"),
            rx.vstack(
                text(rx.cond(WorkoutHomeState.selected_is_today, "No workouts today", "No workouts that day"),
                     t.BODY, t.TEXT_SECONDARY),
                rx.cond(WorkoutHomeState.selected_is_today,
                        primary_button("Start New Workout", WorkoutState.start_session(""), icon="play",
                                       width="100%")),
                spacing="3", width="100%", align="center",
                background=t.SURFACE_1, border_radius=t.RADIUS_CARD, padding=t.space(5),
            ),
        ),
        spacing="3", width="100%",
    )


def _suggested() -> rx.Component:
    return rx.cond(
        WorkoutHomeState.suggested.length() > 0,
        rx.vstack(
            section_header("Suggested Workouts", action="Library", href="/library"),
            rx.hstack(
                rx.foreach(WorkoutHomeState.suggested,
                           lambda r: routine_tile(r["name"], r["abbr"], r["color"], r["last"],
                                                  on_click=WorkoutState.start_session(r["id"]))),
                spacing="3", overflow_x="auto", width="100%", padding_bottom=t.space(1),
                style={"scrollbar_width": "none"},
            ),
            spacing="3", width="100%",
        ),
    )


def _insight(title: str, body: rx.Component, on_click=None, href: str = "") -> rx.Component:
    inner = rx.vstack(
        text(title, t.SUBHEAD, t.TEXT_SECONDARY), body,
        spacing="2", align="start", width="100%", height="100%", min_height="148px",
        background=t.SURFACE_1, border_radius=t.RADIUS_CARD, padding=t.CARD_PADDING,
        cursor="pointer" if (on_click is not None or href) else "default", on_click=on_click,
    )
    return rx.link(inner, href=href, underline="none", width="100%") if href else inner


def _insights() -> rx.Component:
    p = AuthState.progress
    streak = WorkoutState.streak
    return rx.vstack(
        section_header("My insights"),
        rx.grid(
            _insight("Recovery", rx.center(
                ring_metric(WorkoutHomeState.recovery_overall, "Recovered", size=84), width="100%"),
                on_click=WorkoutHomeState.open_recovery),
            _insight("Streak", rx.vstack(
                rx.hstack(rx.icon("flame", size=28, color=rx.cond(streak.weeks > 0, t.STREAK_ORANGE,
                                                                     t.TEXT_TERTIARY)),
                          text(streak.weeks, t.TITLE_1, **t.NUMERAL_GAME), spacing="2", align="center"),
                text(rx.cond(streak.weeks == 1, "week", "weeks"), t.FOOTNOTE, t.TEXT_SECONDARY),
                rx.hstack(rx.foreach(streak.freeze_slots,
                                     lambda held: rx.icon("snowflake", size=14,
                                                          color=rx.cond(held, t.ACCENT_BLUE, t.TEXT_TERTIARY))),
                          spacing="1"),
                text(f"{streak.this_week} of {streak.target} this week", t.FOOTNOTE, t.TEXT_SECONDARY),
                spacing="1", align="start")),
            _insight("Quests", rx.vstack(
                text(WorkoutHomeState.quests_label, t.TITLE_2, **t.NUMERAL_GAME),
                text("done", t.FOOTNOTE, t.TEXT_SECONDARY),
                spacing="0", align="start"), href="/home"),
            _insight("Next rank", rx.vstack(
                rx.cond(
                    p.next_rank != "",
                    rx.vstack(
                        text(rank_title_var(p.next_rank), t.TITLE_2, overflow="hidden",
                             text_overflow="ellipsis", white_space="nowrap", max_width="100%"),
                        text(f"at level {p.next_rank_level}", t.FOOTNOTE, t.TEXT_SECONDARY),
                        text(f"You're level {p.current_level}", t.FOOTNOTE, t.TEXT_SECONDARY),
                        spacing="0", align="start", width="100%"),
                    text("Top rank", t.TITLE_2),
                ),
                spacing="1", align="start", width="100%"), href="/you"),
            columns="2", gap=t.space(3), width="100%",
        ),
        spacing="3", width="100%",
    )


def _recovery_row(row) -> rx.Component:
    return rx.hstack(text(row["name"], t.BODY), rx.spacer(), text(row["percent"], t.HEADLINE, **t.TABULAR),
                     width="100%", min_height=t.TOUCH_MIN, border_bottom=t.HAIRLINE)


def recovery_sheet() -> rx.Component:
    return sheet(
        WorkoutHomeState.show_recovery, "Recovery", WorkoutHomeState.close_recovery,
        rx.center(ring_metric(WorkoutHomeState.recovery_overall, "Overall", size=110), width="100%"),
        body_map(WorkoutHomeState.recovery_paths, size="200px"),
        text("Red is still recovering; the deeper, the more.", t.FOOTNOTE, t.TEXT_SECONDARY),
        rx.cond(WorkoutHomeState.recovery_rows.length() > 0,
                rx.vstack(rx.foreach(WorkoutHomeState.recovery_rows, _recovery_row), spacing="0", width="100%"),
                text("Everything is recovered.", t.BODY, t.TEXT_SECONDARY)),
        text(WorkoutHomeState.recovery_note, t.FOOTNOTE, t.TEXT_TERTIARY),
    )


def workout_home() -> rx.Component:
    return rx.vstack(
        top_bar(WorkoutHomeState.title, icon_button("calendar", "Calendar", href="/you?tab=overview"),
                large=False),
        week_strip(WorkoutHomeState.week_days, on_select=WorkoutHomeState.select_day),
        _today(),
        _suggested(),
        _insights(),
        preset_cards(),
        unit_toggle(),
        recovery_sheet(),
        spacing="5",
        width="100%",
    )
