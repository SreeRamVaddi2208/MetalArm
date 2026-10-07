"""/rewards: your points, the rewards you have set yourself, and what you
have spent. A new reward is written in a sheet."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, notice_banner, shell
from metalarm.models import Redemption, Reward
from metalarm.state.rewards import RewardState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import (
    button,
    field,
    icon_button,
    list_row,
    rows,
    section,
    sheet,
    skeleton_rows,
    stat_group,
    stat_tile,
    text,
)


def reward_card(reward: Reward) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(text(reward.title, t.BODY),
                      text(rx.cond(reward.times_redeemed > 0,
                                   f"{reward.point_cost} pts · redeemed {reward.times_redeemed}×",
                                   f"{reward.point_cost} pts"), t.CAPTION, t.TEXT_2, **t.TABULAR),
                      spacing="1", align="start", flex="1", min_width="0"),
            button("Redeem", RewardState.redeem(reward.id), variant="secondary", disabled=~reward.affordable),
            width="100%", align="center", spacing="3",
        ),
        button("Remove", RewardState.remove(reward.id), variant="ghost", color=t.DANGER, padding="0"),
        spacing="1", width="100%", padding_y=t.space(12), border_bottom=t.HAIRLINE, class_name="ma-reward",
    )


def history_row(entry: Redemption) -> rx.Component:
    return list_row(entry.reward_title, entry.redeemed_at,
                    trailing=text(f"−{entry.points_spent}", t.BODY, t.TEXT_2, **t.TABULAR))


def rewards_page() -> rx.Component:
    s = RewardState
    return shell(
        top_bar("Rewards", back="/profile", trailing=icon_button("plus", "New reward", on_click=s.toggle_form)),
        stat_group(stat_tile(s.figures["balance"], "Balance", big=True), stat_tile(s.figures["earned"], "Earned"),
                   stat_tile(s.figures["spent"], "Spent")),
        error_banner(s.error),
        notice_banner(s.notice),
        section("Shop",
                rx.cond(s.has_rewards, rx.vstack(rx.foreach(s.rewards, reward_card), spacing="0", width="100%"),
                        rx.cond(s.loading, skeleton_rows(3),
                                text("Set something worth working toward, then spend points on it.", t.BODY,
                                     t.TEXT_2)))),
        rx.cond(s.has_history, section("Spent", rows(rx.foreach(s.history, history_row)))),
        sheet(s.show_form, s.toggle_form,
              field(s.new_title, s.set_new_title, "Reward, e.g. order takeout"),
              field(s.new_cost, s.set_new_cost, "Point cost, e.g. 50", mode="numeric"),
              title="New reward", action=button("Add reward", s.create, full=True)),
    )
