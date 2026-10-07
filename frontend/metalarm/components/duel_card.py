"""Duel cards, the activity feed row, and the win moment.

The win moment is deliberately a SMALLER sibling of the rank-up: it borrows
that sequence's veil, card and line classes (components/level_up.py) and
nothing else - no tier table, no crown, no shockwave. A duel is worth a
flourish; a promotion is the event.
"""

import reflex as rx

from metalarm import theme
from metalarm.models import ActivityEntry, BreakdownLine, Duel, DuelMode
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


def head_to_head(duel: Duel) -> rx.Component:
    """Your share of the two scores as one bar - scaleX, never width."""
    return rx.box(
        rx.box(
            width="100%",
            height="100%",
            transform=f"scaleX({duel.my_share})",
            transform_origin="left center",
            background=f"linear-gradient(90deg, {theme.ACCENT_DIM}, {theme.ACCENT})",
            border_radius="999px",
            transition="transform 420ms cubic-bezier(0.22, 1, 0.36, 1)",
        ),
        width="100%",
        height="6px",
        background=theme.BORDER,
        border_radius="999px",
        overflow="hidden",
        margin_top="0.6rem",
    )


def _line(line: BreakdownLine) -> rx.Component:
    return rx.hstack(
        rx.text(line.label, color=theme.MUTED, font_size="0.74rem"),
        rx.spacer(),
        rx.text(line.value_label, color=theme.TEXT, font_size="0.74rem", font_weight="700"),
        width="100%",
    )


def _breakdown_column(title, lines) -> rx.Component:
    return rx.vstack(
        rx.text(title, **theme.LABEL_STYLE),
        rx.cond(
            lines.length() > 0,
            rx.foreach(lines, _line),
            rx.text("Nothing counted yet", color=theme.FAINT, font_size="0.72rem"),
        ),
        spacing="1",
        width="100%",
        align="start",
    )


def duel_detail(duel: Duel) -> rx.Component:
    """What counts toward this mode, and both sides' working - aggregates
    only, as the server sends them."""
    return rx.cond(
        DuelState.open_duel == duel.id,
        rx.vstack(
            rx.text(duel.rules, color=theme.FAINT, font_size="0.74rem", line_height="1.45"),
            rx.grid(
                _breakdown_column("YOU", duel.my_breakdown),
                _breakdown_column(duel.their_name.upper(), duel.their_breakdown),
                columns="2",
                gap="1rem",
                width="100%",
            ),
            spacing="2",
            width="100%",
            padding_top="0.7rem",
            border_top=f"1px solid {theme.BORDER}",
            margin_top="0.6rem",
        ),
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
        head_to_head(duel),
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
        rx.cond(
            ~duel.opponent.is_rival,
            rx.button(
                rx.cond(DuelState.open_duel == duel.id, "Hide details", "Details"),
                on_click=lambda: DuelState.toggle_detail(duel.id),
                background="transparent",
                color=theme.FAINT,
                border="none",
                font_size="0.68rem",
                padding="0.3rem 0",
                margin_top="0.3rem",
                cursor="pointer",
            ),
        ),
        duel_detail(duel),
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
                    on_click=lambda: DuelState.cancel(duel.id),
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


def mode_picker() -> rx.Component:
    """Challenge flow, step two: the modes, each with a line on why it is
    fair. A mode the two of you cannot use yet is shown, disabled, with the
    server's reason - rather than hidden, which would just look missing."""

    def card(mode: DuelMode) -> rx.Component:
        return rx.box(
            rx.vstack(
                rx.text(mode.title, color=rx.cond(mode.eligible, theme.TEXT, theme.FAINT),
                        font_weight="800", font_size="0.9rem"),
                rx.text(mode.fairness, color=theme.MUTED, font_size="0.76rem"),
                rx.cond(~mode.eligible,
                        rx.text(mode.reason, color=theme.FAINT, font_size="0.72rem",
                                font_style="italic")),
                spacing="1",
                align="start",
            ),
            on_click=rx.cond(mode.eligible, DuelState.choose_mode(mode.metric), rx.noop()),
            cursor=rx.cond(mode.eligible, "pointer", "not-allowed"),
            opacity=rx.cond(mode.eligible, "1", "0.55"),
            width="100%",
            padding="0.8rem 0.9rem",
            background=theme.FIELD,
            border=f"1px solid {theme.BORDER}",
            border_radius="12px",
            _hover={"border_color": rx.cond(mode.eligible, theme.BORDER_HI, theme.BORDER)},
            custom_attrs={"role": "button", "aria-disabled": rx.cond(mode.eligible, "false", "true")},
        )

    return rx.cond(
        DuelState.show_modes,
        rx.vstack(
            rx.hstack(
                rx.text(f"CHALLENGE {DuelState.picking_name.upper()}", **theme.LABEL_STYLE),
                rx.spacer(),
                rx.button("Cancel", on_click=DuelState.close_modes, background="transparent",
                          color=theme.FAINT, border="none", font_size="0.72rem", cursor="pointer"),
                width="100%",
                align="center",
            ),
            rx.foreach(DuelState.modes, card),
            spacing="2",
            width="100%",
            padding="1rem",
            background=theme.PANEL,
            border=f"1px solid {theme.BORDER_HI}",
            border_radius="14px",
        ),
    )


def dashboard_duels() -> rx.Component:
    """Running duels on the home screen: a head-to-head bar each."""
    return rx.cond(
        DuelState.active.length() > 0,
        rx.vstack(
            rx.foreach(
                DuelState.active,
                lambda duel: rx.link(
                    rx.box(
                        rx.hstack(
                            rx.text(duel.metric_label, color=theme.ACCENT, font_size="0.64rem",
                                    font_weight="800", letter_spacing="0.16em"),
                            rx.spacer(),
                            rx.text(duel.ends_label, color=theme.FAINT, font_size="0.68rem"),
                            width="100%",
                        ),
                        rx.hstack(
                            rx.text(f"You {duel.my_score_label}", color=theme.TEXT,
                                    font_size="0.8rem", font_weight="700"),
                            rx.spacer(),
                            rx.text(f"{duel.their_score_label} {duel.their_name}",
                                    color=theme.MUTED, font_size="0.8rem"),
                            width="100%",
                            padding_top="0.3rem",
                        ),
                        head_to_head(duel),
                        width="100%",
                        padding="0.75rem 0.9rem",
                        background=theme.PANEL,
                        border=f"1px solid {theme.BORDER}",
                        border_radius="12px",
                    ),
                    href="/duels",
                    width="100%",
                    _hover={"text_decoration": "none"},
                ),
            ),
            spacing="2",
            width="100%",
        ),
    )


def win_overlay() -> rx.Component:
    """A settled duel's moment: the rank-up's veil, card and line, nothing
    more - sized between a quest and a PR. A loss is not a defeat screen: it
    shows what showing up earned, and offers the rematch."""
    kind = DuelState.result_kind
    return rx.cond(
        DuelState.show_win,
        rx.box(
            rx.center(
                rx.vstack(
                    rx.heading(
                        rx.cond(kind == "draw", "DUEL DRAWN",
                                rx.cond(kind == "loss", "GOOD FIGHT", "DUEL WON")),
                        size="7",
                        letter_spacing="0.2em",
                        class_name="lf-line",
                        color=theme.TEXT,
                    ),
                    rx.text(
                        rx.cond(
                            kind == "draw",
                            f"Dead level with {DuelState.won_against}.",
                            rx.cond(kind == "loss",
                                    f"{DuelState.won_against} took this one. You showed up.",
                                    f"You beat {DuelState.won_against}."),
                        ),
                        color=theme.MUTED,
                        font_size="0.9rem",
                        class_name="lf-line",
                        text_align="center",
                    ),
                    rx.cond(
                        DuelState.won_points > 0,
                        rx.text(
                            f"+{DuelState.won_points} points",
                            color=theme.ACCENT,
                            font_size="1.1rem",
                            font_weight="800",
                            class_name="lf-line",
                        ),
                    ),
                    rx.hstack(
                        rx.cond(
                            (kind != "win") & (DuelState.result_their_id != ""),
                            rx.button(
                                "REMATCH",
                                on_click=DuelState.rematch,
                                background="transparent",
                                color=theme.ACCENT,
                                border=f"1px solid {theme.ACCENT}66",
                                border_radius="10px",
                                font_weight="800",
                                letter_spacing="0.14em",
                                font_size="0.75rem",
                                padding="0.6rem 1.1rem",
                                cursor="pointer",
                            ),
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
                        ),
                        spacing="2",
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
                    on_click=rx.stop_propagation,
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
