"""/profile: who you are in the game, then settings as grouped rows -
People, Game, Training, App, Account. Detail sits behind sheets."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.models import Badge, StatRow, TrialRow
from metalarm.ranks import rank_title_var
from metalarm.state.auth import AuthState
from metalarm.state.profile import ProfileState
from metalarm.state.quests import QuestState
from metalarm.state.settings import SettingsState
from metalarm.ui.chrome import avatar, top_bar
from metalarm.ui.path_card import path_card
from metalarm.ui.primitives import (
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
from metalarm.ui.rank_badge import rank_badge


class ProfileSheets(rx.State):
    """Which detail sheet is open: "", "trials", "stats", "badges"."""

    open: str = ""

    def show(self, name: str) -> None:
        self.open = name

    def close(self) -> None:
        self.open = ""


def _icon(name: str) -> rx.Component:
    return rx.icon(name, size=20, color=t.TEXT_2, stroke_width=1.75)


def _header() -> rx.Component:
    p = AuthState.progress
    return rx.vstack(
        rx.hstack(
            avatar(AuthState.initials, size=96),
            rx.spacer(),
            rank_badge(p.rank, 96),
            width="100%", align="center",
        ),
        rx.vstack(text(AuthState.display_name, t.TITLE_LG),
                  text(f"{rank_title_var(p.rank)} · Level {p.current_level}", t.BODY, t.TEXT_2),
                  spacing="0", align="start", width="100%"),
        progress_bar(AuthState.xp_scale,
                     label=rx.cond(p.xp_for_next_level > 0,
                                   f"{p.xp_into_level} / {p.xp_for_next_level} XP to level {p.current_level + 1}",
                                   "Top level")),
        rx.cond(AuthState.rank_gate_message != "", text(AuthState.rank_gate_message, t.CAPTION, t.TEXT_2)),
        stat_group(stat_tile(ProfileState.stats.workouts_completed, "Workouts"),
                   stat_tile(ProfileState.stats.workout_prs, "Records"),
                   stat_tile(ProfileState.stats.volume_value, "Lifted", ProfileState.stats.volume_unit)),
        spacing="4", width="100%", padding_top=t.space(16),
    )


def _switch(checked, on_change, label: str) -> rx.Component:
    return rx.switch(checked=checked, on_change=on_change, aria_label=label, size="3",
                     class_name="ma-switch")


def _groups() -> rx.Component:
    s = SettingsState
    return rx.vstack(
        section("People", rows(
            list_row("Find friends", "Search, and people you may know", leading=_icon("user-plus"), chevron=True,
                     href="/profile/people"),
            list_row("Followers and following", f"{s.followers} followers · {s.following} following",
                     leading=_icon("users"), chevron=True, href="/profile/people"),
        )),
        section("Game", rows(
            list_row("Quests", "Today's and this week's", leading=_icon("scroll-text"), chevron=True, href="/quests"),
            list_row("Duels", "One-on-one challenges", leading=_icon("swords"), chevron=True, href="/duels"),
            list_row("Parties", "Train as a group", leading=_icon("users-round"), chevron=True, href="/parties"),
            list_row("Rewards", f"{AuthState.progress.points_balance} points to spend", leading=_icon("gift"),
                     chevron=True, href="/rewards"),
            list_row("Rank trials", "The lifts between you and the next rank", leading=_icon("shield"),
                     chevron=True, on_click=ProfileSheets.show("trials")),
            list_row("Badges", ProfileState.badge_summary, leading=_icon("award"), chevron=True,
                     on_click=ProfileSheets.show("badges")),
        )),
        section("Training", rows(
            list_row("Training path", rx.cond(ProfileState.class_label != "", ProfileState.class_label, "Not set"),
                     leading=_icon("route"), chevron=True, on_click=s.open_paths),
            list_row("Character stats", "Strength, endurance and the rest", leading=_icon("bar-chart-3"),
                     chevron=True, on_click=ProfileSheets.show("stats")),
            list_row("Units", leading=_icon("weight"),
                     trailing=rx.box(segmented(["kg", "lb"], AuthState.weight_unit, s.set_unit), width="120px")),
            list_row("Default rest", leading=_icon("timer"),
                     trailing=rx.hstack(icon_button("minus", "Shorter rest", on_click=s.bump_rest(-15)),
                                        text(s.rest_label, t.BODY, **t.TABULAR),
                                        icon_button("plus", "Longer rest", on_click=s.bump_rest(15)),
                                        spacing="1", align="center")),
        )),
        rx.vstack(text("Who sees new workouts", t.CAPTION, t.TEXT_2),
                  segmented(["Public", "Followers", "Only me"], s.visibility_label, s.set_visibility),
                  spacing="2", width="100%"),
        section("App", rows(
            list_row("Sound", "The level-up fanfare", leading=_icon("volume-2"),
                     trailing=_switch(~QuestState.sound_muted, lambda _v: QuestState.toggle_sound, "Sound")),
            list_row("Haptics", "A tap when a set logs or a record falls", leading=_icon("vibrate"),
                     trailing=_switch(s.haptics_on, lambda _v: s.toggle_haptics, "Haptics")),
            list_row("Reduce motion", "Still screens, no animations", leading=_icon("pause"),
                     trailing=_switch(s.reduce_on, lambda _v: s.toggle_reduce, "Reduce motion")),
        )),
        section("Account", rows(
            rx.upload(
                list_row(rx.cond(ProfileState.importing, "Importing…", "Import history"),
                         rx.cond(ProfileState.import_message != "", ProfileState.import_message,
                                 "A Strong or Hevy CSV"), leading=_icon("upload"), chevron=True),
                id="history_csv", accept={"text/csv": [".csv"]}, max_files=1, multiple=False, no_drag=False,
                on_drop=ProfileState.import_history(rx.upload_files(upload_id="history_csv")),
                border="none", padding="0", width="100%",
            ),
            list_row("Credits", "Exercise images and their authors", leading=_icon("info"), chevron=True,
                     href="/about/credits"),
            list_row("Sign out", leading=rx.icon("log-out", size=20, color=t.DANGER, stroke_width=1.75),
                     title_color=t.DANGER, on_click=AuthState.do_logout),
        )),
        spacing="6", width="100%",
    )


def _trial(trial: TrialRow) -> rx.Component:
    return rx.vstack(
        rx.hstack(rank_badge(trial.rank, 24), text(trial.description, t.BODY, flex="1", min_width="0"),
                  rx.cond(trial.passed, rx.icon("check", size=20, color=t.ACCENT)),
                  width="100%", align="center", spacing="3"),
        progress_bar(trial.pct / 100, label=trial.progress_label),
        spacing="2", width="100%", padding_y=t.space(12), border_bottom=t.HAIRLINE,
    )


def _stat(stat: StatRow) -> rx.Component:
    return rx.vstack(
        rx.hstack(text(stat.label, t.BODY, rx.cond(stat.highlighted, t.TEXT, t.TEXT_2)), rx.spacer(),
                  text(stat.value, t.BODY, **t.TABULAR), width="100%"),
        progress_bar(stat.value / 100, label=stat.detail),
        spacing="2", width="100%", padding_y=t.space(12),
    )


def _badge(badge: Badge) -> rx.Component:
    return list_row(badge.name, rx.cond(badge.earned, badge.description, badge.progress_label),
                    title_color=rx.cond(badge.earned, t.TEXT, t.TEXT_2),
                    leading=rx.center(rx.text(badge.icon, opacity=rx.cond(badge.earned, "1", "0.4"),
                                              filter=rx.cond(badge.earned, "none", "grayscale(1)"), **t.TITLE),
                                      width="40px", height="40px", border_radius=t.RADIUS_PILL,
                                      background=t.SURFACE_2),
                    trailing=rx.cond(badge.earned, rx.icon("check", size=20, color=t.ACCENT)))


def _sheets() -> rx.Component:
    o = ProfileSheets.open
    return rx.fragment(
        sheet(o == "trials", ProfileSheets.close,
              text("Pass a trial to unlock its rank, on top of the level and streak it asks for.", t.BODY, t.TEXT_2),
              rx.vstack(rx.foreach(ProfileState.trials, _trial), spacing="0", width="100%"),
              title="Rank trials"),
        sheet(o == "stats", ProfileSheets.close,
              text("Your training path highlights the stats it cares about. It never changes a score.", t.BODY,
                   t.TEXT_2),
              rx.vstack(rx.foreach(ProfileState.stats_sheet, _stat), spacing="0", width="100%"),
              title="Character stats"),
        sheet(o == "badges", ProfileSheets.close, rows(rx.foreach(ProfileState.badges, _badge)), title="Badges"),
        sheet(SettingsState.show_paths, SettingsState.close_paths,
              text("It shapes what MetalArm suggests - never your score. Tap yours again to clear it.", t.BODY,
                   t.TEXT_2),
              rx.vstack(rx.foreach(SettingsState.paths,
                                   lambda p: path_card(p, selected=AuthState.character_class == p.category,
                                                       on_click=SettingsState.choose_path(p.category))),
                        spacing="3", width="100%", custom_attrs={"role": "radiogroup"}),
              title="Training path"),
    )


def profile_page() -> rx.Component:
    return shell(
        top_bar("Profile", large=True),
        error_banner(ProfileState.error),
        error_banner(SettingsState.error),
        _header(),
        _groups(),
        _sheets(),
    )
