"""The exercise picker (overhaul 7.5.6): Explore's library in multi-select -
search, muscle and equipment chips, tap to pick several, add them in the
order picked. Custom exercises from the same sheet. Serves the live workout
and the routine editor."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner
from metalarm.state.picker import PickerState
from metalarm.ui.primitives import filter_chip, primary_button, secondary_button, text, thumb


def _row(item) -> rx.Component:
    on = PickerState.selected.contains(item["id"])
    return rx.hstack(
        thumb(item["image"], size="48px", icon="dumbbell"),
        rx.vstack(text(item["name"], t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
                       white_space="nowrap", max_width="100%"),
                  text(item["sub"], t.FOOTNOTE, t.TEXT_SECONDARY),
                  spacing="0", align="start", min_width="0", flex="1"),
        rx.center(rx.cond(on, rx.icon("check", size=18, color=t.TEXT_PRIMARY)),
                  width="28px", height="28px", border_radius=t.RADIUS_PILL, flex_shrink="0",
                  background=rx.cond(on, t.ACCENT_BLUE, "transparent"),
                  border=rx.cond(on, f"2px solid {t.ACCENT_BLUE}", f"2px solid {t.SURFACE_3}")),
        width="100%", align="center", spacing="3", min_height="56px", cursor="pointer",
        on_click=PickerState.toggle(item["id"]),
        custom_attrs={"role": "checkbox", "aria-checked": rx.cond(on, "true", "false"), "aria-label": item["name"]},
    )


def _chips(items, selected, on_pick) -> rx.Component:
    return rx.hstack(
        rx.foreach(items, lambda x: filter_chip(x["label"], selected=selected == x["code"],
                                                on_click=on_pick(x["code"]))),
        spacing="2", overflow_x="auto", width="100%", flex_shrink="0", style={"scrollbar_width": "none"},
    )


def _select(items, value, on_change) -> rx.Component:
    return rx.select(items, value=value, on_change=on_change, width="100%", size="2")


def _create_form() -> rx.Component:
    return rx.vstack(
        text(PickerState.create_label, t.HEADLINE),
        rx.grid(
            rx.vstack(text("Muscle", t.CAPTION, t.TEXT_SECONDARY),
                      _select(PickerState.muscle_codes, PickerState.new_muscle, PickerState.set_new_muscle),
                      spacing="1"),
            rx.vstack(text("Equipment", t.CAPTION, t.TEXT_SECONDARY),
                      _select(PickerState.gear_codes, PickerState.new_equipment, PickerState.set_new_equipment),
                      spacing="1"),
            rx.vstack(text("Type", t.CAPTION, t.TEXT_SECONDARY),
                      _select(PickerState.categories, PickerState.new_category, PickerState.set_new_category),
                      spacing="1"),
            columns="3", gap=t.space(2), width="100%",
        ),
        primary_button("Create and add", PickerState.create_custom, width="100%"),
        spacing="3", width="100%", background=t.SURFACE_2, border_radius=t.RADIUS_CARD, padding=t.CARD_PADDING,
    )


def picker_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.dialog.title("Add exercises", margin="0", **t.HEADLINE),
                    rx.spacer(),
                    rx.dialog.close(text("Cancel", t.BODY, t.ACCENT_BLUE, cursor="pointer")),
                    width="100%", align="center", min_height=t.TOUCH_MIN,
                ),
                rx.input(
                    placeholder="Search exercises…",
                    value=PickerState.query,
                    on_change=PickerState.set_query,
                    debounce_timeout=250,
                    width="100%",
                    size="3",
                    variant="soft",
                    radius="full",
                ),
                _chips(PickerState.muscles, PickerState.muscle, PickerState.pick_muscle),
                _chips(PickerState.gears, PickerState.gear, PickerState.pick_gear),
                error_banner(PickerState.error),
                rx.box(
                    rx.cond(
                        PickerState.results.length() > 0,
                        rx.vstack(
                            rx.foreach(PickerState.results, _row),
                            rx.cond(PickerState.cursor != "",
                                    secondary_button("Show more", PickerState.more, width="100%")),
                            spacing="1", width="100%",
                        ),
                        rx.cond(PickerState.loading,
                                rx.center(rx.spinner(), width="100%", padding=t.space(4)),
                                text("No matches.", t.SUBHEAD, t.TEXT_SECONDARY)),
                    ),
                    flex="1", overflow_y="auto", width="100%", min_height="0",
                ),
                rx.cond(
                    PickerState.show_create,
                    _create_form(),
                    text("Can't find it? Create a custom exercise", t.SUBHEAD, t.ACCENT_BLUE, cursor="pointer",
                         on_click=PickerState.toggle_create),
                ),
                primary_button(PickerState.add_label, PickerState.add_selected,
                               disabled=PickerState.selected.length() == 0, width="100%"),
                spacing="3", width="100%", height="100%",
            ),
            background=t.SURFACE_1,
            border_radius=t.RADIUS_CARD,
            max_width="560px",
            width="94vw",
            height="86vh",
            padding=t.CARD_PADDING,
        ),
        open=PickerState.is_open,
        on_open_change=PickerState.set_open,
    )
