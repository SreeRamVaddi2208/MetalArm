"""Home (overhaul 7.1): the switcher (Following / Leaderboard / Duels), the
game strip, your weekly snapshot, then the chosen view. The full quest board
and rank detail are one tap away, at /quests."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.duel_card import dashboard_duels
from metalarm.components.feed import feed_item
from metalarm.components.layout import error_banner, shell
from metalarm.state.auth import AuthState
from metalarm.state.home import VIEWS, HomeState
from metalarm.state.quests import QuestState
from metalarm.ui.chrome import avatar, icon_button
from metalarm.ui.primitives import (
    delta_pill,
    empty_state,
    number,
    primary_button,
    secondary_button,
    section_header,
    segmented_control,
    skeleton,
    text,
)


def _top() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.link(avatar(AuthState.initials, HomeState.rank, size=36), href="/you", underline="none"),
            rx.hstack(text(HomeState.view, t.TITLE_2), rx.icon("chevron-down", size=20),
                      spacing="1", align="center", cursor="pointer", on_click=HomeState.toggle_views,
                      custom_attrs={"role": "button", "aria-label": "Switch view"}),
            rx.spacer(),
            icon_button("user-plus", "Find friends", href="/explore?tab=people"),
            rx.link(rx.hstack(rx.icon("flame", size=20, color=rx.cond(HomeState.streak_weeks > 0, t.STREAK_ORANGE,
                                                                     t.TEXT_TERTIARY)),
                              text(HomeState.streak_weeks, t.HEADLINE, **t.TABULAR), spacing="1", align="center"),
                    href="/quests", underline="none", color=t.TEXT_PRIMARY),
            icon_button("bell", "Notifications", href="/notifications", badge=HomeState.unread),
            width="100%", align="center", spacing="2", min_height="52px",
        ),
        rx.cond(
            HomeState.show_views,
            rx.vstack(
                *[rx.hstack(text(v, t.BODY), rx.spacer(),
                            rx.cond(HomeState.view == v, rx.icon("check", size=18, color=t.ACCENT_BLUE)),
                            width="100%", min_height=t.TOUCH_MIN, align="center", cursor="pointer",
                            on_click=HomeState.set_view(v), padding=f"0 {t.space(4)}")
                  for v in VIEWS],
                position="absolute", top="52px", left="44px", z_index="30", min_width="220px",
                background=t.SURFACE_2, border_radius=t.RADIUS_THUMB, spacing="0", padding_y=t.space(1),
            ),
        ),
        position="relative", width="100%",
    )


def _game_strip() -> rx.Component:
    return rx.link(
        rx.hstack(
            avatar(HomeState.rank, HomeState.rank, size=44),
            rx.vstack(
                rx.hstack(text(HomeState.rank_name, t.HEADLINE), text(f"· Level {HomeState.level}", t.SUBHEAD,
                                                                      t.TEXT_SECONDARY),
                          rx.spacer(), text(HomeState.quests_label, t.FOOTNOTE, t.TEXT_SECONDARY, white_space="nowrap"),
                          width="100%", align="baseline", spacing="1"),
                rx.box(rx.box(height="100%", width="100%", background=t.ACCENT_BLUE, border_radius=t.RADIUS_PILL,
                              transform=f"scaleX({HomeState.xp_scale})", transform_origin="left center"),
                       height="6px", width="100%", background=t.SURFACE_2, border_radius=t.RADIUS_PILL,
                       overflow="hidden"),
                rx.hstack(text(HomeState.points_week, t.FOOTNOTE, t.STREAK_ORANGE, **t.NUMERAL_GAME),
                          rx.spacer(),
                          text(HomeState.xp_label, t.FOOTNOTE, t.TEXT_SECONDARY, white_space="nowrap",
                               overflow="hidden", text_overflow="ellipsis", min_width="0", **t.TABULAR),
                          width="100%", spacing="2"),
                spacing="1", flex="1", min_width="0",
            ),
            background=t.SURFACE_1, border_radius=t.RADIUS_CARD, padding=t.space(3), spacing="3",
            width="100%", align="center",
        ),
        href="/quests", underline="none", width="100%", class_name="ma-game-strip",
    )


def _tile(tile) -> rx.Component:
    return rx.vstack(
        text(tile["label"], t.SUBHEAD, t.TEXT_SECONDARY),
        number(tile["value"], tile["unit"], style=t.TITLE_2),
        delta_pill(tile["delta"], tile["dir"]),
        spacing="1", align="start", min_width="0", flex="1",
    )


def _snapshot() -> rx.Component:
    return rx.vstack(
        section_header("Your weekly snapshot", action="See more", href="/you"),
        rx.cond(HomeState.tiles.length() > 0,
                rx.hstack(rx.foreach(HomeState.tiles, _tile), width="100%", spacing="3"),
                skeleton("72px")),
        spacing="3", width="100%",
    )


def _following() -> rx.Component:
    return rx.cond(
        HomeState.feed.length() > 0,
        rx.vstack(
            rx.foreach(HomeState.feed, lambda c: feed_item(c, HomeState.toggle_spot(c.session_id))),
            rx.cond(HomeState.feed_cursor != "", secondary_button("Show more", HomeState.more_feed, width="100%")),
            spacing="0", width="100%",
        ),
        rx.cond(
            HomeState.feed_loaded,
            empty_state("Follow friends to see their workouts", "Their finished workouts show up here, and yours.",
                        rx.link(primary_button("Find friends", icon="user-plus"), href="/explore?tab=people",
                                underline="none")),
            rx.vstack(skeleton("220px"), skeleton("220px"), width="100%"),
        ),
    )


def _board_row(r) -> rx.Component:
    return rx.link(
        rx.hstack(
            text(r["position"], t.HEADLINE, t.TEXT_SECONDARY, width="28px", **t.TABULAR),
            avatar(r["initials"], r["rank"], size=36),
            text(r["name"], t.BODY, flex="1", min_width="0", overflow="hidden", text_overflow="ellipsis",
                 white_space="nowrap"),
            text(r["points"], t.HEADLINE, t.STREAK_ORANGE, **t.NUMERAL_GAME),
            width="100%", align="center", spacing="3", min_height="52px", padding=f"0 {t.space(3)}",
            background=rx.cond(r["me"] != "", t.alpha(t.ACCENT_BLUE, 0.12), "transparent"),
            border_radius=t.RADIUS_THUMB,
        ),
        href=f"/u/{r['id']}", underline="none", width="100%",
    )


def _leaderboard() -> rx.Component:
    return rx.vstack(
        segmented_control(["This week", "All time"],
                          rx.cond(HomeState.period == "week", "This week", "All time"), HomeState.set_period),
        rx.vstack(rx.foreach(HomeState.board, _board_row), spacing="1", width="100%"),
        # Your own row stays in sight when the list is long.
        rx.cond(~HomeState.me_in_view & (HomeState.me_row.length() > 0),
                rx.box(_board_row(HomeState.me_row), position="sticky", bottom=t.TAB_BAR_CLEARANCE,
                       width="100%", background=t.COLOR_BG)),
        rx.cond(HomeState.board.length() <= 1,
                text("Follow friends to see how you stack up.", t.SUBHEAD, t.TEXT_SECONDARY)),
        spacing="3", width="100%",
    )


def _duels() -> rx.Component:
    return rx.vstack(
        dashboard_duels(),
        rx.link(secondary_button("All duels and challenges", width="100%"), href="/duels", underline="none",
                width="100%"),
        spacing="3", width="100%",
    )


def home_page() -> rx.Component:
    return shell(
        _top(),
        error_banner(HomeState.error),
        rx.cond(QuestState.streak_saved_notice != "",
                rx.hstack(rx.icon("snowflake", size=18, color=t.ACCENT_BLUE),
                          text(QuestState.streak_saved_notice, t.SUBHEAD, flex="1"),
                          text("OK", t.HEADLINE, t.ACCENT_BLUE, cursor="pointer", on_click=QuestState.dismiss_streak_notice),
                          width="100%", align="center", spacing="3", background=t.SURFACE_1,
                          border_radius=t.RADIUS_CARD, padding=t.CARD_PADDING)),
        _game_strip(),
        _snapshot(),
        rx.match(HomeState.view, ("Leaderboard", _leaderboard()), ("Duels", _duels()), _following()),
    )
