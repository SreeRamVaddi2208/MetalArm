"""People: find and follow (/profile/people), someone's profile (/u/<id>),
and notifications."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.feed import feed_item
from metalarm.components.layout import error_banner, shell
from metalarm.state.people import NotificationsState, PeopleState, ProfileViewState
from metalarm.ui.chrome import avatar, top_bar
from metalarm.ui.primitives import (
    button,
    empty_state,
    field,
    link_button,
    list_row,
    rows,
    section,
    skeleton,
    skeleton_rows,
    stat_group,
    stat_tile,
    text,
)
from metalarm.ui.rank_badge import rank_badge


def follow_button(following, on_click) -> rx.Component:
    """Secondary either way: a list of people has no primary action."""
    return rx.cond(following != "", button("Following", on_click, variant="ghost", class_name="ma-follow"),
                   button("Follow", on_click, variant="secondary", class_name="ma-follow"))


def person_row(p) -> rx.Component:
    """A person in a list: initials, name and rank, why, and Follow."""
    return rx.hstack(
        rx.link(rx.hstack(avatar(p["initials"], size=40),
                          rx.vstack(rx.hstack(text(p["name"], t.BODY, overflow="hidden", text_overflow="ellipsis",
                                                   white_space="nowrap", min_width="0"),
                                              rank_badge(p["rank"], 24), spacing="2", align="center",
                                              min_width="0"),
                                    text(rx.cond(p["follows_you"] != "", "Follows you", p["sub"]), t.CAPTION,
                                         t.TEXT_2),
                                    spacing="0", align="start", min_width="0"),
                          spacing="3", align="center", min_width="0"),
                href=f"/u/{p['id']}", underline="none", flex="1", min_width="0"),
        follow_button(p["following"], PeopleState.toggle_follow(p["id"], p["following"])),
        width="100%", align="center", spacing="3", min_height=t.ROW_MIN, class_name="ma-person",
    )


def people_page() -> rx.Component:
    s = PeopleState
    return shell(
        top_bar("People", back="/profile"),
        field(s.query, s.set_query, "Search people by name", debounce=True),
        error_banner(s.error),
        rx.cond(
            s.query != "",
            rx.cond(s.results.length() > 0, rx.vstack(rx.foreach(s.results, person_row), spacing="1", width="100%"),
                    empty_state("search", "Nobody by that name. Check the spelling, or ask for their username.")),
            section("People you may know",
                    rx.cond(s.suggested.length() > 0,
                            rx.vstack(rx.foreach(s.suggested, person_row), spacing="1", width="100%"),
                            text("Follow a friend and their friends show up here.", t.BODY, t.TEXT_2))),
        ),
    )


def user_page() -> rx.Component:
    s = ProfileViewState
    follow = rx.cond(s.you_follow, button("Following", s.toggle_follow, variant="secondary", full=True),
                     button(rx.cond(s.follows_you, "Follow back", "Follow"), s.toggle_follow, full=True))
    return shell(
        top_bar("", back="history"),
        error_banner(s.error),
        rx.cond(
            s.loaded,
            rx.vstack(
                rx.hstack(
                    avatar(s.initials, size=96),
                    rx.vstack(text(s.name, t.TITLE), text(s.rank_line, t.CAPTION, t.TEXT_2),
                              rx.cond(s.category != "", text(s.category, t.CAPTION, t.TEXT_2)),
                              spacing="1", align="start", flex="1", min_width="0"),
                    rank_badge(s.rank, 48),
                    width="100%", align="center", spacing="4",
                ),
                rx.cond(s.bio != "", text(s.bio, t.BODY, t.TEXT_2)),
                stat_group(stat_tile(s.workouts, "Workouts"), stat_tile(s.followers, "Followers"),
                           stat_tile(s.following, "Following")),
                rx.cond(s.is_friend & ~s.is_me,
                        rows(list_row("Challenge to a duel", "You follow each other", chevron=True, href="/duels",
                                      leading=rx.icon("swords", size=20, color=t.TEXT_2, stroke_width=1.75)))),
                section("Workouts",
                        rx.cond(s.sessions.length() > 0,
                                rx.vstack(rx.foreach(s.sessions, lambda c: feed_item(c, s.toggle_spot(c.session_id))),
                                          spacing="0", width="100%"),
                                empty_state("dumbbell", "Their workouts appear here as their visibility allows.")),
                        rx.cond(s.cursor != "", button("Show more", s.more, variant="ghost", full=True))),
                spacing="6", width="100%",
            ),
            rx.vstack(skeleton("96px"), skeleton("64px"), skeleton_rows(3), spacing="4", width="100%"),
        ),
        pinned=rx.cond(s.loaded & ~s.is_me, follow),
    )


def _note(n) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.cond(n["has_actor"] != "", avatar(n["initials"], size=40),
                    rx.center(rx.icon("scroll-text", size=20, color=t.TEXT_2, stroke_width=1.75),
                              width="40px", height="40px", background=t.SURFACE_2, border_radius=t.RADIUS_PILL)),
            rx.vstack(text(n["line"], t.BODY), text(n["when"], t.CAPTION, t.TEXT_2),
                      spacing="0", align="start", flex="1", min_width="0"),
            rx.cond(n["unread"] != "", rx.box(width="8px", height="8px", border_radius=t.RADIUS_PILL,
                                              background=t.ACCENT, flex_shrink="0",
                                              aria_label="Unread")),
            width="100%", align="center", spacing="3", min_height=t.ROW_MIN, padding_y=t.space(8),
            class_name="ma-press",
        ),
        href=n["href"], underline="none", width="100%", class_name="ma-note",
    )


def notifications_page() -> rx.Component:
    s = NotificationsState
    return shell(
        top_bar("Notifications", back="/home"),
        error_banner(s.error),
        rx.cond(s.items.length() > 0,
                rows(rx.foreach(s.items, _note)),
                empty_state("bell", "Follows, spots, challenges and your friends' records show up here.",
                            link_button("Find friends", "/profile/people", icon="user-plus"))),
        rx.cond(s.cursor != "", button("Show more", s.more, variant="ghost", full=True)),
    )
