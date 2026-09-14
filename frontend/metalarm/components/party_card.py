"""Party components: selector, shared board rows, and the leaderboard."""

import reflex as rx

from metalarm import theme
from metalarm.models import LeaderboardRow, Party, PartyQuest
from metalarm.state.parties import PartyState


def rank_letter(rank: rx.Var) -> rx.Component:
    """Per-rank colour, resolved with rx.match because a Python dict indexed by
    a Var is not available in the compiled component."""
    color = rx.match(
        rank,
        ("E", theme.RANK_COLORS["E"]),
        ("D", theme.RANK_COLORS["D"]),
        ("C", theme.RANK_COLORS["C"]),
        ("B", theme.RANK_COLORS["B"]),
        ("A", theme.RANK_COLORS["A"]),
        ("S", theme.RANK_COLORS["S"]),
        theme.MUTED,
    )
    return rx.center(
        rx.text(rank, color=color, font_weight="900", font_size="0.8rem"),
        width="26px",
        height="26px",
        border=f"1px solid {color}66",
        border_radius="7px",
        flex_shrink="0",
    )


def party_tab(party: Party) -> rx.Component:
    selected = PartyState.selected.id == party.id
    return rx.button(
        rx.hstack(
            rx.text(party.name, font_weight="700", font_size="0.82rem"),
            rx.text(party.seats_label, color=theme.FAINT, font_size="0.65rem"),
            spacing="2",
            align="center",
        ),
        on_click=PartyState.select(party.id),
        background=rx.cond(selected, f"{theme.ACCENT}18", "transparent"),
        color=rx.cond(selected, theme.ACCENT, theme.MUTED),
        border=f"1px solid {rx.cond(selected, theme.ACCENT, theme.BORDER)}",
        border_radius="10px",
        padding="0.5rem 0.85rem",
        cursor="pointer",
        white_space="nowrap",
    )


def invite_panel() -> rx.Component:
    """The invite code, shown only to members - it is a capability, not
    public metadata."""
    return rx.hstack(
        rx.vstack(
            rx.text("INVITE CODE", **theme.LABEL_STYLE),
            rx.text(
                PartyState.selected.invite_code,
                color=theme.ACCENT,
                font_weight="800",
                font_size="1.1rem",
                letter_spacing="0.22em",
                font_family="ui-monospace, SFMono-Regular, Menlo, monospace",
            ),
            spacing="1",
            align="start",
        ),
        rx.spacer(),
        rx.cond(
            PartyState.selected.is_owner,
            rx.button(
                "ROTATE",
                on_click=PartyState.rotate_invite,
                background="transparent",
                color=theme.MUTED,
                border=f"1px solid {theme.BORDER}",
                border_radius="8px",
                font_size="0.68rem",
                letter_spacing="0.12em",
                padding="0.45rem 0.7rem",
                cursor="pointer",
                _hover={"color": theme.WARNING, "border_color": theme.WARNING},
            ),
        ),
        width="100%",
        align="center",
        flex_wrap="wrap",
        spacing="3",
    )


def party_quest_row(quest: PartyQuest) -> rx.Component:
    done = quest.completed_in_current_period
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.box(
                        rx.text(
                            quest.recurrence_label,
                            font_size="0.6rem",
                            letter_spacing="0.14em",
                            font_weight="800",
                            color=theme.ACCENT,
                        ),
                        padding="0.18rem 0.45rem",
                        border=f"1px solid {theme.ACCENT}55",
                        border_radius="6px",
                    ),
                    rx.text(
                        quest.progress_label,
                        color=theme.SUCCESS,
                        font_size="0.68rem",
                        font_weight="700",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text(
                    quest.title,
                    color=rx.cond(done, theme.MUTED, theme.TEXT),
                    font_weight="700",
                    font_size="0.95rem",
                    text_decoration=rx.cond(done, "line-through", "none"),
                ),
                rx.text(f"+{quest.xp_reward} XP", color=theme.ACCENT, font_size="0.75rem"),
                spacing="2",
                align="start",
                flex="1",
                min_width="0",
            ),
            rx.vstack(
                rx.button(
                    rx.cond(done, "DONE", "COMPLETE"),
                    on_click=PartyState.complete(quest.id),
                    disabled=done,
                    background=rx.cond(done, "transparent", theme.ACCENT),
                    color=rx.cond(done, theme.FAINT, theme.ON_ACCENT),
                    border=rx.cond(done, f"1px solid {theme.BORDER}", "none"),
                    border_radius="9px",
                    font_size="0.7rem",
                    font_weight="800",
                    letter_spacing="0.1em",
                    padding="0.5rem 0.8rem",
                    cursor=rx.cond(done, "default", "pointer"),
                    white_space="nowrap",
                ),
                rx.button(
                    "Remove",
                    on_click=PartyState.remove_quest(quest.id),
                    background="transparent",
                    color=theme.FAINT,
                    border="none",
                    font_size="0.66rem",
                    cursor="pointer",
                    padding="0.15rem",
                    _hover={"color": theme.DANGER},
                ),
                spacing="2",
                align="end",
            ),
            width="100%",
            align="start",
            spacing="4",
        ),
        width="100%",
        padding="1rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER}",
        border_radius="12px",
        opacity=rx.cond(done, "0.72", "1"),
    )


def leaderboard_row(entry: LeaderboardRow) -> rx.Component:
    return rx.hstack(
        rx.text(
            entry.position.to_string(),
            color=theme.FAINT,
            font_size="0.8rem",
            font_weight="800",
            min_width="22px",
        ),
        rank_letter(entry.rank),
        rx.vstack(
            rx.text(
                entry.display_name,
                color=rx.cond(entry.is_me, theme.ACCENT, theme.TEXT),
                font_weight=rx.cond(entry.is_me, "800", "600"),
                font_size="0.86rem",
            ),
            rx.text(f"Level {entry.level}", color=theme.FAINT, font_size="0.68rem"),
            spacing="0",
            align="start",
            flex="1",
            min_width="0",
        ),
        rx.text(
            f"{entry.party_xp} XP",
            color=theme.WARNING,
            font_weight="700",
            font_size="0.85rem",
            white_space="nowrap",
        ),
        width="100%",
        align="center",
        spacing="3",
        padding_block="0.55rem",
        border_bottom=f"1px solid {theme.BORDER}",
    )
