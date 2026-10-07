"""The short clip that shows what a movement looks like.

The link comes from the exercise's `media_url`, so adding a demo is adding a URL
to the library (backend/app/data/exercises.json) - no deploy of this app needed.

Muted, looping, no controls and `playsinline`: it is a diagram that moves, not
something to watch. A movement with no link gets a placeholder of the same size,
so a list of them does not jump about as links are filled in.
"""

import reflex as rx

from metalarm import theme as t


def exercise_demo(media_url: rx.Var | str, name: rx.Var | str = "", size: str = "96px") -> rx.Component:
    """A demo box of a fixed size, whichever state it is in."""
    frame = {"width": size, "min_width": size, "height": size, "border_radius": t.RADIUS,
             "background": t.SURFACE_2, "overflow": "hidden"}
    return rx.cond(
        media_url != "",
        rx.box(
            rx.video(src=media_url, width="100%", height="100%", playing=True, loop=True, muted=True,
                     controls=False, playsinline=True, object_fit="cover"),
            aria_label=f"Demo of {name}", class_name="ma-demo", **frame,
        ),
        rx.center(rx.icon("video-off", size=20, color=t.TEXT_3, stroke_width=1.75),
                  aria_label=f"No demo for {name} yet", class_name="ma-demo-placeholder", **frame),
    )
