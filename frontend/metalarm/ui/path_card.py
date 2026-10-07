"""A training path to choose: name, tagline, how it trains. Selected is a
2 px accent outline on accent-soft with a check - no glow. The same card is
used in onboarding and in Settings."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t
from metalarm.ui.primitives import text, when


def path_card(path: Any, *, selected: Any, on_click: Any) -> rx.Component:
    return rx.hstack(
        rx.vstack(text(path.display_name, t.TITLE), text(path.tagline, t.BODY, t.TEXT_2),
                  text(path.summary, t.CAPTION, t.TEXT_2), spacing="1", align="start", flex="1", min_width="0"),
        rx.center(rx.cond(selected, rx.icon("check", size=16, color=t.ON_ACCENT, stroke_width=2.5)),
                  width="24px", height="24px", border_radius=t.RADIUS_PILL, flex_shrink="0",
                  background=when(selected, t.ACCENT, "transparent"),
                  border=when(selected, f"2px solid {t.ACCENT}", f"2px solid {t.BORDER}")),
        on_click=on_click, cursor="pointer", width="100%", align="start", spacing="3",
        padding=t.CARD_PADDING, border_radius=t.RADIUS,
        background=when(selected, t.ACCENT_SOFT, t.SURFACE),
        outline=when(selected, f"2px solid {t.ACCENT}", f"1px solid {t.BORDER}"), outline_offset="-1px",
        class_name="ma-path-card ma-press",
        custom_attrs={"role": "radio", "aria-checked": rx.cond(selected, "true", "false"),
                      "data-path": path.category},
    )
