"""Quest board + Stat Panel."""

import reflex as rx

from levelforge import theme
from levelforge.components.layout import error_banner, section_heading, shell
from levelforge.components.level_up import keyframes, level_up_overlay
from levelforge.components.quest_card import empty_board, quest_card
from levelforge.components.stat_panel import stat_panel
from levelforge.state.quests import QuestState


def input_box(placeholder: str, on_change, value=None, **kwargs) -> rx.Component:
    return rx.input(
        placeholder=placeholder,
        on_change=on_change,
        value=value,
        background="#0b1220",
        border=f"1px solid {theme.BORDER}",
        border_radius="9px",
        color=theme.TEXT,
        padding="0.6rem 0.75rem",
        font_size="0.88rem",
        _focus={"border_color": theme.ACCENT, "outline": "none"},
        **kwargs,
    )


def create_form() -> rx.Component:
    return rx.cond(
        QuestState.show_form,
        rx.vstack(
            input_box("Quest title", QuestState.set_new_title, QuestState.new_title, width="100%"),
            input_box(
                "Description (optional)",
                QuestState.set_new_description,
                QuestState.new_description,
                width="100%",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("XP", **theme.LABEL_STYLE),
                    input_box("50", QuestState.set_new_xp, QuestState.new_xp, width="100%"),
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("POINTS", **theme.LABEL_STYLE),
                    input_box("5", QuestState.set_new_points, QuestState.new_points, width="100%"),
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("REPEATS", **theme.LABEL_STYLE),
                    rx.select(
                        ["daily", "weekly", "none"],
                        value=QuestState.new_recurrence,
                        on_change=QuestState.set_new_recurrence,
                        width="100%",
                    ),
                    spacing="1",
                    width="100%",
                ),
                spacing="3",
                width="100%",
                flex_wrap="wrap",
            ),
            rx.button(
                "CREATE QUEST",
                on_click=QuestState.create,
                background=theme.ACCENT,
                color="#04121c",
                border="none",
                border_radius="9px",
                font_weight="800",
                letter_spacing="0.12em",
                font_size="0.74rem",
                padding="0.65rem 1rem",
                cursor="pointer",
                width="100%",
            ),
            spacing="3",
            **theme.panel(),
        ),
    )


def dashboard_page() -> rx.Component:
    return shell(
        keyframes(),
        level_up_overlay(),
        rx.box(
            rx.vstack(
                stat_panel(),
                rx.vstack(
                    section_heading(
                        "QUEST BOARD",
                        rx.button(
                            rx.cond(QuestState.show_form, "CLOSE", "+ NEW QUEST"),
                            on_click=QuestState.toggle_form,
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
                    error_banner(QuestState.error),
                    create_form(),
                    rx.cond(
                        QuestState.has_quests,
                        rx.vstack(
                            rx.foreach(QuestState.quests, quest_card),
                            spacing="3",
                            width="100%",
                        ),
                        rx.cond(QuestState.loading, rx.spinner(), empty_board()),
                    ),
                    spacing="3",
                    width="100%",
                ),
                spacing="5",
                width="100%",
            ),
            width="100%",
        ),
    )
