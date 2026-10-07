"""/parties: your parties as chips; the chosen one's invite code, shared
quests, league, raid, and boards. Creating and joining happen in sheets."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, notice_banner, shell
from metalarm.components.party_card import invite_panel, leaderboard_row, party_quest_row, party_tab, ranked_row
from metalarm.models import LeagueEntryRow, RaidHitterRow, WorkoutBoardRow
from metalarm.state.parties import PartyState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import (
    button,
    chip,
    chips,
    empty_state,
    field,
    icon_button,
    list_row,
    progress_bar,
    rows,
    section,
    segmented,
    sheet,
    stat_group,
    stat_tile,
    text,
)


def _sheets() -> rx.Component:
    s = PartyState
    return rx.fragment(
        sheet(s.show_create, s.toggle_create, field(s.new_name, s.set_new_name, "Party name"),
              title="Create a party", action=button("Create party", s.create, full=True)),
        sheet(s.show_join, s.toggle_join, field(s.join_code, s.set_join_code, "Invite code, e.g. K7M2QXPA"),
              text("Codes are case-insensitive and dashes are ignored.", t.CAPTION, t.TEXT_2),
              title="Join a party", action=button("Join party", s.join, full=True)),
        sheet(s.show_quest_form, s.toggle_quest_form,
              field(s.quest_title, s.set_quest_title, "Shared quest title"),
              field(s.quest_xp, s.set_quest_xp, "XP, e.g. 25", mode="numeric"),
              chips(*[chip(label, selected=s.quest_recurrence == value, on_click=s.set_quest_recurrence(value))
                      for label, value in (("Daily", "daily"), ("Weekly", "weekly"), ("Once", "none"))]),
              title="Shared quest", action=button("Add to board", s.add_quest, full=True)),
    )


def _league_row(entry: LeagueEntryRow) -> rx.Component:
    return list_row(entry.display_name, rx.cond(entry.promoting, f"Level {entry.level} · moving up", f"Level {entry.level}"),
                    leading=text(entry.position, t.LABEL, t.TEXT_2, width="24px", **t.TABULAR),
                    trailing=text(entry.points, t.BODY, t.TEXT_2, **t.TABULAR),
                    background=rx.cond(entry.is_me, t.ACCENT_SOFT, "transparent"), border_radius=t.RADIUS)


def _league() -> rx.Component:
    lg = PartyState.league
    return section(
        "League",
        text(f"{lg.division_label} · {lg.days_left_label}", t.CAPTION, t.TEXT_2),
        rx.cond(lg.standing_label != "", text(lg.standing_label, t.BODY)),
        rows(rx.foreach(lg.rows, _league_row)),
        text(f"Top {lg.promote_cutoff} move up at the end of the week.", t.CAPTION, t.TEXT_2),
    )


def _hitter(h: RaidHitterRow) -> rx.Component:
    return list_row(rx.cond(h.is_me, f"{h.display_name} (you)", h.display_name), h.hits_label,
                    trailing=text(h.damage_label, t.BODY, **t.TABULAR))


def _raid() -> rx.Component:
    """This week's party boss (backend core/raids.py)."""
    raid = PartyState.raid
    return section(
        "Party raid",
        rx.hstack(text(raid.name, t.TITLE), rx.spacer(), text(raid.days_left_label, t.CAPTION, t.TEXT_2),
                  width="100%", align="center"),
        progress_bar(raid.hp_pct / 100, label=f"{raid.hp_label} · {raid.damage_label} · {raid.healed_label}"),
        rx.cond(raid.hitters.length() > 0, rows(rx.foreach(raid.hitters, _hitter)),
                text("No hits yet. Finish a workout to strike first.", t.BODY, t.TEXT_2)),
        text("Every finished workout hits the boss for the weight you lifted. On days nobody trains, it heals. "
             "A new boss arrives every Monday.", t.CAPTION, t.TEXT_2),
    )


def _workout_row(e: WorkoutBoardRow) -> rx.Component:
    return ranked_row(e.position, e.rank, e.display_name, f"Level {e.level} · {e.workouts_label}",
                      f"{e.points} pts", e.is_me)


def _detail() -> rx.Component:
    s = PartyState
    return rx.vstack(
        rx.vstack(text(s.selected.name, t.TITLE_LG), text(s.selected.seats_label, t.CAPTION, t.TEXT_2),
                  spacing="1", align="start", width="100%"),
        stat_group(stat_tile(s.selected.total_party_xp, "Party XP")),
        invite_panel(),
        section("Shared quests",
                rx.cond(s.has_quests, rx.vstack(rx.foreach(s.quests, party_quest_row), spacing="0", width="100%"),
                        text("No shared quests yet. Anyone in the party can add one.", t.BODY, t.TEXT_2)),
                action="Add", on_action=s.toggle_quest_form),
        rx.cond(s.league.loaded, _league()),
        rx.cond(s.raid.loaded, _raid()),
        section("Leaderboard", rx.vstack(rx.foreach(s.board, leaderboard_row), spacing="1", width="100%"),
                text("Ranked by XP contributed to this party. Personal quests count toward your own level, not "
                     "the party's.", t.CAPTION, t.TEXT_2)),
        section("Workout board",
                segmented(["This week", "All time"], rx.cond(s.workout_period == "week", "This week", "All time"),
                          s.set_workout_label),
                rx.vstack(rx.foreach(s.workout_board, _workout_row), spacing="1", width="100%"),
                text("Ranked by workout points, over the same window for everyone.", t.CAPTION, t.TEXT_2)),
        rx.cond(s.selected.is_owner, button("Dissolve party", s.dissolve, variant="danger", full=True),
                button("Leave party", s.leave, variant="danger", full=True)),
        spacing="6", width="100%",
    )


def parties_page() -> rx.Component:
    s = PartyState
    return shell(
        top_bar("Parties", back="/profile", trailing=icon_button("plus", "Create a party", on_click=s.toggle_create)),
        error_banner(s.error),
        notice_banner(s.notice),
        rx.hstack(rx.cond(s.has_parties, chips(rx.foreach(s.parties, party_tab))), rx.spacer(),
                  button("Join", s.toggle_join, variant="ghost", class_name="ma-join"),
                  width="100%", align="center"),
        rx.cond(s.has_selection, _detail(),
                empty_state("users-round", "Create a party and share its invite code, or join one with a code a "
                                           "friend sent you.",
                            button("Create a party", s.toggle_create, variant="secondary"))),
        _sheets(),
    )
