"""/quests: the server's quests for today and this week, the streak they
feed, and your own. A new quest is written in a sheet."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.components.level_up import keyframes, level_up_overlay
from metalarm.components.quest_card import empty_board, generated_board, quest_card
from metalarm.state.quests import QuestState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import button, chip, chips, field, icon_button, section, sheet, skeleton_rows, text


def _labelled(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(text(label, t.CAPTION, t.TEXT_2), control, spacing="1", width="100%")


def _new_sheet() -> rx.Component:
    s = QuestState
    return sheet(
        s.show_form, s.toggle_form,
        field(s.new_title, s.set_new_title, "Quest title"),
        field(s.new_description, s.set_new_description, "Description (optional)"),
        rx.grid(_labelled("XP", field(s.new_xp, s.set_new_xp, "50", mode="numeric")),
                _labelled("Points", field(s.new_points, s.set_new_points, "5", mode="numeric")),
                columns="2", gap=t.space(12), width="100%"),
        _labelled("Repeats", chips(*[chip(label, selected=s.new_recurrence == value,
                                          on_click=s.set_new_recurrence(value))
                                     for label, value in (("Daily", "daily"), ("Weekly", "weekly"),
                                                          ("Once", "none"))])),
        error_banner(s.error),
        title="New quest",
        action=button("Create quest", s.create, full=True),
    )


def quests_page() -> rx.Component:
    s = QuestState
    return shell(
        keyframes(),
        level_up_overlay(),
        top_bar("Quests", back="/profile", trailing=icon_button("plus", "New quest", on_click=s.toggle_form)),
        error_banner(s.error),
        generated_board(),
        section("Your quests",
                rx.cond(s.has_quests, rx.vstack(rx.foreach(s.quests, quest_card), spacing="0", width="100%"),
                        rx.cond(s.loading, skeleton_rows(3), empty_board()))),
        _new_sheet(),
    )
