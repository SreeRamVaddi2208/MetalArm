"""The Monthly Summary story: full screen, progress bars on top; tap the
right of the screen to go on and the left to go back. Calm slides - one big
number each - and the share card unchanged."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.monthly import MonthlyState
from metalarm.ui.body_map import body_map
from metalarm.ui.primitives import button, link_button, list_row, number, rows, skeleton, stat_group, stat_tile, text


def _bar(state) -> rx.Component:
    return rx.box(
        rx.box(height="100%", border_radius=t.RADIUS_PILL, background=t.TEXT,
               width=rx.match(state, ("done", "100%"), ("now", "100%"), "0%")),
        flex="1", height="4px", border_radius=t.RADIUS_PILL, background=t.BORDER, overflow="hidden",
    )


def _slide(eyebrow, *children: rx.Component) -> rx.Component:
    return rx.vstack(text(eyebrow, t.CAPTION, t.TEXT_2), *children, spacing="4", align="start", width="100%",
                     class_name="ma-slide")


def _slides() -> rx.Component:
    s = MonthlyState
    return rx.match(
        s.slide,
        (0, _slide(s.title, text("You trained", t.TITLE), number(s.workouts, "workouts"),
                   text(f"{s.time_label} under the bar, across {s.active_days} days. Your best week: "
                        f"{s.best_week} workouts.", t.BODY, t.TEXT_2))),
        (1, _slide("Volume", number(s.volume_label), text(s.comparison, t.TITLE),
                   text(f"{s.sets} working sets.", t.BODY, t.TEXT_2))),
        (2, _slide("Most trained",
                   rx.cond(s.top_muscle != "",
                           rx.vstack(text(s.top_muscle, t.TITLE_LG),
                                     rx.center(body_map(s.muscle_paths, size="200px"), width="100%"),
                                     text(s.muscle_list, t.CAPTION, t.TEXT_2), spacing="3", width="100%"),
                           text("No lifting this month.", t.TITLE)))),
        (3, _slide("Records", number(s.record_count, "records"),
                   rows(rx.foreach(s.records, lambda r: list_row(r["name"], r["kind"], trailing=r["value"]))))),
        (4, _slide("Points and rank", number(s.points, "points"), text(s.rank_line, t.TITLE),
                   rx.foreach(s.rank_ups, lambda line: text(line, t.BODY, t.TEXT_2)))),
        (5, _slide("Quests and duels", number(s.quests, "quests done"),
                   text(f"{s.duels_won} of {s.duels_played} duels won", t.TITLE))),
        _slide("Your month",
               text(s.title, t.TITLE_LG),
               stat_group(stat_tile(s.workouts, "Workouts"), stat_tile(s.record_count, "Records"),
                          stat_tile(s.points, "Points")),
               text(s.comparison, t.BODY, t.TEXT_2),
               # Above the tap zones.
               rx.vstack(link_button("Done", "/progress", variant="primary", full=True),
                         button("Share", s.share, variant="ghost", icon="share", full=True),
                         spacing="2", width="100%", position="relative", z_index="3")),
    )


def monthly_page() -> rx.Component:
    s = MonthlyState
    return shell(
        rx.box(
            rx.vstack(
                rx.hstack(rx.foreach(s.bars, _bar), spacing="1", width="100%"),
                rx.hstack(rx.spacer(),
                          rx.link(rx.icon("x", size=24, color=t.TEXT, stroke_width=1.75), href="/progress",
                                  custom_attrs={"aria-label": "Close"}),
                          width="100%", position="relative", z_index="3"),
                error_banner(s.error),
                rx.cond(s.loaded, rx.box(_slides(), width="100%", padding_top=t.space(24)),
                        rx.vstack(skeleton("80px"), skeleton("200px"), width="100%")),
                spacing="3", width="100%", max_width=t.MAX_WIDTH, margin="0 auto",
                padding=f"calc({t.space(12)} + env(safe-area-inset-top)) {t.GUTTER} {t.space(24)}",
                position="relative", z_index="2", pointer_events="none",
                style={"& a, & button, & [role=button]": {"pointer_events": "auto"}},
            ),
            # Tap zones: left third back, the rest forward.
            rx.box(position="absolute", top="0", bottom="0", left="0", width="33%", z_index="1",
                   on_click=s.prev_slide, custom_attrs={"aria-label": "Previous", "role": "button"}),
            rx.box(position="absolute", top="0", bottom="0", right="0", width="67%", z_index="1",
                   on_click=s.next_slide, custom_attrs={"aria-label": "Next", "role": "button"},
                   class_name="ma-next"),
            position="fixed", inset="0", z_index="85", background=t.BG, overflow_y="auto",
        ),
    )
