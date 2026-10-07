"""The exercise picker - a sheet. Search, muscle and equipment chips, what
you did lately first, tap to pick several; Add appears with the count.
Custom exercises from the same sheet. Serves the live workout and the
routine editor."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner
from metalarm.state.picker import PickerState
from metalarm.ui.primitives import button, chip, chips, field, list_row, rows, sheet, skeleton_rows, text, when


def _thumb(src) -> rx.Component:
    return rx.cond(src != "", rx.image(src=src, width="40px", height="40px", object_fit="cover",
                                       border_radius=t.RADIUS, background=t.SURFACE_2, loading="lazy"),
                   rx.center(rx.icon("dumbbell", size=20, color=t.TEXT_3), width="40px", height="40px",
                             border_radius=t.RADIUS, background=t.SURFACE_2))


def _row(item) -> rx.Component:
    on = PickerState.selected.contains(item["id"])
    return list_row(
        item["name"], item["sub"], leading=_thumb(item["image"]),
        trailing=rx.center(rx.cond(on, rx.icon("check", size=16, stroke_width=2.5, color=t.ON_ACCENT)),
                           width="24px", height="24px", border_radius=t.RADIUS_PILL,
                           background=when(on, t.ACCENT, "transparent"),
                           border=when(on, f"1px solid {t.ACCENT}", f"1px solid {t.TEXT_3}")),
        on_click=PickerState.toggle(item["id"]),
        custom_attrs={"role": "checkbox", "aria-checked": rx.cond(on, "true", "false"), "aria-label": item["name"]},
    )


def _create_form() -> rx.Component:
    def select(items, value, on_change):
        return rx.select(items, value=value, on_change=on_change, width="100%", size="3")
    return rx.vstack(
        text(PickerState.create_label, t.LABEL),
        rx.grid(select(PickerState.muscle_codes, PickerState.new_muscle, PickerState.set_new_muscle),
                select(PickerState.gear_codes, PickerState.new_equipment, PickerState.set_new_equipment),
                select(PickerState.categories, PickerState.new_category, PickerState.set_new_category),
                columns="3", gap=t.space(8), width="100%"),
        button("Create and add", PickerState.create_custom, variant="secondary", full=True),
        spacing="3", width="100%",
    )


def picker_dialog() -> rx.Component:
    return sheet(
        PickerState.is_open, PickerState.close,
        field(PickerState.query, PickerState.set_query, "Search exercises…", debounce=True),
        chips(rx.foreach(PickerState.muscles, lambda m: chip(m["label"], selected=PickerState.muscle == m["code"],
                                                             on_click=PickerState.pick_muscle(m["code"])))),
        chips(rx.foreach(PickerState.gears, lambda g: chip(g["label"], selected=PickerState.gear == g["code"],
                                                           on_click=PickerState.pick_gear(g["code"])))),
        error_banner(PickerState.error),
        rx.cond(PickerState.browsing & (PickerState.recent.length() > 0),
                rx.vstack(text("Recently used", t.CAPTION, t.TEXT_2), rows(rx.foreach(PickerState.recent, _row)),
                          text("All exercises", t.CAPTION, t.TEXT_2), spacing="1", width="100%")),
        rx.cond(PickerState.results.length() > 0,
                rows(rx.foreach(PickerState.results, _row)),
                rx.cond(PickerState.loading, skeleton_rows(4), text("No matches.", t.BODY, t.TEXT_2))),
        rx.cond(PickerState.cursor != "", button("Show more", PickerState.more, variant="ghost", full=True)),
        rx.cond(PickerState.show_create, _create_form(),
                button("Create a custom exercise", PickerState.toggle_create, variant="ghost", full=True)),
        title="Add exercises",
        action=rx.cond(PickerState.selected.length() > 0,
                       rx.box(button(PickerState.add_label, PickerState.add_selected, full=True),
                              position="sticky", bottom="0", padding_y=t.space(12), background=t.SURFACE,
                              width="100%")),
    )
