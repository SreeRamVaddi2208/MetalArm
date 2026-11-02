"""The Explore tab: search, then Programs (pages/library.py) and Exercises -
the muscle and equipment grids, and the figure cards they lead to."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.pages.library import programs_tab
from metalarm.state.explore import ExploreState
from metalarm.ui.library import program_card, workout_card
from metalarm.ui.primitives import rows, button, chip, chips, empty_state, field, section, skeleton_rows, text, when


def _tab(label: str) -> rx.Component:
    on = ExploreState.tab == label
    return rx.el.button(
        text(label, t.LABEL, when(on, t.TEXT, t.TEXT_2)), on_click=ExploreState.set_tab(label), flex="1",
        min_height=t.TOUCH, background="transparent", border="none",
        border_bottom=rx.cond(on, f"2px solid {t.TEXT}", "2px solid transparent"), cursor="pointer",
        custom_attrs={"aria-pressed": rx.cond(on, "true", "false"), "data-explore-tab": label.lower()},
    )


def _grid(*children: rx.Component, columns: int = 3) -> rx.Component:
    return rx.grid(*children, grid_template_columns=f"repeat({columns}, minmax(0, 1fr))", gap=t.space(12), width="100%")


def _muscle(m) -> rx.Component:
    return rx.el.button(
        rx.image(src=m["image"], width="100%", aspect_ratio="1", object_fit="contain", alt="", loading="lazy"),
        text(m["label"], t.LABEL, text_align="center"),
        on_click=ExploreState.pick_muscle(m["code"], m["label"]), background="transparent", border="none",
        padding="0", cursor="pointer", min_width="0", class_name="ma-press ma-muscle-tile",
    )


def _gear(e) -> rx.Component:
    return rx.el.button(
        rx.center(rx.image(src=e["image"], width="70%", aspect_ratio="1", object_fit="contain", alt="", loading="lazy"),
                  width="100%", aspect_ratio="1", border_radius=t.RADIUS_PILL, background=t.SURFACE),
        text(e["label"], t.LABEL, text_align="center", margin_top=t.space(8)),
        on_click=ExploreState.pick_gear(e["code"], e["label"]), background="transparent", border="none",
        padding="0", cursor="pointer", min_width="0", class_name="ma-press ma-gear-tile",
    )


def _exercise_card(row) -> rx.Component:
    return rx.box(
        rx.link(
            rx.image(src=row["image"], width="100%", aspect_ratio="1", object_fit="contain", alt=row["name"],
                     loading="lazy", background=t.SURFACE),
            rx.vstack(text(row["name"], t.LABEL, class_name="ma-clamp-2"), text(row["muscle"], t.CAPTION, t.TEXT_2),
                      spacing="1", align="start", padding=t.space(12), width="100%"),
            href=f"/exercise/{row['id']}", underline="none", display="block",
        ),
        rx.el.button(
            rx.icon("bookmark", size=20, stroke_width=1.75, color=when(row["favorite"] != "", t.ACCENT, t.TEXT_2),
                    fill=rx.cond(row["favorite"] != "", t.ACCENT, "none")),
            on_click=ExploreState.toggle_favorite(row["id"]), position="absolute", top="0", left="0",
            width=t.ICON_HIT, height=t.ICON_HIT, display="flex", align_items="center", justify_content="center",
            background="transparent", border="none", cursor="pointer",
            custom_attrs={"aria-label": "Bookmark", "aria-pressed": rx.cond(row["favorite"] != "", "true", "false")},
        ),
        position="relative", background=t.SURFACE_2, border_radius=t.RADIUS, overflow="hidden", min_width="0",
        class_name="ma-exercise-card",
    )


def _listing() -> rx.Component:
    s = ExploreState
    title = rx.cond(s.muscle_label != "", s.muscle_label, rx.cond(s.gear_label != "", s.gear_label, "Results"))
    return rx.vstack(
        rx.hstack(text(title, t.TITLE), rx.spacer(), button("Clear", s.clear_filters, variant="ghost"),
                  width="100%", align="center"),
        chips(rx.foreach(s.muscles, lambda m: chip(m["label"], selected=s.muscle == m["code"],
                                                   on_click=s.pick_muscle(m["code"], m["label"])))),
        chips(rx.foreach(s.equipment, lambda e: chip(e["label"], selected=s.gear == e["code"],
                                                     on_click=s.pick_gear(e["code"], e["label"])))),
        text(s.total_label, t.CAPTION, t.TEXT_2),
        rx.cond(s.results.length() > 0, _grid(rx.foreach(s.results, _exercise_card), columns=2),
                rx.cond(s.busy, skeleton_rows(6), empty_state("search", "No exercises match. Try fewer filters."))),
        rx.cond(s.cursor != "", button("Show more", s.more, variant="ghost", full=True)),
        spacing="3", width="100%",
    )


def _exercises_tab() -> rx.Component:
    s = ExploreState
    return rx.cond(
        s.listing,
        _listing(),
        rx.vstack(
            rx.cond(s.recents.length() > 0,
                    rx.hstack(text("Recent", t.CAPTION, t.TEXT_2),
                              chips(rx.foreach(s.recents, lambda q: chip(q, on_click=s.use_recent(q)))),
                              spacing="2", align="center", width="100%", class_name="ma-recents")),
            section("Muscle Groups", _grid(rx.foreach(s.muscles, _muscle))),
            section("Equipment", _grid(rx.foreach(s.equipment, _gear))),
            spacing="6", width="100%",
        ),
    )


def _program_hits() -> rx.Component:
    s = ExploreState
    return rx.cond(
        (s.program_hits.length() > 0) | (s.workout_hits.length() > 0),
        rx.vstack(
            rx.cond(s.program_hits.length() > 0, section("Programs", rx.vstack(rx.foreach(s.program_hits, lambda p: program_card(p)),
                                                                              spacing="3", width="100%"))),
            rx.cond(s.workout_hits.length() > 0, section("Workouts", rows(rx.foreach(s.workout_hits, workout_card)))),
            spacing="6", width="100%", class_name="ma-program-hits",
        ),
        empty_state("search", "No programs or workouts match."),
    )


def explore_page() -> rx.Component:
    s = ExploreState
    return shell(
        field(s.query, s.set_query, rx.cond(s.tab == "Programs", "Search for programs", "Search for exercises"), debounce=True, on_blur=s.blur_search),
        rx.hstack(_tab("Programs"), _tab("Exercises"), spacing="0", width="100%", border_bottom=t.HAIRLINE),
        error_banner(s.error),
        rx.cond(s.tab == "Programs", rx.cond(s.query != "", _program_hits(), programs_tab()), _exercises_tab()),
    )
