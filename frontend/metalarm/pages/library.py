"""The Library tab.

/library                   your program, then what is recommended for your
                           path, then the other paths - two taps to a workout
/library/path/<category>   every program and workout of one path, filtered
/library/program/<slug>    a program: its weeks and days; Follow
/library/workout/<slug>    a workout: exercises and targets; Start
/library/exercises         the exercise library (pages/train.py)

What leads, and in what order, is the server's decision.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, notice_banner, shell
from metalarm.state.auth import AuthState
from metalarm.state.library import (
    DAY_OPTIONS,
    DIFFICULTIES,
    DURATIONS,
    EQUIPMENT,
    PATHS,
    LibraryProgramState,
    LibraryState,
    LibraryWorkoutState,
    label,
)
from metalarm.state.settings import SettingsState
from metalarm.ui.chrome import top_bar
from metalarm.ui.library import path_chip, program_card, program_shelf, schedule_grid, workout_card
from metalarm.ui.path_card import path_card
from metalarm.ui.primitives import (
    button,
    card,
    chip,
    chips,
    empty_state,
    error_state,
    icon_button,
    list_row,
    pill,
    rows,
    section,
    sheet,
    skeleton,
    skeleton_rows,
    stat_group,
    stat_tile,
    text,
)

NOTE = "These are templates, not coaching. Adjust the load to your ability."


def _path_chips(selected) -> rx.Component:
    own = AuthState.character_class
    return rx.hstack(
        *[path_chip(name, selected=selected == code, own=own == code, href=f"/library/path/{code}")
          for code, name in PATHS.items()],
        spacing="2", overflow_x="auto", flex_wrap="nowrap", class_name="ma-scroll-x ma-bleed ma-path-chips",
    )


# ---------------------------------------------------------------------------
# /library
# ---------------------------------------------------------------------------


def _your_program() -> rx.Component:
    p = LibraryState.your_program
    return rx.cond(
        p.length() > 0,
        card(
            text("Your program", t.CAPTION, t.TEXT_2),
            rx.link(text(p["name"], t.TITLE), href=f"/library/program/{p['slug']}", underline="none"),
            text(p["where"], t.CAPTION, t.TEXT_2),
            rx.cond(
                p["next_slug"] != "",
                rx.vstack(
                    rows(list_row(f"Next: {p['next_name']}", p["next_meta"], chevron=True,
                                  href=f"/library/workout/{p['next_slug']}")),
                    button("Start", LibraryState.start(p["next_slug"]), icon="play", full=True,
                           class_name="ma-your-program-start"),
                    spacing="3", width="100%",
                ),
            ),
            class_name="ma-your-program",
        ),
    )


def _choose_path() -> rx.Component:
    """No path yet: one card and one primary, never an empty screen."""
    return card(
        text("Pick your training path", t.TITLE),
        text("The Library leads with programs and workouts made for how you train. Until then, here is "
             "everything.", t.BODY, t.TEXT_2),
        button("Choose your path", SettingsState.open_paths, full=True, class_name="ma-choose-path"),
    )


def _path_sheet() -> rx.Component:
    return sheet(
        SettingsState.show_paths, SettingsState.close_paths,
        text("It shapes what the Library leads with - never your score. Change it any time in Profile.",
             t.BODY, t.TEXT_2),
        rx.vstack(rx.foreach(SettingsState.paths,
                             lambda p: path_card(p, selected=AuthState.character_class == p.category,
                                                 on_click=[SettingsState.choose_path(p.category), LibraryState.load])),
                  spacing="3", width="100%", custom_attrs={"role": "radiogroup"}),
        title="Training path",
    )


def _other_paths() -> rx.Component:
    return section(
        rx.cond(LibraryState.needs_path, "Browse by path", "Explore other paths"),
        rows(rx.foreach(LibraryState.others, lambda o: list_row(
            o["label"], o["meta"], chevron=True, href=f"/library/path/{o['category']}",
            class_name="ma-other-path"))),
    )


def library_home_page() -> rx.Component:
    s = LibraryState
    own = AuthState.character_class
    return shell(
        top_bar("Library", large=True,
                trailing=icon_button("search", "Search and filter",
                                     href=rx.cond(own != "", f"/library/path/{own}?filters=1",
                                                  "/library/path/athlete?filters=1"))),
        _path_chips(own),
        rx.cond(s.error != "", error_state(s.error, s.load)),
        rx.cond(
            s.loaded,
            rx.vstack(
                _your_program(),
                rx.cond(
                    s.needs_path,
                    _choose_path(),
                    rx.vstack(
                        section("Recommended for you", program_shelf(s.programs),
                                action="See all", href=f"/library/path/{s.path}"),
                        text("Workouts", t.CAPTION, t.TEXT_2),
                        rows(rx.foreach(s.workouts, workout_card), class_name="ma-recommended-workouts"),
                        spacing="3", width="100%",
                    ),
                ),
                _other_paths(),
                rows(list_row("Exercises", "Every exercise, by muscle and equipment",
                              leading=rx.icon("search", size=20, color=t.TEXT_2, stroke_width=1.75),
                              chevron=True, href="/library/exercises")),
                spacing="6", width="100%",
            ),
            rx.vstack(skeleton("120px"), skeleton("160px"), skeleton_rows(3), spacing="4", width="100%"),
        ),
        _path_sheet(),
    )


# ---------------------------------------------------------------------------
# /library/path/<category>
# ---------------------------------------------------------------------------


def _filter_sheet() -> rx.Component:
    s = LibraryState

    def group(title: str, *items: rx.Component) -> rx.Component:
        return rx.vstack(text(title, t.CAPTION, t.TEXT_2), chips(*items), spacing="2", width="100%")

    return sheet(
        s.show_filters, s.close_filters,
        group("Days a week", *[chip(d, selected=s.f_days == d, on_click=s.pick_days(d)) for d in DAY_OPTIONS]),
        group("Difficulty", *[chip(label(d), selected=s.f_difficulty == d, on_click=s.pick_difficulty(d))
                              for d in DIFFICULTIES]),
        group("Equipment you have", *[chip(label(e), selected=s.f_equipment.contains(e),
                                           on_click=s.toggle_equipment(e)) for e in EQUIPMENT]),
        group("Workout length", *[chip(f"Up to {m} min", selected=s.f_minutes == m, on_click=s.pick_minutes(m))
                                  for m in DURATIONS]),
        button("Clear filters", s.clear_filters, variant="ghost", full=True),
        title="Filter",
        action=button("Show results", s.apply_filters, full=True),
    )


def library_path_page() -> rx.Component:
    s = LibraryState
    clear = button("Clear filters", s.clear_filters, variant="secondary")
    return shell(
        top_bar(s.category_label, back="/library",
                trailing=icon_button("sliders-horizontal", "Filter", on_click=s.open_filters,
                                     badge=s.filter_count)),
        _path_chips(s.category),
        rx.cond(s.filtering, rx.hstack(text(f"{s.filter_count} filters on", t.CAPTION, t.TEXT_2), rx.spacer(),
                                       button("Clear", s.clear_filters, variant="ghost"),
                                       width="100%", align="center")),
        rx.cond(s.error != "", error_state(s.error, s.load_path)),
        rx.cond(
            s.loaded,
            rx.vstack(
                section("Programs",
                        rx.cond(s.programs.length() > 0,
                                rx.vstack(rx.foreach(s.programs, lambda p: program_card(p, show_pill=False)),
                                          spacing="3", width="100%"),
                                empty_state("calendar", "No programs match these filters.", clear))),
                section("Workouts",
                        rx.cond(s.workouts.length() > 0, rows(rx.foreach(s.workouts, workout_card)),
                                empty_state("dumbbell", "No workouts match these filters.", clear))),
                spacing="6", width="100%",
            ),
            rx.vstack(skeleton("120px"), skeleton("120px"), skeleton_rows(4), spacing="3", width="100%"),
        ),
        _filter_sheet(),
    )


# ---------------------------------------------------------------------------
# /library/program/<slug>
# ---------------------------------------------------------------------------


def library_program_page() -> rx.Component:
    s = LibraryProgramState
    primary = rx.match(
        s.status,
        ("active", rx.cond(s.next_slug != "",
                           button(f"Start next: {s.next_name}", s.start_next, icon="play", full=True,
                                  disabled=s.busy),
                           button("Follow again", s.follow, full=True))),
        ("paused", button("Resume program", s.follow, full=True)),
        ("completed", button("Start it again", s.follow, full=True)),
        button("Follow program", s.follow, full=True),
    )
    return shell(
        top_bar("", back="history"),
        rx.cond(s.error != "", error_state(s.error, s.load)),
        rx.cond(
            s.loaded & (s.name != ""),
            rx.vstack(
                rx.vstack(text(s.name, t.TITLE_LG), pill(s.path, accent=False), spacing="2", align="start"),
                stat_group(stat_tile(s.weeks, "Weeks"), stat_tile(s.days, "Days a week"),
                           stat_tile(s.difficulty, "Level")),
                text(s.description, t.BODY, t.TEXT_2),
                rx.cond(s.status == "active",
                        rx.hstack(text(f"Following · {s.where}", t.CAPTION, t.TEXT_2), rx.spacer(),
                                  button("Pause", s.unfollow, variant="ghost"), width="100%", align="center")),
                section("Schedule", schedule_grid(s.schedule)),
                section("Workouts in this program", rows(rx.foreach(s.workouts, workout_card))),
                text(NOTE, t.CAPTION, t.TEXT_2, class_name="ma-adjust-note"),
                spacing="6", width="100%",
            ),
            rx.cond(s.error == "", rx.vstack(skeleton("96px"), skeleton("64px"), skeleton("200px"),
                                             spacing="3", width="100%")),
        ),
        pinned=rx.cond(s.loaded & (s.name != ""), primary),
    )


# ---------------------------------------------------------------------------
# /library/workout/<slug>
# ---------------------------------------------------------------------------


def _exercise_row(r) -> rx.Component:
    sub = rx.cond(r["superset"] != "", f"{r['superset']} · {r['target']}", r["target"])
    return rx.vstack(
        list_row(r["name"], f"{r['muscle']} · {sub}", href=f"/exercise/{r['exercise_id']}", chevron=True,
                 class_name="ma-library-exercise"),
        rx.cond(r["note"] != "", text(r["note"], t.CAPTION, t.TEXT_3, padding_bottom=t.space(8))),
        spacing="0", width="100%",
    )


def library_workout_page() -> rx.Component:
    s = LibraryWorkoutState
    return shell(
        top_bar("", back="history"),
        rx.cond(s.error != "", error_banner(s.error)),
        notice_banner(s.notice),
        rx.cond(
            s.loaded & (s.name != ""),
            rx.vstack(
                rx.vstack(text(s.name, t.TITLE_LG), pill(s.path, accent=False), spacing="2", align="start"),
                stat_group(stat_tile(s.duration, "Minutes"), stat_tile(s.count, "Exercises")),
                text(s.gear, t.CAPTION, t.TEXT_2),
                rx.cond(s.description != "", text(s.description, t.BODY, t.TEXT_2)),
                rows(rx.foreach(s.rows, _exercise_row)),
                button(rx.cond(s.saved, "In your routines", "Save to routines"), s.save, variant="secondary",
                       icon="bookmark-plus", disabled=s.saved, full=True, class_name="ma-save-routine"),
                spacing="5", width="100%",
            ),
            rx.cond(s.error == "", rx.vstack(skeleton("96px"), skeleton_rows(5), spacing="3", width="100%")),
        ),
        pinned=rx.cond(s.loaded & (s.name != ""),
                       button(rx.cond(s.busy, "Starting…", "Start workout"), s.start, icon="play", full=True,
                              disabled=s.busy, class_name="ma-start-library")),
    )
