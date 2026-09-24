"""Workout UI: the game HUD, start screen, live session, exercise cards, and
the finish summary.

Designed for one-handed logging mid-set (the brief's #1 UX bar): every card is
pre-filled from last time, weight and reps have large ± steppers, and logging a
repeat set is a single 52px tap. The HUD keeps the game layer - level, rank, XP
bar, streak, this workout's points - on screen the whole time, so the tracker
never feels bolted on.

Every number shown is from the API. Nothing here computes points or PRs.
"""

import reflex as rx

from metalarm import ranks, theme
from metalarm.components.exercise_demo import exercise_demo
from metalarm.components.presets import preset_cards
from metalarm.components.layout import section_heading
from metalarm.components.rest_timer import elapsed_clock
from metalarm.components.stat_panel import xp_bar
from metalarm.state.auth import AuthState
from metalarm.state.picker import PickerState
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import (
    AwardLine,
    ExerciseCard,
    HistoryRow,
    PrView,
    RoutineItem,
    SetRow,
)

PR_COLOR = theme.RANK_COLORS["A"]
FIELD_BG = theme.FIELD


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------


def button(label, on_click=None, *, color: str = theme.ACCENT, solid: bool = True, **overrides):
    style = {
        "background": color if solid else "transparent",
        "color": theme.ON_ACCENT if solid else color,
        "border": "none" if solid else f"1px solid {color}66",
        "border_radius": "10px",
        "font_weight": "800",
        "letter_spacing": "0.12em",
        "font_size": "0.74rem",
        "padding": "0.65rem 1rem",
        "height": "auto",
        "cursor": "pointer",
    }
    style.update(overrides)
    events = {"on_click": on_click} if on_click is not None else {}
    return rx.button(label, **events, **style)


def pill(text, color: str) -> rx.Component:
    return rx.box(
        rx.text(text, font_size="0.6rem", letter_spacing="0.14em", font_weight="800", color=color),
        padding="0.18rem 0.5rem",
        border=f"1px solid {color}66",
        border_radius="6px",
        background=f"{color}14",
        flex_shrink="0",
    )


def stat(label: str, value, color: str = theme.TEXT) -> rx.Component:
    return rx.vstack(
        rx.text(label, **theme.LABEL_STYLE),
        rx.text(value, color=color, font_weight="800", font_size="1.05rem"),
        spacing="1",
        align="start",
    )


def empty(message: str) -> rx.Component:
    return rx.box(
        rx.text(message, color=theme.FAINT, font_size="0.85rem", text_align="center"),
        width="100%",
        padding="1.75rem 1rem",
        border=f"1px dashed {theme.BORDER}",
        border_radius="12px",
    )


def _rank_color():
    return ranks.rank_color_var(AuthState.progress.rank)


# ---------------------------------------------------------------------------
# HUD - the game layer, always on screen
# ---------------------------------------------------------------------------


def hud() -> rx.Component:
    color = _rank_color()
    return rx.vstack(
        rx.hstack(
            rx.center(
                rx.text(
                    ranks.rank_title_var(AuthState.progress.rank),
                    color=color,
                    font_weight="900",
                    font_size="0.72rem",
                    text_align="center",
                    line_height="1.05",
                ),
                min_width="40px",
                height="40px",
                padding="0 0.5rem",
                border=f"2px solid {color}",
                border_radius="10px",
                box_shadow=f"0 0 22px -8px {color}",
                flex_shrink="0",
            ),
            rx.vstack(
                rx.text(
                    f"LEVEL {AuthState.progress.current_level}",
                    color=theme.TEXT,
                    font_weight="800",
                    font_size="0.85rem",
                    letter_spacing="0.12em",
                ),
                rx.text(
                    WorkoutState.streak.label,
                    color=rx.cond(WorkoutState.streak.weeks > 0, theme.SUCCESS, theme.FAINT),
                    font_size="0.66rem",
                    font_weight="800",
                    letter_spacing="0.14em",
                ),
                spacing="0",
                align="start",
            ),
            rx.spacer(),
            rx.cond(
                WorkoutState.has_session,
                rx.vstack(
                    rx.text("THIS WORKOUT", **theme.LABEL_STYLE),
                    rx.text(
                        f"+{WorkoutState.session_points}",
                        color=theme.ACCENT,
                        font_weight="900",
                        font_size="1.35rem",
                        line_height="1.1",
                    ),
                    spacing="0",
                    align="end",
                ),
                rx.vstack(
                    rx.text("POINTS", **theme.LABEL_STYLE),
                    rx.text(
                        AuthState.progress.points_balance.to_string(),
                        color=theme.WARNING,
                        font_weight="900",
                        font_size="1.35rem",
                        line_height="1.1",
                    ),
                    spacing="0",
                    align="end",
                ),
            ),
            width="100%",
            align="center",
            spacing="3",
        ),
        xp_bar(),
        rx.text(WorkoutState.streak.sub, color=theme.FAINT, font_size="0.72rem"),
        spacing="3",
        **theme.panel(padding="1rem 1.1rem", box_shadow=theme.glow(theme.ACCENT, "50px")),
    )


# ---------------------------------------------------------------------------
# Start screen
# ---------------------------------------------------------------------------


def history_row(row: HistoryRow) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.hstack(
                rx.text(row.title, color=theme.TEXT, font_weight="700", font_size="0.9rem"),
                rx.cond(row.status != "completed", pill(row.status_label, theme.FAINT)),
                spacing="2",
                align="center",
            ),
            rx.text(
                f"{row.date_label} · {row.duration_label} · {row.sets_label} · {row.volume_label}",
                color=theme.FAINT,
                font_size="0.72rem",
            ),
            spacing="1",
            align="start",
            min_width="0",
        ),
        rx.spacer(),
        rx.cond(row.pr_count > 0, pill(f"{row.pr_count} PR", PR_COLOR)),
        rx.text(
            f"+{row.points}",
            color=theme.WARNING,
            font_weight="800",
            font_size="0.9rem",
            min_width="3.5ch",
            text_align="right",
        ),
        width="100%",
        align="center",
        spacing="3",
        padding_block="0.65rem",
        border_bottom=f"1px solid {theme.BORDER}",
    )


def _routine_row(routine: RoutineItem) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(routine.name, color=theme.TEXT, font_weight="800", font_size="0.95rem"),
            rx.text(routine.summary_label, color=theme.FAINT, font_size="0.74rem"),
            spacing="1",
            align="start",
            min_width="0",
        ),
        rx.spacer(),
        button("START", WorkoutState.start_session(routine.id), height="44px", flex_shrink="0"),
        width="100%",
        align="center",
        spacing="3",
        padding="0.85rem 1rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER}",
        border_radius="12px",
    )


def unit_toggle() -> rx.Component:
    def option(unit: str) -> rx.Component:
        active = WorkoutState.unit == unit
        return rx.button(
            unit.upper(),
            on_click=WorkoutState.set_unit(unit),
            background=rx.cond(active, f"{theme.ACCENT}22", "transparent"),
            color=rx.cond(active, theme.ACCENT, theme.FAINT),
            border=rx.cond(active, f"1px solid {theme.ACCENT}", f"1px solid {theme.BORDER}"),
            border_radius="8px",
            font_size="0.68rem",
            font_weight="800",
            letter_spacing="0.12em",
            padding="0.35rem 0.7rem",
            cursor="pointer",
        )

    return rx.hstack(
        rx.text("WEIGHT UNIT", **theme.LABEL_STYLE),
        option("kg"),
        option("lb"),
        spacing="2",
        align="center",
    )


def start_view() -> rx.Component:
    return rx.vstack(
        rx.vstack(
            rx.text("READY WHEN YOU ARE", **{**theme.LABEL_STYLE, "color": theme.ACCENT}),
            rx.heading("Start a workout", size="6", color=theme.TEXT),
            rx.text(
                "Every set you log earns XP on the spot. Finish the workout to bank its "
                "points in your wallet.",
                color=theme.MUTED,
                font_size="0.85rem",
            ),
            button(
                "START EMPTY WORKOUT",
                WorkoutState.start_session(""),
                width="100%",
                height="56px",
                font_size="0.85rem",
            ),
            spacing="3",
            **theme.panel(),
        ),
        preset_cards(),
        section_heading(
            "FROM A ROUTINE",
            rx.link("MANAGE ROUTINES", href="/routines", color=theme.ACCENT, font_size="0.68rem",
                    font_weight="800", letter_spacing="0.12em"),
        ),
        rx.cond(
            WorkoutState.has_routines,
            rx.vstack(rx.foreach(WorkoutState.routines, _routine_row), spacing="2", width="100%"),
            empty("No routines yet. Build one and every future workout starts in a single tap."),
        ),
        section_heading(
            "RECENT",
            rx.link("PROGRESS", href="/progress", color=theme.ACCENT, font_size="0.68rem",
                    font_weight="800", letter_spacing="0.12em"),
        ),
        rx.cond(
            WorkoutState.has_recent,
            rx.box(rx.foreach(WorkoutState.recent, history_row), **theme.panel(padding="0.2rem 1rem")),
            empty("Your finished workouts show up here."),
        ),
        unit_toggle(),
        spacing="4",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Live session
# ---------------------------------------------------------------------------


def session_header() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text("IN PROGRESS", **{**theme.LABEL_STYLE, "color": theme.SUCCESS}),
                rx.heading(WorkoutState.session_name, size="5", color=theme.TEXT),
                spacing="1",
                align="start",
                min_width="0",
            ),
            rx.spacer(),
            elapsed_clock(
                WorkoutState.started_at,
                font_size="1.6rem",
                font_weight="900",
                color=theme.TEXT,
                font_variant_numeric="tabular-nums",
            ),
            width="100%",
            align="center",
        ),
        rx.hstack(
            stat("SETS", WorkoutState.working_sets.to_string()),
            stat("VOLUME", WorkoutState.volume_label),
            stat("POINTS", f"+{WorkoutState.session_points}", theme.ACCENT),
            spacing="6",
        ),
        rx.cond(
            WorkoutState.confirm_abandon,
            rx.hstack(
                rx.text(
                    "Discard this workout? Everything it earned is reversed.",
                    color=theme.DANGER,
                    font_size="0.8rem",
                    flex="1",
                    min_width="12rem",
                ),
                button("KEEP", WorkoutState.cancel_abandon, color=theme.MUTED, solid=False, height="44px"),
                button("DISCARD", WorkoutState.abandon, color=theme.DANGER, height="44px"),
                width="100%",
                spacing="2",
                align="center",
                flex_wrap="wrap",
            ),
            rx.hstack(
                button(
                    rx.cond(WorkoutState.busy, "WORKING…", "FINISH WORKOUT"),
                    WorkoutState.finish,
                    color=theme.SUCCESS,
                    flex="1",
                    height="50px",
                    font_size="0.8rem",
                    disabled=WorkoutState.busy,
                ),
                button("DISCARD", WorkoutState.ask_abandon, color=theme.FAINT, solid=False, height="50px"),
                width="100%",
                spacing="2",
            ),
        ),
        spacing="3",
        **theme.panel(padding="1.1rem"),
    )


def _flash(card: ExerciseCard) -> rx.Component:
    color = rx.match(
        card.flash_kind,
        ("pr", PR_COLOR),
        ("record", theme.SUCCESS),
        theme.MUTED,
    )
    return rx.cond(card.flash_kind != "", pill(card.flash_label, color))


def _set_number(entry: SetRow) -> rx.Component:
    return rx.center(
        rx.text(
            rx.cond(entry.is_warmup, "W", entry.set_number.to_string()),
            font_size="0.72rem",
            font_weight="800",
            color=rx.cond(entry.is_warmup, theme.WARNING, theme.MUTED),
        ),
        width="28px",
        height="28px",
        border_radius="8px",
        background=FIELD_BG,
        border=f"1px solid {theme.BORDER}",
        flex_shrink="0",
    )


def _edit_field(label: str, value, on_change, **overrides) -> rx.Component:
    return rx.vstack(
        rx.text(label, **{**theme.LABEL_STYLE, "font_size": "0.6rem"}),
        _number_field(value, on_change, height="46px", font_size="1rem", **overrides),
        spacing="1",
        flex="1",
        min_width="0",
    )


def _edit_row(entry: SetRow, is_cardio) -> rx.Component:
    """Inline editor for a logged set. Saving PATCHes it; the API re-judges
    the set, so the result is shown exactly like a new log."""
    return rx.vstack(
        rx.hstack(
            _set_number(entry),
            rx.text("EDIT SET", **{**theme.LABEL_STYLE, "color": theme.ACCENT}),
            rx.spacer(),
            rx.button(
                rx.cond(WorkoutState.edit_warmup, "WARM-UP ✓", "WARM-UP"),
                on_click=WorkoutState.toggle_edit_warmup,
                background=rx.cond(WorkoutState.edit_warmup, f"{theme.WARNING}22", "transparent"),
                color=rx.cond(WorkoutState.edit_warmup, theme.WARNING, theme.FAINT),
                border=rx.cond(WorkoutState.edit_warmup, f"1px solid {theme.WARNING}", f"1px solid {theme.BORDER}"),
                border_radius="8px",
                font_size="0.62rem",
                font_weight="800",
                letter_spacing="0.1em",
                padding="0.35rem 0.6rem",
                cursor="pointer",
            ),
            width="100%",
            align="center",
            spacing="3",
        ),
        rx.hstack(
            rx.cond(
                is_cardio,
                rx.fragment(
                    _edit_field("MINUTES", WorkoutState.edit_duration, WorkoutState.set_edit_duration),
                    _edit_field("KM", WorkoutState.edit_distance, WorkoutState.set_edit_distance),
                ),
                rx.fragment(
                    _edit_field(f"WEIGHT ({WorkoutState.unit})", WorkoutState.edit_weight, WorkoutState.set_edit_weight),
                    _edit_field("REPS", WorkoutState.edit_reps, WorkoutState.set_edit_reps),
                ),
            ),
            _edit_field("RPE", WorkoutState.edit_rpe, WorkoutState.set_edit_rpe, width="100%"),
            spacing="2",
            width="100%",
        ),
        rx.hstack(
            button(
                rx.cond(WorkoutState.busy, "SAVING…", "SAVE"),
                WorkoutState.save_edit,
                flex="1",
                height="44px",
                disabled=WorkoutState.busy,
            ),
            button("CANCEL", WorkoutState.cancel_edit, color=theme.MUTED, solid=False, height="44px"),
            rx.button(
                "DELETE",
                on_click=WorkoutState.delete_set(entry.id),
                background="transparent",
                color=theme.DANGER,
                border=f"1px solid {theme.DANGER}55",
                border_radius="10px",
                font_size="0.7rem",
                font_weight="800",
                letter_spacing="0.1em",
                height="44px",
                padding="0 0.8rem",
                cursor="pointer",
                custom_attrs={"aria-label": "Delete set"},
            ),
            width="100%",
            spacing="2",
        ),
        spacing="3",
        width="100%",
        padding="0.75rem",
        margin_block="0.35rem",
        background=FIELD_BG,
        border=f"1px solid {theme.ACCENT}55",
        border_radius="12px",
    )


def _set_row(entry: SetRow, is_cardio) -> rx.Component:
    return rx.cond(
        WorkoutState.editing_set_id == entry.id,
        _edit_row(entry, is_cardio),
        rx.hstack(
            # The whole row is the edit target: a big, forgiving tap area.
            rx.hstack(
                _set_number(entry),
                rx.text(entry.summary, color=theme.TEXT, font_weight="700", font_size="0.95rem"),
                rx.cond(entry.detail != "", rx.text(entry.detail, color=theme.FAINT, font_size="0.72rem")),
                rx.cond(entry.is_pr, pill("PR", PR_COLOR)),
                rx.spacer(),
                rx.text("EDIT", color=theme.FAINT, font_size="0.6rem", font_weight="800", letter_spacing="0.12em"),
                on_click=WorkoutState.start_edit(entry.id),
                cursor="pointer",
                align="center",
                spacing="3",
                flex="1",
                min_width="0",
                padding_block="0.2rem",
                custom_attrs={"role": "button", "aria-label": "Edit set"},
            ),
            rx.button(
                "✕",
                on_click=WorkoutState.delete_set(entry.id),
                background="transparent",
                color=theme.FAINT,
                border="none",
                font_size="0.85rem",
                cursor="pointer",
                padding="0.35rem 0.55rem",
                custom_attrs={"aria-label": "Delete set"},
                _hover={"color": theme.DANGER},
            ),
            width="100%",
            align="center",
            spacing="2",
            padding_block="0.4rem",
            border_bottom=f"1px solid {theme.BORDER}",
        ),
    )


def _number_field(value, on_change, placeholder: str = "", **overrides) -> rx.Component:
    style = {
        "type": "number",
        "size": "3",
        "width": "100%",
        "height": "52px",
        "font_size": "1.15rem",
        "font_weight": "800",
        "text_align": "center",
        "background": FIELD_BG,
        "color": theme.TEXT,
    }
    style.update(overrides)
    return rx.input(value=value, on_change=on_change, placeholder=placeholder, **style)


def _step_button(label: str, on_click) -> rx.Component:
    return rx.button(
        label,
        on_click=on_click,
        width="48px",
        min_width="48px",
        height="52px",
        padding="0",
        background=FIELD_BG,
        color=theme.TEXT,
        border=f"1px solid {theme.BORDER_HI}",
        border_radius="10px",
        font_size="1.35rem",
        font_weight="700",
        cursor="pointer",
    )


def _stepper(label, value, on_change, minus, plus) -> rx.Component:
    return rx.vstack(
        rx.text(label, **theme.LABEL_STYLE),
        rx.hstack(
            _step_button("−", minus),
            _number_field(value, on_change),
            _step_button("+", plus),
            spacing="2",
            width="100%",
            align="center",
        ),
        spacing="1",
        flex="1",
        min_width="0",
        width="100%",
    )


def _strength_entry(card: ExerciseCard, index) -> rx.Component:
    return rx.flex(
        _stepper(
            f"WEIGHT ({WorkoutState.unit})",
            card.weight_input,
            lambda value: WorkoutState.set_weight(index, value),
            WorkoutState.bump_weight(index, -1),
            WorkoutState.bump_weight(index, 1),
        ),
        _stepper(
            "REPS",
            card.reps_input,
            lambda value: WorkoutState.set_reps(index, value),
            WorkoutState.bump_reps(index, -1),
            WorkoutState.bump_reps(index, 1),
        ),
        direction=rx.breakpoints(initial="column", sm="row"),
        gap="0.75rem",
        width="100%",
    )


def _cardio_entry(card: ExerciseCard, index) -> rx.Component:
    def field(label: str, value, on_change) -> rx.Component:
        return rx.vstack(
            rx.text(label, **theme.LABEL_STYLE),
            _number_field(value, on_change),
            spacing="1",
            flex="1",
            width="100%",
        )

    return rx.flex(
        field("MINUTES", card.duration_input, lambda value: WorkoutState.set_duration(index, value)),
        field("DISTANCE (KM)", card.distance_input, lambda value: WorkoutState.set_distance(index, value)),
        direction="row",
        gap="0.75rem",
        width="100%",
    )


def _log_row(card: ExerciseCard, index) -> rx.Component:
    return rx.hstack(
        rx.button(
            rx.cond(card.warmup, "WARM-UP ✓", "WARM-UP"),
            on_click=WorkoutState.toggle_warmup(index),
            background=rx.cond(card.warmup, f"{theme.WARNING}22", "transparent"),
            color=rx.cond(card.warmup, theme.WARNING, theme.FAINT),
            border=rx.cond(card.warmup, f"1px solid {theme.WARNING}", f"1px solid {theme.BORDER}"),
            border_radius="10px",
            height="52px",
            padding="0 0.75rem",
            font_size="0.66rem",
            font_weight="800",
            letter_spacing="0.1em",
            cursor="pointer",
            flex_shrink="0",
        ),
        _number_field(
            card.rpe_input,
            lambda value: WorkoutState.set_rpe(index, value),
            placeholder="RPE",
            width="76px",
            font_size="0.95rem",
        ),
        rx.button(
            rx.cond(WorkoutState.busy, "…", "LOG SET"),
            on_click=WorkoutState.log_set(index),
            disabled=WorkoutState.busy,
            flex="1",
            height="52px",
            background=rx.cond(card.warmup, theme.WARNING, theme.ACCENT),
            color=theme.ON_ACCENT,
            border="none",
            border_radius="10px",
            font_size="0.85rem",
            font_weight="900",
            letter_spacing="0.16em",
            cursor="pointer",
            box_shadow=theme.glow(theme.ACCENT, "30px"),
        ),
        width="100%",
        spacing="2",
        align="center",
    )


def exercise_card(card: ExerciseCard, index) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            exercise_demo(card.media_url, card.name, size="52px", radius="10px"),
            rx.vstack(
                rx.text(card.name, color=theme.TEXT, font_weight="800", font_size="1.02rem"),
                rx.text(card.muscles_label, color=theme.FAINT, font_size="0.62rem", letter_spacing="0.1em"),
                spacing="1",
                align="start",
                min_width="0",
            ),
            rx.spacer(),
            _flash(card),
            rx.cond(
                card.sets.length() == 0,
                rx.button(
                    "REMOVE",
                    on_click=WorkoutState.remove_card(index),
                    background="transparent",
                    color=theme.FAINT,
                    border="none",
                    font_size="0.62rem",
                    letter_spacing="0.12em",
                    cursor="pointer",
                    _hover={"color": theme.DANGER},
                ),
            ),
            width="100%",
            align="start",
            spacing="2",
        ),
        rx.cond(
            card.target_label != "",
            rx.text(f"TARGET  {card.target_label}", color=theme.ACCENT, font_size="0.7rem",
                    font_weight="700", letter_spacing="0.08em"),
        ),
        rx.cond(
            card.previous_label != "",
            rx.text(card.previous_label, color=theme.FAINT, font_size="0.74rem"),
        ),
        rx.cond(
            card.sets.length() > 0,
            rx.vstack(
                rx.foreach(card.sets, lambda entry: _set_row(entry, card.is_cardio)),
                spacing="0",
                width="100%",
            ),
        ),
        rx.cond(card.is_cardio, _cardio_entry(card, index), _strength_entry(card, index)),
        rx.cond(card.ghost_label != "", rx.text(card.ghost_label, color=theme.MUTED, font_size="0.72rem")),
        rx.cond(
            card.hint_label != "",
            rx.text(
                card.hint_label,
                color=rx.cond(card.hint_kind == "progress", theme.ACCENT, theme.WARNING),
                font_size="0.74rem",
                font_weight="600",
            ),
        ),
        _log_row(card, index),
        spacing="3",
        **theme.panel(
            padding="1.1rem",
            border=rx.cond(card.flash_kind == "pr", f"1px solid {PR_COLOR}99", f"1px solid {theme.BORDER}"),
        ),
    )


def live_view() -> rx.Component:
    return rx.vstack(
        session_header(),
        rx.cond(
            WorkoutState.has_cards,
            rx.vstack(rx.foreach(WorkoutState.cards, exercise_card), spacing="3", width="100%"),
            empty("Add your first exercise to start logging."),
        ),
        rx.button(
            "+ ADD EXERCISE",
            on_click=PickerState.open_for("session"),
            width="100%",
            height="56px",
            background="transparent",
            color=theme.ACCENT,
            border=f"1px dashed {theme.ACCENT}88",
            border_radius="12px",
            font_weight="800",
            letter_spacing="0.14em",
            font_size="0.8rem",
            cursor="pointer",
        ),
        # Room at the bottom so the rest bar never covers the last card.
        rx.box(height="88px"),
        spacing="3",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Finish summary
# ---------------------------------------------------------------------------


def _award_line(line: AwardLine) -> rx.Component:
    return rx.hstack(
        rx.text(line.label, color=theme.MUTED, font_size="0.85rem"),
        rx.spacer(),
        rx.text(
            line.points_label,
            color=rx.cond(line.negative, theme.DANGER, theme.TEXT),
            font_weight="800",
            font_size="0.9rem",
        ),
        width="100%",
        padding_block="0.35rem",
        border_bottom=f"1px solid {theme.BORDER}",
    )


def pr_line(view: PrView) -> rx.Component:
    return rx.hstack(
        pill(view.record_label, PR_COLOR),
        rx.text(view.exercise_name, color=theme.MUTED, font_size="0.82rem", min_width="0"),
        rx.spacer(),
        rx.text(view.headline, color=theme.TEXT, font_weight="800", font_size="0.9rem"),
        rx.cond(view.delta != "", rx.text(view.delta, color=PR_COLOR, font_size="0.72rem", font_weight="700")),
        width="100%",
        align="center",
        spacing="2",
        padding_block="0.4rem",
        border_bottom=f"1px solid {theme.BORDER}",
        flex_wrap="wrap",
    )


def summary_view() -> rx.Component:
    s = WorkoutState.summary
    return rx.vstack(
        rx.vstack(
            rx.text("WORKOUT COMPLETE", **{**theme.LABEL_STYLE, "color": theme.SUCCESS, "letter_spacing": "0.3em"}),
            rx.heading(s.title, size="6", color=theme.TEXT, text_align="center"),
            rx.text(
                f"+{s.points_credited}",
                color=theme.WARNING,
                font_size="3.2rem",
                font_weight="900",
                line_height="1",
                class_name="lf-card",
            ),
            rx.text("points banked to your wallet", color=theme.MUTED, font_size="0.8rem"),
            rx.grid(
                stat("DURATION", s.duration_label),
                stat("VOLUME", s.volume_label),
                stat("SETS", s.sets_label),
                stat("PRS", s.pr_count.to_string(), PR_COLOR),
                columns=rx.breakpoints(initial="2", sm="4"),
                gap="1rem",
                width="100%",
                padding_top="0.5rem",
            ),
            align="center",
            spacing="3",
            **theme.panel(box_shadow=theme.glow(theme.SUCCESS, "70px")),
        ),
        rx.cond(
            s.qualified_note != "",
            rx.box(
                rx.text(s.qualified_note, color=theme.WARNING, font_size="0.8rem", line_height="1.5"),
                width="100%",
                padding="0.75rem 1rem",
                background=theme.WARNING_BG,
                border=f"1px solid {theme.WARNING}44",
                border_radius="10px",
            ),
        ),
        rx.vstack(
            rx.text("POINTS", **theme.LABEL_STYLE),
            rx.foreach(s.lines, _award_line),
            spacing="1",
            **theme.panel(padding="1rem 1.1rem"),
        ),
        rx.cond(
            s.prs.length() > 0,
            rx.vstack(
                rx.text("RECORDS BROKEN", **{**theme.LABEL_STYLE, "color": PR_COLOR}),
                rx.foreach(s.prs, pr_line),
                spacing="1",
                **theme.panel(padding="1rem 1.1rem"),
            ),
        ),
        rx.vstack(
            rx.text(s.streak.label, color=rx.cond(s.streak.weeks > 0, theme.SUCCESS, theme.FAINT),
                    font_weight="900", letter_spacing="0.16em", font_size="0.85rem"),
            rx.text(s.streak.sub, color=theme.MUTED, font_size="0.8rem"),
            spacing="1",
            **theme.panel(padding="1rem 1.1rem"),
        ),
        rx.hstack(
            button("DONE", WorkoutState.close_summary, flex="1", height="52px", font_size="0.82rem"),
            # A 1080 x 1920 story card of this workout (metalarm/share_card.py).
            button("SHARE", WorkoutState.share_card, color=theme.ACCENT, solid=False, height="52px"),
            rx.link(
                button("PROGRESS", color=theme.ACCENT, solid=False, height="52px"),
                href="/progress",
            ),
            width="100%",
            spacing="2",
        ),
        spacing="3",
        width="100%",
    )
