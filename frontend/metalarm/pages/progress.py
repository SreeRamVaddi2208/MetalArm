"""The Progress tab.

/progress                 one chart (all training, or one exercise), records,
                          and the way to everything else. No primary button.
/progress/history         the calendar, then every workout, week by week
/progress/measurements    body weight and the rest; Log measurement
/progress/recovery        what you worked this week, and what has recovered
"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.auth import AuthState
from metalarm.state.monthly import MonthlyState
from metalarm.state.workout_home import WorkoutHomeState
from metalarm.state.you import FOCUS_METRICS, METRICS, RANGES, YouState
from metalarm.ui.body_map import body_map
from metalarm.ui.calendar import month_calendar
from metalarm.ui.chart import line_chart
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import (
    button,
    card,
    chip,
    chips,
    empty_state,
    field,
    icon_button,
    list_row,
    number,
    rows,
    section,
    segmented,
    sheet,
    skeleton,
    skeleton_rows,
    stat_group,
    stat_tile,
    text,
)

# ---------------------------------------------------------------------------
# /progress
# ---------------------------------------------------------------------------


def _month_card() -> rx.Component:
    """Last month's story, in the first week of a month."""
    m = MonthlyState
    return rx.cond(
        m.hero_show,
        card(text(f"Your {m.hero_title}", t.TITLE), text(f"{m.hero_workouts} workouts · see your month", t.CAPTION,
                                                         t.TEXT_2),
             href=f"/summary/{m.hero_month}"),
    )


def _focus_row() -> rx.Component:
    return rows(list_row(YouState.focus_label, "Change what the chart shows",
                         leading=rx.icon("chart-line", size=20, color=t.TEXT_2, stroke_width=1.75),
                         chevron=True, on_click=YouState.open_focus, class_name="ma-focus-row"))


def _focus_sheet() -> rx.Component:
    s = YouState
    return sheet(
        s.show_focus, s.close_focus,
        rows(
            list_row("All training", "Duration, volume, workouts and points by week",
                     trailing=rx.cond(s.focus_id == "", rx.icon("check", size=20, color=t.ACCENT)),
                     on_click=s.pick_focus("", "")),
            rx.foreach(s.exercises, lambda e: list_row(
                e["name"], e["sub"], on_click=s.pick_focus(e["id"], e["name"]),
                trailing=rx.cond(s.focus_id == e["id"], rx.icon("check", size=20, color=t.ACCENT))),
            ),
        ),
        rx.cond(s.exercises_cursor != "", button("Show more", s.more_exercises, variant="ghost", full=True)),
        title="Show on the chart",
    )


def _chart() -> rx.Component:
    s = YouState
    return rx.vstack(
        rx.vstack(text(s.headline_label, t.CAPTION, t.TEXT_2), number(s.headline, s.headline_unit),
                  spacing="1", align="start", width="100%"),
        rx.cond(s.chart.length() > 1,
                rx.box(line_chart(s.chart), width="100%", class_name="ma-progress-chart"),
                empty_state("chart-line", "Log a few workouts to see the line.")),
        rx.cond(s.focus_id == "", segmented(METRICS, s.metric, s.set_metric),
                segmented(FOCUS_METRICS, s.focus_metric, s.set_focus_metric)),
        segmented(RANGES, s.range_, s.set_range),
        spacing="4", width="100%",
    )


def _pr(r) -> rx.Component:
    return list_row(r["exercise_name"], f"{r['record_label']} · {r['date_label']}", trailing=r["value_label"],
                    href=f"/exercise/{r['exercise_id']}")


def progress_page() -> rx.Component:
    s = YouState
    return shell(
        top_bar("Progress", large=True),
        error_banner(s.error),
        _month_card(),
        _focus_row(),
        rx.cond(s.loaded, _chart(), skeleton("320px")),
        section("Records",
                rx.cond(s.visible_prs.length() > 0, rows(rx.foreach(s.visible_prs, _pr)),
                        rx.cond(s.loaded, text("Records appear as you beat your best.", t.BODY, t.TEXT_2),
                                skeleton_rows(3)))),
        rows(
            list_row("History", "Every workout, week by week", chevron=True, href="/progress/history",
                     leading=rx.icon("history", size=20, color=t.TEXT_2, stroke_width=1.75)),
            list_row("Body measurements", "Weight, body fat, and the rest", chevron=True,
                     href="/progress/measurements",
                     leading=rx.icon("ruler", size=20, color=t.TEXT_2, stroke_width=1.75)),
            list_row("Muscles & recovery", "What you worked, and what is ready", chevron=True,
                     href="/progress/recovery",
                     leading=rx.icon("activity", size=20, color=t.TEXT_2, stroke_width=1.75)),
            list_row("Monthly summary", "Your month, as a story", chevron=True,
                     href=f"/summary/{MonthlyState.hero_month}",
                     leading=rx.icon("calendar", size=20, color=t.TEXT_2, stroke_width=1.75)),
        ),
        _focus_sheet(),
    )


# ---------------------------------------------------------------------------
# /progress/history
# ---------------------------------------------------------------------------


def session_row(row) -> rx.Component:
    """A finished workout in a list: title, when, how long, how much."""
    return list_row(row["title"], f"{row['date_label']} · {row['duration']} · {row['volume']}",
                    trailing=row["points"], chevron=True, href=f"/session/{row['id']}", class_name="ma-session-row")


def _history_row(row) -> rx.Component:
    return rx.fragment(
        rx.cond(row["first_of_week"] != "",
                text(row["week_label"], t.CAPTION, t.TEXT_2, padding_top=t.space(16), padding_bottom=t.space(4),
                     width="100%")),
        session_row(row),
    )


def history_page() -> rx.Component:
    s = YouState
    return shell(
        top_bar("History", back="/progress"),
        error_banner(s.error),
        rx.vstack(
            rx.hstack(
                icon_button("chevron-left", "Previous month", on_click=s.shift_month(-1)),
                rx.vstack(text(s.month_title, t.LABEL), text(s.month_count, t.CAPTION, t.TEXT_2),
                          spacing="0", align="center", flex="1"),
                icon_button("chevron-right", "Next month", on_click=s.shift_month(1)),
                width="100%", align="center",
            ),
            month_calendar("", s.month_weeks),
            spacing="2", width="100%",
        ),
        rx.cond(
            s.history.length() > 0,
            rx.vstack(rows(rx.foreach(s.history, _history_row)),
                      rx.cond(s.history_cursor != "", button("Show more", s.more_history, variant="ghost", full=True)),
                      spacing="3", width="100%"),
            rx.cond(s.loaded, empty_state("history", "Finished workouts are kept here."), skeleton_rows(5)),
        ),
    )


# ---------------------------------------------------------------------------
# /progress/measurements
# ---------------------------------------------------------------------------


def _measure_row(group) -> rx.Component:
    return list_row(group["title"], group["when"], trailing=group["latest"],
                    title_color=rx.cond(YouState.measure_selected == group["key"], t.TEXT, t.TEXT_2),
                    leading=rx.icon("chart-line", size=20, stroke_width=1.75,
                                    color=rx.cond(YouState.measure_selected == group["key"], t.TEXT, t.TEXT_3)),
                    on_click=YouState.pick_measure(group["key"]))


def _log_sheet() -> rx.Component:
    s = YouState
    return sheet(
        s.show_log, s.close_log,
        chips(*[chip(label, selected=s.measure_kind == kind, on_click=s.set_measure_kind(kind))
                for label, kind in (("Body weight", "weight"), ("Body fat", "body_fat"), ("Custom", "custom"))]),
        rx.cond(s.measure_kind == "custom", field(s.measure_label, s.set_measure_label, "Name, e.g. Waist (cm)")),
        field(s.measure_value, s.set_measure_value,
              rx.match(s.measure_kind, ("weight", f"Value ({AuthState.weight_unit})"), ("body_fat", "Value (%)"),
                       "Value (cm)"), mode="decimal"),
        error_banner(s.error),
        title="Log measurement",
        action=button("Save", s.add_measure, full=True),
    )


def measurements_page() -> rx.Component:
    s = YouState
    latest = s.measure_groups[0]
    return shell(
        top_bar("Body measurements", back="/progress"),
        rx.cond(
            s.measure_groups.length() > 0,
            rx.vstack(
                stat_group(stat_tile(latest["latest"], f"{latest['title']} · {latest['when']}")),
                rx.cond(s.measure_chart.length() > 1, line_chart(s.measure_chart, height=200, from_zero=False)),
                rows(rx.foreach(s.measure_groups, _measure_row)),
                spacing="5", width="100%",
            ),
            rx.cond(s.loaded, empty_state("ruler", "Log your body weight to see it over time."), skeleton_rows(3)),
        ),
        _log_sheet(),
        pinned=button("Log measurement", s.open_log, icon="plus", full=True),
    )


# ---------------------------------------------------------------------------
# /progress/recovery
# ---------------------------------------------------------------------------


def recovery_page() -> rx.Component:
    w = WorkoutHomeState
    return shell(
        top_bar("Muscles & recovery", back="/progress"),
        error_banner(w.error),
        section("This week",
                rx.cond(YouState.muscle_names != "",
                        rx.vstack(rx.center(body_map(YouState.muscle_paths, size="190px"), width="100%"),
                                  text(YouState.muscle_names, t.CAPTION, t.TEXT_2, text_align="center",
                                       width="100%"), spacing="2", width="100%"),
                        text("No workouts yet this week.", t.BODY, t.TEXT_2))),
        section(
            "Recovery",
            rx.cond(
                w.recovery_loaded,
                rx.vstack(
                    stat_group(stat_tile(f"{w.recovery_overall}%", "Recovered overall")),
                    rx.cond(w.recovery_note != "", text(w.recovery_note, t.BODY, t.TEXT_2)),
                    rx.cond(w.recovery_rows.length() > 0,
                            rows(rx.foreach(w.recovery_rows, lambda r: list_row(r["name"], trailing=r["percent"]))),
                            text("Everything is fully recovered.", t.BODY, t.TEXT_2)),
                    spacing="4", width="100%",
                ),
                skeleton_rows(4),
            ),
        ),
    )
