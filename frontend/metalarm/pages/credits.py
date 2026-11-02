"""Credits: who drew each exercise figure, and whose words the how-to steps
are. wger's text (https://wger.de) is Creative Commons Attribution-ShareAlike;
attribution is a condition of that licence."""

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


def _text_row(row) -> rx.Component:
    return rx.link(list_row(row["name"], f"wger contributors · {row['license']}", chevron=True),
                   href=row["source"], is_external=True, underline="none", width="100%")


def credits_page() -> rx.Component:
    return shell(
        top_bar("Credits", back="/profile"),
        text(f"The muscle figures on {CreditsState.diagrams} exercises are MetalArm's own drawings, released under "
             "CC0 1.0.", t.BODY, t.TEXT_2),
        text("Many how-to steps come from the wger project (wger.de) and its contributors, under Creative Commons "
             "Attribution-ShareAlike licences. Tap an entry for its source.", t.BODY, t.TEXT_2),
        error_banner(CreditsState.error),
        rx.cond(CreditsState.rows.length() > 0,
                section("Exercise figures", rows(rx.foreach(CreditsState.rows, _row)))),
        section("How-to steps", rows(rx.foreach(CreditsState.text_rows, _text_row))),
    )
