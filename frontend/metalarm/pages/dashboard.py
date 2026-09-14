"""Quest board + Stat Panel."""

import reflex as rx

from metalarm import theme
from metalarm.components.layout import error_banner, section_heading, shell
from metalarm.components.level_up import keyframes, level_up_overlay
from metalarm.components.quest_card import empty_board, quest_card
from metalarm.components.scroll_reveal import pinned, reveal, reveal_assets
from metalarm.components.stat_panel import stat_panel
from metalarm.state.quests import QuestState


def input_box(placeholder: str, on_change, value=None, **kwargs) -> rx.Component:
    return rx.input(
        placeholder=placeholder,
        on_change=on_change,
        value=value,
        background=theme.FIELD,
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
                color=theme.ON_ACCENT,
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


def revealed_quest(quest) -> rx.Component:
    """No artificial stagger delay.

    With a scroll-linked reveal the stagger already comes from the real thing -
    cards enter the viewport at different scroll positions. Adding a fixed
    per-index delay on top would make later cards arrive visibly late on a long
    board, which reads as lag rather than polish.
    """
    return reveal(quest_card(quest))


def dashboard_page() -> rx.Component:
    return shell(
        keyframes(),
        reveal_assets(),
        level_up_overlay(),
        rx.box(
            # Two columns from 900px up: the Stat Panel holds position while
            # the quest board scrolls past it - the pinned-hero pattern from
            # Section 7. Below that width it stacks and the panel is a normal
            # block, because there is nothing beside it to scroll.
            rx.flex(
                rx.box(
                    pinned(stat_panel()),
                    width=rx.breakpoints(initial="100%", lg="340px"),
                    flex_shrink="0",
                ),
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
                            rx.foreach(QuestState.quests, revealed_quest),
                            spacing="3",
                            width="100%",
                        ),
                        rx.cond(QuestState.loading, rx.spinner(), empty_board()),
                    ),
                    spacing="3",
                    width="100%",
                    flex="1",
                    min_width="0",
                ),
                # rx.breakpoints, not a list: Flex.direction is a typed Radix
                # prop and rejects the list shorthand that style props accept.
                # `lg` is 1024px and MUST match the .lf-pinned media query in
                # scroll_reveal.py - pinning the panel at a width where there
                # is no second column beside it would just freeze it in place.
                direction=rx.breakpoints(initial="column", lg="row"),
                gap="1.25rem",
                width="100%",
                align="start",
            ),
            width="100%",
        ),
    )
