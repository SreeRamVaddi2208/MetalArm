"""The Train tab.

/train                 the live workout when one is running, its summary when
                       it has just finished, otherwise what to train
/train/routine/<id>    a routine: its exercises and targets; Start; Edit
/train/program/<id>    a program (yours, or a curated plan by its slug)
/train/exercises       the exercise library: search, muscle, equipment
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.active_workout import live_view
from metalarm.components.exercise_picker import picker_dialog
from metalarm.components.layout import error_banner, shell
from metalarm.components.level_up import keyframes, level_up_overlay
from metalarm.components.presets import preset_sheet
from metalarm.components.rest_timer import rest_bar
from metalarm.components.workout_summary import summary_done, summary_view
from metalarm.state.explore import ExploreState
from metalarm.state.picker import PickerState
from metalarm.state.routines import RoutineState
from metalarm.state.train import ProgramState, TrainState
from metalarm.state.workout import WorkoutState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import (
    button,
    card,
    chip,
    chips,
    empty_state,
    field,
    icon_button,
    link_button,
    list_row,
    rows,
    section,
    skeleton_rows,
    text,
)
from metalarm.workout_models import RoutineSlot

# ---------------------------------------------------------------------------
# /train
# ---------------------------------------------------------------------------


def _routine_row(r) -> rx.Component:
    return list_row(r["name"], r["sub"], chevron=True, href=f"/train/routine/{r['id']}")


def _landing() -> rx.Component:
    s = TrainState
    return rx.vstack(
        top_bar("Train", large=True),
        error_banner(s.error),
        rx.cond(
            s.up_next.length() > 0,
            card(text("Up next", t.CAPTION, t.TEXT_2), text(s.up_next["name"], t.TITLE),
                 text(s.up_next["sub"], t.CAPTION, t.TEXT_2), href=f"/train/routine/{s.up_next['id']}"),
        ),
        section(
            "Routines",
            rx.cond(s.loaded,
                    rx.cond(s.routines.length() > 0, rows(rx.foreach(s.routines, _routine_row)),
                            empty_state("list", "Save a workout as a routine, or build one.")),
                    skeleton_rows(3)),
            action="New routine", href="/train/routine/new",
        ),
        section(
            "Programs",
            rows(
                rx.foreach(s.programs, lambda p: list_row(p["name"], p["sub"], chevron=True,
                                                          href=f"/train/program/{p['id']}")),
                rx.foreach(s.curated, lambda p: list_row(p["name"], p["sub"], chevron=True,
                                                         href=f"/train/program/{p['slug']}")),
            ),
        ),
        section(
            "Ready-made workouts",
            rows(rx.foreach(WorkoutState.presets,
                            lambda p: list_row(p.name, f"{p.category_label} · {p.exercises.length()} exercises",
                                               chevron=True, on_click=WorkoutState.choose_preset(p.slug),
                                               custom_attrs={"data-preset": p.slug}, class_name="ma-preset-card"))),
        ),
        rows(list_row("Browse exercises", "Every exercise, by muscle and equipment",
                      leading=rx.icon("search", size=20, color=t.TEXT_2), chevron=True, href="/train/exercises")),
        spacing="6", width="100%",
    )


def train_page() -> rx.Component:
    live = WorkoutState.has_session & ~WorkoutState.show_summary
    return shell(
        keyframes(),
        level_up_overlay(),
        picker_dialog(),
        preset_sheet(),
        rx.cond(live, rest_bar()),
        error_banner(WorkoutState.error),
        rx.cond(
            WorkoutState.loaded,
            rx.cond(WorkoutState.show_summary, summary_view(), rx.cond(WorkoutState.has_session, live_view(), _landing())),
            skeleton_rows(4),
        ),
        pinned=rx.cond(
            WorkoutState.show_summary, summary_done(),
            rx.cond(WorkoutState.loaded & ~WorkoutState.has_session,
                    button("Start empty workout", WorkoutState.start_session(""), icon="play", full=True)),
        ),
    )


# ---------------------------------------------------------------------------
# /train/routine/<id>
# ---------------------------------------------------------------------------


def _slot_view(slot: RoutineSlot) -> rx.Component:
    target = rx.cond(slot.target_label != "", slot.target_label, "No target")
    return list_row(slot.name, rx.cond(slot.superset_group > 0, f"Superset {slot.superset_group} · {target}", target))


def _slot_edit(slot: RoutineSlot, index) -> rx.Component:
    s = RoutineState
    return rx.vstack(
        rx.hstack(
            rx.vstack(text(slot.name, t.BODY, overflow="hidden", text_overflow="ellipsis", white_space="nowrap",
                           max_width="100%"),
                      text(rx.cond(slot.superset_group > 0, f"Superset {slot.superset_group}", slot.muscles_label),
                           t.CAPTION, t.TEXT_2),
                      spacing="0", align="start", flex="1", min_width="0"),
            icon_button("arrow-up", "Move up", on_click=s.move_slot(index, -1)),
            icon_button("arrow-down", "Move down", on_click=s.move_slot(index, 1)),
            icon_button("trash-2", "Remove", on_click=s.remove_slot(index)),
            width="100%", align="center",
        ),
        rx.grid(field(slot.target_sets, lambda v: s.set_slot_sets(index, v), "Sets", mode="numeric"),
                field(slot.target_reps, lambda v: s.set_slot_reps(index, v), "Reps 8-12"),
                field(slot.target_weight, lambda v: s.set_slot_weight(index, v), "Weight", mode="decimal"),
                field(slot.rest_seconds, lambda v: s.set_slot_rest(index, v), "Rest s", mode="numeric"),
                columns="4", gap=t.space(8), width="100%"),
        rx.hstack(chip(rx.cond(slot.superset_group > 0, "In a superset", "Superset with next"),
                       selected=slot.superset_group > 0, on_click=s.superset_with_next(index)), width="100%"),
        spacing="2", width="100%", padding_y=t.space(12), border_bottom=t.HAIRLINE,
    )


def routine_page() -> rx.Component:
    s = RoutineState
    editor = rx.vstack(
        top_bar(rx.cond(s.edit_id != "", "Edit routine", "New routine"),
                trailing=icon_button("x", "Cancel", on_click=s.cancel_editing)),
        error_banner(s.error),
        field(s.form_name, s.set_form_name, "Routine name"),
        field(s.form_notes, s.set_form_notes, "Notes (optional)"),
        rx.cond(s.has_slots, rx.vstack(rx.foreach(s.slots, _slot_edit), spacing="0", width="100%"),
                empty_state("list-plus", "Add the exercises in the order you do them.")),
        button("Add exercises", PickerState.open_for("routine"), variant="secondary", icon="plus", full=True),
        rx.cond(s.edit_id != "", button("Delete routine", s.delete(s.edit_id), variant="danger", full=True)),
        spacing="4", width="100%",
    )
    view = rx.vstack(
        top_bar(s.viewing.name, back="/train", trailing=icon_button("pencil", "Edit", on_click=s.start_editing)),
        error_banner(s.error),
        rx.cond(s.viewing.notes != "", text(s.viewing.notes, t.BODY, t.TEXT_2)),
        rx.cond(s.viewing.slots.length() > 0, rows(rx.foreach(s.viewing.slots, _slot_view)),
                empty_state("list-plus", "No exercises yet - edit to add them.")),
        spacing="4", width="100%",
    )
    return shell(
        picker_dialog(),
        rx.cond(s.editing, editor, view),
        pinned=rx.cond(s.editing, button("Save routine", s.save, full=True),
                       button("Start routine", s.start(s.edit_id), icon="play", full=True)),
    )


# ---------------------------------------------------------------------------
# /train/program/<id>
# ---------------------------------------------------------------------------


def program_page() -> rx.Component:
    s = ProgramState
    return shell(
        top_bar(s.name, back="/train"),
        error_banner(s.error),
        rx.cond(
            s.loaded,
            rx.vstack(
                text(s.meta, t.CAPTION, t.TEXT_2),
                rx.cond(s.description != "", text(s.description, t.BODY, t.TEXT_2)),
                rx.cond(
                    s.curated,
                    rows(rx.foreach(s.routines, lambda r: list_row(r["name"], r["sub"]))),
                    rows(rx.foreach(s.routines, lambda r: list_row(r["name"], r["sub"], chevron=True,
                                                                   href=f"/train/routine/{r['id']}"))),
                ),
                rx.cond(~s.curated, rx.vstack(
                    link_button("Add routine", f"/train/routine/new?program={s.key}", icon="plus", full=True),
                    button("Delete program", s.delete, variant="danger", full=True), spacing="3", width="100%")),
                spacing="4", width="100%",
            ),
            skeleton_rows(4),
        ),
        pinned=rx.cond(s.curated & s.loaded,
                       rx.cond(s.saved_id != "", link_button("Open in your library", f"/train/program/{s.saved_id}",
                                                             variant="secondary", full=True),
                               button("Save to library", s.save, icon="bookmark-plus", full=True))),
    )


# ---------------------------------------------------------------------------
# /train/exercises
# ---------------------------------------------------------------------------


def _exercise(row) -> rx.Component:
    return list_row(row["name"], row["sub"], chevron=True, href=f"/exercise/{row['id']}",
                    leading=rx.cond(row["image"] != "",
                                    rx.image(src=row["image"], width="40px", height="40px", object_fit="cover",
                                             border_radius=t.RADIUS, background=t.SURFACE_2, loading="lazy"),
                                    rx.center(rx.icon("dumbbell", size=20, color=t.TEXT_3), width="40px",
                                              height="40px", border_radius=t.RADIUS, background=t.SURFACE_2)))


def exercises_page() -> rx.Component:
    s = ExploreState
    return shell(
        top_bar("Exercises", back="/train"),
        field(s.query, s.set_query, "Search exercises", debounce=True, on_blur=s.blur_search),
        rx.cond((s.query == "") & (s.recents.length() > 0),
                rx.hstack(text("Recent", t.CAPTION, t.TEXT_2),
                          chips(rx.foreach(s.recents, lambda q: chip(q, on_click=s.use_recent(q)))),
                          spacing="2", align="center", width="100%", class_name="ma-recents")),
        chips(rx.foreach(s.muscles, lambda m: chip(m["label"], selected=s.muscle == m["code"],
                                                   on_click=s.pick_muscle(m["code"], m["label"])))),
        chips(rx.foreach(s.equipment, lambda e: chip(e["label"], selected=s.gear == e["code"],
                                                     on_click=s.pick_gear(e["code"], e["label"])))),
        error_banner(s.error),
        rx.hstack(text(s.total_label, t.CAPTION, t.TEXT_2), rx.spacer(),
                  rx.cond(s.listing, button("Clear", s.clear_filters, variant="ghost")), width="100%", align="center"),
        rx.cond(s.results.length() > 0, rows(rx.foreach(s.results, _exercise)),
                rx.cond(s.busy, skeleton_rows(6), empty_state("search", "No exercises match. Try fewer filters."))),
        rx.cond(s.cursor != "", button("Show more", s.more, variant="ghost", full=True)),
    )
