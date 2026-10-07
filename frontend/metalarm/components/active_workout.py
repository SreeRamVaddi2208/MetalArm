"""The active workout - the most important screen. One job: log the next set
in two taps or fewer.

Top: the workout's name and elapsed time, Finish as a ghost button (it
confirms in a sheet). Then one card per exercise. Only the card in focus
shows the steppers and the accent Log set - the screen's one accent action;
the others show what was logged and a quiet "Log next set". Everything else
(set type, RPE, notes, rest, order, superset, remove) lives in the exercise's
options sheet; a logged set opens its own sheet to edit or delete it.

A record shows as a short banner from the bottom - never a takeover while the
lifter is still lifting. Cardio cards log duration and distance.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.offline import offline_assets
from metalarm.components.rest_timer import elapsed_clock
from metalarm.components.voice_log import voice_bar
from metalarm.state.picker import PickerState
from metalarm.state.workout import WorkoutState
from metalarm.ui.primitives import (
    button,
    chip,
    chips,
    empty_state,
    field,
    icon_button,
    list_row,
    rows,
    sheet,
    text,
)
from metalarm.ui.set_row import done_row, entry_panel
from metalarm.workout_models import ExerciseCard, SetRow

_PR_CSS = f"""
@keyframes ma-pr-banner {{
  0% {{ opacity: 0; transform: translateY(16px); }}
  10%, 85% {{ opacity: 1; transform: translateY(0); }}
  100% {{ opacity: 0; transform: translateY(16px); visibility: hidden; }}
}}
.ma-pr-banner {{ animation: ma-pr-banner 2500ms {t.EASE} both; }}
@media (prefers-reduced-motion: reduce) {{
  @keyframes ma-pr-banner {{ 0%, 90% {{ opacity: 1; }} 100% {{ opacity: 0; visibility: hidden; }} }}
}}
"""


def workout_header() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                text(WorkoutState.session_name, t.LABEL, overflow="hidden", text_overflow="ellipsis",
                     white_space="nowrap", max_width="100%"),
                rx.hstack(elapsed_clock(WorkoutState.started_at, color=t.TEXT_2, **t.LABEL),
                          text(f"· {WorkoutState.working_sets} sets", t.LABEL, t.TEXT_2), spacing="1"),
                spacing="0", align="start", flex="1", min_width="0",
            ),
            button("Finish", WorkoutState.ask_finish, variant="ghost"),
            width="100%", align="center",
        ),
        position="sticky", top="0", z_index="20", background=t.BG, width="100%",
        padding_y=t.space(8), border_bottom=t.HAIRLINE,
    )


def _logged(entry: SetRow) -> rx.Component:
    return done_row(entry.set_number, entry.set_type, entry.summary, pr=entry.is_pr,
                    on_click=WorkoutState.start_edit(entry.id))


def _strength_entry(card: ExerciseCard, index) -> rx.Component:
    return entry_panel(
        card.sets.length() + 1, card.entry_type,
        weight=card.weight_input, reps=card.reps_input, unit=WorkoutState.unit,
        ghost_weight=card.ghost_weight, ghost_reps=card.ghost_reps,
        on_weight=lambda v: WorkoutState.set_weight(index, v),
        on_reps=lambda v: WorkoutState.set_reps(index, v),
        on_weight_minus=WorkoutState.bump_weight(index, -1), on_weight_plus=WorkoutState.bump_weight(index, 1),
        on_reps_minus=WorkoutState.bump_reps(index, -1), on_reps_plus=WorkoutState.bump_reps(index, 1),
        on_log=WorkoutState.log_set(index), on_type=WorkoutState.cycle_type(index), busy=WorkoutState.busy,
        # Read by components/offline.py to queue a set with no connection.
        custom_attrs={"data-ma-session": WorkoutState.session_id, "data-ma-exercise": card.exercise_id,
                      "data-ma-card": card.session_exercise_id, "data-ma-type": card.entry_type,
                      "data-ma-unit": WorkoutState.unit},
    )


def _cardio_entry(card: ExerciseCard, index) -> rx.Component:
    return rx.vstack(
        rx.hstack(field(card.duration_input, lambda v: WorkoutState.set_duration(index, v), "Minutes",
                        mode="decimal"),
                  field(card.distance_input, lambda v: WorkoutState.set_distance(index, v), "Km", mode="decimal"),
                  spacing="2", width="100%"),
        button("Log", WorkoutState.log_set(index), icon="check", full=True, disabled=WorkoutState.busy),
        spacing="3", width="100%", class_name="ma-entry",
    )


def exercise_card(card: ExerciseCard, index) -> rx.Component:
    focused = WorkoutState.focus_index == index
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                text(card.name, t.TITLE, overflow="hidden", text_overflow="ellipsis", white_space="nowrap",
                     max_width="100%"),
                text(rx.cond(card.superset_group > 0, f"Superset {card.superset_group} · {card.muscles_label}",
                             card.muscles_label), t.CAPTION, t.TEXT_2),
                spacing="0", align="start", flex="1", min_width="0",
            ),
            icon_button("ellipsis", "Exercise options", on_click=WorkoutState.open_options(index)),
            width="100%", align="center",
        ),
        rx.cond(card.notes != "", text(card.notes, t.CAPTION, t.TEXT_2)),
        rx.vstack(rx.foreach(card.sets, _logged), spacing="1", width="100%"),
        rx.cond(
            focused,
            rx.vstack(
                # What to try next (backend progression_hints), then last time.
                rx.cond(card.hint_label != "", text(card.hint_label, t.CAPTION, t.TEXT_2, class_name="ma-hint")),
                rx.cond(card.entry_previous != "-",
                        text(f"Last time · {card.entry_previous}", t.CAPTION, t.TEXT_3),
                        rx.cond((card.sets.length() == 0) & (card.previous_label != ""),
                                text(card.previous_label, t.CAPTION, t.TEXT_3))),
                rx.cond(card.is_cardio, _cardio_entry(card, index), _strength_entry(card, index)),
                spacing="2", width="100%",
            ),
            rx.hstack(text(rx.cond(card.sets.length() > 0, "Log next set", "Start this exercise"), t.LABEL, t.TEXT_2),
                      rx.spacer(), rx.icon("chevron-down", size=20, color=t.TEXT_3),
                      width="100%", align="center", min_height=t.TOUCH, cursor="pointer",
                      on_click=WorkoutState.focus(index), class_name="ma-press",
                      custom_attrs={"role": "button"}),
        ),
        spacing="3", width="100%", background=t.SURFACE, border_radius=t.RADIUS, padding=t.CARD_PADDING,
        class_name="ma-card",
    )


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


def options_sheet() -> rx.Component:
    """An exercise's options: the next set's type, notes, rest, order,
    superset, remove."""
    s = WorkoutState
    card = s.options_card
    index = s.options_index
    return sheet(
        s.options_index >= 0, s.close_options,
        text("Next set", t.CAPTION, t.TEXT_2),
        chips(*[chip(label, selected=card.entry_type == kind, on_click=s.set_entry_type(index, kind))
                for label, kind in (("Normal", "normal"), ("Warm-up", "warmup"), ("Drop", "drop"),
                                    ("Failure", "failure"))]),
        field(card.rpe_input, lambda v: s.set_rpe(index, v), "RPE (optional)", mode="decimal"),
        rx.el.textarea(value=card.notes, placeholder="Notes for this exercise",
                       on_change=lambda v: s.set_notes(index, v),
                       on_blur=s.flush_notes, rows=2,
                       background=t.SURFACE_2, color=t.TEXT, border="none", border_radius=t.RADIUS,
                       padding=t.space(16), width="100%", **t.BODY),
        rows(
            list_row("Rest", trailing=rx.hstack(
                button("−15s", s.bump_rest(index, -15), variant="secondary", padding=f"0 {t.space(16)}"),
                text(f"{card.rest_seconds}s", t.LABEL, min_width="44px", text_align="center"),
                button("+15s", s.bump_rest(index, 15), variant="secondary", padding=f"0 {t.space(16)}"),
                spacing="2", align="center")),
            list_row("Move up", leading=rx.icon("arrow-up", size=20, color=t.TEXT_2),
                     on_click=[s.flush_notes, s.move_card(index, -1), s.close_options]),
            list_row("Move down", leading=rx.icon("arrow-down", size=20, color=t.TEXT_2),
                     on_click=[s.flush_notes, s.move_card(index, 1), s.close_options]),
            list_row(rx.cond(card.superset_group > 0, "Leave superset", "Superset with next"),
                     leading=rx.icon("link", size=20, color=t.TEXT_2), on_click=[s.flush_notes, s.superset_with_next(index)]),
        ),
        button(rx.cond(card.sets.length() > 0, "Remove with its sets", "Remove exercise"),
               [s.flush_notes, s.remove_card(index), s.close_options], variant="danger", full=True),
        title=card.name,
    )


def set_sheet() -> rx.Component:
    """A logged set: change it, or delete it."""
    s = WorkoutState
    return sheet(
        s.editing_set_id != "", s.cancel_edit,
        rx.cond(
            s.edit_is_cardio,
            rx.hstack(field(s.edit_duration, s.set_edit_duration, "Minutes", mode="decimal"),
                      field(s.edit_distance, s.set_edit_distance, "Km", mode="decimal"), spacing="2", width="100%"),
            rx.hstack(field(s.edit_weight, s.set_edit_weight, "Weight", mode="decimal"),
                      field(s.edit_reps, s.set_edit_reps, "Reps", mode="numeric"),
                      field(s.edit_rpe, s.set_edit_rpe, "RPE", mode="decimal"), spacing="2", width="100%"),
        ),
        chips(chip("Warm-up", selected=s.edit_warmup, on_click=s.toggle_edit_warmup)),
        button(rx.cond(s.busy, "Saving…", "Save"), s.save_edit, full=True, disabled=s.busy),
        button("Delete set", s.delete_set(s.editing_set_id), variant="danger", full=True),
        title="Edit set",
    )


def finish_sheet() -> rx.Component:
    s = WorkoutState
    return sheet(
        s.confirm_finish, s.cancel_finish,
        text("Your sets are saved. Finishing banks the workout's points.", t.BODY, t.TEXT_2),
        button(rx.cond(s.busy, "Finishing…", "Finish workout"), s.finish, full=True, disabled=s.busy),
        button("Keep going", s.cancel_finish, variant="ghost", full=True),
        button("Discard workout", [s.cancel_finish, s.ask_abandon], variant="danger", full=True),
        title="Finish workout?",
    )


def discard_sheet() -> rx.Component:
    s = WorkoutState
    return sheet(
        s.confirm_abandon, s.cancel_abandon,
        text("Everything this workout earned is reversed.", t.BODY, t.TEXT_2),
        button("Discard", s.abandon, variant="danger", full=True),
        button("Keep it", s.cancel_abandon, variant="ghost", full=True),
        title="Discard this workout?",
    )


def pr_banner() -> rx.Component:
    """A record: a short banner rising from the bottom, 2.5 s."""
    s = WorkoutState
    return rx.fragment(
        rx.el.style(_PR_CSS),
        rx.cond(
            s.show_pr,
            rx.hstack(
                rx.icon("medal", size=20, stroke_width=1.75, color=t.ACCENT),
                text(f"New PR · {s.pr.exercise_name} {s.pr.headline}", t.LABEL, flex="1", min_width="0"),
                rx.cond(s.pr_points > 0, text(f"+{s.pr_points} pts", t.LABEL, t.ACCENT, white_space="nowrap")),
                key=s.pr_serial.to_string(),
                position="fixed", left="0", right="0", margin="0 auto", max_width=f"calc({t.MAX_WIDTH} - 40px)",
                bottom=t.FLOAT_BOTTOM,
                background=t.SURFACE_2, border_radius=t.RADIUS_PILL, padding=f"{t.space(12)} {t.space(16)}",
                spacing="2", align="center", z_index="60", class_name="ma-pr-banner",
                custom_attrs={"role": "status", "aria-live": "polite"},
            ),
        ),
    )


def live_view() -> rx.Component:
    return rx.vstack(
        offline_assets(),
        workout_header(),
        rx.cond(
            WorkoutState.has_cards,
            rx.vstack(rx.foreach(WorkoutState.cards, exercise_card), spacing="3", width="100%"),
            empty_state("dumbbell", "Add the first exercise to start logging."),
        ),
        rx.hstack(
            button("Add exercise", PickerState.open_for("session"), variant="secondary", icon="plus", flex="1"),
            width="100%",
        ),
        voice_bar(),
        options_sheet(),
        set_sheet(),
        finish_sheet(),
        discard_sheet(),
        pr_banner(),
        spacing="4",
        width="100%",
    )
