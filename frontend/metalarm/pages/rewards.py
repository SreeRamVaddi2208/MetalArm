"""Rewards shop."""

import reflex as rx

from metalarm import theme
from metalarm.components.layout import (
    error_banner,
    notice_banner,
    section_heading,
    shell,
)
from metalarm.components.reward_card import history_row, reward_card, wallet_panel
from metalarm.components.scroll_reveal import pinned, reveal, reveal_assets
from metalarm.state.rewards import RewardState


def create_form() -> rx.Component:
    return rx.cond(
        RewardState.show_form,
        rx.vstack(
            rx.input(
                placeholder="Reward title, e.g. order takeout",
                on_change=RewardState.set_new_title,
                value=RewardState.new_title,
                width="100%",
                background="#0b1220",
                border=f"1px solid {theme.BORDER}",
                border_radius="9px",
                color=theme.TEXT,
                padding="0.6rem 0.75rem",
                font_size="0.88rem",
                _focus={"border_color": theme.WARNING, "outline": "none"},
            ),
            rx.vstack(
                rx.text("POINT COST", **theme.LABEL_STYLE),
                rx.input(
                    placeholder="50",
                    on_change=RewardState.set_new_cost,
                    value=RewardState.new_cost,
                    width="100%",
                    background="#0b1220",
                    border=f"1px solid {theme.BORDER}",
                    border_radius="9px",
                    color=theme.TEXT,
                    padding="0.6rem 0.75rem",
                    font_size="0.88rem",
                ),
                spacing="1",
                width="100%",
            ),
            rx.button(
                "ADD REWARD",
                on_click=RewardState.create,
                background=theme.WARNING,
                color="#1a1206",
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


def empty_shop() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text("NO REWARDS YET", **theme.LABEL_STYLE),
            rx.text(
                "Define something worth working toward, then spend points on it.",
                color=theme.FAINT,
                font_size="0.85rem",
                text_align="center",
            ),
            spacing="2",
            align="center",
        ),
        width="100%",
        padding="2.5rem 1rem",
        border=f"1px dashed {theme.BORDER}",
        border_radius="12px",
    )


def revealed_reward(reward) -> rx.Component:
    return reveal(reward_card(reward))


def rewards_page() -> rx.Component:
    return shell(
        reveal_assets(),
        # The wallet is this page's hero: it holds position while the shop and
        # the spend history scroll past, so the balance stays readable while
        # you decide what to spend it on.
        pinned(wallet_panel()),
        error_banner(RewardState.error),
        notice_banner(RewardState.notice),
        rx.vstack(
            section_heading(
                "REWARDS SHOP",
                rx.button(
                    rx.cond(RewardState.show_form, "CLOSE", "+ NEW REWARD"),
                    on_click=RewardState.toggle_form,
                    background="transparent",
                    color=theme.WARNING,
                    border=f"1px solid {theme.WARNING}55",
                    border_radius="8px",
                    font_size="0.7rem",
                    letter_spacing="0.12em",
                    font_weight="700",
                    padding="0.45rem 0.8rem",
                    cursor="pointer",
                ),
            ),
            create_form(),
            rx.cond(
                RewardState.has_rewards,
                rx.vstack(
                    rx.foreach(RewardState.rewards, revealed_reward),
                    spacing="3",
                    width="100%",
                ),
                rx.cond(RewardState.loading, rx.spinner(), empty_shop()),
            ),
            spacing="3",
            width="100%",
        ),
        rx.cond(
            RewardState.has_history,
            rx.vstack(
                section_heading("SPEND HISTORY"),
                rx.box(
                    rx.foreach(RewardState.history, history_row),
                    **theme.panel(),
                ),
                spacing="3",
                width="100%",
            ),
        ),
    )
