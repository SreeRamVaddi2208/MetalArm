"""Credits: every piece of library artwork, its author and its licence.

Most of it comes from wger (https://wger.de) under Creative Commons
Attribution-ShareAlike; attribution is a condition of that licence. Images
were resized for the app and remain under the same licence."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.credits import CreditsState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import list_row, rows, section, text


def _row(row) -> rx.Component:
    thumb = rx.image(src=row["image"], width="40px", height="40px", object_fit="cover", border_radius=t.RADIUS,
                     background=t.SURFACE_2, loading="lazy", alt="")
    return rx.link(list_row(row["name"], f"{row['author']} · {row['license']}", leading=thumb, chevron=True),
                   href=row["source"], is_external=True, underline="none", width="100%")


def credits_page() -> rx.Component:
    return shell(
        top_bar("Credits", back="/profile"),
        text("Exercise images and how-to steps come from the wger project (wger.de) and its contributors, under "
             "Creative Commons Attribution-ShareAlike licences. The images have been resized for MetalArm and "
             "remain under the same licence. Tap an entry for its source.", t.BODY, t.TEXT_2),
        text(f"The muscle diagrams on the other {CreditsState.diagrams} exercises are MetalArm's own drawings, "
             "released under CC0 1.0.", t.BODY, t.TEXT_2),
        error_banner(CreditsState.error),
        section("Exercise images", rows(rx.foreach(CreditsState.rows, _row))),
    )
