"""Someone's profile (/u/<id>), notifications, and the People tab's rows."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.feed import feed_item
from metalarm.components.layout import error_banner, shell
from metalarm.state.people import NotificationsState, PeopleState, ProfileViewState
from metalarm.ui.chrome import avatar, top_bar
from metalarm.ui.primitives import (
    empty_state,
    primary_button,
    secondary_button,
    section_header,
    skeleton,
    text,
)


def _back() -> rx.Component:
    return rx.box(
        rx.hstack(rx.icon("chevron-left", size=22, color=t.ACCENT_BLUE), text("Back", t.BODY, t.ACCENT_BLUE),
                  spacing="0", align="center"),
        on_click=rx.call_script("window.history.length > 1 ? window.history.back() : window.location.assign('/home')"),
        cursor="pointer", min_height=t.TOUCH_MIN, display="flex", align_items="center",
        custom_attrs={"role": "button"},
    )


def follow_button(following, on_click) -> rx.Component:
    return rx.cond(
        following != "",
        secondary_button("Following", on_click),
        primary_button("Follow", on_click),
    )


def person_row(p) -> rx.Component:
    """A person in a list: frame, name, why, and Follow."""
    return rx.hstack(
        rx.link(rx.hstack(avatar(p["initials"], p["rank"], size=44),
                          rx.vstack(text(p["name"], t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
                                         white_space="nowrap", max_width="100%"),
                                    text(rx.cond(p["follows_you"] != "", "Follows you", p["sub"]), t.FOOTNOTE,
                                         t.TEXT_SECONDARY),
                                    spacing="0", align="start", min_width="0"),
                          spacing="3", align="center", min_width="0"),
                href=f"/u/{p['id']}", underline="none", flex="1", min_width="0"),
        follow_button(p["following"], PeopleState.toggle_follow(p["id"], p["following"])),
        width="100%", align="center", spacing="3", min_height="56px",
        class_name="ma-person",
    )


def people_tab() -> rx.Component:
    return rx.vstack(
        rx.input(value=PeopleState.query, on_change=PeopleState.set_query, debounce_timeout=250,
                 placeholder="Search people by name", size="3", variant="soft", radius="full", width="100%"),
        error_banner(PeopleState.error),
        rx.cond(
            PeopleState.query != "",
            rx.cond(PeopleState.results.length() > 0,
                    rx.vstack(rx.foreach(PeopleState.results, person_row), spacing="2", width="100%"),
                    empty_state("Nobody by that name", "Check the spelling, or ask for their username.")),
            rx.vstack(
                section_header("People you may know"),
                rx.cond(PeopleState.suggested.length() > 0,
                        rx.vstack(rx.foreach(PeopleState.suggested, person_row), spacing="2", width="100%"),
                        text("Follow a friend and their friends show up here. Search for someone above.",
                             t.SUBHEAD, t.TEXT_SECONDARY)),
                spacing="3", width="100%",
            ),
        ),
        spacing="3", width="100%",
    )


def _count(value, label: str) -> rx.Component:
    return rx.vstack(text(value, t.HEADLINE, **t.TABULAR), text(label, t.FOOTNOTE, t.TEXT_SECONDARY),
                     spacing="0", align="center", flex="1")


def user_page() -> rx.Component:
    s = ProfileViewState
    return shell(
        _back(),
        error_banner(s.error),
        rx.cond(
            s.loaded,
            rx.vstack(
                rx.hstack(
                    avatar(s.initials, s.rank, size=72),
                    rx.vstack(text(s.name, t.TITLE_2), text(s.rank_line, t.SUBHEAD, t.TEXT_SECONDARY),
                              rx.cond(s.category != "", text(s.category, t.FOOTNOTE, t.TEXT_SECONDARY)),
                              spacing="0", align="start", min_width="0"),
                    width="100%", align="center", spacing="4",
                ),
                rx.cond(s.bio != "", text(s.bio, t.BODY)),
                rx.hstack(_count(s.workouts, "Workouts"), _count(s.followers, "Followers"),
                          _count(s.following, "Following"), width="100%"),
                rx.cond(
                    ~s.is_me,
                    rx.hstack(
                        rx.cond(s.you_follow, secondary_button("Following", s.toggle_follow, flex="1"),
                                primary_button(rx.cond(s.follows_you, "Follow back", "Follow"), s.toggle_follow,
                                               flex="1")),
                        rx.cond(s.is_friend, rx.link(secondary_button("Challenge", icon="swords"), href="/duels",
                                                     underline="none")),
                        width="100%", spacing="2",
                    ),
                ),
                rx.cond(s.is_friend, text("Friends: you follow each other.", t.FOOTNOTE, t.TEXT_SECONDARY)),
                section_header("Workouts"),
                rx.cond(s.sessions.length() > 0,
                        rx.vstack(rx.foreach(s.sessions, lambda c: feed_item(c, s.toggle_spot(c.session_id))),
                                  spacing="0", width="100%"),
                        empty_state("No workouts to show", "Theirs appear here as their visibility allows.")),
                rx.cond(s.cursor != "", secondary_button("Show more", s.more, width="100%")),
                spacing="4", width="100%",
            ),
            rx.vstack(skeleton("72px"), skeleton("44px"), skeleton("220px"), width="100%"),
        ),
    )


def _note(n) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.cond(n["has_actor"] != "", avatar(n["initials"], n["rank"], size=40),
                    rx.center(rx.icon("scroll-text", size=20, color=t.STREAK_ORANGE),
                              width="40px", height="40px", background=t.SURFACE_2, border_radius=t.RADIUS_PILL)),
            rx.vstack(text(n["line"], t.BODY), text(n["when"], t.FOOTNOTE, t.TEXT_SECONDARY),
                      spacing="0", align="start", flex="1", min_width="0"),
            rx.cond(n["unread"] != "", rx.box(width="8px", height="8px", border_radius=t.RADIUS_PILL,
                                              background=t.ACCENT_BLUE, flex_shrink="0")),
            width="100%", align="center", spacing="3", min_height="56px",
        ),
        href=n["href"], underline="none", width="100%", class_name="ma-note",
    )


def notifications_page() -> rx.Component:
    s = NotificationsState
    return shell(
        top_bar("Notifications"),
        error_banner(s.error),
        rx.cond(s.items.length() > 0,
                rx.vstack(rx.foreach(s.items, _note), spacing="2", width="100%"),
                empty_state("Nothing yet", "Follows, spots, challenges and your friends' records show up here.")),
        rx.cond(s.cursor != "", secondary_button("Show more", s.more, width="100%")),
    )
