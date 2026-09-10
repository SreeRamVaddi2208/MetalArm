"""Quest board cards."""

import reflex as rx

from metalarm import theme
from metalarm.models import Quest
from metalarm.state.quests import QuestState


def pill(text: rx.Var | str, color: str) -> rx.Component:
    return rx.box(
        rx.text(text, font_size="0.62rem", letter_spacing="0.14em", font_weight="800", color=color),
        padding="0.2rem 0.5rem",
        border=f"1px solid {color}55",
        border_radius="6px",
        background=f"{color}12",
    )


def quest_card(quest: Quest) -> rx.Component:
    done = quest.completed_in_current_period
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    pill(quest.recurrence_label, theme.ACCENT),
                    rx.cond(
                        done,
                        rx.box(
                            pill("✓ DONE", theme.SUCCESS),
                            class_name="lf-check",
                        ),
                    ),
                    spacing="2",
                ),
                rx.text(
                    quest.title,
                    color=rx.cond(done, theme.MUTED, theme.TEXT),
                    font_weight="700",
                    font_size="1rem",
                    text_decoration=rx.cond(done, "line-through", "none"),
                ),
                rx.cond(
                    quest.description != "",
                    rx.text(quest.description, color=theme.FAINT, font_size="0.8rem"),
                ),
                rx.hstack(
                    rx.text(f"+{quest.xp_reward} XP", color=theme.ACCENT, font_size="0.78rem"),
                    rx.cond(
                        quest.points_reward > 0,
                        rx.text(
                            f"+{quest.points_reward} pts",
                            color=theme.WARNING,
                            font_size="0.78rem",
                        ),
                    ),
                    spacing="3",
                ),
                spacing="2",
                align="start",
                flex="1",
                min_width="0",
            ),
            rx.vstack(
                rx.button(
                    rx.cond(done, "DONE", "COMPLETE"),
                    on_click=QuestState.complete(quest.id),
                    disabled=done,
                    background=rx.cond(done, "transparent", theme.ACCENT),
                    color=rx.cond(done, theme.FAINT, "#04121c"),
                    border=rx.cond(done, f"1px solid {theme.BORDER}", "none"),
                    border_radius="9px",
                    font_size="0.72rem",
                    font_weight="800",
                    letter_spacing="0.12em",
                    padding="0.55rem 0.9rem",
                    cursor=rx.cond(done, "default", "pointer"),
                    white_space="nowrap",
                ),
                rx.hstack(
                    rx.button(
                        "Archive",
                        on_click=QuestState.archive(quest.id),
                        background="transparent",
                        color=theme.FAINT,
                        border="none",
                        font_size="0.68rem",
                        cursor="pointer",
                        padding="0.2rem",
                        _hover={"color": theme.MUTED},
                    ),
                    rx.button(
                        "Delete",
                        on_click=QuestState.remove(quest.id),
                        background="transparent",
                        color=theme.FAINT,
                        border="none",
                        font_size="0.68rem",
                        cursor="pointer",
                        padding="0.2rem",
                        _hover={"color": theme.DANGER},
                    ),
                    spacing="2",
                ),
                spacing="2",
                align="end",
            ),
            width="100%",
            align="start",
            spacing="4",
        ),
        width="100%",
        padding="1.1rem",
        background=theme.PANEL,
        border=f"1px solid {rx.cond(done, theme.BORDER, theme.BORDER_HI)}",
        border_radius="12px",
        opacity=rx.cond(done, "0.72", "1"),
        # Opacity only. A completed card settles rather than celebrating -
        # Section 7 reserves the heavy motion for level-up and rank-up.
        transition="opacity 260ms ease",
        class_name=rx.cond(done, "lf-complete", ""),
    )


def empty_board() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text("NO ACTIVE QUESTS", **theme.LABEL_STYLE),
            rx.text(
                "Create your first quest to start earning XP.",
                color=theme.FAINT,
                font_size="0.85rem",
            ),
            spacing="2",
            align="center",
        ),
        width="100%",
        padding="2.5rem 1rem",
        border=f"1px dashed {theme.BORDER}",
        border_radius="12px",
    )
