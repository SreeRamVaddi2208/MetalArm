"""Quest board cards."""

import reflex as rx

from metalarm import theme
from metalarm.models import GeneratedQuest, Quest
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
                    color=rx.cond(done, theme.FAINT, theme.ON_ACCENT),
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


# ---------------------------------------------------------------------------
# Generated quests - handed out and tracked by the server
# ---------------------------------------------------------------------------


def _progress_bar(scale) -> rx.Component:
    """scaleX, not width: a transform stays on the compositor (see xp_bar)."""
    return rx.box(
        rx.box(
            width="100%",
            height="100%",
            transform=f"scaleX({scale})",
            transform_origin="left center",
            background=f"linear-gradient(90deg, {theme.ACCENT_DIM}, {theme.ACCENT})",
            border_radius="999px",
            transition="transform 420ms cubic-bezier(0.22, 1, 0.36, 1)",
        ),
        width="100%",
        height="6px",
        background=theme.FIELD,
        border_radius="999px",
        overflow="hidden",
    )


def generated_quest_card(quest: GeneratedQuest) -> rx.Component:
    done = quest.done
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.cond(
                    done,
                    rx.box(pill("✓ DONE", theme.SUCCESS), class_name="lf-check"),
                    rx.text(quest.time_left, color=theme.FAINT, font_size="0.68rem"),
                ),
                rx.spacer(),
                rx.text(f"+{quest.reward_points} pts", color=theme.WARNING, font_size="0.74rem", font_weight="700"),
                width="100%",
                align="center",
            ),
            rx.text(
                quest.title,
                color=rx.cond(done, theme.MUTED, theme.TEXT),
                font_weight="700",
                font_size="0.95rem",
            ),
            rx.text(quest.description, color=theme.FAINT, font_size="0.78rem", line_height="1.45"),
            _progress_bar(quest.scale),
            rx.hstack(
                rx.text(quest.progress_label, color=theme.MUTED, font_size="0.72rem"),
                rx.spacer(),
                rx.cond(
                    quest.can_reroll,
                    rx.button(
                        rx.icon("refresh-cw", size=12),
                        "Reroll",
                        on_click=QuestState.reroll(quest.id),
                        background="transparent",
                        color=theme.MUTED,
                        border=f"1px solid {theme.BORDER}",
                        border_radius="7px",
                        font_size="0.66rem",
                        letter_spacing="0.08em",
                        padding="0.25rem 0.55rem",
                        cursor="pointer",
                        _hover={"color": theme.TEXT, "border_color": theme.BORDER_HI},
                    ),
                ),
                width="100%",
                align="center",
            ),
            spacing="2",
            width="100%",
            align="start",
        ),
        width="100%",
        padding="1rem",
        background=theme.PANEL,
        border=f"1px solid {rx.cond(done, theme.BORDER, theme.BORDER_HI)}",
        border_radius="12px",
        opacity=rx.cond(done, "0.72", "1"),
        transition="opacity 260ms ease",
        class_name=rx.cond(done, "lf-complete", ""),
    )


def freeze_icons(slots) -> rx.Component:
    """One snowflake per freeze slot, lit where a freeze is held."""
    return rx.hstack(
        rx.foreach(
            slots,
            lambda held: rx.icon(
                "snowflake",
                size=14,
                color=rx.cond(held, theme.ACCENT, theme.BORDER_HI),
            ),
        ),
        spacing="1",
        align="center",
        title="Streak freezes: each one covers a week that falls short",
    )


def generated_board() -> rx.Component:
    """Today's and this week's quests, above the user's own."""
    column = lambda label, items: rx.vstack(  # noqa: E731
        rx.text(label, **theme.LABEL_STYLE),
        rx.foreach(items, generated_quest_card),
        spacing="2",
        width="100%",
        min_width="0",
    )
    return rx.cond(
        QuestState.has_generated,
        rx.vstack(
            rx.hstack(
                rx.text(QuestState.streak.label, color=rx.cond(QuestState.streak.weeks > 0, theme.SUCCESS, theme.FAINT),
                        font_size="0.7rem", font_weight="800", letter_spacing="0.14em"),
                freeze_icons(QuestState.streak.freeze_slots),
                rx.spacer(),
                rx.text(QuestState.streak.sub, color=theme.FAINT, font_size="0.72rem"),
                width="100%",
                align="center",
                flex_wrap="wrap",
                spacing="2",
            ),
            rx.grid(
                column("TODAY", QuestState.daily),
                column("THIS WEEK", QuestState.weekly),
                columns="1",
                gap="1rem",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
    )
