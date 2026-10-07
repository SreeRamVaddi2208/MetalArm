"""Quest rows: the server's quests (today, this week) and your own."""

import reflex as rx

from metalarm import theme as t
from metalarm.models import GeneratedQuest, Quest
from metalarm.state.quests import QuestState
from metalarm.ui.primitives import button, icon_button, progress_bar, text


def quest_card(quest: Quest) -> rx.Component:
    """One of your own quests. Complete is secondary: the board has no primary."""
    done = quest.completed_in_current_period
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                text(quest.title, t.BODY, rx.cond(done, t.TEXT_2, t.TEXT),
                     text_decoration=rx.cond(done, "line-through", "none")),
                text(rx.cond(quest.points_reward > 0,
                             f"{quest.recurrence_label} · +{quest.xp_reward} XP · +{quest.points_reward} pts",
                             f"{quest.recurrence_label} · +{quest.xp_reward} XP"),
                     t.CAPTION, t.TEXT_2),
                rx.cond(quest.description != "", text(quest.description, t.CAPTION, t.TEXT_2)),
                spacing="1", align="start", flex="1", min_width="0",
            ),
            rx.cond(done, rx.icon("check", size=20, color=t.ACCENT),
                    button("Complete", QuestState.complete(quest.id), variant="secondary")),
            width="100%", align="center", spacing="3",
        ),
        rx.hstack(
            button("Archive", QuestState.archive(quest.id), variant="ghost", padding="0"),
            button("Delete", QuestState.remove(quest.id), variant="ghost", color=t.DANGER, padding="0"),
            spacing="5",
        ),
        spacing="1", width="100%", padding_y=t.space(12), border_bottom=t.HAIRLINE,
        class_name=rx.cond(done, "ma-quest ma-quest-done", "ma-quest"),
    )


def empty_board() -> rx.Component:
    return text("No quests of your own yet. Add one for anything you want to hold yourself to.", t.BODY, t.TEXT_2)


def generated_quest_card(quest: GeneratedQuest) -> rx.Component:
    done = quest.done
    return rx.vstack(
        rx.hstack(
            text(quest.title, t.BODY, rx.cond(done, t.TEXT_2, t.TEXT), flex="1", min_width="0"),
            rx.cond(done, rx.icon("check", size=20, color=t.ACCENT),
                    text(f"+{quest.reward_points} pts", t.CAPTION, t.TEXT_2, **t.TABULAR)),
            width="100%", align="center", spacing="3",
        ),
        text(quest.description, t.CAPTION, t.TEXT_2),
        progress_bar(quest.scale),
        rx.hstack(
            text(rx.cond(done, quest.progress_label, f"{quest.progress_label} · {quest.time_left}"), t.CAPTION,
                 t.TEXT_2),
            rx.spacer(),
            rx.cond(quest.can_reroll, icon_button("refresh-cw", "Reroll", on_click=QuestState.reroll(quest.id))),
            width="100%", align="center", min_height=t.ICON_HIT,
        ),
        spacing="2", width="100%", padding_y=t.space(12), border_bottom=t.HAIRLINE,
        class_name=rx.cond(done, "ma-gen-quest ma-quest-done", "ma-gen-quest"),
    )


def generated_board() -> rx.Component:
    """Today's and this week's quests, with the streak they feed."""
    s = QuestState
    return rx.cond(
        s.has_generated,
        rx.vstack(
            rx.hstack(
                rx.icon("flame", size=20, color=rx.cond(s.streak.weeks > 0, t.TEXT, t.TEXT_3), stroke_width=1.75),
                rx.vstack(text(s.streak.label, t.BODY), text(s.streak.sub, t.CAPTION, t.TEXT_2), spacing="0",
                          align="start", flex="1", min_width="0"),
                rx.hstack(rx.foreach(s.streak.freeze_slots,
                                     lambda held: rx.icon("snowflake", size=16,
                                                          color=rx.cond(held, t.TEXT, t.TEXT_3))),
                          spacing="1", title="Streak freezes: each one covers a week that falls short"),
                width="100%", align="center", spacing="3", min_height=t.ROW_MIN,
            ),
            text("Today", t.CAPTION, t.TEXT_2, padding_top=t.space(8)),
            rx.vstack(rx.foreach(s.daily, generated_quest_card), spacing="0", width="100%"),
            text("This week", t.CAPTION, t.TEXT_2, padding_top=t.space(8)),
            rx.vstack(rx.foreach(s.weekly, generated_quest_card), spacing="0", width="100%"),
            spacing="2", width="100%",
        ),
    )
