"""/duels: head to head over a window you choose - challenges waiting,
duels running, duels settled, and what your circle has been doing."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.duel_card import activity_row, duel_card, mode_picker, pending_card, win_overlay
from metalarm.components.layout import error_banner, shell
from metalarm.components.level_up import keyframes
from metalarm.state.duels import DuelState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import button, chip, chips, list_row, rows, section, stepper, text


def _challenge() -> rx.Component:
    s = DuelState
    return section(
        "New duel",
        chips(*[chip(label, selected=s.challenge_metric == value, on_click=s.set_challenge_metric(value))
                for label, value in (("Volume", "volume"), ("Sets", "sets"), ("Sessions", "sessions"))]),
        stepper(s.challenge_days, s.set_challenge_days,
                s.bump_days(-1), s.bump_days(1),
                unit="days", label="Days", mode="numeric"),
        button("Challenge your rival", s.challenge_rival, variant="secondary", icon="swords", full=True,
               class_name="ma-challenge-rival"),
        # The rival is generated from YOUR history. Saying so is the difference
        # between a training tool and a fake friend.
        text("Your rival's pace comes from your own recent weeks, not another lifter.", t.CAPTION, t.TEXT_2),
        rx.cond(s.opponents.length() > 0,
                rows(rx.foreach(s.opponents, lambda m: list_row(
                    m.display_name, "Friend or party member", chevron=True,
                    on_click=s.open_modes(m.user_id, m.display_name))))),
    )


def _group(title: str, items, render) -> rx.Component:
    return rx.cond(items.length() > 0,
                   section(title, rx.vstack(rx.foreach(items, render), spacing="2", width="100%")))


def duels_page() -> rx.Component:
    s = DuelState
    return shell(
        keyframes(),
        win_overlay(),
        top_bar("Duels", back="/profile"),
        error_banner(s.error),
        _group("Waiting", s.pending, lambda d: pending_card(d, incoming=~d.i_challenged)),
        _group("Running", s.active, duel_card),
        _challenge(),
        _group("Settled", s.completed, duel_card),
        section("Activity",
                rx.cond(s.feed.length() > 0, rows(rx.foreach(s.feed, activity_row)),
                        text("Nothing yet. Finish a workout, hit a record, or win a duel.", t.BODY, t.TEXT_2))),
        mode_picker(),
    )
