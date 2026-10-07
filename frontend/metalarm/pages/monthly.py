"""The Monthly Summary story (overhaul 7.9): full screen, progress bars on
top, tap the right of the screen to go on and the left to go back."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.monthly import MonthlyState
from metalarm.ui.body_map import body_map
from metalarm.ui.primitives import primary_button, secondary_button, skeleton, text


def _bar(state) -> rx.Component:
    return rx.box(
        rx.box(height="100%", border_radius=t.RADIUS_PILL, background=t.TEXT_PRIMARY,
               width=rx.match(state, ("done", "100%"), ("now", "100%"), "0%"),
               opacity=rx.cond(state == "now", "1", "0.9")),
        flex="1", height="3px", border_radius=t.RADIUS_PILL, background=t.alpha(t.TEXT_PRIMARY, 0.3),
        overflow="hidden",
    )


def _big(value, unit="") -> rx.Component:
    return rx.hstack(text(value, t.DISPLAY_HERO, font_family=t.FONT_GAME),
                     text(unit, t.TITLE_2, t.TEXT_SECONDARY), spacing="2", align="baseline")


def _slide(eyebrow: str, *children: rx.Component) -> rx.Component:
    return rx.vstack(text(eyebrow, t.CAPTION, t.TEXT_SECONDARY), *children, spacing="4", align="start",
                     width="100%", class_name="ma-slide")


def _record(r) -> rx.Component:
    return rx.hstack(rx.icon("medal", size=18, color=t.PR_GOLD),
                     rx.vstack(text(r["name"], t.BODY), text(r["kind"], t.FOOTNOTE, t.TEXT_SECONDARY),
                               spacing="0", align="start", flex="1", min_width="0"),
                     text(r["value"], t.HEADLINE, **t.TABULAR), width="100%", align="center", spacing="3")


def _slides() -> rx.Component:
    s = MonthlyState
    return rx.match(
        s.slide,
        (0, _slide(s.title, text("You trained", t.TITLE_2), _big(s.workouts, "workouts"),
                   text(f"{s.time_label} under the bar, across {s.active_days} days.", t.BODY, t.TEXT_SECONDARY),
                   text(f"Your best week: {s.best_week} workouts.", t.BODY, t.TEXT_SECONDARY))),
        (1, _slide("Volume", _big(s.volume_label), text(s.comparison, t.TITLE_2),
                   text(f"{s.sets} working sets.", t.BODY, t.TEXT_SECONDARY))),
        (2, _slide("Most trained",
                   rx.cond(s.top_muscle != "",
                           rx.vstack(text(s.top_muscle, t.LARGE_TITLE), body_map(s.muscle_paths, size="220px"),
                                     text(s.muscle_list, t.FOOTNOTE, t.TEXT_SECONDARY), spacing="3", width="100%"),
                           text("No lifting this month.", t.TITLE_2)))),
        (3, _slide("Records", _big(s.record_count, "records"),
                   rx.vstack(rx.foreach(s.records, _record), spacing="3", width="100%"))),
        (4, _slide("Points and rank", _big(s.points, "points"), text(s.rank_line, t.TITLE_2),
                   rx.foreach(s.rank_ups, lambda line: rx.hstack(rx.icon("crown", size=18, color=t.PR_GOLD),
                                                                 text(line, t.BODY), spacing="2", align="center")))),
        (5, _slide("Quests and duels", _big(s.quests, "quests done"),
                   text(f"{s.duels_won} of {s.duels_played} duels won", t.TITLE_2))),
        _slide("Your month",
               rx.vstack(
                   text(s.title, t.TITLE_1),
                   rx.grid(*[rx.vstack(text(v, t.TITLE_2, **t.TABULAR), text(label, t.FOOTNOTE, t.TEXT_SECONDARY),
                                       spacing="0", align="start")
                             for v, label in ((s.workouts, "Workouts"), (s.volume_label, "Volume"),
                                              (s.record_count, "Records"), (s.points, "Points"))],
                           columns="2", gap=t.space(4), width="100%"),
                   text(s.comparison, t.SUBHEAD, t.TEXT_SECONDARY),
                   spacing="3", width="100%", background=t.SUMMARY_GRADIENT, border_radius=t.RADIUS_CARD,
                   padding=t.space(5)),
               # Above the tap zones.
               rx.hstack(secondary_button("Share", s.share, icon="share", flex="1"),
                         rx.link(primary_button("Done", width="100%"), href="/home", underline="none", flex="1"),
                         width="100%", spacing="2", position="relative", z_index="3")),
    )


def monthly_page() -> rx.Component:
    s = MonthlyState
    return shell(
        rx.box(
            rx.vstack(
                rx.hstack(rx.foreach(s.bars, _bar), spacing="1", width="100%"),
                rx.hstack(rx.spacer(),
                          rx.link(rx.icon("x", size=24, color=t.TEXT_PRIMARY), href="/home",
                                  custom_attrs={"aria-label": "Close"}),
                          width="100%", position="relative", z_index="3"),
                error_banner(s.error),
                rx.cond(s.loaded, rx.box(_slides(), width="100%", padding_top=t.space(6)),
                        rx.vstack(skeleton("80px"), skeleton("200px"), width="100%")),
                spacing="3", width="100%", max_width="560px", margin="0 auto",
                padding=f"calc({t.space(3)} + env(safe-area-inset-top)) {t.GUTTER} {t.space(6)}",
                position="relative", z_index="2", pointer_events="none",
                style={"& a, & button, & [role=button]": {"pointer_events": "auto"}},
            ),
            # Tap zones: left third back, the rest forward.
            rx.box(position="absolute", top="0", bottom="0", left="0", width="33%", z_index="1",
                   on_click=s.prev_slide, custom_attrs={"aria-label": "Previous", "role": "button"}),
            rx.box(position="absolute", top="0", bottom="0", right="0", width="67%", z_index="1",
                   on_click=s.next_slide, custom_attrs={"aria-label": "Next", "role": "button"},
                   class_name="ma-next"),
            position="fixed", inset="0", z_index="85", background=t.COLOR_BG, overflow_y="auto",
        ),
    )
