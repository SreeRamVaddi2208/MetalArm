"""Small building blocks: numbers with units, delta pills, stat tiles,
section headers, chips, segmented controls, sub-tabs, list rows, empty states
and skeletons."""

from __future__ import annotations

from typing import Any

import reflex as rx
from reflex.vars import Var

from metalarm import theme as t


def when(condition: Any, yes: Any, no: Any) -> Any:
    """`yes if condition else no`, for a Python bool or a Reflex Var."""
    if isinstance(condition, Var):
        return rx.cond(condition, yes, no)
    return yes if condition else no


def text(value: Any, style: dict, color: str = t.TEXT_PRIMARY, **props) -> rx.Component:
    return rx.text(value, color=color, margin="0", **{**style, **props})


def number(value: Any, unit: Any = "", *, style: dict = t.DISPLAY_NUMBER,
           color: str = t.TEXT_PRIMARY) -> rx.Component:
    """A number and its unit: the unit about half size, same weight, on the
    baseline ("93%", "1h 35m", "14,715 kg")."""
    size = int(style["font_size"].rstrip("px"))
    return rx.el.span(
        rx.el.span(value),
        rx.cond(
            unit != "" if isinstance(unit, Var) else bool(unit),
            rx.el.span(unit, font_size=f"{round(size * t.UNIT_SCALE)}px", margin_left="2px"),
        ),
        color=color,
        white_space="nowrap",
        **{**{k: v for k, v in style.items() if k != "letter_spacing"}, **t.TABULAR},
    )


def delta_pill(value: Any, direction: Any = "down") -> rx.Component:
    """▲ in recovery green when up; ▼ in neutral grey when down - a lighter
    week is not a failure."""
    up = direction == "up"
    return rx.el.span(
        when(up, "▲ ", "▼ "),
        value,
        background=t.SURFACE_2,
        color=when(up, t.RECOVERY_GREEN, t.TEXT_SECONDARY),
        border_radius=t.RADIUS_PILL,
        padding=f"{t.space(1)} {t.space(2)}",
        white_space="nowrap",
        **{**t.FOOTNOTE, **t.TABULAR},
    )


def stat_tile(label: Any, value: Any, unit: Any = "", *, delta: Any = None,
              direction: Any = "down", align: str = "center") -> rx.Component:
    return rx.vstack(
        text(label, t.SUBHEAD, t.TEXT_SECONDARY),
        number(value, unit, style=t.TITLE_2),
        delta_pill(delta, direction) if delta is not None else rx.fragment(),
        spacing="1",
        align=align,
        min_width="0",
        flex="1",
    )


def section_header(title: Any, subtitle: Any = "", *, action: Any = "",
                   on_action: Any = None, href: str = "") -> rx.Component:
    link = rx.fragment()
    if action:
        link = text(action, t.SUBHEAD, t.ACCENT_BLUE, cursor="pointer",
                    on_click=on_action) if not href else rx.link(
            text(action, t.SUBHEAD, t.ACCENT_BLUE), href=href, underline="none")
    return rx.vstack(
        rx.hstack(text(title, t.TITLE_2), rx.spacer(), link, width="100%", align="baseline"),
        rx.cond(subtitle != "", text(subtitle, t.SUBHEAD, t.TEXT_SECONDARY))
        if isinstance(subtitle, Var) else (text(subtitle, t.SUBHEAD, t.TEXT_SECONDARY) if subtitle else rx.fragment()),
        spacing="1",
        width="100%",
        align="start",
    )


def filter_chip(label: Any, *, selected: Any = False, on_click: Any = None,
                disabled: Any = False) -> rx.Component:
    return rx.el.button(
        label,
        on_click=on_click,
        disabled=disabled,
        background=t.SURFACE_2,
        color=when(selected, t.ACCENT_BLUE, t.TEXT_PRIMARY),
        border=when(selected, f"1.5px solid {t.ACCENT_BLUE}", "1.5px solid transparent"),
        border_radius=t.RADIUS_PILL,
        padding=f"{t.space(2)} {t.space(4)}",
        min_height="36px",
        opacity=when(disabled, "0.4", "1"),
        cursor=when(disabled, "not-allowed", "pointer"),
        white_space="nowrap",
        **t.FOOTNOTE,
    )


def segmented_control(options: list[str], selected: Any, on_select=None) -> rx.Component:
    """3M / 6M / Year / All."""
    return rx.hstack(
        *[
            rx.el.button(
                option,
                on_click=on_select(option) if on_select else None,
                flex="1",
                background=when(selected == option, t.SURFACE_3, "transparent"),
                color=t.TEXT_PRIMARY,
                border="none",
                border_radius=t.RADIUS_PILL,
                min_height="32px",
                cursor="pointer",
                **t.FOOTNOTE,
            )
            for option in options
        ],
        background=t.SURFACE_2,
        border_radius=t.RADIUS_PILL,
        padding="2px",
        spacing="0",
        width="100%",
    )


def sub_tabs(tabs: list[tuple[str, str]], selected: Any, on_select=None) -> rx.Component:
    """Text tabs with an underline; (label, icon) - icons are optional and can
    be hidden by the screen on scroll."""
    return rx.hstack(
        *[
            rx.vstack(
                rx.hstack(
                    rx.icon(icon, size=16) if icon else rx.fragment(),
                    text(label, t.HEADLINE, when(selected == label, t.TEXT_PRIMARY, t.TEXT_SECONDARY)),
                    spacing="1",
                    align="center",
                ),
                rx.box(height="2px", width="100%", border_radius=t.RADIUS_PILL,
                       background=when(selected == label, t.TEXT_PRIMARY, "transparent")),
                spacing="2",
                cursor="pointer",
                on_click=on_select(label) if on_select else None,
                color=when(selected == label, t.TEXT_PRIMARY, t.TEXT_SECONDARY),
                align="center",
            )
            for label, icon in tabs
        ],
        spacing="5",
        width="100%",
        border_bottom=t.HAIRLINE,
        flex_wrap="nowrap",
        overflow_x="auto",
        white_space="nowrap",
        style={"scrollbar_width": "none"},
    )


def thumb(src: Any = "", *, size: str = "64px", icon: str = "image") -> rx.Component:
    """A square thumbnail: the image when there is one, a calm placeholder
    otherwise. Lazy-loaded."""
    placeholder = rx.center(rx.icon(icon, size=22, color=t.TEXT_TERTIARY),
                            width=size, height=size, background=t.SURFACE_2,
                            border_radius=t.RADIUS_THUMB, flex_shrink="0")
    image = rx.image(src=src, width=size, height=size, object_fit="cover",
                     border_radius=t.RADIUS_THUMB, flex_shrink="0", loading="lazy",
                     background=t.SURFACE_2)
    if isinstance(src, Var):
        return rx.cond(src != "", image, placeholder)
    return image if src else placeholder


def list_row(title: Any, subtitle: Any = "", *, image: Any = "", icon: str = "image",
             chevron: bool = True, on_click: Any = None, href: str = "") -> rx.Component:
    row = rx.hstack(
        thumb(image, icon=icon),
        rx.vstack(
            text(title, t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
                 white_space="nowrap", max_width="100%"),
            text(subtitle, t.SUBHEAD, t.TEXT_SECONDARY, overflow="hidden",
                 text_overflow="ellipsis", white_space="nowrap", max_width="100%"),
            spacing="1",
            align="start",
            min_width="0",
            flex="1",
        ),
        rx.icon("chevron-right", size=18, color=t.TEXT_TERTIARY) if chevron else rx.fragment(),
        spacing="3",
        align="center",
        width="100%",
        min_height=t.TOUCH_MIN,
        cursor="pointer" if (on_click is not None or href) else "default",
        on_click=on_click,
    )
    return rx.link(row, href=href, underline="none", width="100%") if href else row


def metric_chips(options: list[str], selected: Any, on_select=None) -> rx.Component:
    return rx.hstack(
        *[filter_chip(o, selected=selected == o, on_click=on_select(o) if on_select else None)
          for o in options],
        spacing="2",
        overflow_x="auto",
        width="100%",
        style={"scrollbar_width": "none"},
    )


def empty_state(title: Any, line: Any, action: Any = None) -> rx.Component:
    """What is missing, and the one thing to do about it."""
    return rx.vstack(
        text(title, t.HEADLINE),
        text(line, t.SUBHEAD, t.TEXT_SECONDARY, text_align="center"),
        action if action is not None else rx.fragment(),
        spacing="2",
        align="center",
        width="100%",
        padding=t.space(6),
        background=t.SURFACE_1,
        border_radius=t.RADIUS_CARD,
    )


def skeleton(height: str = "64px", width: str = "100%", radius: str = t.RADIUS_THUMB) -> rx.Component:
    """A loading block - screens show these, never a full-page spinner."""
    return rx.box(height=height, width=width, border_radius=radius,
                  background=t.SURFACE_1, class_name="ma-skeleton")


def card(*children, **props) -> rx.Component:
    return rx.vstack(*children, background=t.SURFACE_1, border_radius=t.RADIUS_CARD,
                     padding=t.CARD_PADDING, width="100%", spacing="3",
                     **props)


def primary_button(label: Any, on_click: Any = None, *, icon: str = "", disabled: Any = False,
                   **props) -> rx.Component:
    return rx.el.button(
        rx.hstack(rx.icon(icon, size=18) if icon else rx.fragment(), rx.el.span(label),
                  spacing="2", align="center", justify="center"),
        on_click=on_click,
        disabled=disabled,
        background=t.ACCENT_BLUE,
        color=t.TEXT_PRIMARY,
        border="none",
        border_radius=t.RADIUS_PILL,
        min_height=t.TOUCH_MIN,
        padding=f"0 {t.space(5)}",
        opacity=when(disabled, "0.4", "1"),
        cursor=when(disabled, "not-allowed", "pointer"),
        **t.HEADLINE,
        **props,
    )


def secondary_button(label: Any, on_click: Any = None, *, icon: str = "", disabled: Any = False,
                     color: str = t.TEXT_PRIMARY, **props) -> rx.Component:
    """The quieter action beside a primary one: grey fill, white or tinted label."""
    return rx.el.button(
        rx.hstack(rx.icon(icon, size=18) if icon else rx.fragment(), rx.el.span(label),
                  spacing="2", align="center", justify="center"),
        on_click=on_click,
        disabled=disabled,
        background=t.SURFACE_2,
        color=color,
        border="none",
        border_radius=t.RADIUS_PILL,
        min_height=t.TOUCH_MIN,
        padding=f"0 {t.space(4)}",
        opacity=when(disabled, "0.4", "1"),
        cursor=when(disabled, "not-allowed", "pointer"),
        **t.HEADLINE,
        **props,
    )


def sheet(open_: Any, title: Any, on_close: Any, *children: rx.Component) -> rx.Component:
    """A bottom sheet over everything (tab bar included): scrim, a rounded
    panel, a title and Done. Dialogs still open above it."""
    return rx.cond(
        open_,
        rx.box(
            rx.box(position="absolute", inset="0", background=t.SCRIM, on_click=on_close),
            rx.vstack(
                rx.hstack(text(title, t.HEADLINE), rx.spacer(),
                          text("Done", t.HEADLINE, t.ACCENT_BLUE, cursor="pointer", on_click=on_close,
                               custom_attrs={"role": "button"}),
                          width="100%", align="center", min_height=t.TOUCH_MIN),
                *children,
                position="absolute", left="0", right="0", bottom="0",
                max_height="88vh", overflow_y="auto",
                background=t.SURFACE_1,
                border_radius=f"{t.RADIUS_CARD} {t.RADIUS_CARD} 0 0",
                padding=f"{t.space(3)} {t.GUTTER} calc({t.space(6)} + env(safe-area-inset-bottom))",
                spacing="3", width="100%", max_width="560px", margin="0 auto",
            ),
            position="fixed", inset="0", z_index="80",
        ),
    )
