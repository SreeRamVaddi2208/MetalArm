"""Duels page: who you are up against, and what your party has been doing."""

import reflex as rx

from metalarm import theme
from metalarm.components.duel_card import activity_row, duel_card, pending_card, win_overlay
from metalarm.components.layout import error_banner, section_heading, shell
from metalarm.components.level_up import keyframes
from metalarm.state.duels import DuelState


def _metric_option(label: str, value: str) -> rx.Component:
    selected = DuelState.challenge_metric == value
    return rx.button(
        label,
        on_click=lambda: DuelState.set_challenge_metric(value),
        background=rx.cond(selected, theme.ACCENT, "transparent"),
        color=rx.cond(selected, theme.ON_ACCENT, theme.MUTED),
        border=f"1px solid {theme.BORDER}",
        border_radius="9px",
        font_size="0.7rem",
        font_weight="700",
        letter_spacing="0.1em",
        padding="0.4rem 0.7rem",
        cursor="pointer",
    )


def challenge_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            _metric_option("VOLUME", "volume"),
            _metric_option("SETS", "sets"),
            _metric_option("SESSIONS", "sessions"),
            spacing="2",
            flex_wrap="wrap",
        ),
        rx.hstack(
            rx.text("over", color=theme.MUTED, font_size="0.8rem"),
            rx.input(
                value=DuelState.challenge_days,
                on_change=DuelState.set_challenge_days,
                type="number",
                width="4.5rem",
                background=theme.FIELD,
                border=f"1px solid {theme.BORDER}",
                border_radius="9px",
                color=theme.TEXT,
                padding="0.45rem 0.6rem",
                font_size="0.85rem",
            ),
            rx.text("days", color=theme.MUTED, font_size="0.8rem"),
            spacing="2",
            align="center",
            padding_top="0.5rem",
        ),
        rx.button(
            "CHALLENGE YOUR RIVAL",
            on_click=DuelState.challenge_rival,
            background=theme.ACCENT,
            color=theme.ON_ACCENT,
            border="none",
            border_radius="10px",
            font_size="0.72rem",
            font_weight="800",
            letter_spacing="0.12em",
            padding="0.6rem 1rem",
            cursor="pointer",
            width="100%",
            margin_top="0.6rem",
        ),
        # The rival is generated from YOUR history. Saying so is the difference
        # between a training tool and a fake friend.
        rx.text(
            "Your rival's pace comes from your own recent weeks, not another lifter.",
            color=theme.FAINT,
            font_size="0.72rem",
            padding_top="0.35rem",
        ),
        rx.cond(
            DuelState.opponents.length() > 0,
            rx.vstack(
                rx.text(
                    "OR CHALLENGE SOMEONE IN YOUR PARTY",
                    color=theme.MUTED,
                    font_size="0.68rem",
                    letter_spacing="0.14em",
                    padding_top="0.9rem",
                ),
                rx.foreach(
                    DuelState.opponents,
                    lambda member: rx.hstack(
                        rx.text(member.display_name, color=theme.TEXT, font_size="0.85rem"),
                        rx.spacer(),
                        rx.button(
                            "CHALLENGE",
                            on_click=lambda: DuelState.challenge_member(member.user_id),
                            background="transparent",
                            color=theme.ACCENT,
                            border=f"1px solid {theme.BORDER}",
                            border_radius="9px",
                            font_size="0.68rem",
                            padding="0.35rem 0.7rem",
                            cursor="pointer",
                        ),
                        width="100%",
                        align="center",
                        padding="0.35rem 0",
                    ),
                ),
                width="100%",
                spacing="1",
                align="start",
            ),
        ),
        width="100%",
        align="start",
        padding="1rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER}",
        border_radius="14px",
    )


def duels_page() -> rx.Component:
    return shell(
        rx.vstack(
            keyframes(),
            win_overlay(),
            section_heading("DUELS", "Head to head, over a window you choose"),
            error_banner(DuelState.error),
            challenge_panel(),
            rx.cond(
                DuelState.pending.length() > 0,
                rx.vstack(
                    rx.text(
                        "WAITING",
                        color=theme.MUTED,
                        font_size="0.68rem",
                        letter_spacing="0.14em",
                        padding_top="0.6rem",
                    ),
                    rx.foreach(
                        DuelState.pending,
                        lambda duel: pending_card(duel, incoming=~duel.i_challenged),
                    ),
                    width="100%",
                    spacing="2",
                    align="start",
                ),
            ),
            rx.cond(
                DuelState.active.length() > 0,
                rx.vstack(
                    rx.text(
                        "RUNNING",
                        color=theme.MUTED,
                        font_size="0.68rem",
                        letter_spacing="0.14em",
                        padding_top="0.6rem",
                    ),
                    rx.foreach(DuelState.active, duel_card),
                    width="100%",
                    spacing="2",
                    align="start",
                ),
            ),
            rx.cond(
                DuelState.completed.length() > 0,
                rx.vstack(
                    rx.text(
                        "SETTLED",
                        color=theme.MUTED,
                        font_size="0.68rem",
                        letter_spacing="0.14em",
                        padding_top="0.6rem",
                    ),
                    rx.foreach(DuelState.completed, duel_card),
                    width="100%",
                    spacing="2",
                    align="start",
                ),
            ),
            section_heading("ACTIVITY", "What your party has been up to"),
            rx.cond(
                DuelState.feed.length() > 0,
                rx.vstack(
                    rx.foreach(DuelState.feed, activity_row),
                    width="100%",
                    spacing="0",
                    align="start",
                    padding="0.25rem 1rem",
                    background=theme.PANEL,
                    border=f"1px solid {theme.BORDER}",
                    border_radius="14px",
                ),
                rx.text(
                    "Nothing yet. Finish a workout, hit a record, or win a duel.",
                    color=theme.FAINT,
                    font_size="0.82rem",
                ),
            ),
            width="100%",
            spacing="3",
            align="start",
        )
    )
