"""Party pieces: the party chips, the invite code, shared quest rows, and
the ranked rows of the party's boards."""

import reflex as rx

from metalarm import theme as t
from metalarm.models import LeaderboardRow, Party, PartyQuest
from metalarm.state.parties import PartyState
from metalarm.ui.primitives import button, chip, text
from metalarm.ui.rank_badge import rank_badge


def party_tab(party: Party) -> rx.Component:
    return chip(party.name, selected=PartyState.selected.id == party.id, on_click=PartyState.select(party.id))


def invite_panel() -> rx.Component:
    """The invite code, shown only to members - it is a capability, not
    public metadata."""
    return rx.hstack(
        rx.vstack(text("Invite code", t.CAPTION, t.TEXT_2),
                  text(PartyState.selected.invite_code, t.TITLE, letter_spacing="0.16em", class_name="ma-invite"),
                  spacing="0", align="start"),
        rx.spacer(),
        rx.cond(PartyState.selected.is_owner, button("Rotate", PartyState.rotate_invite, variant="ghost")),
        width="100%", align="center",
    )


def party_quest_row(quest: PartyQuest) -> rx.Component:
    done = quest.completed_in_current_period
    return rx.vstack(
        rx.hstack(
            rx.vstack(text(quest.title, t.BODY, rx.cond(done, t.TEXT_2, t.TEXT),
                           text_decoration=rx.cond(done, "line-through", "none")),
                      text(f"{quest.recurrence_label} · +{quest.xp_reward} XP · {quest.progress_label}", t.CAPTION,
                           t.TEXT_2),
                      spacing="1", align="start", flex="1", min_width="0"),
            rx.cond(done, rx.icon("check", size=20, color=t.ACCENT),
                    button("Complete", PartyState.complete(quest.id), variant="secondary")),
            width="100%", align="center", spacing="3",
        ),
        button("Remove", PartyState.remove_quest(quest.id), variant="ghost", color=t.DANGER, padding="0"),
        spacing="1", width="100%", padding_y=t.space(12), border_bottom=t.HAIRLINE, class_name="ma-party-quest",
    )


def ranked_row(position, rank, name, sub, value, is_me) -> rx.Component:
    """Position, rank badge, name, and the number it is ranked by. Yours is
    tinted."""
    return rx.hstack(
        text(position, t.LABEL, t.TEXT_2, width="24px", **t.TABULAR),
        rank_badge(rank, 24),
        rx.vstack(text(name, t.BODY, overflow="hidden", text_overflow="ellipsis", white_space="nowrap",
                       max_width="100%"),
                  text(sub, t.CAPTION, t.TEXT_2), spacing="0", align="start", flex="1", min_width="0"),
        text(value, t.BODY, t.TEXT_2, white_space="nowrap", **t.TABULAR),
        width="100%", align="center", spacing="3", min_height=t.ROW_MIN, padding_x=t.space(8),
        background=rx.cond(is_me, t.ACCENT_SOFT, "transparent"), border_radius=t.RADIUS,
    )


def leaderboard_row(entry: LeaderboardRow) -> rx.Component:
    return ranked_row(entry.position, entry.rank, entry.display_name, f"Level {entry.level}",
                      f"{entry.party_xp} XP", entry.is_me)
