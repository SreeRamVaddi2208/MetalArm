"""Explore: browse by muscle group and by equipment. (Phase 0 cut - the grids;
search, filtered lists and programs come in phase 3.)"""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.explore import ExploreState
from metalarm.ui.body_map import body_map
from metalarm.ui.cards import equipment_circle, muscle_tile
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import section_header, skeleton, sub_tabs, text


def _search() -> rx.Component:
    return rx.hstack(
        rx.icon("search", size=18, color=t.TEXT_SECONDARY),
        text("Search for exercises", t.BODY, t.TEXT_SECONDARY),
        background=t.SURFACE_1, border_radius=t.RADIUS_PILL, padding=f"{t.space(3)} {t.space(4)}",
        width="100%", spacing="2", align="center",
    )


def _muscle(m) -> rx.Component:
    views = rx.cond(m["side"] == "back", body_map(m["paths"], views=("back",), size="96px"),
                    body_map(m["paths"], views=("front",), size="96px"))
    return muscle_tile(m["label"], views)


def explore_page() -> rx.Component:
    return shell(
        top_bar("Explore"),
        _search(),
        sub_tabs([("Programs", "layers"), ("Exercises", "dumbbell"), ("People", "users")],
                 ExploreState.tab, ExploreState.set_tab),
        error_banner(ExploreState.error),
        section_header("Muscle Groups", "Find exercises by the muscle they train."),
        rx.cond(
            ExploreState.loaded,
            rx.grid(rx.foreach(ExploreState.muscles, _muscle), columns="3", gap=t.space(3), width="100%"),
            rx.grid(*[skeleton("120px") for _ in range(6)], columns="3", gap=t.space(3), width="100%"),
        ),
        section_header("Equipment", "Or by what you have to hand."),
        rx.grid(rx.foreach(ExploreState.equipment,
                           lambda e: equipment_circle(e["code"], e["label"])),
                columns="4", gap=t.space(3), width="100%"),
    )
