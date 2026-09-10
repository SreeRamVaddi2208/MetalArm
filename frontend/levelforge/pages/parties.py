"""Party page: selector, shared quest board, and leaderboard."""

import reflex as rx

from levelforge import theme
from levelforge.components.layout import (
    error_banner,
    notice_banner,
    section_heading,
    shell,
)
from levelforge.components.party_card import (
    invite_panel,
    leaderboard_row,
    party_quest_row,
    party_tab,
)
from levelforge.components.scroll_reveal import reveal, reveal_assets
from levelforge.state.parties import PartyState


def text_input(placeholder: str, on_change, value=None, accent=theme.ACCENT):
    return rx.input(
        placeholder=placeholder,
        on_change=on_change,
        value=value,
        width="100%",
        background="#0b1220",
        border=f"1px solid {theme.BORDER}",
        border_radius="9px",
        color=theme.TEXT,
        padding="0.6rem 0.75rem",
        font_size="0.88rem",
        _focus={"border_color": accent, "outline": "none"},
    )


def action_button(label, on_click, color=theme.ACCENT, fg="#04121c"):
    return rx.button(
        label,
        on_click=on_click,
        background=color,
        color=fg,
        border="none",
        border_radius="9px",
        font_weight="800",
        letter_spacing="0.12em",
        font_size="0.72rem",
        padding="0.6rem 1rem",
        cursor="pointer",
        width="100%",
    )


def ghost_button(label, on_click, hover=theme.DANGER):
    return rx.button(
        label,
        on_click=on_click,
        background="transparent",
        color=theme.FAINT,
        border=f"1px solid {theme.BORDER}",
        border_radius="8px",
        font_size="0.68rem",
        letter_spacing="0.12em",
        padding="0.45rem 0.7rem",
        cursor="pointer",
        _hover={"color": hover, "border_color": hover},
    )


def create_join_forms() -> rx.Component:
    return rx.vstack(
        rx.cond(
            PartyState.show_create,
            rx.vstack(
                text_input("Party name", PartyState.set_new_name, PartyState.new_name),
                action_button("CREATE PARTY", PartyState.create),
                spacing="3",
                **theme.panel(),
            ),
        ),
        rx.cond(
            PartyState.show_join,
            rx.vstack(
                text_input(
                    "Invite code, e.g. K7M2QXPA",
                    PartyState.set_join_code,
                    PartyState.join_code,
                ),
                rx.text(
                    "Codes are case-insensitive and dashes are ignored.",
                    color=theme.FAINT,
                    font_size="0.72rem",
                ),
                action_button("JOIN PARTY", PartyState.join),
                spacing="3",
                **theme.panel(),
            ),
        ),
        spacing="3",
        width="100%",
    )


def empty_state() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text("NO PARTIES YET", **theme.LABEL_STYLE),
            rx.text(
                "Create a party and share its invite code, or join one with a "
                "code a friend sent you.",
                color=theme.FAINT,
                font_size="0.85rem",
                text_align="center",
                max_width="380px",
            ),
            spacing="2",
            align="center",
        ),
        width="100%",
        padding="2.5rem 1rem",
        border=f"1px dashed {theme.BORDER}",
        border_radius="12px",
    )


def revealed_party_quest(quest) -> rx.Component:
    return reveal(party_quest_row(quest))


def party_detail() -> rx.Component:
    return rx.vstack(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.text("PARTY", **theme.LABEL_STYLE),
                    rx.heading(PartyState.selected.name, size="6", color=theme.TEXT),
                    rx.text(
                        PartyState.selected.seats_label,
                        color=theme.FAINT,
                        font_size="0.72rem",
                        letter_spacing="0.12em",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text("PARTY XP", **theme.LABEL_STYLE),
                    rx.heading(
                        PartyState.selected.total_party_xp.to_string(),
                        size="7",
                        color=theme.WARNING,
                    ),
                    spacing="1",
                    align="end",
                ),
                width="100%",
                align="center",
                flex_wrap="wrap",
                spacing="4",
            ),
            rx.divider(border_color=theme.BORDER),
            invite_panel(),
            rx.hstack(
                rx.spacer(),
                rx.cond(
                    PartyState.selected.is_owner,
                    ghost_button("DISSOLVE PARTY", PartyState.dissolve),
                    ghost_button("LEAVE PARTY", PartyState.leave),
                ),
                width="100%",
            ),
            spacing="3",
            **theme.panel(box_shadow=theme.glow(theme.ACCENT, "55px")),
        ),
        # --- shared board ---
        rx.vstack(
            section_heading(
                "SHARED QUEST BOARD",
                rx.button(
                    rx.cond(PartyState.show_quest_form, "CLOSE", "+ ADD QUEST"),
                    on_click=PartyState.toggle_quest_form,
                    background="transparent",
                    color=theme.ACCENT,
                    border=f"1px solid {theme.ACCENT}55",
                    border_radius="8px",
                    font_size="0.7rem",
                    letter_spacing="0.12em",
                    font_weight="700",
                    padding="0.45rem 0.8rem",
                    cursor="pointer",
                ),
            ),
            rx.cond(
                PartyState.show_quest_form,
                rx.vstack(
                    text_input(
                        "Shared quest title",
                        PartyState.set_quest_title,
                        PartyState.quest_title,
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("XP", **theme.LABEL_STYLE),
                            text_input("25", PartyState.set_quest_xp, PartyState.quest_xp),
                            spacing="1",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text("REPEATS", **theme.LABEL_STYLE),
                            rx.select(
                                ["daily", "weekly", "none"],
                                value=PartyState.quest_recurrence,
                                on_change=PartyState.set_quest_recurrence,
                                width="100%",
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                        flex_wrap="wrap",
                    ),
                    action_button("ADD TO BOARD", PartyState.add_quest),
                    spacing="3",
                    **theme.panel(),
                ),
            ),
            rx.cond(
                PartyState.has_quests,
                rx.vstack(
                    rx.foreach(PartyState.quests, revealed_party_quest),
                    spacing="3",
                    width="100%",
                ),
                rx.box(
                    rx.text(
                        "No shared quests yet. Anyone in the party can add one.",
                        color=theme.FAINT,
                        font_size="0.85rem",
                        text_align="center",
                    ),
                    width="100%",
                    padding="1.75rem 1rem",
                    border=f"1px dashed {theme.BORDER}",
                    border_radius="12px",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        # --- leaderboard ---
        rx.vstack(
            section_heading("LEADERBOARD"),
            rx.box(
                rx.foreach(PartyState.board, leaderboard_row),
                **theme.panel(),
            ),
            rx.text(
                "Ranked by XP contributed to this party. Personal quests count "
                "toward your own level, not the party's.",
                color=theme.FAINT,
                font_size="0.72rem",
                line_height="1.5",
            ),
            spacing="3",
            width="100%",
        ),
        spacing="5",
        width="100%",
    )


def parties_page() -> rx.Component:
    return shell(
        reveal_assets(),
        error_banner(PartyState.error),
        notice_banner(PartyState.notice),
        rx.hstack(
            rx.cond(
                PartyState.has_parties,
                rx.hstack(
                    rx.foreach(PartyState.parties, party_tab),
                    spacing="2",
                    overflow_x="auto",
                    flex="1",
                    min_width="0",
                    padding_bottom="0.25rem",
                ),
                rx.spacer(),
            ),
            rx.hstack(
                rx.button(
                    "+ CREATE",
                    on_click=PartyState.toggle_create,
                    background="transparent",
                    color=theme.ACCENT,
                    border=f"1px solid {theme.ACCENT}55",
                    border_radius="8px",
                    font_size="0.68rem",
                    letter_spacing="0.1em",
                    font_weight="700",
                    padding="0.45rem 0.7rem",
                    cursor="pointer",
                    white_space="nowrap",
                ),
                rx.button(
                    "JOIN",
                    on_click=PartyState.toggle_join,
                    background="transparent",
                    color=theme.MUTED,
                    border=f"1px solid {theme.BORDER}",
                    border_radius="8px",
                    font_size="0.68rem",
                    letter_spacing="0.1em",
                    font_weight="700",
                    padding="0.45rem 0.7rem",
                    cursor="pointer",
                    white_space="nowrap",
                ),
                spacing="2",
            ),
            width="100%",
            align="center",
            spacing="3",
            flex_wrap="wrap",
        ),
        create_join_forms(),
        rx.cond(PartyState.has_selection, party_detail(), empty_state()),
    )
