"""A finished workout in the feed: who and when, the workout, three numbers,
what it held, and "spotted". Calm - no tiles, no colour but the spot."""

import reflex as rx

from metalarm import theme as t
from metalarm.ui.chrome import avatar
from metalarm.ui.primitives import stat_group, stat_tile, text
from metalarm.ui.rank_badge import rank_badge
from metalarm.workout_models import FeedCard


def feed_item(card: FeedCard, on_spot) -> rx.Component:
    return rx.vstack(
        rx.link(
            rx.hstack(avatar(card.initials, size=40),
                      rx.vstack(rx.hstack(text(card.name, t.LABEL), rank_badge(card.rank, 24), spacing="2",
                                          align="center"),
                                text(card.when, t.CAPTION, t.TEXT_2), spacing="0", align="start", min_width="0"),
                      spacing="3", align="center"),
            href=f"/u/{card.user_id}", underline="none",
        ),
        rx.link(
            rx.vstack(
                text(card.title, t.TITLE),
                stat_group(stat_tile(card.duration, "Duration"), stat_tile(card.volume, "Volume"),
                           stat_tile(card.points, "Points")),
                text(card.exercise_line, t.CAPTION, t.TEXT_2, overflow="hidden", text_overflow="ellipsis", white_space="nowrap",
                     max_width="100%"),
                spacing="3", width="100%", align="start",
            ),
            href=f"/session/{card.session_id}", underline="none", width="100%",
        ),
        rx.hstack(
            rx.cond(card.records > 0, text(f"{card.records} PR", t.CAPTION, t.TEXT_2)),
            rx.spacer(),
            rx.hstack(
                rx.icon("hand-metal", size=20, stroke_width=1.75,
                        color=rx.cond(card.spotted_by_me, t.ACCENT, t.TEXT_2)),
                text(rx.cond(card.spotted > 0, card.spotted.to_string(), "Spot"), t.LABEL,
                     rx.cond(card.spotted_by_me, t.ACCENT, t.TEXT_2), **t.TABULAR),
                spacing="1", align="center", cursor="pointer", min_height=t.TOUCH, min_width=t.TOUCH,
                justify="center", on_click=on_spot, class_name="ma-press",
                custom_attrs={"role": "button", "aria-label": "Spotted",
                              "aria-pressed": rx.cond(card.spotted_by_me, "true", "false")},
            ),
            width="100%", align="center",
        ),
        spacing="3", width="100%", padding_y=t.space(16), border_bottom=t.HAIRLINE,
        class_name="ma-feed-card",
    )
