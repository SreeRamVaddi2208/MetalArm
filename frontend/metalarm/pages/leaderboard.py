"""/leaderboard: friends ranked by points, this week or all time. Your own
row stays in sight when the list runs past it. No podium."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.pages.home import board_row
from metalarm.state.home import HomeState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import empty_state, link_button, segmented, skeleton_rows


def leaderboard_page() -> rx.Component:
    s = HomeState
    return shell(
        top_bar("Leaderboard", back="/home"),
        segmented(["This week", "All time"], rx.cond(s.period == "week", "This week", "All time"), s.set_period),
        error_banner(s.error),
        rx.cond(
            s.board_loaded,
            rx.cond(
                s.board.length() > 1,
                rx.vstack(rx.foreach(s.board, board_row), spacing="1", width="100%", class_name="ma-board"),
                empty_state("trophy", "Follow friends to see how you stack up.",
                            link_button("Find friends", "/profile/people", icon="user-plus")),
            ),
            skeleton_rows(6),
        ),
        pinned=rx.cond(~s.me_in_view & (s.me_row.length() > 0),
                       rx.box(board_row(s.me_row), width="100%", background=t.BG)),
    )
