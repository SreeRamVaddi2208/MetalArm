"""The area chart: a line, a gradient fill, hollow points, the axis on the
right, and a scrub marker on the selected point (recharts)."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t


def area_chart(data: Any, *, x_key: str = "label", y_key: str = "value",
               height: int = 220) -> rx.Component:
    gradient_id = f"ma-area-{y_key}"
    return rx.recharts.area_chart(
        rx.el.defs(
            rx.el.linear_gradient(
                rx.el.stop(offset="0%", stop_color=t.CHART_LINE, stop_opacity="0.35"),
                rx.el.stop(offset="100%", stop_color=t.CHART_LINE, stop_opacity="0"),
                id=gradient_id, x1="0", y1="0", x2="0", y2="1",
            )
        ),
        rx.recharts.cartesian_grid(vertical=False, stroke=t.SEPARATOR),
        rx.recharts.x_axis(data_key=x_key, tick_line=False, axis_line=False,
                           tick={"fill": t.TEXT_SECONDARY, "fontSize": 11}),
        rx.recharts.y_axis(orientation="right", tick_line=False, axis_line=False, width=48,
                           tick={"fill": t.TEXT_SECONDARY, "fontSize": 11}),
        rx.recharts.tooltip(
            cursor={"stroke": t.TEXT_SECONDARY, "strokeWidth": 1},
            content_style={"background": t.SURFACE_2, "border": "none",
                           "borderRadius": t.RADIUS_THUMB, "color": t.TEXT_PRIMARY},
            label_style={"color": t.TEXT_SECONDARY},
        ),
        rx.recharts.area(
            data_key=y_key, type_="monotone", stroke=t.CHART_LINE, stroke_width=2.5,
            fill=f"url(#{gradient_id})",
            dot={"r": 3.5, "fill": t.COLOR_BG, "stroke": t.CHART_LINE, "strokeWidth": 2},
            active_dot={"r": 5, "fill": t.CHART_LINE},
            is_animation_active=False,
        ),
        data=data,
        height=height,
        width="100%",
        margin={"top": 8, "right": 0, "bottom": 0, "left": 0},
    )
