"""Explore (overhaul 7.2): search; Exercises - muscle and equipment grids that
open a filtered list (combine a muscle with equipment); Programs - curated
plans by training path, saved into the Library in one tap; People - with
following, in phase 4."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.explore import ExploreState
from metalarm.ui.body_map import body_map
from metalarm.ui.cards import equipment_circle, muscle_tile
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import (
    empty_state,
    filter_chip,
    list_row,
    primary_button,
    secondary_button,
    section_header,
    sheet,
    skeleton,
    sub_tabs,
    text,
    thumb,
)


def _search() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("search", size=18, color=t.TEXT_SECONDARY),
            rx.input(
                value=ExploreState.query,
                on_change=ExploreState.set_query,
                on_focus=ExploreState.focus_search,
                on_blur=ExploreState.blur_search,
                debounce_timeout=250,
                placeholder="Search exercises and programs",
                variant="soft",
                background="transparent",
                color=t.TEXT_PRIMARY,
                border="none",
                outline="none",
                box_shadow="none",
                width="100%",
                min_width="0",
                **t.BODY,
            ),
            rx.cond(ExploreState.query != "",
                    rx.box(rx.icon("x", size=18, color=t.TEXT_SECONDARY), cursor="pointer",
                           on_click=ExploreState.clear_query,
                           custom_attrs={"role": "button", "aria-label": "Clear search"})),
            background=t.SURFACE_1, border_radius=t.RADIUS_PILL, padding=f"{t.space(1.5)} {t.space(4)}",
            width="100%", spacing="2", align="center", min_height=t.TOUCH_MIN,
        ),
        # Recent searches, while the box is focused and empty.
        rx.cond(
            ExploreState.searching & (ExploreState.query == "") & (ExploreState.recents.length() > 0),
            rx.vstack(
                text("Recent", t.FOOTNOTE, t.TEXT_SECONDARY),
                rx.foreach(ExploreState.recents,
                           lambda term: rx.hstack(rx.icon("history", size=16, color=t.TEXT_TERTIARY),
                                                  text(term, t.BODY), spacing="2", align="center",
                                                  min_height="36px", width="100%", cursor="pointer",
                                                  # Before the input's blur clears the list.
                                                  on_mouse_down=ExploreState.use_recent(term))),
                spacing="1", width="100%", padding=f"0 {t.space(2)}",
            ),
        ),
        spacing="2", width="100%",
    )


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


def _muscle(m) -> rx.Component:
    views = rx.cond(m["side"] == "back", body_map(m["paths"], views=("back",), size="96px"),
                    body_map(m["paths"], views=("front",), size="96px"))
    return muscle_tile(m["label"], views, on_click=ExploreState.pick_muscle(m["code"], m["label"]))


def _grids() -> rx.Component:
    return rx.vstack(
        section_header("Muscle Groups", "Find exercises by the muscle they train."),
        rx.cond(
            ExploreState.loaded,
            rx.grid(rx.foreach(ExploreState.muscles, _muscle), columns="3", gap=t.space(3), width="100%"),
            rx.grid(*[skeleton("120px") for _ in range(6)], columns="3", gap=t.space(3), width="100%"),
        ),
        section_header("Equipment", "Or by what you have to hand."),
        rx.grid(rx.foreach(ExploreState.equipment,
                           lambda e: equipment_circle(e["code"], e["label"],
                                                      on_click=ExploreState.pick_gear(e["code"], e["label"]))),
                columns="4", gap=t.space(3), width="100%"),
        spacing="4", width="100%",
    )


def _chip_row(items, selected, on_pick) -> rx.Component:
    return rx.hstack(
        rx.foreach(items, lambda x: filter_chip(x["label"], selected=selected == x["code"],
                                                on_click=on_pick(x["code"], x["label"]))),
        spacing="2", overflow_x="auto", width="100%", padding_bottom=t.space(1),
        style={"scrollbar_width": "none"},
    )


def _result(row) -> rx.Component:
    return rx.link(list_row(row["name"], row["sub"], image=row["image"], icon="dumbbell"),
                   href=f"/exercise/{row['id']}", underline="none", width="100%")


def _listing() -> rx.Component:
    return rx.vstack(
        _chip_row(ExploreState.muscles, ExploreState.muscle, ExploreState.pick_muscle),
        _chip_row(ExploreState.equipment, ExploreState.gear, ExploreState.pick_gear),
        rx.hstack(text(ExploreState.total_label, t.SUBHEAD, t.TEXT_SECONDARY), rx.spacer(),
                  text("Clear", t.SUBHEAD, t.ACCENT_BLUE, cursor="pointer", on_click=ExploreState.clear_filters),
                  width="100%"),
        rx.cond(
            ExploreState.results.length() > 0,
            rx.vstack(rx.foreach(ExploreState.results, _result), spacing="3", width="100%"),
            rx.cond(ExploreState.busy, rx.vstack(*[skeleton("64px") for _ in range(4)], width="100%"),
                    empty_state("No exercises match", "Try fewer filters, or another name.")),
        ),
        rx.cond(ExploreState.cursor != "", secondary_button("Show more", ExploreState.more, width="100%")),
        spacing="3", width="100%",
    )


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


def _program_card(p) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(text(p["category"], t.FOOTNOTE, t.ACCENT_BLUE), background=t.alpha(t.ACCENT_BLUE, 0.14),
                   border_radius=t.RADIUS_PILL, padding=f"{t.space(0.5)} {t.space(2.5)}"),
            rx.spacer(),
            rx.cond(p["saved"] != "", rx.hstack(rx.icon("check", size=14, color=t.RECOVERY_GREEN),
                                                text("In your Library", t.FOOTNOTE, t.RECOVERY_GREEN),
                                                spacing="1", align="center")),
            width="100%", align="center",
        ),
        text(p["name"], t.TITLE_2),
        text(p["meta"], t.SUBHEAD, t.TEXT_SECONDARY),
        text(p["description"], t.SUBHEAD),
        text(f"{p['routines']} routines", t.FOOTNOTE, t.TEXT_SECONDARY),
        spacing="2", width="100%", align="start",
        background=t.SURFACE_1, border_radius=t.RADIUS_CARD, padding=t.CARD_PADDING,
        cursor="pointer", on_click=ExploreState.open_program(p["slug"]),
        class_name="ma-program-card",
    )


def _program_row(row) -> rx.Component:
    return rx.cond(
        row["kind"] == "head",
        rx.vstack(text(row["title"], t.HEADLINE), text(row["sub"], t.FOOTNOTE, t.TEXT_SECONDARY),
                  spacing="0", align="start", width="100%", padding_top=t.space(2)),
        rx.link(rx.hstack(thumb(row["image"], size="44px", icon="dumbbell"),
                          rx.vstack(text(row["title"], t.BODY), text(row["sub"], t.FOOTNOTE, t.TEXT_SECONDARY),
                                    spacing="0", align="start", min_width="0"),
                          spacing="3", align="center", width="100%"),
                href=f"/exercise/{row['id']}", underline="none", width="100%"),
    )


def program_sheet() -> rx.Component:
    p = ExploreState.program
    return sheet(
        ExploreState.program_slug != "", p["name"], ExploreState.close_program,
        text(p["meta"], t.SUBHEAD, t.TEXT_SECONDARY),
        text(p["description"], t.BODY),
        rx.cond(
            (p["saved"] != "") | (ExploreState.saved_note != ""),
            rx.link(secondary_button("In your Library - open it", icon="check", width="100%",
                                     color=t.RECOVERY_GREEN),
                    href="/library", underline="none", width="100%"),
            primary_button("Save to Library", ExploreState.save_program, icon="bookmark-plus", width="100%"),
        ),
        rx.vstack(rx.foreach(ExploreState.program_rows, _program_row), spacing="2", width="100%"),
    )


def _programs() -> rx.Component:
    return rx.cond(
        ExploreState.visible_programs.length() > 0,
        rx.vstack(
            text("Plans built from the library. The first are for your training path.", t.SUBHEAD,
                 t.TEXT_SECONDARY),
            rx.foreach(ExploreState.visible_programs, _program_card),
            spacing="3", width="100%",
        ),
        empty_state("No programs match", "Try another name."),
    )


def explore_page() -> rx.Component:
    return shell(
        top_bar("Explore"),
        _search(),
        sub_tabs([("Programs", "layers"), ("Exercises", "dumbbell"), ("People", "users")],
                 ExploreState.tab, ExploreState.set_tab),
        error_banner(ExploreState.error),
        rx.match(
            ExploreState.tab,
            ("Programs", _programs()),
            ("People", empty_state("People", "Finding and following friends arrives with the feed.")),
            rx.cond(ExploreState.listing, _listing(), _grids()),
        ),
        program_sheet(),
    )
