"""Library (overhaul 7.7): your programs, routines and exercises.

Chips choose what is listed, the sort cycles Recents / Name / Most used, and
the grid/list toggle changes how. A program opens to its routines; a routine
opens in the editor (rep ranges, supersets, notes, order) and starts a
workout from there in one tap.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.exercise_picker import picker_dialog
from metalarm.components.layout import error_banner, shell
from metalarm.state.library import LibraryState
from metalarm.state.picker import PickerState
from metalarm.state.routines import RoutineState
from metalarm.ui.chrome import icon_button, top_bar
from metalarm.ui.primitives import (
    card,
    empty_state,
    filter_chip,
    list_row,
    primary_button,
    secondary_button,
    skeleton,
    text,
    thumb,
)
from metalarm.workout_models import RoutineSlot

FILTERS = [("Programs", "programs"), ("Routines", "routines"), ("Exercises", "exercises")]


def _input(value, on_change, placeholder: str = "", **props) -> rx.Component:
    return rx.el.input(
        value=value,
        on_change=on_change,
        placeholder=placeholder,
        background=t.SURFACE_2,
        color=t.TEXT_PRIMARY,
        border="none",
        border_radius=t.RADIUS_THUMB,
        padding=f"0 {t.space(3)}",
        min_height=t.TOUCH_MIN,
        width="100%",
        min_width="0",
        **{**t.BODY, **props},
    )


def _tap(icon: str, label: str, on_click, color: str = t.TEXT_SECONDARY) -> rx.Component:
    return rx.box(rx.icon(icon, size=20, color=color), width=t.TOUCH_MIN, height=t.TOUCH_MIN,
                  display="flex", align_items="center", justify_content="center", cursor="pointer",
                  flex_shrink="0", on_click=on_click,
                  custom_attrs={"role": "button", "aria-label": label})


# ---------------------------------------------------------------------------
# The listing
# ---------------------------------------------------------------------------


def _open(item):
    return rx.match(
        item["type"],
        ("program", LibraryState.open_program(item["id"])),
        ("routine", RoutineState.open_routine(item["id"])),
        LibraryState.toggle_favorite(item["type"], item["id"], item["favorite"] == ""),
    )


def _star(item) -> rx.Component:
    on = item["favorite"] != ""
    return _tap("star", "Favourite", LibraryState.toggle_favorite(item["type"], item["id"], ~on),
                rx.cond(on, t.STREAK_ORANGE, t.TEXT_TERTIARY))


def _tile(item) -> rx.Component:
    art = rx.cond(
        item["image"] != "",
        rx.image(src=item["image"], width="100%", aspect_ratio="1", object_fit="cover",
                 border_radius=t.RADIUS_TILE, background=t.SURFACE_2, loading="lazy"),
        rx.center(text(item["initials"], t.TITLE_1), width="100%", aspect_ratio="1",
                  background=item["color"], border_radius=t.RADIUS_TILE),
    )
    return rx.vstack(
        rx.box(art, rx.cond(item["favorite"] != "",
                            rx.box(rx.icon("star", size=16, color=t.STREAK_ORANGE, fill=t.STREAK_ORANGE),
                                   position="absolute", top=t.space(2), right=t.space(2))),
               position="relative", width="100%"),
        text(item["title"], t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
             white_space="nowrap", max_width="100%"),
        text(item["subtitle"], t.FOOTNOTE, t.TEXT_SECONDARY, overflow="hidden",
             text_overflow="ellipsis", white_space="nowrap", max_width="100%"),
        spacing="1",
        align="start",
        min_width="0",
        cursor="pointer",
        on_click=_open(item),
    )


def _row(item) -> rx.Component:
    return rx.hstack(
        rx.box(
            rx.cond(item["image"] != "", thumb(item["image"], size="56px"),
                    rx.center(text(item["initials"], t.HEADLINE), width="56px", height="56px",
                              background=item["color"], border_radius=t.RADIUS_THUMB, flex_shrink="0")),
            on_click=_open(item), cursor="pointer",
        ),
        rx.vstack(
            text(item["title"], t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
                 white_space="nowrap", max_width="100%"),
            text(item["subtitle"], t.SUBHEAD, t.TEXT_SECONDARY),
            spacing="0", align="start", min_width="0", flex="1", on_click=_open(item), cursor="pointer",
        ),
        _star(item),
        width="100%", align="center", spacing="3",
    )


def _program_form() -> rx.Component:
    return rx.cond(
        LibraryState.creating_program,
        card(
            text("New program", t.HEADLINE),
            _input(LibraryState.program_name, LibraryState.set_program_name, "Name, e.g. Upper / Lower"),
            rx.hstack(secondary_button("Cancel", LibraryState.cancel_program, flex="1"),
                      primary_button("Create", LibraryState.create_program, flex="1"),
                      width="100%", spacing="2"),
        ),
        list_row("Create new program", "Group routines into a plan", icon="folder-plus",
                 on_click=LibraryState.start_program),
    )


def _listing() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            *[filter_chip(label, selected=LibraryState.filter == key, on_click=LibraryState.set_filter(key))
              for label, key in FILTERS],
            spacing="2", overflow_x="auto", width="100%", style={"scrollbar_width": "none"},
        ),
        rx.hstack(
            rx.hstack(rx.icon("arrow-up-down", size=16, color=t.ACCENT_BLUE),
                      text(LibraryState.sort_label, t.SUBHEAD, t.ACCENT_BLUE),
                      spacing="1", align="center", cursor="pointer", on_click=LibraryState.cycle_sort,
                      min_height=t.TOUCH_MIN),
            rx.spacer(),
            rx.cond(LibraryState.grid,
                    _tap("list", "Show as a list", LibraryState.toggle_grid),
                    _tap("layout-grid", "Show as a grid", LibraryState.toggle_grid)),
            width="100%", align="center",
        ),
        rx.cond(
            LibraryState.filter == "favorites",
            list_row("All of your library", "Back to everything", icon="arrow-left",
                     on_click=LibraryState.set_filter("routines")),
            list_row("Favorites", f"{LibraryState.favorite_count} saved", icon="star",
                     on_click=LibraryState.set_filter("favorites")),
        ),
        rx.cond(LibraryState.filter == "programs", _program_form()),
        rx.cond(
            LibraryState.has_items,
            rx.cond(
                LibraryState.grid,
                rx.grid(rx.foreach(LibraryState.items, _tile), columns="2", gap=t.space(4), width="100%"),
                rx.vstack(rx.foreach(LibraryState.items, _row), spacing="2", width="100%"),
            ),
            rx.cond(
                LibraryState.loading,
                rx.grid(*[skeleton("160px") for _ in range(4)], columns="2", gap=t.space(4), width="100%"),
                rx.match(
                    LibraryState.filter,
                    ("programs", empty_state("No programs yet", "A program is a plan: routines in order.")),
                    ("exercises", empty_state("Nothing logged yet", "Exercises you log show up here.")),
                    ("favorites", empty_state("No favourites", "Star a routine, program or exercise.")),
                    empty_state("No routines yet", "Save a workout as a routine, or build one with +.",
                                primary_button("New routine", RoutineState.new_routine(""), icon="plus")),
                ),
            ),
        ),
        rx.cond(LibraryState.next_cursor != "",
                secondary_button("Show more", LibraryState.load_more, width="100%")),
        spacing="3",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Program detail
# ---------------------------------------------------------------------------


def _program_routine(r) -> rx.Component:
    return rx.hstack(
        rx.center(text(r["initials"], t.HEADLINE), width="56px", height="56px", background=r["color"],
                  border_radius=t.RADIUS_THUMB, flex_shrink="0"),
        rx.vstack(text(r["title"], t.HEADLINE), text(r["subtitle"], t.SUBHEAD, t.TEXT_SECONDARY),
                  spacing="0", align="start", min_width="0", flex="1", cursor="pointer",
                  on_click=RoutineState.open_routine(r["id"])),
        _tap("play", "Start", LibraryState.start_routine(r["id"]), t.ACCENT_BLUE),
        width="100%", align="center", spacing="3",
    )


def _program() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            _tap("chevron-left", "Back", LibraryState.close_program, t.ACCENT_BLUE),
            text(LibraryState.program_name_view, t.TITLE_1, flex="1", min_width="0", overflow="hidden",
                 text_overflow="ellipsis", white_space="nowrap"),
            _tap("trash-2", "Delete program", LibraryState.delete_program),
            width="100%", align="center", spacing="1",
        ),
        rx.cond(LibraryState.program_description != "",
                text(LibraryState.program_description, t.SUBHEAD, t.TEXT_SECONDARY)),
        rx.cond(
            LibraryState.program_routines.length() > 0,
            card(rx.foreach(LibraryState.program_routines, _program_routine)),
            empty_state("No routines in this program", "Add the first day of the plan."),
        ),
        secondary_button("Add routine", RoutineState.new_routine(LibraryState.program_id), icon="plus",
                         width="100%"),
        spacing="3",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Routine editor (a full-screen sheet)
# ---------------------------------------------------------------------------


def _field(label: str, value, on_change, mode: str = "numeric") -> rx.Component:
    return rx.vstack(
        text(label, t.CAPTION, t.TEXT_SECONDARY),
        _input(value, on_change, input_mode=mode, text_align="center", **t.TABULAR),
        spacing="1", flex="1", min_width="0",
    )


def _slot(slot: RoutineSlot, index) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            thumb(slot.image, size="44px", icon="dumbbell"),
            rx.vstack(
                text(slot.name, t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
                     white_space="nowrap", max_width="100%"),
                rx.hstack(
                    rx.cond(slot.superset_group > 0,
                            text(f"Superset {slot.superset_group}", t.FOOTNOTE, t.STREAK_ORANGE,
                                 white_space="nowrap", flex_shrink="0")),
                    text(slot.muscles_label, t.FOOTNOTE, t.TEXT_SECONDARY, overflow="hidden",
                         text_overflow="ellipsis", white_space="nowrap", min_width="0"),
                    spacing="2", width="100%", min_width="0",
                ),
                spacing="0", align="start", min_width="0", flex="1",
            ),
            _tap("arrow-up", "Move up", RoutineState.move_slot(index, -1)),
            _tap("arrow-down", "Move down", RoutineState.move_slot(index, 1)),
            width="100%", align="center", spacing="1",
        ),
        rx.hstack(
            _field("Sets", slot.target_sets, lambda v: RoutineState.set_slot_sets(index, v)),
            _field("Reps", slot.target_reps, lambda v: RoutineState.set_slot_reps(index, v), "text"),
            _field("Weight", slot.target_weight, lambda v: RoutineState.set_slot_weight(index, v), "decimal"),
            _field("Rest s", slot.rest_seconds, lambda v: RoutineState.set_slot_rest(index, v)),
            width="100%", spacing="2",
        ),
        _input(slot.notes, lambda v: RoutineState.set_slot_notes(index, v), "Notes"),
        rx.hstack(
            secondary_button(rx.cond(slot.superset_group > 0, "Superset ✓", "Superset with next"),
                             RoutineState.superset_with_next(index), icon="link", flex="1",
                             color=rx.cond(slot.superset_group > 0, t.STREAK_ORANGE, t.TEXT_PRIMARY)),
            secondary_button("Remove", RoutineState.remove_slot(index), color=t.DANGER_RED),
            width="100%", spacing="2",
        ),
        spacing="2",
        width="100%",
        background=t.SURFACE_1,
        border_radius=t.RADIUS_CARD,
        padding=t.CARD_PADDING,
        border_left=rx.cond(slot.superset_group > 0, f"3px solid {t.STREAK_ORANGE}", "3px solid transparent"),
    )


def _editor() -> rx.Component:
    return rx.cond(
        RoutineState.editing,
        rx.box(
            rx.vstack(
                rx.hstack(
                    text("Cancel", t.BODY, t.ACCENT_BLUE, cursor="pointer", on_click=RoutineState.cancel),
                    rx.spacer(),
                    text(rx.cond(RoutineState.edit_id != "", "Edit routine", "New routine"), t.HEADLINE),
                    rx.spacer(),
                    text("Save", t.HEADLINE, t.ACCENT_BLUE, cursor="pointer", on_click=RoutineState.save),
                    width="100%", align="center", min_height=t.TOUCH_MIN,
                ),
                error_banner(RoutineState.error),
                _input(RoutineState.form_name, RoutineState.set_form_name, "Routine name", **t.TITLE_2),
                _input(RoutineState.form_notes, RoutineState.set_form_notes, "Notes (optional)"),
                rx.cond(
                    RoutineState.has_slots,
                    rx.vstack(rx.foreach(RoutineState.slots, _slot), spacing="3", width="100%"),
                    empty_state("No exercises yet", "Add them in the order you do them."),
                ),
                secondary_button("Add exercise", PickerState.open_for("routine"), icon="plus",
                                 width="100%", color=t.ACCENT_BLUE),
                rx.cond(
                    RoutineState.edit_id != "",
                    rx.hstack(
                        secondary_button("Delete", RoutineState.delete(RoutineState.edit_id),
                                         color=t.DANGER_RED),
                        primary_button("Start workout", RoutineState.start(RoutineState.edit_id),
                                       icon="play", flex="1"),
                        width="100%", spacing="2",
                    ),
                ),
                rx.box(height=t.space(10)),
                spacing="3",
                width="100%",
                max_width="560px",
                margin="0 auto",
                padding=f"{t.space(3)} {t.GUTTER}",
            ),
            position="fixed",
            inset="0",
            # Over the tab bar: the sheet is the whole screen while open.
            z_index="80",
            background=t.COLOR_BG,
            overflow_y="auto",
        ),
    )


def library_page() -> rx.Component:
    return shell(
        picker_dialog(),
        _editor(),
        top_bar("Library", icon_button("plus", "New routine", RoutineState.new_routine(""))),
        error_banner(LibraryState.error),
        rx.cond(LibraryState.program_id != "", _program(), _listing()),
    )
