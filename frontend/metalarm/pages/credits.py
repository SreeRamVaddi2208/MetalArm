"""Credits: every piece of library artwork, its author and its licence.

Most of it comes from wger (https://wger.de) under Creative Commons
Attribution-ShareAlike; attribution is a condition of that licence. Images
were resized for the app and remain under the same licence."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import error_banner, shell
from metalarm.state.credits import CreditsState
from metalarm.ui.chrome import top_bar
from metalarm.ui.primitives import list_row, section_header, text


def _row(row) -> rx.Component:
    return rx.link(
        list_row(row["name"], f"{row['author']} · {row['license']}", image=row["image"],
                 icon="dumbbell", chevron=True),
        href=row["source"], is_external=True, underline="none", width="100%",
    )


def credits_page() -> rx.Component:
    return shell(
        top_bar("Credits"),
        text("Exercise images come from the wger project (wger.de) and its contributors, "
             "under Creative Commons Attribution-ShareAlike licences. They have been resized "
             "for MetalArm and remain under the same licence. Tap an entry for its source.",
             t.SUBHEAD, t.TEXT_SECONDARY),
        error_banner(CreditsState.error),
        section_header("Exercise images"),
        rx.vstack(rx.foreach(CreditsState.rows, _row), spacing="3", width="100%"),
    )
