"""One line chart for the whole app: the user's series in accent, no fill, a
dot only on the points that matter (the latest and the records). Gridlines in
border; axes in text-2. One series - so no legend."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t


def line_chart(data: Any, *, x_key: str = "label", y_key: str = "value", mark_key: str = "mark",
               height: int = 220, from_zero: bool = True) -> rx.Component:
    """`data`: rows of {label, value, mark}. `mark` is the value again on the
    points to dot (the latest, a record) and null elsewhere. Totals start the
    axis at zero; a level like body weight (`from_zero=False`) fits its range."""
    tick = {"fill": t.TEXT_2, "fontSize": 12}
    return rx.recharts.line_chart(
        rx.recharts.cartesian_grid(vertical=False, stroke=t.BORDER),
        rx.recharts.x_axis(data_key=x_key, tick_line=False, axis_line=False, tick=tick, min_tick_gap=24),
        rx.recharts.y_axis(orientation="right", tick_line=False, axis_line=False, width=44, tick=tick,
                           domain=[0, "auto"] if from_zero else ["dataMin - 2", "dataMax + 2"]),
        rx.recharts.tooltip(
            cursor={"stroke": t.BORDER, "strokeWidth": 1},
            content_style={"background": t.SURFACE_2, "border": "none", "borderRadius": t.RADIUS,
                           "color": t.TEXT},
            label_style={"color": t.TEXT_2},
        ),
        rx.recharts.line(data_key=y_key, type_="monotone", stroke=t.ACCENT, stroke_width=2,
                         dot=False, active_dot={"r": 4, "fill": t.ACCENT}, is_animation_active=False),
        rx.recharts.line(data_key=mark_key, stroke="none", dot={"r": 4, "fill": t.ACCENT, "stroke": t.BG,
                                                                "strokeWidth": 2},
                         is_animation_active=False, legend_type="none", tooltip_type="none"),
        data=data, height=height, width="100%", margin={"top": 8, "right": 0, "bottom": 0, "left": 0},
    )
