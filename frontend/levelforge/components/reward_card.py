"""Rewards shop cards."""

import reflex as rx

from levelforge import theme
from levelforge.models import Redemption, Reward
from levelforge.state.rewards import RewardState


def reward_card(reward: Reward) -> rx.Component:
    can_buy = reward.affordable
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(reward.title, color=theme.TEXT, font_weight="700", font_size="1rem"),
                rx.hstack(
                    rx.text(
                        f"{reward.point_cost} pts",
                        color=rx.cond(can_buy, theme.WARNING, theme.FAINT),
                        font_size="0.82rem",
                        font_weight="700",
                    ),
                    rx.cond(
                        reward.times_redeemed > 0,
                        rx.text(
                            f"redeemed {reward.times_redeemed}x",
                            color=theme.FAINT,
                            font_size="0.74rem",
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
                    "REDEEM",
                    on_click=RewardState.redeem(reward.id),
                    disabled=~can_buy,
                    background=rx.cond(can_buy, theme.WARNING, "transparent"),
                    color=rx.cond(can_buy, "#1a1206", theme.FAINT),
                    border=rx.cond(can_buy, "none", f"1px solid {theme.BORDER}"),
                    border_radius="9px",
                    font_size="0.72rem",
                    font_weight="800",
                    letter_spacing="0.12em",
                    padding="0.55rem 0.9rem",
                    cursor=rx.cond(can_buy, "pointer", "not-allowed"),
                    white_space="nowrap",
                ),
                rx.button(
                    "Remove",
                    on_click=RewardState.remove(reward.id),
                    background="transparent",
                    color=theme.FAINT,
                    border="none",
                    font_size="0.68rem",
                    cursor="pointer",
                    padding="0.2rem",
                    _hover={"color": theme.DANGER},
                ),
                spacing="2",
                align="end",
            ),
            width="100%",
            align="center",
            spacing="4",
        ),
        width="100%",
        padding="1.1rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER}",
        border_radius="12px",
    )


def history_row(entry: Redemption) -> rx.Component:
    return rx.hstack(
        rx.text(entry.reward_title, color=theme.MUTED, font_size="0.82rem"),
        rx.spacer(),
        rx.text(entry.redeemed_at, color=theme.FAINT, font_size="0.72rem"),
        rx.text(
            f"-{entry.points_spent}",
            color=theme.DANGER,
            font_size="0.82rem",
            font_weight="700",
            min_width="48px",
            text_align="right",
        ),
        width="100%",
        padding_block="0.5rem",
        border_bottom=f"1px solid {theme.BORDER}",
        spacing="3",
        align="center",
    )


def wallet_panel() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text("BALANCE", **theme.LABEL_STYLE),
            rx.heading(
                RewardState.balance.to_string(), size="7", color=theme.WARNING
            ),
            spacing="1",
            align="start",
        ),
        rx.spacer(),
        rx.vstack(
            rx.text("EARNED", **theme.LABEL_STYLE),
            rx.text(
                RewardState.earned.to_string(),
                color=theme.SUCCESS,
                font_weight="700",
            ),
            spacing="1",
            align="end",
        ),
        rx.vstack(
            rx.text("SPENT", **theme.LABEL_STYLE),
            rx.text(
                RewardState.spent.to_string(), color=theme.MUTED, font_weight="700"
            ),
            spacing="1",
            align="end",
        ),
        align="center",
        spacing="6",
        **theme.panel(box_shadow=theme.glow(theme.WARNING, "50px")),
    )
