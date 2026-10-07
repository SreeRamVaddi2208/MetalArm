"""Home: who you are in the game, this week in three numbers, the last
workout, how you stand with friends, then their workouts. One primary:
Start workout (or Resume, while one is live)."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.feed import feed_item
from metalarm.components.layout import error_banner, shell
from metalarm.state.auth import AuthState
from metalarm.state.home import HomeState
from metalarm.state.quests import QuestState
from metalarm.state.workout import WorkoutState
from metalarm.ui.chrome import avatar
from metalarm.ui.primitives import (
    button,
    empty_state,
    icon_button,
    link_button,
    list_row,
    progress_bar,
    rows,
    section,
    skeleton,
    skeleton_rows,
    stat_group,
    stat_tile,
    text,
)
from metalarm.ui.rank_badge import rank_badge


def _top() -> rx.Component:
    s = HomeState
    return rx.vstack(
        rx.hstack(
            rx.link(rank_badge(s.rank, 48), href="/profile", underline="none", aria_label="Your rank"),
            rx.vstack(text(f"Hi, {AuthState.display_name}", t.TITLE, overflow="hidden", text_overflow="ellipsis",
                           white_space="nowrap", max_width="100%"),
                      text(f"{s.rank_name} · Level {s.level}", t.CAPTION, t.TEXT_2),
                      spacing="0", align="start", flex="1", min_width="0"),
            icon_button("bell", "Notifications", href="/notifications", badge=s.unread),
            width="100%", align="center", spacing="3",
        ),
        progress_bar(s.xp_scale, label=s.xp_label),
        spacing="4", width="100%", padding_top=t.space(16),
    )


def _week() -> rx.Component:
    s = HomeState
    return rx.cond(
        s.loaded,
        stat_group(stat_tile(s.streak_weeks, "Week streak"), stat_tile(s.workouts_week, "Workouts this week"),
                   stat_tile(s.points_week_value, "Points this week")),
        skeleton("64px"),
    )


def _last() -> rx.Component:
    last = HomeState.last
    return rx.cond(
        last.length() > 0,
        section("Last workout",
                rows(list_row(last["title"], f"{last['date_label']} · {last['duration']} · {last['volume']}",
                              trailing=last["points"], chevron=True, href=f"/session/{last['id']}"))),
    )


def board_row(r) -> rx.Component:
    """One line of the friends leaderboard; yours is tinted."""
    return rx.link(
        rx.hstack(
            text(r["position"], t.LABEL, t.TEXT_2, width="24px", **t.TABULAR),
            avatar(r["initials"], size=40),
            rx.hstack(text(r["name"], t.BODY, overflow="hidden", text_overflow="ellipsis", white_space="nowrap",
                           min_width="0"),
                      rank_badge(r["rank"], 24), spacing="2", align="center", flex="1", min_width="0"),
            text(r["points"], t.BODY, t.TEXT_2, **t.TABULAR),
            width="100%", align="center", spacing="3", min_height=t.ROW_MIN, padding_x=t.space(8),
            background=rx.cond(r["me"] != "", t.ACCENT_SOFT, "transparent"), border_radius=t.RADIUS,
            class_name="ma-press",
        ),
        href=f"/u/{r['id']}", underline="none", width="100%", class_name="ma-board-row",
    )


def _board() -> rx.Component:
    s = HomeState
    return section(
        "Leaderboard",
        rx.cond(
            s.board_loaded,
            rx.cond(
                s.board.length() > 1,
                rx.vstack(rx.foreach(s.preview, board_row),
                          rx.cond(~s.me_in_preview & (s.me_row.length() > 0), board_row(s.me_row)),
                          spacing="1", width="100%"),
                text("Follow friends to see how you stack up.", t.BODY, t.TEXT_2),
            ),
            skeleton_rows(3),
        ),
        action="See all", href="/leaderboard",
    )


def _feed() -> rx.Component:
    s = HomeState
    return section(
        "Friends' workouts",
        rx.cond(
            s.feed.length() > 0,
            rx.vstack(
                rx.foreach(s.feed, lambda c: feed_item(c, s.toggle_spot(c.session_id))),
                rx.cond(s.feed_cursor != "", button("Show more", s.more_feed, variant="ghost", full=True)),
                spacing="0", width="100%",
            ),
            rx.cond(
                s.feed_loaded,
                empty_state("users", "Follow friends to see their workouts here.",
                            link_button("Find friends", "/profile/people", icon="user-plus")),
                skeleton_rows(3),
            ),
        ),
    )


def _streak_notice() -> rx.Component:
    return rx.cond(
        QuestState.streak_saved_notice != "",
        rx.hstack(rx.icon("snowflake", size=20, color=t.TEXT_2, stroke_width=1.75),
                  text(QuestState.streak_saved_notice, t.BODY, t.TEXT_2, flex="1"),
                  button("OK", QuestState.dismiss_streak_notice, variant="ghost"),
                  width="100%", align="center", spacing="3", background=t.SURFACE, border_radius=t.RADIUS,
                  padding=t.CARD_PADDING),
    )


def home_page() -> rx.Component:
    start = rx.cond(
        HomeState.live,
        link_button("Resume workout", "/train", variant="primary", icon="play", full=True),
        button("Start workout", [WorkoutState.start_session(""), rx.redirect("/train")], icon="play", full=True),
    )
    return shell(
        _top(),
        error_banner(HomeState.error),
        _streak_notice(),
        _week(),
        _last(),
        _board(),
        _feed(),
        pinned=start,
    )
