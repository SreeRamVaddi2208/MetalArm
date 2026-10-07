"""Toast: surface-2, at the bottom, three seconds, an icon and a sentence -
no colour. One at a time; showing another replaces it."""

from __future__ import annotations

import reflex as rx

from metalarm import theme as t
from metalarm.ui.primitives import text


# Icons are compiled in, so a toast picks one of these by name.
ICONS = ("check", "scroll-text", "medal", "cloud-off", "bookmark-plus", "user-plus", "circle-alert")


class ToastState(rx.State):
    message: str = ""
    icon: str = "check"
    # Bumped per toast so the same message twice still replays.
    serial: int = 0

    def show(self, message: str, icon: str = "check") -> None:
        self.message, self.icon, self.serial = message, icon, self.serial + 1


def toast() -> rx.Component:
    return rx.cond(
        ToastState.message != "",
        rx.box(
            rx.hstack(rx.match(ToastState.icon,
                               *[(name, rx.icon(name, size=20, stroke_width=1.75, color=t.TEXT_2)) for name in ICONS],
                               rx.icon("info", size=20, stroke_width=1.75, color=t.TEXT_2)),
                      text(ToastState.message, t.LABEL), spacing="2", align="center"),
            key=ToastState.serial.to_string(),
            position="fixed", left="0", right="0", margin="0 auto", width="fit-content",
            max_width=f"calc({t.MAX_WIDTH} - 40px)",
            bottom=t.TOAST_BOTTOM,
            background=t.SURFACE_2, border_radius=t.RADIUS_PILL, padding=f"{t.space(12)} {t.space(16)}",
            z_index="90", class_name="ma-toast", custom_attrs={"role": "status", "aria-live": "polite"},
        ),
    )
