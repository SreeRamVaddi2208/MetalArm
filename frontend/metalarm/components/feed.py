"""A finished workout in the feed (overhaul 7.1.5): who and when, the
workout, its four numbers, up to six exercises, and "spotted"."""

import reflex as rx

from metalarm import theme as t
from metalarm.ui.chrome import avatar
from metalarm.ui.primitives import text, thumb
from metalarm.workout_models import FeedCard


def _stat(label: str, value, icon: str = "", color: str = t.TEXT_PRIMARY) -> rx.Component:
    return rx.vstack(
        text(label, t.FOOTNOTE, t.TEXT_SECONDARY),
        rx.hstack(rx.icon(icon, size=15, color=t.PR_GOLD) if icon else rx.fragment(),
                  text(value, t.HEADLINE, color, **t.TABULAR), spacing="1", align="center"),
        spacing="0", align="start", min_width="0",
    )


def _tile(e) -> rx.Component:
    return rx.vstack(thumb(e["image"], size="100%", icon="dumbbell"),
                     text(e["caption"], t.FOOTNOTE, t.TEXT_SECONDARY, overflow="hidden", text_overflow="ellipsis",
                          white_space="nowrap", max_width="100%"),
                     spacing="1", width="100%", min_width="0")


def feed_item(card: FeedCard, on_spot) -> rx.Component:
    return rx.vstack(
        rx.link(
            rx.hstack(avatar(card.initials, card.rank, size=40),
                      rx.vstack(text(card.name, t.HEADLINE), text(card.when, t.FOOTNOTE, t.TEXT_SECONDARY),
                                spacing="0", align="start", min_width="0"),
                      spacing="3", align="center"),
            href=f"/u/{card.user_id}", underline="none",
        ),
        rx.link(
            rx.vstack(
                text(card.title, t.TITLE_2),
                rx.grid(_stat("Duration", card.duration), _stat("Volume", card.volume),
                        _stat("Records", card.records, icon="medal"),
                        _stat("Points", card.points, color=t.STREAK_ORANGE),
                        columns="4", gap=t.space(2), width="100%"),
                rx.grid(rx.foreach(card.exercises, _tile), columns="3", gap=t.space(2), width="100%"),
                rx.cond(card.more > 0, text(f"+{card.more} more", t.FOOTNOTE, t.TEXT_SECONDARY)),
                spacing="3", width="100%", align="start",
            ),
            href=f"/session/{card.session_id}", underline="none", width="100%",
        ),
        rx.hstack(
            rx.spacer(),
            rx.hstack(
                rx.icon("hand-metal", size=20, color=rx.cond(card.spotted_by_me, t.STREAK_ORANGE, t.TEXT_SECONDARY)),
                text(rx.cond(card.spotted > 0, card.spotted.to_string(), "Spot"), t.SUBHEAD,
                     rx.cond(card.spotted_by_me, t.STREAK_ORANGE, t.TEXT_SECONDARY), **t.TABULAR),
                spacing="1", align="center", cursor="pointer", min_height=t.TOUCH_MIN,
                padding=f"0 {t.space(2)}", on_click=on_spot,
                custom_attrs={"role": "button", "aria-label": "Spotted",
                              "aria-pressed": rx.cond(card.spotted_by_me, "true", "false")},
            ),
            width="100%", align="center",
        ),
        spacing="3", width="100%", padding_y=t.space(4), border_bottom=t.HAIRLINE,
        class_name="ma-feed-card",
    )
