"""The building blocks every screen is assembled from (docs/DESIGN_SYSTEM.md).

Pages compose these and rx.vstack / rx.hstack / rx.grid for layout; they never
restyle them. Each reads only theme tokens.

Anti-clutter rules the primitives encode:
- one filled accent button per screen (button(variant="primary"));
- numbers are the hero: number() pairs a big tabular figure with a small,
  muted unit;
- space before lines, lines before boxes: rows() separates with an inset
  hairline, card() is for distinct, tappable units only - never nested;
- no shadows, gradients or glows anywhere here.
"""

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


def text(value: Any, style: dict = t.BODY, color: str = t.TEXT, **props) -> rx.Component:
    return rx.text(value, color=color, margin="0", **{**style, **props})


def number(value: Any, unit: Any = "", *, style: dict = t.DISPLAY, color: str = t.TEXT) -> rx.Component:
    """A figure with its unit beside it, small and muted, on the baseline."""
    parts = [text(value, style, color)]
    if isinstance(unit, Var) or unit:
        parts.append(text(unit, t.CAPTION, t.TEXT_2))
    return rx.hstack(*parts, spacing="1", align="baseline")


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

_BUTTON = {
    "primary": {"background": t.ACCENT, "color": t.ON_ACCENT, "border": "none"},
    "secondary": {"background": "transparent", "color": t.TEXT, "border": t.HAIRLINE},
    "ghost": {"background": "transparent", "color": t.TEXT, "border": "none"},
    "danger": {"background": "transparent", "color": t.DANGER, "border": f"1px solid {t.DANGER}"},
}


def button(label: Any, on_click: Any = None, *, variant: str = "primary", icon: str = "",
           disabled: Any = False, full: bool = False, **props) -> rx.Component:
    """52 px, full pill. ONE primary per screen; everything else is secondary,
    ghost or danger."""
    style = _BUTTON[variant]
    extra_class = props.pop("class_name", "")
    return rx.el.button(
        rx.hstack(rx.icon(icon, size=20, stroke_width=1.75) if icon else rx.fragment(), rx.el.span(label),
                  spacing="2", align="center", justify="center"),
        on_click=on_click,
        disabled=disabled,
        min_height=t.BUTTON_HEIGHT,
        border_radius=t.RADIUS_PILL,
        width="100%" if full else "auto",
        cursor=when(disabled, "not-allowed", "pointer"),
        opacity=when(disabled, "0.4", "1"),
        transition=f"background {t.FAST} {t.EASE}, opacity {t.FAST} {t.EASE}",
        class_name=f"ma-button ma-button-{variant} {extra_class}".strip(),
        **{"padding": f"0 {t.space(24)}", **style, **t.LABEL, **props},
    )


def link_button(label: Any, href: Any, *, variant: str = "secondary", icon: str = "", full: bool = False,
                **props) -> rx.Component:
    return rx.link(button(label, variant=variant, icon=icon, full=full), href=href, underline="none",
                   width="100%" if full else "auto", **props)


def icon_button(icon: str, label: str, on_click: Any = None, *, href: Any = "", badge: Any = None,
                color: str = t.TEXT_2) -> rx.Component:
    """44 px hit area, no background until pressed."""
    dot = rx.fragment() if badge is None else rx.cond(
        badge > 0, rx.box(position="absolute", top=t.space(8), right=t.space(8), width=t.space(8),
                          height=t.space(8), border_radius=t.RADIUS_PILL, background=t.ACCENT))
    inner = rx.center(
        rx.icon(icon, size=24, stroke_width=1.75, color=color), dot,
        width=t.ICON_HIT, height=t.ICON_HIT, border_radius=t.RADIUS_PILL, position="relative",
        cursor="pointer", on_click=on_click, flex_shrink="0", class_name="ma-press",
        custom_attrs={"role": "button", "aria-label": label},
    )
    return rx.link(inner, href=href, underline="none") if (isinstance(href, Var) or href) else inner


# ---------------------------------------------------------------------------
# Surfaces and rows
# ---------------------------------------------------------------------------


def card(*children: rx.Component, on_click: Any = None, href: Any = "", spacing: str = "3",
         **props) -> rx.Component:
    """surface, 12 px radius, 16 px padding, no border, no shadow. Tappable
    cards press to surface-2."""
    tappable = on_click is not None or isinstance(href, Var) or bool(href)
    body = rx.vstack(*children, background=t.SURFACE, border_radius=t.RADIUS, padding=t.CARD_PADDING,
                     width="100%", spacing=spacing, align="start", on_click=on_click,
                     cursor="pointer" if tappable else "default",
                     class_name="ma-card-surface ma-press" if tappable else "ma-card-surface", **props)
    if isinstance(href, Var) or href:
        return rx.link(body, href=href, underline="none", width="100%")
    return body


def rows(*children: rx.Component, **props) -> rx.Component:
    """A run of ListRows, separated by a hairline inset 16 px."""
    return rx.vstack(*children, spacing="0", width="100%", class_name="ma-rows", **props)


def list_row(title: Any, subtitle: Any = "", *, leading: rx.Component | None = None,
             trailing: Any = None, chevron: bool = False, on_click: Any = None, href: Any = "",
             title_color: str = t.TEXT, **props) -> rx.Component:
    """Leading icon/avatar, title, subtitle, trailing value or chevron.
    Minimum 56 px."""
    right = []
    if trailing is not None:
        right.append(trailing if isinstance(trailing, rx.Component) else text(trailing, t.BODY, t.TEXT_2))
    if chevron:
        right.append(rx.icon("chevron-right", size=20, stroke_width=1.75, color=t.TEXT_3))
    sub = (rx.cond(subtitle != "", text(subtitle, t.CAPTION, t.TEXT_2, overflow="hidden", text_overflow="ellipsis",
                                       white_space="nowrap", max_width="100%"))
           if isinstance(subtitle, Var) else
           (text(subtitle, t.CAPTION, t.TEXT_2) if subtitle else rx.fragment()))
    tappable = on_click is not None or isinstance(href, Var) or bool(href)
    extra = props.pop("class_name", "")
    row = rx.hstack(
        leading if leading is not None else rx.fragment(),
        rx.vstack(text(title, t.BODY, title_color, overflow="hidden", text_overflow="ellipsis",
                       white_space="nowrap", max_width="100%"), sub,
                  spacing="0", align="start", flex="1", min_width="0"),
        *right,
        spacing="3", align="center", width="100%", min_height=t.ROW_MIN, padding_y=t.space(8),
        position="relative", on_click=on_click, cursor="pointer" if tappable else "default",
        class_name=("ma-row ma-press" if tappable else "ma-row") + (f" {extra}" if extra else ""), **props,
    )
    return rx.link(row, href=href, underline="none", width="100%") if (isinstance(href, Var) or href) else row


def stat_tile(value: Any, label: Any, unit: Any = "", *, big: bool = False) -> rx.Component:
    """A number, its unit, and a small label under it. Groups of 2-3."""
    return rx.vstack(number(value, unit, style=t.DISPLAY if big else t.TITLE),
                     text(label, t.CAPTION, t.TEXT_2), spacing="1", align="start", min_width="0", flex="1")


def stat_group(*tiles: rx.Component) -> rx.Component:
    return rx.grid(*tiles, columns=str(len(tiles)), gap=t.space(16), width="100%")


def section(title: Any, *children: rx.Component, action: Any = "", href: Any = "",
            on_action: Any = None) -> rx.Component:
    """A titled group of content - spaced, not boxed."""
    link = rx.fragment()
    if action:
        inner = rx.hstack(text(action, t.LABEL, t.TEXT_2), rx.icon("chevron-right", size=16, color=t.TEXT_2),
                          spacing="1", align="center", cursor="pointer", on_click=on_action, min_height=t.TOUCH)
        link = rx.link(inner, href=href, underline="none") if (isinstance(href, Var) or href) else inner
    return rx.vstack(
        rx.hstack(text(title, t.TITLE), rx.spacer(), link, width="100%", align="center"),
        *children, spacing="3", width="100%", align="start",
    )


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------


def chip(label: Any, *, selected: Any = False, on_click: Any = None) -> rx.Component:
    """Pill; surface-2 by default, accent-soft with accent text when selected."""
    return rx.el.button(
        label, on_click=on_click,
        background=when(selected, t.ACCENT_SOFT, t.SURFACE_2),
        color=when(selected, t.ACCENT, t.TEXT),
        border="none", border_radius=t.RADIUS_PILL, padding=f"0 {t.space(16)}", min_height="40px",
        white_space="nowrap", cursor="pointer", flex_shrink="0",
        transition=f"background {t.FAST} {t.EASE}", **t.LABEL,
    )


def chips(*items: rx.Component) -> rx.Component:
    return rx.hstack(*items, spacing="2", overflow_x="auto", width="100%", flex_wrap="nowrap",
                     padding_bottom=t.space(4), class_name="ma-scroll-x")


def segmented(options: list[str], selected: Any, on_select=None) -> rx.Component:
    """2-4 options: a surface track, a surface-2 thumb."""
    return rx.hstack(
        *[rx.el.button(
            option, on_click=on_select(option) if on_select else None, flex="1",
            background=when(selected == option, t.SURFACE_2, "transparent"),
            color=when(selected == option, t.TEXT, t.TEXT_2),
            border="none", border_radius=t.RADIUS_PILL, min_height="40px", cursor="pointer",
            transition=f"background {t.FAST} {t.EASE}", **t.LABEL,
            custom_attrs={"aria-pressed": when(selected == option, "true", "false")},
        ) for option in options],
        background=t.SURFACE, border_radius=t.RADIUS_PILL, padding=t.space(4), spacing="1", width="100%",
        role="tablist",
    )


def progress_bar(scale: Any, *, label: Any = "") -> rx.Component:
    """4 px track in surface-2, accent fill. `scale` is 0-1."""
    bar = rx.box(rx.box(height="100%", width="100%", background=t.ACCENT, border_radius=t.RADIUS_PILL,
                        transform=f"scaleX({scale})", transform_origin="left center",
                        transition=f"transform {t.BASE} {t.EASE}"),
                 height="4px", width="100%", background=t.SURFACE_2, border_radius=t.RADIUS_PILL,
                 overflow="hidden")
    if isinstance(label, Var) or label:
        return rx.vstack(bar, text(label, t.CAPTION, t.TEXT_2), spacing="2", width="100%", align="start")
    return bar


def pill(label: Any, *, accent: bool = True) -> rx.Component:
    """A small tag - the "PR" pill."""
    return rx.box(text(label, t.CAPTION, t.ACCENT if accent else t.TEXT_2, font_weight="700"),
                  background=t.ACCENT_SOFT if accent else t.SURFACE_2, border_radius=t.RADIUS_PILL,
                  padding=f"0 {t.space(8)}", flex_shrink="0")


def field(value: Any, on_change: Any, placeholder: Any = "", *, type_: str = "text", mode: str = "",
          on_blur: Any = None, debounce: bool = False, **props) -> rx.Component:
    """A text input: surface-2, 12 px radius, 52 px tall."""
    style = dict(background=t.SURFACE_2, color=t.TEXT, border="none", border_radius=t.RADIUS,
                 min_height=t.BUTTON_HEIGHT, padding=f"0 {t.space(16)}", width="100%", min_width="0",
                 outline="none", **t.BODY)
    style.update(props)
    if debounce:
        extra = {"on_blur": on_blur} if on_blur is not None else {}
        return rx.input(value=value, on_change=on_change, placeholder=placeholder, type=type_,
                        debounce_timeout=250, variant="soft", radius="large", size="3", **extra, **style)
    attrs = {"type": type_, **({"input_mode": mode} if mode else {})}
    return rx.el.input(value=value, on_change=on_change, placeholder=placeholder, on_blur=on_blur,
                       **attrs, **style)


def stepper(value: Any, on_change: Any, on_minus: Any, on_plus: Any, *, unit: Any = "",
            placeholder: Any = "", label: str = "", mode: str = "decimal") -> rx.Component:
    """A large number with − / + (48 px each); tap the number to type."""
    side = dict(width=t.TOUCH, height=t.TOUCH, border_radius=t.RADIUS_PILL, background=t.SURFACE_2,
                color=t.TEXT, border="none", cursor="pointer", flex_shrink="0",
                display="flex", align_items="center", justify_content="center")
    return rx.vstack(
        text(label, t.CAPTION, t.TEXT_2) if label else rx.fragment(),
        rx.hstack(
            rx.el.button(rx.icon("minus", size=24, stroke_width=1.75), on_click=on_minus,
                         custom_attrs={"aria-label": f"Less {label.lower()}".strip()}, class_name="ma-press", **side),
            rx.hstack(
                # Sized to its contents (field-sizing), so the unit sits right
                # after the number; max_width bounds browsers without it.
                rx.el.input(value=value, on_change=on_change, placeholder=placeholder, input_mode=mode,
                            background="transparent", color=t.TEXT, border="none", outline="none",
                            text_align="center", min_width="2ch", max_width="5.5ch", padding="0",
                            style={"field_sizing": "content"},
                            custom_attrs={"aria-label": label or "value"}, **t.DISPLAY),
                text(unit, t.CAPTION, t.TEXT_2) if (isinstance(unit, Var) or unit) else rx.fragment(),
                spacing="1", align="baseline", flex="1", min_width="0", justify="center",
            ),
            rx.el.button(rx.icon("plus", size=24, stroke_width=1.75), on_click=on_plus,
                         custom_attrs={"aria-label": f"More {label.lower()}".strip()}, class_name="ma-press", **side),
            spacing="2", align="center", width="100%",
        ),
        spacing="1", width="100%", align="start",
    )


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


def empty_state(icon: str, line: Any, action: rx.Component | None = None) -> rx.Component:
    """One line icon, one sentence, one (secondary) button."""
    return rx.vstack(
        rx.icon(icon, size=24, stroke_width=1.75, color=t.TEXT_3),
        text(line, t.BODY, t.TEXT_2, text_align="center"),
        action if action is not None else rx.fragment(),
        spacing="3", align="center", width="100%", padding=f"{t.space(32)} {t.space(16)}",
    )


def error_state(message: Any, retry: Any = None) -> rx.Component:
    """What went wrong, in a sentence, and Try again."""
    return rx.cond(
        message != "",
        rx.vstack(rx.icon("circle-alert", size=24, stroke_width=1.75, color=t.TEXT_3),
                  text(message, t.BODY, t.TEXT_2, text_align="center"),
                  button("Try again", retry, variant="secondary") if retry is not None else rx.fragment(),
                  spacing="3", align="center", width="100%", padding=t.space(24),
                  custom_attrs={"role": "alert"}),
    )


def skeleton(height: str = t.ROW_MIN, width: str = "100%", radius: str = t.RADIUS) -> rx.Component:
    """surface-2 blocks matching the final layout - never a spinner."""
    return rx.box(height=height, width=width, border_radius=radius, background=t.SURFACE_2,
                  class_name="ma-skeleton")


def skeleton_rows(n: int = 3) -> rx.Component:
    return rx.vstack(*[skeleton() for _ in range(n)], spacing="2", width="100%")


def sheet(open_: Any, on_close: Any, *children: rx.Component, title: Any = "",
          action: rx.Component | None = None) -> rx.Component:
    """A bottom sheet: surface, 16 px top radius, grab handle, scrim."""
    return rx.cond(
        open_,
        rx.box(
            rx.box(position="absolute", inset="0", background=t.SCRIM, on_click=on_close,
                   class_name="ma-scrim"),
            rx.vstack(
                rx.center(rx.box(width="36px", height="4px", border_radius=t.RADIUS_PILL, background=t.BORDER),
                          width="100%", padding_top=t.space(8)),
                rx.hstack(text(title, t.TITLE), rx.spacer(),
                          icon_button("x", "Close", on_click=on_close), width="100%", align="center")
                if (isinstance(title, Var) or title) else rx.fragment(),
                *children,
                action if action is not None else rx.fragment(),
                position="absolute", left="0", right="0", bottom="0", margin="0 auto", max_width=t.MAX_WIDTH,
                max_height="88vh", overflow_y="auto", background=t.SURFACE,
                border_radius=f"{t.RADIUS_SHEET} {t.RADIUS_SHEET} 0 0",
                padding=f"0 {t.GUTTER} calc({t.space(24)} + env(safe-area-inset-bottom))",
                spacing="3", width="100%", class_name="ma-sheet",
                custom_attrs={"role": "dialog", "aria-modal": "true"},
            ),
            position="fixed", inset="0", z_index="80",
        ),
    )
