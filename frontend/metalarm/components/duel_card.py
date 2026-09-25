"""Duel cards, the activity feed row, and the win moment.

The win moment is deliberately a SMALLER sibling of the rank-up: it borrows
that sequence's veil, card and line classes (components/level_up.py) and
nothing else - no tier table, no crown, no shockwave. A duel is worth a
flourish; a promotion is the event.
"""

import reflex as rx

from metalarm import theme
from metalarm.models import ActivityEntry, Duel
from metalarm.state.duels import DuelState


def _score(label: str, value: str, ahead, accent: str) -> rx.Component:
    return rx.vstack(
        rx.text(label, color=theme.MUTED, font_size="0.7rem", letter_spacing="0.12em"),
        rx.text(
            value,
            color=rx.cond(ahead, accent, theme.TEXT),
            font_size="1.4rem",
            font_weight="800",
            line_height="1.1",
        ),
        spacing="1",
        align="start",
    )


def duel_card(duel: Duel) -> rx.Component:
    """One duel, from the reader's point of view: your score first."""
    return rx.box(
        rx.hstack(
            rx.text(
                duel.metric_label,
                color=theme.ACCENT,
                font_size="0.68rem",
                font_weight="800",
                letter_spacing="0.16em",
            ),
            rx.spacer(),
            rx.text(duel.ends_label, color=theme.MUTED, font_size="0.72rem"),
            width="100%",
            align="center",
        ),
        rx.hstack(
            _score("YOU", duel.my_score_label, duel.i_am_ahead, theme.ACCENT),
            rx.text("vs", color=theme.FAINT, font_size="0.8rem", padding="0 0.4rem"),
            _score(
                rx.cond(duel.opponent.is_rival, "YOUR RIVAL", duel.their_name.upper()),
                duel.their_score_label,
                ~duel.i_am_ahead,
                theme.ACCENT_DIM,
            ),
            width="100%",
            align="center",
            padding_top="0.6rem",
        ),
        rx.cond(
            duel.status == "completed",
            rx.text(
                rx.cond(
                    duel.is_draw,
                    "Drawn.",
                    rx.cond(duel.i_won, "You won.", f"{duel.their_name} won."),
                ),
                color=rx.cond(duel.i_won, theme.SUCCESS, theme.MUTED),
                font_size="0.78rem",
                font_weight="700",
                padding_top="0.5rem",
            ),
        ),
        width="100%",
        padding="0.9rem 1rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER}",
        border_radius="14px",
    )


def pending_card(duel: Duel, *, incoming: bool) -> rx.Component:
    """A challenge waiting on somebody. Accepting restarts the clock, so the
    card says so rather than letting the window quietly shrink."""
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(
                    rx.cond(incoming, f"{duel.their_name} challenged you", f"Waiting for {duel.their_name}"),
                    color=theme.TEXT,
                    font_size="0.9rem",
                    font_weight="700",
                ),
                rx.text(
                    f"{duel.metric_label} · starts when accepted",
                    color=theme.MUTED,
                    font_size="0.74rem",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.cond(
                incoming,
                rx.hstack(
                    rx.button(
                        "ACCEPT",
                        on_click=lambda: DuelState.accept(duel.id),
                        background=theme.ACCENT,
                        color=theme.ON_ACCENT,
                        border="none",
                        border_radius="9px",
                        font_size="0.7rem",
                        font_weight="800",
                        letter_spacing="0.1em",
                        padding="0.45rem 0.8rem",
                        cursor="pointer",
                    ),
                    rx.button(
                        "DECLINE",
                        on_click=lambda: DuelState.decline(duel.id),
                        background="transparent",
                        color=theme.FAINT,
                        border=f"1px solid {theme.BORDER}",
                        border_radius="9px",
                        font_size="0.7rem",
                        padding="0.45rem 0.8rem",
                        cursor="pointer",
                    ),
                    spacing="2",
                ),
                rx.button(
                    "WITHDRAW",
                    on_click=lambda: DuelState.decline(duel.id),
                    background="transparent",
                    color=theme.FAINT,
                    border=f"1px solid {theme.BORDER}",
                    border_radius="9px",
                    font_size="0.7rem",
                    padding="0.45rem 0.8rem",
                    cursor="pointer",
                ),
            ),
            width="100%",
            align="center",
        ),
        width="100%",
        padding="0.85rem 1rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER}",
        border_radius="14px",
    )


def activity_row(entry: ActivityEntry) -> rx.Component:
    return rx.hstack(
        rx.text(entry.icon, color=theme.ACCENT, font_size="0.85rem", width="1.2rem"),
        rx.vstack(
            rx.text(
                entry.headline,
                color=theme.TEXT,
                font_size="0.84rem",
                font_weight="600",
            ),
            rx.text(
                f"{entry.display_name} · {entry.when_label}",
                color=theme.MUTED,
                font_size="0.72rem",
            ),
            spacing="0",
            align="start",
        ),
        width="100%",
        align="start",
        padding="0.6rem 0",
        border_bottom=f"1px solid {theme.BORDER}",
    )


def win_overlay() -> rx.Component:
    """The smaller sibling: the rank-up's veil, card and line, nothing more."""
    return rx.cond(
        DuelState.show_win,
        rx.box(
            rx.center(
                rx.vstack(
                    rx.heading(
                        "DUEL WON",
                        size="7",
                        letter_spacing="0.2em",
                        class_name="lf-line",
                        color=theme.TEXT,
                    ),
                    rx.text(
                        f"You beat {DuelState.won_against}.",
                        color=theme.MUTED,
                        font_size="0.9rem",
                        class_name="lf-line",
                    ),
                    rx.text(
                        f"+{DuelState.won_points} points",
                        color=theme.ACCENT,
                        font_size="1.1rem",
                        font_weight="800",
                        class_name="lf-line",
                    ),
                    rx.button(
                        "CONTINUE",
                        on_click=DuelState.dismiss_win,
                        background=theme.ACCENT,
                        color=theme.ON_ACCENT,
                        border="none",
                        border_radius="10px",
                        font_weight="800",
                        letter_spacing="0.14em",
                        font_size="0.75rem",
                        padding="0.6rem 1.3rem",
                        cursor="pointer",
                        class_name="lf-line",
                    ),
                    spacing="3",
                    align="center",
                    class_name="lf-card",
                    padding="2rem 1.75rem",
                    background=theme.PANEL,
                    border=f"1px solid {theme.ACCENT}40",
                    border_radius="18px",
                    box_shadow=theme.glow(theme.ACCENT, "70px"),
                    max_width="90vw",
                ),
                width="100%",
                height="100%",
            ),
            class_name="lf-veil",
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            background=theme.VEIL,
            backdrop_filter="blur(3px)",
            z_index="100",
            on_click=DuelState.dismiss_win,
        ),
    )
