"""Progress: exercise charts, personal records, workout history, points, and
body measurements."""

import reflex as rx

from metalarm import theme
from metalarm.components.layout import error_banner, section_heading, shell
from metalarm.components.scroll_reveal import reveal, reveal_assets
from metalarm.components.workout import FIELD_BG, PR_COLOR, button, empty, history_row, pill, stat
from metalarm.state.auth import AuthState
from metalarm.state.progress import ProgressState
from metalarm.workout_models import BodyRow, ExerciseOption, RecordRow


def _axis_style() -> dict:
    return {"stroke": theme.FAINT, "font_size": 11}


def _tooltip() -> rx.Component:
    return rx.recharts.graphing_tooltip(
        content_style={"background": theme.PANEL, "border": f"1px solid {theme.BORDER_HI}", "borderRadius": "8px"},
        label_style={"color": theme.MUTED},
    )


def stats_panel() -> rx.Component:
    return rx.grid(
        stat("WORKOUT POINTS", ProgressState.total_points.to_string(), theme.WARNING),
        stat("THIS WEEK", ProgressState.week_points.to_string(), theme.ACCENT),
        stat("WORKOUTS", ProgressState.sessions_completed.to_string()),
        stat("STREAK", ProgressState.streak.label, theme.SUCCESS),
        columns=rx.breakpoints(initial="2", md="4"),
        gap="1rem",
        **theme.panel(),
    )


def _option(option: ExerciseOption) -> rx.Component:
    return rx.select.item(option.name, value=option.id)


def exercise_panel() -> rx.Component:
    return rx.vstack(
        section_heading("EXERCISE PROGRESS"),
        rx.cond(
            ProgressState.exercise_options.length() > 0,
            rx.select.root(
                rx.select.trigger(placeholder="Choose an exercise", width="100%"),
                rx.select.content(rx.foreach(ProgressState.exercise_options, _option)),
                value=ProgressState.selected_id,
                on_change=ProgressState.select_exercise,
                size="3",
            ),
        ),
        rx.cond(
            ProgressState.has_chart,
            rx.vstack(
                rx.text(f"TOP SET & ESTIMATED 1RM ({AuthState.weight_unit})", **theme.LABEL_STYLE),
                rx.recharts.line_chart(
                    rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke=theme.BORDER),
                    rx.recharts.x_axis(data_key="date", **_axis_style()),
                    rx.recharts.y_axis(**_axis_style()),
                    _tooltip(),
                    rx.recharts.line(data_key="top", name="Top set", stroke=theme.ACCENT, stroke_width=2, connect_nulls=True),
                    rx.recharts.line(data_key="e1rm", name="Est. 1RM", stroke=PR_COLOR, stroke_width=2, connect_nulls=True),
                    data=ProgressState.chart_data,
                    width="100%",
                    height=240,
                ),
                rx.text(f"VOLUME PER WORKOUT ({AuthState.weight_unit})", **theme.LABEL_STYLE),
                rx.recharts.bar_chart(
                    rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke=theme.BORDER),
                    rx.recharts.x_axis(data_key="date", **_axis_style()),
                    rx.recharts.y_axis(**_axis_style()),
                    _tooltip(),
                    rx.recharts.bar(data_key="volume", name="Volume", fill=theme.ACCENT_DIM),
                    data=ProgressState.chart_data,
                    width="100%",
                    height=180,
                ),
                spacing="2",
                width="100%",
            ),
            empty("Finish a workout and your charts start here - one point per session."),
        ),
        spacing="3",
        **theme.panel(),
    )


def _record_row(row: RecordRow) -> rx.Component:
    # Two fixed lines rather than one wrapping line: on a phone the wrap put
    # the date under the name at a random point, which read as broken.
    return rx.hstack(
        rx.vstack(
            rx.text(row.exercise_name, color=theme.TEXT, font_size="0.85rem", font_weight="600"),
            pill(row.record_label, PR_COLOR),
            spacing="1",
            align="start",
            min_width="0",
        ),
        rx.spacer(),
        rx.vstack(
            rx.text(row.value_label, color=theme.TEXT, font_weight="800", font_size="0.92rem", white_space="nowrap"),
            rx.text(row.date_label, color=theme.FAINT, font_size="0.68rem"),
            spacing="1",
            align="end",
        ),
        width="100%",
        align="center",
        spacing="3",
        padding_block="0.55rem",
        border_bottom=f"1px solid {theme.BORDER}",
    )


def records_panel() -> rx.Component:
    return rx.vstack(
        section_heading("PERSONAL RECORDS"),
        rx.cond(
            ProgressState.has_records,
            rx.box(rx.foreach(ProgressState.records, _record_row), width="100%",
                   max_height="420px", overflow_y="auto"),
            empty("Records appear the moment you log your first sets."),
        ),
        spacing="3",
        **theme.panel(),
    )


def history_panel() -> rx.Component:
    return rx.vstack(
        section_heading("WORKOUT HISTORY"),
        rx.cond(
            ProgressState.has_history,
            rx.vstack(
                rx.box(rx.foreach(ProgressState.history, history_row), width="100%"),
                rx.cond(
                    ProgressState.has_more,
                    button("LOAD MORE", ProgressState.more_history, color=theme.MUTED, solid=False, width="100%"),
                ),
                spacing="3",
                width="100%",
            ),
            empty("No workouts yet."),
        ),
        spacing="3",
        **theme.panel(),
    )


def _body_row(row: BodyRow) -> rx.Component:
    return rx.hstack(
        rx.text(row.metric_label, **{**theme.LABEL_STYLE, "font_size": "0.62rem"}),
        rx.text(row.value_label, color=theme.TEXT, font_weight="800", font_size="0.9rem"),
        rx.spacer(),
        rx.text(row.date_label, color=theme.FAINT, font_size="0.72rem"),
        rx.button(
            "✕",
            on_click=ProgressState.delete_measurement(row.id),
            background="transparent",
            color=theme.FAINT,
            border="none",
            cursor="pointer",
            padding="0.3rem 0.5rem",
            custom_attrs={"aria-label": "Delete measurement"},
            _hover={"color": theme.DANGER},
        ),
        width="100%",
        align="center",
        spacing="3",
        padding_block="0.4rem",
        border_bottom=f"1px solid {theme.BORDER}",
    )


def body_panel() -> rx.Component:
    return rx.vstack(
        section_heading("BODY"),
        rx.flex(
            rx.select(["weight", "body_fat", "custom"], value=ProgressState.m_metric,
                      on_change=ProgressState.set_m_metric, size="3"),
            rx.cond(
                ProgressState.is_custom_metric,
                rx.input(placeholder="Name, e.g. Waist", value=ProgressState.m_label,
                         on_change=ProgressState.set_m_label, size="3", background=FIELD_BG,
                         color=theme.TEXT, flex="1", min_width="8rem"),
            ),
            rx.input(placeholder="Value", value=ProgressState.m_value, on_change=ProgressState.set_m_value,
                     type="number", size="3", background=FIELD_BG, color=theme.TEXT, width="7rem"),
            rx.select(ProgressState.m_unit_options, value=ProgressState.m_unit,
                      on_change=ProgressState.set_m_unit, size="3"),
            button("ADD", ProgressState.add_measurement, height="40px"),
            gap="0.5rem",
            wrap="wrap",
            align="center",
            width="100%",
        ),
        rx.cond(
            ProgressState.has_weight_chart,
            rx.recharts.line_chart(
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke=theme.BORDER),
                rx.recharts.x_axis(data_key="date", **_axis_style()),
                rx.recharts.y_axis(domain=["dataMin - 2", "dataMax + 2"], **_axis_style()),
                _tooltip(),
                rx.recharts.line(data_key="value", name="Body weight", stroke=theme.SUCCESS, stroke_width=2),
                data=ProgressState.weight_chart,
                width="100%",
                height=200,
            ),
        ),
        rx.cond(
            ProgressState.has_measurements,
            rx.box(rx.foreach(ProgressState.measurements, _body_row), width="100%",
                   max_height="320px", overflow_y="auto"),
            empty("Track body weight, body fat, or any measurement. Tracking only - no points."),
        ),
        spacing="3",
        **theme.panel(),
    )


def progress_page() -> rx.Component:
    return shell(
        reveal_assets(),
        stats_panel(),
        error_banner(ProgressState.error),
        reveal(exercise_panel()),
        rx.grid(
            reveal(records_panel()),
            reveal(history_panel()),
            columns=rx.breakpoints(initial="1", lg="2"),
            gap="1.25rem",
            width="100%",
        ),
        reveal(body_panel()),
    )
