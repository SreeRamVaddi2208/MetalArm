"""Duel rows, the activity row, the mode sheet, and the win moment.

The win moment is a SMALLER sibling of the rank-up: it borrows that
sequence's veil, card and line classes (components/level_up.py) and nothing
else. A duel is worth a flourish; a promotion is the event.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.models import ActivityEntry, BreakdownLine, Duel, DuelMode
from metalarm.state.duels import DuelState
from metalarm.ui.primitives import button, list_row, number, progress_bar, sheet, text


def _line(line: BreakdownLine) -> rx.Component:
    return rx.hstack(text(line.label, t.CAPTION, t.TEXT_2), rx.spacer(),
                     text(line.value_label, t.CAPTION, **t.TABULAR), width="100%")


def _breakdown_column(title, lines) -> rx.Component:
    return rx.vstack(
        text(title, t.LABEL),
        rx.cond(lines.length() > 0, rx.foreach(lines, _line), text("Nothing counted yet", t.CAPTION, t.TEXT_2)),
        spacing="1", width="100%", align="start",
    )


def duel_detail(duel: Duel) -> rx.Component:
    """What counts toward this mode, and both sides' working - aggregates
    only, as the server sends them."""
    return rx.cond(
        DuelState.open_duel == duel.id,
        rx.vstack(
            text(duel.rules, t.CAPTION, t.TEXT_2),
            rx.grid(_breakdown_column("You", duel.my_breakdown),
                    _breakdown_column(duel.their_name, duel.their_breakdown),
                    columns="2", gap=t.space(16), width="100%"),
            spacing="3", width="100%", padding_top=t.space(12), border_top=t.HAIRLINE,
        ),
    )


def duel_card(duel: Duel) -> rx.Component:
    """One duel from the reader's side: your score first, a share bar."""
    return rx.vstack(
        rx.hstack(text(duel.metric_label, t.LABEL), rx.spacer(), text(duel.ends_label, t.CAPTION, t.TEXT_2),
                  width="100%", align="center"),
        rx.hstack(
            rx.vstack(text("You", t.CAPTION, t.TEXT_2), number(duel.my_score_label, style=t.TITLE),
                      spacing="0", align="start"),
            rx.spacer(),
            rx.vstack(text(rx.cond(duel.opponent.is_rival, "Your rival", duel.their_name), t.CAPTION, t.TEXT_2),
                      number(duel.their_score_label, style=t.TITLE, color=t.TEXT_2), spacing="0", align="end"),
            width="100%", align="end",
        ),
        progress_bar(duel.my_share),
        rx.cond(duel.status == "completed",
                text(rx.cond(duel.is_draw, "Drawn.", rx.cond(duel.i_won, "You won.", f"{duel.their_name} won.")),
                     t.BODY, t.TEXT_2)),
        rx.cond(~duel.opponent.is_rival,
                button(rx.cond(DuelState.open_duel == duel.id, "Hide details", "Details"),
                       DuelState.toggle_detail(duel.id), variant="ghost", padding="0")),
        duel_detail(duel),
        spacing="3", width="100%", padding=t.CARD_PADDING, background=t.SURFACE, border_radius=t.RADIUS,
        class_name="ma-duel",
    )


def pending_card(duel: Duel, *, incoming) -> rx.Component:
    """A challenge waiting on somebody. Accepting restarts the clock, so the
    card says so rather than letting the window quietly shrink."""
    return rx.vstack(
        rx.vstack(text(rx.cond(incoming, f"{duel.their_name} challenged you", f"Waiting for {duel.their_name}"),
                       t.BODY),
                  text(f"{duel.metric_label} · starts when accepted", t.CAPTION, t.TEXT_2),
                  spacing="0", align="start", width="100%"),
        rx.cond(incoming,
                rx.hstack(button("Accept", DuelState.accept(duel.id), variant="secondary"),
                          button("Decline", DuelState.decline(duel.id), variant="ghost"), spacing="2"),
                button("Withdraw", DuelState.cancel(duel.id), variant="ghost")),
        spacing="2", width="100%", padding=t.CARD_PADDING, background=t.SURFACE, border_radius=t.RADIUS,
        class_name="ma-pending",
    )


def activity_row(entry: ActivityEntry) -> rx.Component:
    return list_row(entry.headline, f"{entry.display_name} · {entry.when_label}",
                    leading=rx.center(rx.text(entry.icon, **t.BODY), width="40px", height="40px",
                                      border_radius=t.RADIUS_PILL, background=t.SURFACE_2))


def mode_picker() -> rx.Component:
    """Challenge flow, step two: the modes, each with why it is fair. A mode
    the two of you cannot use yet is shown, disabled, with the server's
    reason - rather than hidden, which would just look missing."""

    def card(mode: DuelMode) -> rx.Component:
        return rx.vstack(
            text(mode.title, t.BODY, rx.cond(mode.eligible, t.TEXT, t.TEXT_2)),
            text(mode.fairness, t.CAPTION, t.TEXT_2),
            rx.cond(~mode.eligible, text(mode.reason, t.CAPTION, t.TEXT_2)),
            on_click=rx.cond(mode.eligible, DuelState.choose_mode(mode.metric), rx.noop()),
            cursor=rx.cond(mode.eligible, "pointer", "not-allowed"),
            opacity=rx.cond(mode.eligible, "1", "0.4"),
            spacing="1", align="start", width="100%", padding=t.CARD_PADDING, background=t.SURFACE_2,
            border_radius=t.RADIUS, class_name="ma-press ma-mode",
            custom_attrs={"role": "button", "aria-disabled": rx.cond(mode.eligible, "false", "true")},
        )

    return sheet(DuelState.show_modes, DuelState.close_modes,
                 rx.vstack(rx.foreach(DuelState.modes, card), spacing="2", width="100%"),
                 title=f"Challenge {DuelState.picking_name}")


def win_overlay() -> rx.Component:
    """A settled duel's moment - a reward moment, so it may glow. A loss is
    not a defeat screen: it shows what showing up earned, and offers the
    rematch."""
    kind = DuelState.result_kind
    return rx.cond(
        DuelState.show_win,
        rx.box(
            rx.center(
                rx.vstack(
                    text(rx.cond(kind == "draw", "Duel drawn", rx.cond(kind == "loss", "Good fight", "Duel won")),
                         t.TITLE_LG, class_name="lf-line"),
                    text(rx.cond(kind == "draw", f"Dead level with {DuelState.won_against}.",
                                 rx.cond(kind == "loss", f"{DuelState.won_against} took this one. You showed up.",
                                         f"You beat {DuelState.won_against}.")),
                         t.BODY, t.TEXT_2, text_align="center", class_name="lf-line"),
                    rx.cond(DuelState.won_points > 0,
                            number(f"+{DuelState.won_points}", "points", color=t.ACCENT)),
                    rx.vstack(
                        button("Continue", DuelState.dismiss_win, full=True),
                        rx.cond((kind != "win") & (DuelState.result_their_id != ""),
                                button("Rematch", DuelState.rematch, variant="ghost", full=True)),
                        spacing="2", width="100%", class_name="lf-line",
                    ),
                    spacing="4", align="center", class_name="lf-card", padding=t.space(32),
                    background=t.SURFACE, border_radius=t.RADIUS_SHEET, width="calc(100% - 40px)",
                    max_width="360px", box_shadow=f"0 0 64px {t.ACCENT_SOFT}", on_click=rx.stop_propagation,
                ),
                width="100%", height="100%",
            ),
            class_name="lf-veil", position="fixed", inset="0", background=t.SCRIM, z_index="100",
            on_click=DuelState.dismiss_win,
        ),
    )
