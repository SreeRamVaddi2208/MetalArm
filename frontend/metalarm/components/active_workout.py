"""The active workout (overhaul 7.5) - the most important screen.

A header (name, elapsed time, Finish), then one card per exercise: its menu
(move, superset with next, notes, rest, remove), and a set table - SET (tap
to cycle normal / W / D / F), PREVIOUS (tap to copy), KG, REPS, RPE, and the
check that logs it. Logged sets are rows above the entry row; tapping one's
SET cell opens the set editor. Inline feedback (+N points, PR medal, quest
chip) never blocks the next input.

Cardio cards keep the duration/distance entry from components/workout.py
until they get a table of their own.
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.rest_timer import elapsed_clock
from metalarm.components.voice_log import voice_bar
from metalarm.components.workout import _edit_row, exercise_card, quest_moment
from metalarm.state.picker import PickerState
from metalarm.state.workout import WorkoutState
from metalarm.ui.primitives import empty_state, primary_button, secondary_button, text, thumb, when
from metalarm.ui.set_row import set_header, set_row
from metalarm.workout_models import ExerciseCard, SetRow


def workout_header() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                text(WorkoutState.session_name, t.TITLE_2, overflow="hidden",
                     text_overflow="ellipsis", white_space="nowrap", max_width="100%"),
                rx.hstack(
                    elapsed_clock(WorkoutState.started_at, color=t.TEXT_SECONDARY,
                                  **{**t.SUBHEAD, **t.TABULAR}),
                    text(f"{WorkoutState.working_sets} sets · {WorkoutState.volume_label}", t.SUBHEAD,
                         t.TEXT_SECONDARY, **t.TABULAR),
                    spacing="3",
                ),
                spacing="0",
                align="start",
                min_width="0",
                flex="1",
            ),
            rx.box(rx.icon("trash-2", size=20, color=t.TEXT_SECONDARY), width=t.TOUCH_MIN,
                   height=t.TOUCH_MIN, display="flex", align_items="center", justify_content="center",
                   cursor="pointer", on_click=WorkoutState.ask_abandon,
                   custom_attrs={"role": "button", "aria-label": "Discard workout"}),
            primary_button(rx.cond(WorkoutState.busy, "Saving…", "Finish"), WorkoutState.finish,
                           disabled=WorkoutState.busy),
            width="100%",
            align="center",
            spacing="3",
        ),
        quest_moment(),
        rx.cond(
            WorkoutState.confirm_abandon,
            rx.hstack(
                text("Discard this workout? Everything it earned is reversed.", t.FOOTNOTE, t.DANGER_RED,
                     flex="1"),
                secondary_button("Keep", WorkoutState.cancel_abandon),
                secondary_button("Discard", WorkoutState.abandon, color=t.DANGER_RED),
                width="100%", align="center", spacing="2",
            ),
        ),
        position="sticky",
        top="0",
        z_index="20",
        background=t.COLOR_BG,
        padding_y=t.space(2),
        width="100%",
        spacing="2",
    )


def _menu_item(icon: str, label, on_click, color: str = t.TEXT_PRIMARY) -> rx.Component:
    return rx.hstack(
        rx.icon(icon, size=18, color=color), text(label, t.BODY, color),
        spacing="3", align="center", width="100%", min_height=t.TOUCH_MIN,
        cursor="pointer", on_click=on_click,
        custom_attrs={"role": "button"},
    )


def _menu(card: ExerciseCard, index) -> rx.Component:
    return rx.cond(
        card.menu_open,
        rx.vstack(
            rx.el.textarea(
                value=card.notes,
                placeholder="Notes for this exercise",
                on_change=lambda value: WorkoutState.set_notes(index, value),
                on_blur=lambda value: WorkoutState.save_notes(card.session_exercise_id, value),
                rows=2,
                width="100%",
                background=t.SURFACE_2,
                color=t.TEXT_PRIMARY,
                border="none",
                border_radius=t.RADIUS_THUMB,
                padding=t.space(3),
                **t.SUBHEAD,
            ),
            rx.hstack(
                text("Rest", t.BODY, flex="1"),
                rx.el.button("−15s", on_click=WorkoutState.bump_rest(index, -15), background=t.SURFACE_2,
                             color=t.TEXT_PRIMARY, border="none", border_radius=t.RADIUS_PILL,
                             min_height="36px", padding=f"0 {t.space(3)}", **t.FOOTNOTE),
                text(f"{card.rest_seconds}s", t.HEADLINE, min_width="48px", text_align="center", **t.TABULAR),
                rx.el.button("+15s", on_click=WorkoutState.bump_rest(index, 15), background=t.SURFACE_2,
                             color=t.TEXT_PRIMARY, border="none", border_radius=t.RADIUS_PILL,
                             min_height="36px", padding=f"0 {t.space(3)}", **t.FOOTNOTE),
                width="100%", align="center", spacing="2",
            ),
            _menu_item("arrow-up", "Move up", WorkoutState.move_card(index, -1)),
            _menu_item("arrow-down", "Move down", WorkoutState.move_card(index, 1)),
            _menu_item("link", rx.cond(card.superset_group > 0, "Superset: change", "Superset with next"),
                       WorkoutState.superset_with_next(index)),
            _menu_item("trash-2", rx.cond(card.sets.length() > 0, "Remove with its sets", "Remove"),
                       WorkoutState.remove_card(index), t.DANGER_RED),
            spacing="1",
            width="100%",
            padding_top=t.space(2),
            border_top=t.HAIRLINE,
        ),
    )


def _logged(entry: SetRow, card: ExerciseCard, index) -> rx.Component:
    return rx.cond(
        WorkoutState.editing_set_id == entry.id,
        _edit_row(entry, card.is_cardio),
        rx.vstack(
            set_row(
                entry.set_number, set_type=entry.set_type, previous=entry.previous,
                weight=rx.cond(entry.weight != "", entry.weight, "0"), reps=entry.reps,
                rpe=rx.cond(entry.rpe != "", entry.rpe, "-"), done=True, pr=entry.is_pr,
                on_type=WorkoutState.start_edit(entry.id),
                on_check=WorkoutState.start_edit(entry.id),
            ),
            rx.cond(entry.flagged, text("This set won't count toward competitions", t.FOOTNOTE,
                                        t.TEXT_TERTIARY, padding_left=t.space(10))),
            spacing="0",
            width="100%",
        ),
    )


def active_card(card: ExerciseCard, index) -> rx.Component:
    strength = rx.vstack(
        rx.hstack(
            thumb(card.thumbnail_url, size="44px", icon="dumbbell"),
            rx.vstack(
                text(card.name, t.HEADLINE, color=t.ACCENT_BLUE, overflow="hidden",
                     text_overflow="ellipsis", white_space="nowrap", max_width="100%"),
                rx.hstack(
                    rx.cond(card.superset_group > 0,
                            text(f"Superset {card.superset_group}", t.FOOTNOTE, t.STREAK_ORANGE)),
                    text(card.target_label, t.FOOTNOTE, t.TEXT_SECONDARY),
                    rx.hstack(rx.icon("timer", size=13, color=t.TEXT_SECONDARY),
                              text(f"{card.rest_seconds}s", t.FOOTNOTE, t.TEXT_SECONDARY, **t.TABULAR),
                              spacing="1", align="center"),
                    spacing="2", align="center", flex_wrap="wrap",
                ),
                spacing="0", align="start", min_width="0", flex="1",
            ),
            rx.box(rx.icon("ellipsis", size=22, color=t.TEXT_SECONDARY), width=t.TOUCH_MIN,
                   height=t.TOUCH_MIN, display="flex", align_items="center", justify_content="center",
                   cursor="pointer", on_click=WorkoutState.toggle_menu(index),
                   custom_attrs={"role": "button", "aria-label": "Exercise options"}),
            width="100%", align="center", spacing="3",
        ),
        rx.cond(card.notes != "", text(card.notes, t.FOOTNOTE, t.TEXT_SECONDARY)),
        # Last time's sets are in the PREV column; only "first time" needs saying.
        rx.cond((card.previous.length() == 0) & (card.previous_label != ""),
                text(card.previous_label, t.FOOTNOTE, t.TEXT_SECONDARY)),
        rx.cond(card.hint_label != "",
                text(card.hint_label, t.FOOTNOTE,
                     rx.cond(card.hint_kind == "progress", t.RECOVERY_GREEN, t.STREAK_ORANGE))),
        _menu(card, index),
        # The last set's moment, inline: a record, or a first-ever baseline.
        rx.cond(card.flash_label != "",
                text(card.flash_label, t.FOOTNOTE,
                     rx.match(card.flash_kind, ("pr", t.PR_GOLD), ("record", t.PR_GOLD), t.TEXT_SECONDARY),
                     font_weight="600")),
        set_header(rpe=True),
        rx.foreach(card.sets, lambda entry: _logged(entry, card, index)),
        set_row(
            card.sets.length() + 1,
            set_type=card.entry_type,
            previous=card.entry_previous,
            weight=card.weight_input,
            reps=card.reps_input,
            rpe=card.rpe_input,
            done=False,
            on_type=WorkoutState.cycle_type(index),
            on_copy=WorkoutState.copy_previous(index),
            on_weight=lambda value: WorkoutState.set_weight(index, value),
            on_reps=lambda value: WorkoutState.set_reps(index, value),
            on_rpe=lambda value: WorkoutState.set_rpe(index, value),
            on_check=WorkoutState.log_set(index),
            points=card.last_points,
        ),
        spacing="2",
        width="100%",
        background=t.SURFACE_1,
        border_radius=t.RADIUS_CARD,
        padding=t.CARD_PADDING,
        border_left=rx.cond(card.superset_group > 0, f"3px solid {t.STREAK_ORANGE}", "3px solid transparent"),
        class_name="ma-card",
    )
    return rx.cond(card.is_cardio, exercise_card(card, index), strength)


def live_view() -> rx.Component:
    return rx.vstack(
        workout_header(),
        rx.cond(
            WorkoutState.has_cards,
            rx.vstack(rx.foreach(WorkoutState.cards, active_card), spacing="3", width="100%"),
            empty_state("No exercises yet", "Add one to start logging."),
        ),
        rx.el.button(
            rx.hstack(rx.icon("plus", size=18), rx.el.span("Add Exercise"), spacing="2",
                      align="center", justify="center"),
            on_click=PickerState.open_for("session"),
            width="100%",
            min_height="52px",
            background=t.SURFACE_1,
            color=t.ACCENT_BLUE,
            border="none",
            border_radius=t.RADIUS_CARD,
            cursor="pointer",
            **t.HEADLINE,
        ),
        # Voice and typed logging: an addition beside the tap loop.
        voice_bar(),
        spacing="3",
        width="100%",
    )
